"""seed.py, verify_tape.py and bench.py — the recording, the re-derivation, the timing."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import bench  # noqa: E402
import seed  # noqa: E402
import verify_tape  # noqa: E402
from conftest import USDC, make_row  # noqa: E402

from middleman import enrich, tape  # noqa: E402

MOTO = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"


def _tape_rows():
    rows, lg = [], 1
    for h in range(100, 130):
        rows.append(make_row(h, lg, "W", "sell", 1000, 1.00, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 1, "W", "buy", 1000, 1.02, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 2, f"o{h}", "buy", 10, 0.0101, v=10))
        rows.append(make_row(h, lg + 3, f"p{h}", "sell", 10, 0.01008, v=10))
        lg += 4
    return rows


def _meta(pages=8, **over):
    m = {
        "captured_utc": "2026-09-19T00:00:00Z",
        "pages": pages,
        "error": None,
        "throttled": False,
        "stalled": False,
        "credits": 0,
        "keyed": False,
        "calls": [
            {
                "ok": True,
                "url": tape.BASE + tape.SWAPS + "?p",
                "status": 200,
                "utc": "t",
                "sha256": f"h{i}",
            }
            for i in range(pages)
        ],
        "wall_s": 0.1,
    }
    m.update(over)
    return m


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Every script writes under tmp_path; every network function is replaced; no key."""
    for var in tape.KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    data, proof = tmp_path / "data", tmp_path / "docs" / "proof"
    for mod in (seed, verify_tape, bench):
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        monkeypatch.setattr(mod, "DATA", data)
    monkeypatch.setattr(seed, "PROOF", proof)
    monkeypatch.setattr(verify_tape, "PROOF", proof)
    monkeypatch.setattr(
        tape, "pull", lambda p, a, pages=8, quiet=False: (_tape_rows(), _meta(pages))
    )
    monkeypatch.setattr(enrich, "token_pools", lambda p, a, quiet=False: ([], {"ok": True}))
    monkeypatch.setattr(
        enrich, "security", lambda p, a, quiet=False: (None, {"ok": False, "error": "x"})
    )
    monkeypatch.setattr(enrich, "pair_quotes", lambda p, addr, quiet=False: (None, {"ok": False}))
    monkeypatch.setattr(
        enrich,
        "platforms",
        lambda quiet=False: (
            {1: {"name": "Ethereum", "txuf": "https://etherscan.io/tx/%s"}},
            {"ok": True, "utc": "t", "url": "u", "sha256": "s"},
        ),
    )
    return tmp_path


def _hero_call(name="MOTO/WETH", sym="MOTO", addr=MOTO):
    return {
        "ok": True,
        "url": "u",
        "status": 200,
        "utc": "t",
        "sha256": "s",
        "credit_count": 1,
        "body": {
            "data": [
                {
                    "name": name,
                    "base_asset_symbol": sym,
                    "base_asset_contract_address": addr,
                    "contract_address": "0xpool",
                    "dex_slug": "uniswap-v2",
                }
            ]
        },
    }


# ── seed ─────────────────────────────────────────────────────────────────────────────────────


def test_file_names_are_the_symbol_with_the_chain_appended_off_ethereum():
    assert seed.slug("MOTO", "ethereum") == "moto"
    assert seed.slug("USDT", "bsc") == "usdt-bsc"
    assert seed.slug("$PAAL", "ethereum") == "paal"
    assert seed.slug("", "solana") == "token-solana"


def test_the_hero_rule_reads_cmcs_ranking_and_names_itself(monkeypatch):
    monkeypatch.setattr(tape, "get", lambda path, quiet=False, **p: _hero_call())
    hero, _ = seed.pick_hero("ethereum", {"network_id": 1, "dex_slug": "uniswap-v2"})
    assert hero["address"] == MOTO and hero["pair"] == "MOTO/WETH"
    assert "#1 uniswap-v2 pair on ethereum by 24h transactions" in hero["rule"]
    monkeypatch.setattr(
        tape,
        "get",
        lambda path, quiet=False, **p: {
            "ok": False,
            "error": "HTTP 429",
            "throttled": True,
            "url": "u",
        },
    )
    hero, receipt = seed.pick_hero("bsc", {"network_id": 14, "dex_slug": "pancakeswap-v2"})
    assert hero is None and receipt["throttled"]


