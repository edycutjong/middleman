"""The door a judge walks through: the receipt shape, the printed table, the exits."""

import io
import json
import runpy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import USDC, make_row  # noqa: E402

from middleman import cli, enrich, tape  # noqa: E402

MOTO = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"


def _tape():
    """Two pools: a washed WETH pool with 60 organic prints, and a thin USDC pool."""
    rows, lg = [], 1
    for h in range(100, 130):
        rows.append(make_row(h, lg, "W", "sell", 1000, 1.00, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 1, "W", "buy", 1000, 1.02, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 2, f"o{h}", "buy", 10, 0.0101, v=10))
        rows.append(make_row(h, lg + 3, f"p{h}", "sell", 10, 0.01008, v=10))
        lg += 4
    rows.append(make_row(131, 1, "z", "buy", 10, 0.01, t1a=USDC, t1s="USDC"))
    rows.append(make_row(131, 2, "y", "buy", 10, 0.0102, t1a=USDC, t1s="USDC"))
    return rows


def _meta(calls=1, **over):
    m = {
        "pages": calls,
        "error": None,
        "throttled": False,
        "stalled": False,
        "credits": 0,
        "keyed": False,
        "calls": [{"ok": True, "url": "u", "status": 200, "utc": "t", "sha256": "h"}] * calls,
        "wall_s": 0.1,
    }
    m.update(over)
    return m


@pytest.fixture
def offline(monkeypatch):
    """Every network function replaced; no key exported."""
    for var in tape.KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(tape, "pull", lambda p, a, pages=8, quiet=False: (_tape(), _meta(pages)))
    pools = [
        {
            "addr": "0xweth",
            "venue": "Uniswap v2",
            "liq_usd": 959000.0,
            "base_address": MOTO,
            "quote_address": make_row(1, 1, "a", "buy", 1, 1)["t1a"],
        },
    ]
    monkeypatch.setattr(enrich, "token_pools", lambda p, a, quiet=False: (pools, {"ok": True}))
    monkeypatch.setattr(
        enrich,
        "security",
        lambda p, a, quiet=False: (
            {"buy_tax": 0.0, "sell_tax": 0.0, "level": "safe"},
            {"ok": True},
        ),
    )
    monkeypatch.setattr(
        enrich,
        "pair_quotes",
        lambda p, addr, quiet=False: (
            {
                "num_transactions_24h": 4848,
                "buys_24h": 2621,
                "sells_24h": 2227,
                "liquidity_usd": 1.0,
            },
            {"ok": True},
        ),
    )
    monkeypatch.setattr(
        enrich,
        "hero_pair",
        lambda quiet=False: (
            {
                "name": "MOTO/WETH",
                "symbol": "MOTO",
                "address": MOTO,
                "pool": "0xweth",
                "rule": enrich.HERO_RULE,
                "rows_returned": 100,
            },
            {"ok": True},
        ),
    )


def test_the_receipt_carries_every_number_the_table_shows_and_the_calls_behind_them(offline):
    r = cli.analyse("ethereum", MOTO, "MOTO", pages=8)
    assert r["auth"].startswith("none") and r["credits_used"] == 0
    assert r["window"]["prints"] == 122 and r["window"]["partial"] is False
    assert r["window"]["first_block"] == "100" and r["window"]["last_block"] == "131"
    weth, usdc = r["pools"]
    assert weth["round_trips"]["pairs"] == 30 and weth["round_trips"]["wallets"] == ["W"]
    assert weth["n_organic"] == 60 and weth["addr"] == "0xweth" and weth["liq_usd"] == 959000.0
    assert weth["buy_tax"] == 0.0 and usdc["addr"] is None
    assert r["decision"]["pool"] == weth["key"] and r["decision"]["cap_pct"] >= 0.05
    assert r["coverage"]["window_share_of_24h"] == round(120 / 4848, 4)
    assert len(r["calls"]) == 8 + 3 and set(r["rules"]) >= {
        "round_trip",
        "sandwich",
        "route",
        "cap",
    }


def test_without_enrichment_the_table_still_renders_and_no_extra_call_is_made(offline, monkeypatch):
    monkeypatch.setattr(enrich, "token_pools", lambda *a, **k: pytest.fail("called"))
    r = cli.analyse("ethereum", MOTO, "MOTO", pages=2, with_enrich=False)
    assert len(r["calls"]) == 2 and r["taxes"] is None and r["coverage"] is None
    assert r["pools"][0]["addr"] is None


def test_a_fetch_that_returns_nothing_is_an_error_result_not_an_empty_table(offline, monkeypatch):
    monkeypatch.setattr(
        tape, "pull", lambda *a, **k: ([], _meta(0, error="HTTP 429 x", throttled=True))
    )
    r = cli.analyse("ethereum", MOTO, "MOTO")
    assert r["error"] == "HTTP 429 x" and r["throttled"] is True and "pools" not in r


def test_the_printed_table_names_the_route_the_rule_the_coverage_and_the_raw_rows(offline):
    r = cli.analyse("ethereum", MOTO, "MOTO", pages=8)
    out = io.StringIO()
    cli.render(r, out=out)
    text = out.getvalue()
    assert "route via Uniswap v2 / WETH · cap slippage at" in text
    assert "rule: lowest organic p90" in text
    assert "coverage: this window is 2% of the routed pool's 24h transactions" in text
    assert "block 100 — raw rows (round-trip)" in text and "◀ leg" in text
    assert "→ round-trip" in text and "◀ route" in text
    assert "buying back what they just sold" in text


