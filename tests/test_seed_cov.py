"""seed.py — the branches the recording script takes when a rule, a pull or a receipt is missing."""

import json
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import seed  # noqa: E402
from conftest import USDC, make_row  # noqa: E402

from middleman import enrich, tape  # noqa: E402

MOTO = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"
SEED_PY = ROOT / "scripts" / "seed.py"


def _washed_rows():
    rows, lg = [], 1
    for h in range(100, 130):
        rows.append(make_row(h, lg, "W", "sell", 1000, 1.00, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 1, "W", "buy", 1000, 1.02, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 2, f"o{h}", "buy", 10, 0.0101, v=10))
        rows.append(make_row(h, lg + 3, f"p{h}", "sell", 10, 0.01008, v=10))
        lg += 4
    return rows


def _two_pool_rows():
    rows = [make_row(h, 1, f"a{h}", "buy", 10, 0.0101 + h * 0.0002) for h in range(1, 120)]
    rows += [
        make_row(h, 2, f"b{h}", "buy", 10, 0.0101 + h * 1e-6, t1a=USDC, t1s="USDC")
        for h in range(1, 120)
    ]
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
                "url": tape.BASE + tape.SWAPS,
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


def _call(ok=True, rows=None, **over):
    c = {"ok": ok, "url": "u", "status": 200, "utc": "t", "sha256": "s", "credit_count": 1}
    if ok:
        c["body"] = {"data": rows if rows is not None else []}
    c.update(over)
    return c