def test_capture_freezes_the_rows_verbatim_with_their_page_hashes_and_a_receipt(sandbox):
    r = seed.capture("MOTO", MOTO, "ethereum", 8)
    tape_file = json.loads((sandbox / "data" / "tape_moto.json").read_text())
    proof = json.loads((sandbox / "docs" / "proof" / "moto.json").read_text())
    assert tape_file["swap_count"] == 120 and tape_file["page_sha256"] == [
        f"h{i}" for i in range(8)
    ]
    assert tape_file["swaps"][0] == _tape_rows()[0] and "RECORDING" in tape_file["_note"]
    assert (
        proof["tape"] == "data/tape_moto.json" and proof["pools"][0]["round_trips"]["pairs"] == 30
    )
    assert r["decision"]["pool"] == proof["decision"]["pool"]


def test_capture_refuses_to_write_a_tape_it_could_not_pull(sandbox, monkeypatch):
    monkeypatch.setattr(
        tape, "pull", lambda *a, **k: ([], _meta(0, error="HTTP 429", throttled=True))
    )
    r = seed.capture("MOTO", MOTO, "ethereum", 8)
    assert r["error"] == "HTTP 429" and not (sandbox / "data").exists()


def test_the_census_takes_the_spread_over_ethereum_only_and_names_which_rule_fired(sandbox):
    washed = seed.capture("MOTO", MOTO, "ethereum", 8)
    clean_rows = [make_row(h, 1, f"a{h}", "buy", 10, 0.0101 + h * 0.0002) for h in range(1, 120)]
    clean_rows += [
        make_row(h, 2, f"b{h}", "buy", 10, 0.0101 + h * 1e-6, t1a=USDC, t1s="USDC")
        for h in range(1, 120)
    ]
    sandbox_pull = lambda p, a, pages=8, quiet=False: (clean_rows, _meta(pages))  # noqa: E731
    import middleman.tape as t

    t.pull = sandbox_pull
    clean = seed.capture("PEPE", "0xpepe", "ethereum", 8)
    foreign = seed.capture("USDT", "0xusdt", "bsc", 8)
    heroes = [
        {
            "platform": "ethereum",
            "symbol": "MOTO",
            "address": MOTO,
            "pair": "MOTO/WETH",
            "rule": "r",
        }
    ]
    strip = seed.census([washed, clean, foreign], heroes)
    assert strip["tokens"] == 3 and strip["prints"] == 120 + 238 * 2
    assert strip["hero"]["fired"] == "round-trip share" and strip["hero"]["pool"]["wallets"] == [
        "W"
    ]
    assert strip["widest_spread"]["symbol"] == "PEPE" and strip["widest_spread"]["ratio"] > 1
    assert all(s["platform"] == "ethereum" for s in strip["spreads"])
    assert {r["symbol"] for r in strip["rows"]} == {"MOTO", "PEPE", "USDT"}
    # without a washed hero the spread is what fires; with nothing, "none"
    strip = seed.census(
        [clean],
        [{"platform": "ethereum", "symbol": "PEPE", "address": "0xpepe", "pair": "p", "rule": "r"}],
    )
    assert strip["hero"]["fired"] == "sibling-pool spread"
    assert seed.census([], [])["hero"]["fired"] == "none"


def test_seed_main_runs_the_rules_the_watchlist_and_writes_the_strip(sandbox, monkeypatch, capsys):
    def ranking(path, quiet=False, **p):
        dex = p.get("dex_slug", "")
        return _hero_call() if dex == "uniswap-v2" else _hero_call(f"X/{dex}", "X", f"0x{dex}")

    monkeypatch.setattr(tape, "get", ranking)
    seed.main(["--only", "MOTO"])
    out = capsys.readouterr().out
    assert "hero rule · ethereum  MOTO/WETH" in out and "census · 1 tokens" in out
    strip = json.loads((sandbox / "docs" / "proof" / "census.json").read_text())
    assert strip["hero"]["symbol"] == "MOTO" and len(strip["heroes"]) == 3
    assert (sandbox / "docs" / "proof" / "platforms.json").exists()
    seed.main(["--census-only"])
    assert "rebuilt" in capsys.readouterr().out