def test_a_partial_window_is_said_out_loud_before_the_table(offline, monkeypatch):
    monkeypatch.setattr(
        tape,
        "pull",
        lambda p, a, pages=8, quiet=False: (_tape(), _meta(3, error="HTTP 429", throttled=True)),
    )
    r = cli.analyse("ethereum", MOTO, "MOTO", pages=8)
    out = io.StringIO()
    cli.render(r, out=out)
    assert "note: 3 of 8 page(s) landed — throttled" in out.getvalue()


def test_the_hero_line_falls_back_from_round_trips_to_sandwiches_to_the_pool_spread_to_nothing():
    def rows(rt, sw, p50s):
        return [
            {
                "venue": f"v{i}",
                "quote": "Q",
                "n_organic": 100,
                "round_trips": {
                    "pairs": rt if i == 0 else 0,
                    "wallets": ["W"],
                    "share_volume": 0.8,
                    "same_tx_share": 1.0,
                },
                "sandwiches": {"count": sw if i == 0 else 0, "victims": sw},
                "q2f": {"p50_bps": p50},
            }
            for i, p50 in enumerate(p50s)
        ]

    assert "80.0% of v0 / Q volume" in cli.hero_line({"pools": rows(5, 0, [10.0])})
    assert "2 sandwich(es) in v0 / Q" in cli.hero_line({"pools": rows(0, 2, [10.0])})
    assert "a fill pays 4.0× more in v1 / Q" in cli.hero_line({"pools": rows(0, 0, [10.0, 40.0])})
    assert "every print organic" in cli.hero_line({"pools": rows(0, 0, [10.0])})


def test_main_with_no_flags_runs_the_hero_rule_live_and_writes_the_receipt(
    offline, capsys, tmp_path
):
    out = tmp_path / "run.json"
    cli.main(["--json", str(out)])
    text = capsys.readouterr().out
    assert "hero rule:" in text and "MOTO/WETH" in text and "0 credits — keyless" in text
    payload = json.loads(out.read_text())
    assert payload["hero_rule"]["address"] == MOTO and len(payload["results"]) == 1
    assert payload["results"][0]["symbol"] == "MOTO" and payload["credits_used"] == 0


def test_main_with_an_address_skips_the_hero_rule(offline, capsys, monkeypatch):
    monkeypatch.setattr(enrich, "hero_pair", lambda quiet=False: pytest.fail("hero rule called"))
    cli.main(["--address", MOTO, "--symbol", "X", "--pages", "2"])
    assert "X · ethereum · 122 prints" in capsys.readouterr().out


def test_the_watchlist_prints_a_census_line(offline, capsys):
    cli.main(["--watchlist"])
    text = capsys.readouterr().out
    assert "census · 3 tokens · 366 prints · 0 sandwiches · 1 round-trip wallet(s)" in text


def test_a_run_the_throttle_killed_outright_exits_75_with_the_way_through(
    offline, monkeypatch, capsys
):
    monkeypatch.setattr(
        tape,
        "pull",
        lambda *a, **k: ([], _meta(0, error="HTTP 429 (error 1022): limit", throttled=True)),
    )
    with pytest.raises(SystemExit) as e:
        cli.main(["--address", MOTO])
    assert e.value.code == 75
    err = capsys.readouterr().err
    assert "no tape" in err and "CMC_API_KEY" in err


def test_a_run_that_failed_for_another_reason_exits_1_with_the_error(offline, monkeypatch):
    monkeypatch.setattr(
        tape, "pull", lambda *a, **k: ([], _meta(0, error="URLError: dns", throttled=False))
    )
    with pytest.raises(SystemExit) as e:
        cli.main(["--address", MOTO])
    assert "URLError: dns" in str(e.value.code)


def test_a_throttled_hero_rule_exits_75_before_pulling_anything(offline, monkeypatch):
    monkeypatch.setattr(
        enrich,
        "hero_pair",
        lambda quiet=False: (None, {"ok": False, "error": "HTTP 429", "throttled": True}),
    )
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 75


def test_a_keyed_run_announces_itself_on_the_first_line_and_in_the_receipt(
    offline, monkeypatch, capsys, tmp_path
):
    monkeypatch.setenv("CMC_API_KEY", "sekrit")
    monkeypatch.setattr(
        tape,
        "pull",
        lambda p, a, pages=8, quiet=False: (_tape(), _meta(pages, keyed=True, credits=pages)),
    )
    out = tmp_path / "run.json"
    cli.main(["--address", MOTO, "--pages", "2", "--json", str(out)])
    text = capsys.readouterr().out
    assert "keyed via $CMC_API_KEY (escape hatch" in text and "sekrit" not in text
    payload = json.loads(out.read_text())
    assert payload["credits_used"] == 2 and "$CMC_API_KEY" in payload["results"][0]["auth"]
    assert "sekrit" not in out.read_text()


def test_the_file_a_judge_runs_is_the_file_that_runs(offline, capsys, monkeypatch):
    """python3 scripts/middleman.py — through the __main__ guard, not an import."""
    monkeypatch.setattr(sys, "argv", ["middleman.py", "--address", MOTO, "--pages", "1"])
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts" / "middleman.py"), run_name="__main__"
    )
    assert "route via" in capsys.readouterr().out


def test_python_dash_m_middleman_also_runs(offline, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["middleman", "--address", MOTO, "--pages", "1"])
    runpy.run_module("middleman", run_name="__main__")
    assert "route via" in capsys.readouterr().out