def _pair(name="MOTO/WETH", sym="MOTO", addr=MOTO, dex="uniswap-v2"):
    return {
        "name": name,
        "base_asset_symbol": sym,
        "base_asset_contract_address": addr,
        "contract_address": "0xpool",
        "dex_slug": dex,
    }


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """seed writes under tmp_path; every network function is replaced; no key is exported."""
    for var in tape.KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(seed, "ROOT", tmp_path)
    monkeypatch.setattr(seed, "DATA", tmp_path / "data")
    monkeypatch.setattr(seed, "PROOF", tmp_path / "docs" / "proof")
    monkeypatch.setattr(
        tape, "pull", lambda p, a, pages=8, quiet=False: (_washed_rows(), _meta(pages))
    )
    monkeypatch.setattr(
        tape, "get", lambda path, quiet=False, **p: _call(rows=[_pair(dex=p["dex_slug"])])
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


@pytest.fixture
def proof(sandbox):
    return sandbox / "docs" / "proof"


def _seed_census(proof, results, heroes=(), extra_rows=()):
    strip = seed.census(results, list(heroes))
    strip["rows"] += list(extra_rows)
    proof.mkdir(parents=True, exist_ok=True)
    (proof / "census.json").write_text(json.dumps(strip, default=str))
    return strip


def test_a_ranking_that_returns_no_pairs_yields_no_hero_but_keeps_the_receipt(monkeypatch):
    monkeypatch.setattr(tape, "get", lambda path, quiet=False, **p: _call(rows=[]))
    hero, receipt = seed.pick_hero("solana", {"network_slug": "solana", "dex_slug": "raydium"})
    assert hero is None and receipt["ok"] and "body" not in receipt


def test_recompute_re_derives_every_receipt_that_has_a_tape_and_keeps_its_labels(
    sandbox, proof, monkeypatch, capsys
):
    moto = seed.capture("MOTO", MOTO, "ethereum", 8)
    routed = moto["decision"]["pool"]
    assert routed is not None
    moto_proof = proof / "moto.json"
    old = json.loads(moto_proof.read_text())
    for p in old["pools"]:
        p["liq_usd"] = 12345.0
        p["addr"] = "0xlabelled"
    old["coverage"] = {"num_transactions_24h": 600}
    old["calls"] = ["kept"]
    moto_proof.write_text(json.dumps(old))
    monkeypatch.setattr(
        tape, "pull", lambda p, a, pages=8, quiet=False: (_two_pool_rows(), _meta(pages))
    )
    seed.capture("PEPE", "0xpepe", "ethereum", 8)
    (sandbox / "data" / "tape_orphan.json").write_text("{}")
    _seed_census(proof, [moto])

    seed.recompute()

    out = capsys.readouterr().out
    assert "recomputed 2 receipt(s)" in out and "rebuilt docs/proof/census.json" in out
    fresh = json.loads(moto_proof.read_text())
    assert fresh["decision"]["pool"] == routed and fresh["calls"] == ["kept"]
    assert all(p["liq_usd"] == 12345.0 and p["addr"] == "0xlabelled" for p in fresh["pools"])
    routed_n = next(p["n"] for p in fresh["pools"] if p["key"] == routed)
    assert fresh["coverage"]["window_share_of_24h"] == round(routed_n / 600, 4)
    pepe = json.loads((proof / "pepe.json").read_text())
    assert pepe["coverage"] is None and all(p["liq_usd"] is None for p in pepe["pools"])


def test_rebuild_census_skips_rows_whose_receipt_is_gone_and_keeps_the_old_timestamp(proof, capsys):
    moto = seed.capture("MOTO", MOTO, "ethereum", 8)
    hero = {"platform": "ethereum", "symbol": "MOTO", "address": MOTO, "pair": "p", "rule": "r"}
    old = _seed_census(
        proof,
        [moto],
        [hero],
        [{"symbol": "GONE", "platform": "ethereum", "file": "docs/proof/gone.json"}],
    )
    old["captured_utc"] = "2020-01-01T00:00:00Z"
    (proof / "census.json").write_text(json.dumps(old, default=str))

    seed.rebuild_census()

    strip = json.loads((proof / "census.json").read_text())
    assert "from 1 receipt(s)" in capsys.readouterr().out
    assert strip["captured_utc"] == "2020-01-01T00:00:00Z" and strip["tokens"] == 1
    assert strip["hero"]["symbol"] == "MOTO" and strip["hero"]["fired"] == "round-trip share"


def test_rebuild_census_with_no_receipts_on_disk_says_how_to_make_some(sandbox):
    with pytest.raises(SystemExit) as e:
        seed.rebuild_census()
    assert "scripts/seed.py" in str(e.value.code)


def test_the_recompute_flag_runs_the_engine_over_the_tapes_without_the_network(
    proof, monkeypatch, capsys
):
    moto = seed.capture("MOTO", MOTO, "ethereum", 8)
    _seed_census(proof, [moto])
    monkeypatch.setattr(tape, "pull", lambda *a, **k: pytest.fail("network"))
    monkeypatch.setattr(tape, "get", lambda *a, **k: pytest.fail("network"))
    assert seed.main(["--recompute"]) is None
    assert "recomputed 1 receipt(s)" in capsys.readouterr().out


def test_main_without_a_platform_table_writes_no_platforms_file_and_reports_failed_rules(
    sandbox, proof, monkeypatch, capsys
):
    monkeypatch.setattr(enrich, "platforms", lambda quiet=False: ({}, {"ok": False}))

    def ranking(path, quiet=False, **p):
        if p["dex_slug"] == "raydium":
            return _call(ok=False, error="HTTP 429", throttled=True)
        if p["dex_slug"] == "pancakeswap-v2":
            return _call(rows=[_pair("USDT/WBNB", "USDT", "0xusdt", p["dex_slug"])])
        return _call(rows=[_pair(dex=p["dex_slug"])])

    monkeypatch.setattr(tape, "get", ranking)
    seed.main(["--only", "MOTO"])
    out = capsys.readouterr().out
    assert "hero rule · solana    failed: HTTP 429" in out
    assert not (proof / "platforms.json").exists()
    strip = json.loads((proof / "census.json").read_text())
    assert len(strip["heroes"]) == 2 and strip["tokens"] == 1


def test_main_without_heroes_or_a_filter_records_the_whole_watchlist_and_names_failures(
    sandbox, proof, monkeypatch, capsys
):
    def pull(platform, address, pages=8, quiet=False):
        if address == seed.WATCHLIST[1][1]:
            return [], _meta(0, error="HTTP 429", throttled=True)
        return _washed_rows(), _meta(pages)

    monkeypatch.setattr(tape, "pull", pull)
    monkeypatch.setattr(tape, "get", lambda *a, **k: pytest.fail("the hero rule must not run"))
    seed.main(["--no-heroes", "--pages", "2"])
    out = capsys.readouterr().out
    assert "  failed: HTTP 429" in out and "2 page(s)" in out
    strip = json.loads((proof / "census.json").read_text())
    assert strip["tokens"] == len(seed.WATCHLIST) - 1 and strip["heroes"] == []
    assert strip["errors"] == [{"symbol": "PEPE", "platform": "ethereum", "error": "HTTP 429"}]
    assert strip["hero"]["symbol"] is None and strip["hero"]["fired"] == "none"
    assert len(list((sandbox / "data").glob("tape_*.json"))) == len(seed.WATCHLIST) - 1


def test_main_prints_the_widest_sibling_spread_when_two_priced_pools_disagree(
    sandbox, proof, monkeypatch, capsys
):
    monkeypatch.setattr(
        tape, "pull", lambda p, a, pages=8, quiet=False: (_two_pool_rows(), _meta(pages))
    )

    def ranking(path, quiet=False, **p):
        dex = p["dex_slug"]
        if dex == "uniswap-v2":
            return _call(rows=[_pair("PEPE/WETH", "PEPE", "0xpepe")])
        return _call(rows=[_pair(f"X/{dex}", "X", f"0x{dex}", dex)])

    monkeypatch.setattr(tape, "get", ranking)
    seed.main(["--only", "PEPE"])
    out = capsys.readouterr().out
    assert "widest sibling spread · PEPE" in out and "× (" in out
    assert "hero · PEPE · fired: sibling-pool spread" in out
    strip = json.loads((proof / "census.json").read_text())
    assert strip["hero"]["pool"] is None and strip["tokens"] == 2
    assert seed.main(["--census-only"]) is None
    assert "rebuilt docs/proof/census.json from 2 receipt(s)" in capsys.readouterr().out


def test_running_the_script_as_main_goes_through_the_key_gate(monkeypatch):
    monkeypatch.setenv("CMC_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["seed.py"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(SEED_PY), run_name="__main__")
    assert "keyless by definition" in str(e.value.code)


def test_a_stablecoin_off_ethereum_never_enters_the_sibling_spread(sandbox, monkeypatch):
    monkeypatch.setattr(
        tape, "pull", lambda p, a, pages=8, quiet=False: (_two_pool_rows(), _meta(pages))
    )
    foreign = seed.capture("USDT", "0xusdt", "bsc", 8)
    strip = seed.census([foreign], [])
    assert strip["tokens"] == 1 and strip["pools"] == 2
    assert strip["spreads"] == [] and strip["widest_spread"] is None