def test_seed_refuses_to_record_a_keyed_receipt(monkeypatch):
    monkeypatch.setenv("CMC_API_KEY", "x")
    with pytest.raises(SystemExit) as e:
        seed.main([])
    assert "keyless by definition" in str(e.value.code)


# ── verify_tape ──────────────────────────────────────────────────────────────────────────────


def test_a_receipt_that_matches_its_tape_verifies_and_a_tampered_one_is_named(sandbox, capsys):
    seed.capture("MOTO", MOTO, "ethereum", 8)
    assert verify_tape.main([]) == 0
    assert "every published number re-derives" in capsys.readouterr().out
    proof = sandbox / "docs" / "proof" / "moto.json"
    d = json.loads(proof.read_text())
    d["pools"][0]["round_trips"]["pairs"] = 99
    d["decision"]["cap_pct"] = 9.99
    proof.write_text(json.dumps(d))
    assert verify_tape.main(["--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert any("round_trips" in x for x in report["drifts"]) and any(
        "cap_pct" in x for x in report["drifts"]
    )


def test_a_tape_without_a_receipt_is_a_drift_and_no_tapes_is_an_error(sandbox, capsys):
    seed.capture("MOTO", MOTO, "ethereum", 8)
    (sandbox / "docs" / "proof" / "moto.json").unlink()
    assert verify_tape.main([]) == 1 and "no receipt" in capsys.readouterr().out
    (sandbox / "data" / "tape_moto.json").unlink()
    with pytest.raises(SystemExit):
        verify_tape.main([])


def test_the_committed_receipts_re_derive_from_the_committed_tapes():
    """The drift gate on the real repository: what the page shows is what the rows say."""
    drifts = []
    for t in sorted((ROOT / "data").glob("tape_*.json")):
        drifts += verify_tape.compare(t)
    assert drifts == []


# ── bench ────────────────────────────────────────────────────────────────────────────────────


def test_replay_measures_the_engine_over_the_hero_tape_with_the_socket_unplugged(
    sandbox, monkeypatch, capsys
):
    seed.capture("MOTO", MOTO, "ethereum", 8)
    (sandbox / "docs" / "proof" / "census.json").write_text(
        json.dumps({"hero": {"symbol": "MOTO"}})
    )
    monkeypatch.setattr(tape.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    out = sandbox / "bench.json"
    bench.main(["--replay", "--iterations", "5", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["mode"] == "replay" and d["detect"]["n"] == 5 and d["prints"] == 120
    assert d["tape"] == "data/tape_moto.json" and "no network" in capsys.readouterr().out


def test_replay_without_a_tape_says_how_to_make_one(sandbox):
    with pytest.raises(SystemExit) as e:
        bench.main(["--replay"])
    assert "seed.py" in str(e.value.code)


def test_a_throttled_iteration_is_not_timed_as_a_detect(sandbox, monkeypatch, capsys):
    answers = [([], _meta(0, error="HTTP 429", throttled=True)), (_tape_rows(), _meta(1))]
    monkeypatch.setattr(tape, "pull", lambda *a, **k: answers.pop(0))
    out = sandbox / "b.json"
    bench.main(["--iterations", "2", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["fetch"]["n"] == 2 and d["detect"]["n"] == 1 and d["credits_used"] == 0
    assert "iteration 1: API error" in capsys.readouterr().out


def test_the_live_bench_stops_when_every_iteration_is_throttled(sandbox, monkeypatch):
    monkeypatch.setattr(
        tape, "pull", lambda *a, **k: ([], _meta(0, error="HTTP 429", throttled=True))
    )
    with pytest.raises(SystemExit):
        bench.main(["--iterations", "1"])
