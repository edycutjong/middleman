"""render_site.py branch by branch: the formatters, every headline fall-through, the block
drawing, the panels, the four pages and the --check gate — on synthetic receipts and on private
copies of the committed ones, never writing into site/."""

import copy
import json
import runpy
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import render_site  # noqa: E402
from conftest import BASE, USDC, WETH  # noqa: E402

from middleman import enrich  # noqa: E402

TX_URL = "https://pro-api.coinmarketcap.com/public-api/v1/dex/tokens/transactions?platform=ethereum"
POOLS_URL = "https://pro-api.coinmarketcap.com/public-api/v1/dex/token/pools?platform=ethereum"


def _call(url=TX_URL, ok=True, **over):
    c = {
        "ok": ok,
        "url": url,
        "status": 200 if ok else None,
        "sha256": "f00d" if ok else "",
        "utc": "2026-09-18T22:36:19Z",
        "elapsed_ms": 12.5,
        "credit_count": 1,
    }
    c.update(over)
    return c


def _ex_row(lgid, ma, tp, a0, a1, tx=None):
    return {"h": "100", "lgid": str(lgid), "ma": ma, "tp": tp, "a0": a0, "a1": a1, "tx": tx}


def _pool(venue="Uniswap v2", quote="WETH", t1a=WETH, pairs=0, sandwiches=0, example=None, **over):
    p = {
        "key": [venue, BASE, t1a],
        "venue": venue,
        "quote": quote,
        "n": 12,
        "n_organic": 10,
        "round_trips": {
            "pairs": pairs,
            "wallets": ["0xa"] if pairs else [],
            "share_volume": 0.4 if pairs else 0.0,
            "same_tx_share": 1.0,
            "volume_usd": 400.0,
        },
        "sandwiches": {"count": sandwiches, "victims": sandwiches, "wallets": [], "take_quote": 0},
        "q2f": {"n": 10, "p50_bps": 10.0, "p90_bps": 20.0},
        "naive": {"n": 11, "p50_bps": 30.0, "p90_bps": 40.0},
        "buy_tax": None,
        "sell_tax": None,
        "liq_usd": None,
        "volume_usd": 1000.0,
        "pools_merged": 1,
        "example": example,
    }
    p.update(over)
    return p


def _receipt(pools, route=0, calls=None, **over):
    routed = pools[route] if route is not None else None
    r = {
        "symbol": "TOK",
        "platform": "ethereum",
        "address": BASE,
        "captured_utc": "2026-09-18T22:36:19Z",
        "window": {"prints": 12, "span_hours": 1.5, "first_block": "100", "last_block": "101"},
        "decision": {
            "pool": routed and routed["key"],
            "venue": routed and routed["venue"],
            "quote": routed and routed["quote"],
            "cap_pct": 0.65,
            "p90_bps": 20.0,
            "candidates": 1,
            "why": "fewer than 50 organic prints in every pool",
        },
        "coverage": {"window_share_of_24h": 0.25, "num_transactions_24h": 48},
        "calls": [_call()] if calls is None else calls,
        "wall_s": 2.0,
        "auth": "none",
        "credits_used": 0,
        "tape": "data/tape_tok.json",
        "rules": {"order": "by (h, lgid)"},
        "pools": pools,
    }
    r.update(over)
    return r


SPREAD = {
    "symbol": "TOK",
    "ratio": 3.2,
    "high": {"pool": "Uniswap v3 / USDC", "p50_bps": 9.0},
    "low": {"pool": "Uniswap v2 / WETH", "p50_bps": 2.8},
}


def _census(r, fired="round-trip share", spread=None, heroes=None):
    pool = r["pools"][0]
    return {
        "captured_utc": "2026-09-18T22:40:32Z",
        "hero": {
            "symbol": r["symbol"],
            "address": r["address"],
            "fired": fired,
            "rule": "the base token of the #1 pair",
            "pool": {"venue": pool["venue"], "quote": pool["quote"]},
        },
        "widest_spread": spread,
        "heroes": heroes or [],
        "rows": [
            {
                "file": "docs/proof/tok.json",
                "platform": "ethereum",
                "symbol": "TOK",
                "span_hours": 1.5,
            }
        ],
        "tokens": 1,
        "prints": 12,
        "pools": len(r["pools"]),
        "sandwiches": 0,
        "round_trip_pairs": 0,
        "round_trip_wallets": [],
    }


@pytest.fixture
def committed():
    census, platforms, receipts = render_site.load_all()
    return copy.deepcopy(census), platforms, copy.deepcopy(receipts)


@pytest.fixture
def proof(tmp_path, monkeypatch):
    """A private copy of docs/proof/ the test may rewrite."""
    private = tmp_path / "proof"
    shutil.copytree(ROOT / "docs" / "proof", private)
    monkeypatch.setattr(render_site, "PROOF", private)
    return private


def _rewrite(path, edit):
    m = json.loads(path.read_text())
    edit(m)
    path.write_text(json.dumps(m))


def test_usd_formats_millions_thousands_units_and_a_missing_value():
    assert [render_site.usd(v) for v in (None, 2.5e6, 12_400, 7.6)] == ["—", "$2.5M", "$12k", "$8"]


def test_bps_prints_one_decimal_or_a_dash():
    assert render_site.bps(None) == "—" and render_site.bps(12.345) == "12.3"


def test_price_is_quote_over_base_and_none_for_rows_it_cannot_price():
    assert render_site.price({"a0": 4, "a1": 2}) == 0.5
    assert render_site.price({"a0": 0, "a1": 2}) is None
    assert render_site.price({"a0": -1, "a1": 2}) is None
    assert render_site.price({"a1": 2}) is None
    assert render_site.price({"a0": "x", "a1": 2}) is None


def test_short_truncates_long_addresses_and_leaves_short_ones_alone():
    assert render_site.short(BASE) == "0xbd96…35e0"
    assert render_site.short("0xabc") == "0xabc"
    assert render_site.short(None) == ""


def test_load_all_skips_a_census_row_whose_receipt_is_not_on_disk(tmp_path, monkeypatch):
    proof = tmp_path / "docs" / "proof"
    proof.mkdir(parents=True)
    rows = [{"file": "docs/proof/tok.json"}, {"file": "docs/proof/gone.json"}]
    (proof / "census.json").write_text(json.dumps({"rows": rows}))
    (proof / "platforms.json").write_text(json.dumps({"platforms": {"ethereum": {}}}))
    (proof / "tok.json").write_text(json.dumps({"symbol": "TOK"}))
    monkeypatch.setattr(render_site, "BUILD", tmp_path)
    monkeypatch.setattr(render_site, "PROOF", proof)
    census, platforms, receipts = render_site.load_all()
    assert [r["symbol"] for r in receipts] == ["TOK"]
    assert platforms == {"ethereum": {}} and census["rows"] == rows


def test_the_middle_headline_drops_same_transaction_for_split_legs_and_names_unknown_coverage():
    pool = _pool(pairs=3)
    pool["round_trips"]["same_tx_share"] = 0.2
    r = _receipt([pool], coverage=None)
    hero = render_site.hero_ctx(r, _census(r))
    assert hero["kind"] == "middle" and hero["share"] == "40.0%"
    assert "same transaction" not in hero["claim"]
    assert hero["coverage"] == "an unknown share"


def test_the_spread_headline_names_both_pools_and_the_quiet_headline_counts_the_prints():
    r = _receipt([_pool(), _pool(venue="Uniswap v3", quote="USDC", t1a=USDC)], route=1)
    spread = render_site.hero_ctx(r, _census(r, fired="sibling-pool spread", spread=SPREAD))
    assert spread["kind"] == "spread" and spread["share"] == "3.2×"
    assert "Uniswap v3 / USDC" in spread["claim"] and spread["quote"] == "USDC"
    quiet = render_site.hero_ctx(r, _census(r, fired="none"))
    assert quiet["kind"] == "none" and quiet["share"] == "0%"
    assert quiet["support"] == "12 prints, every one organic."


def test_the_lead_words_the_title_for_each_headline_kind():
    r = _receipt([_pool(pairs=2)])
    census = _census(r)
    hero = render_site.hero_ctx(r, census)
    pool = render_site.hero_pool(r)
    middle = render_site.lead_ctx(r, census, hero, pool)
    assert "1 wallet trading with themselves" in middle["line2"]
    assert middle["title"].startswith("Middleman — 40% of the #1 Uniswap v2 pair")
    assert middle["viz_foot"].endswith("12 prints · 1 pages · 2.0 s")
    census = _census(r, fired="sibling-pool spread", spread=SPREAD)
    spread = render_site.lead_ctx(r, census, render_site.hero_ctx(r, census), pool)
    assert spread["line1"] == "Same token, same hours, two pools."
    assert "3× more per fill in one TOK pool" in spread["title"]
    assert "12 prints, 1.5 h" in spread["description"]
    census = _census(r, fired="none")
    none = render_site.lead_ctx(r, census, render_site.hero_ctx(r, census), pool)
    assert none["line1"] == "No middleman in this window."
    assert "of 12 prints had a wallet on both sides" in none["line2"]
    assert none["og_alt"].endswith("no hairpin.")


def test_the_block_drawing_with_no_rows_is_a_bare_rail():
    r = _receipt([_pool()])
    svg, key = render_site.hero_viz(r, r["pools"][0])
    assert 'aria-label="No example block in this window"' in svg and "<rect" not in svg
    assert key == "<span><i></i>TOK: a single print in the window — nothing to compare</span>"


def test_the_block_drawing_marks_the_legs_the_victim_and_the_hairpin_of_a_sandwich():
    rows = [
        _ex_row(1, "0xattacker", "buy", 100.0, 1.0, tx="0xt1"),
        _ex_row(2, "0xvictim", "buy", 50.0, 0.6, tx="0xt2"),
        _ex_row(3, "0xattacker", "sell", 102.0, 1.1, tx="0xt3"),
        _ex_row(4, "0xother", "sell", 0, 0.0, tx="0xt4"),
    ]
    ex = {"h": "100", "kind": "sandwich", "rows": rows, "highlight": ["1", "3"], "victims": ["2"]}
    r = _receipt([_pool(sandwiches=1, example=ex)])
    svg, key = render_site.hero_viz(r, r["pools"][0])
    assert 'class="row leg l1"' in svg and 'class="row leg l2"' in svg
    assert 'class="row victim"' in svg and 'class="row print"' in svg
    assert 'class="hairpin"' in svg and "a sandwich." in svg
    assert "same block" in key and "sizes 2.0 % apart" in key
    assert '<b class="red">1 victim print</b> between the legs' in key


def test_the_block_drawing_draws_an_organic_fill_plain_and_skips_the_hairpin_for_a_lone_leg():
    """An organic example highlights a fill, not a wallet's legs: the legend draws it with the
    plain swatch, so the bar is `fill`, never `leg` (which the reveal animation turns orange)."""
    rows = [_ex_row(1, "0xa", "buy", 10.0, 1.0, tx="0xs"), _ex_row(2, "0xb", "sell", 9.0, 0.9)]
    organic = {"h": "100", "kind": "organic", "rows": rows, "highlight": ["1", "2"]}
    r = _receipt([_pool(example=organic)])
    svg, key = render_site.hero_viz(r, r["pools"][0])
    assert svg.count('class="row fill"') == 2 and "leg" not in svg and "hairpin" not in svg
    assert "the quote-to-fill." in svg and "two consecutive organic prints" in key
    lone = {
        "h": "100",
        "kind": "round-trip",
        "rows": rows,
        "highlight": ["1", "9"],
        "same_tx": True,
    }
    svg, key = render_site.hero_viz(r, _pool(example=lone))
    assert 'class="row leg l1"' in svg and "hairpin" not in svg
    assert "two consecutive organic prints" in key


def test_the_context_line_falls_back_to_the_engine_rule_when_the_census_has_none():
    r = _receipt([_pool()])
    census = _census(r)
    census["hero"]["rule"] = None
    line = render_site.context_line(r, census)
    assert f"chosen by rule: {render_site.esc(enrich.HERO_RULE)}" in line
    assert "blocks 100–101" in line and "captured 2026-09-18 22:36:19 UTC" in line


def test_table_rows_mark_the_route_the_merged_pools_the_taxes_and_the_middle_pool():
    routed = _pool(pools_merged=2, buy_tax=1.0, sell_tax=2.0, liq_usd=2.5e6)
    middle = _pool(venue="Uniswap v3", quote="USDC", t1a=USDC, pairs=4)
    rows = render_site.table_rows(_receipt([routed, middle])).split("\n")
    assert rows[0].startswith('<tr class="routed" data-i="0" tabindex="0" aria-selected="false">')
    assert "<small>×2</small>" in rows[0] and "◀ route" in rows[0]
    assert '<td class="mono">1 / 2</td>' in rows[0] and "$2.5M" in rows[0]
    assert 'class="mono rt none">—' in rows[0]
    assert rows[1].startswith('<tr class="middle" data-i="1" tabindex="0" aria-selected="true">')
    assert "4 · 1 wallet · 40.0%" in rows[1] and '<td class="mono">—</td>' in rows[1]
    assert "×" not in rows[1]


def test_route_ctx_explains_a_missing_route_and_counts_the_candidates_of_a_found_one():
    r = _receipt([_pool()], route=None)
    assert render_site.route_ctx(r) == {
        "line": "no route — fewer than 50 organic prints in every pool",
        "rule": render_site.esc(render_site.recommend.RULE),
    }
    found = render_site.route_ctx(_receipt([_pool()]))
    assert found["line"] == "▶ route via Uniswap v2 / WETH · cap slippage at 0.65 %"
    assert found["rule"].endswith("organic p90 here 20.0 bps · 1 candidate pool")


def test_hero_pool_falls_through_round_trips_sandwiches_the_route_then_the_first_pool():
    a, b = _pool(quote="A", pairs=1), _pool(quote="B", t1a=USDC, pairs=3)
    b["round_trips"]["share_volume"] = 0.9
    assert render_site.hero_pool(_receipt([a, b]))["quote"] == "B"
    c, d = _pool(quote="C", sandwiches=1), _pool(quote="D", t1a=USDC, sandwiches=5)
    assert render_site.hero_pool(_receipt([c, d]))["quote"] == "D"
    e, f = _pool(quote="E"), _pool(quote="F", t1a=USDC)
    assert render_site.hero_pool(_receipt([e, f], route=1))["quote"] == "F"
    assert render_site.hero_pool(_receipt([e, f], route=None))["quote"] == "E"


def test_the_rows_panel_without_an_example_block_says_there_is_nothing_to_compare():
    ctx = render_site.example_ctx(_receipt([_pool()]), {"ethereum": {"txuf": "x/%s"}})
    assert ctx["title"] == "Uniswap v2 / WETH — raw rows" and ctx["table"] == ""
    assert ctx["cap"].startswith("this pool has a single print") and ctx["json"] == "[]"


def test_the_rows_panel_links_transactions_only_with_an_explorer_and_flags_unpriceable_rows():
    rows = [
        _ex_row(1, "0xattacker", "buy", 100.0, 1.0, tx="0xt1"),
        _ex_row(2, "0xvictim", "buy", 50.0, 0.6, tx="0xt2"),
        _ex_row(3, "0xattacker", "sell", 102.0, 1.1, tx="0xt3"),
        _ex_row(4, "0xbystander", "buy", "n/a", 1.0),
    ]
    ex = {
        "h": "100",
        "kind": "sandwich",
        "rows": rows,
        "highlight": ["1", "3"],
        "victims": ["2"],
        "arithmetic": ["leg 1 <b>", "leg 2"],
    }
    r = _receipt([_pool(sandwiches=1, example=ex)])
    linked = render_site.example_ctx(r, {"ethereum": {"txuf": "https://etherscan.io/tx/%s"}})
    assert linked["title"].endswith("raw rows (sandwich)")
    assert 'href="https://etherscan.io/tx/0xt1"' in linked["table"]
    assert '<tr class="leg">' in linked["table"] and '<tr class="victim">' in linked["table"]
    assert '<tr class="">' in linked["table"] and "unpriceable row" in linked["table"]
    assert linked["arith"] == "<li>leg 1 &lt;b&gt;</li><li>leg 2</li>"
    assert "the first sandwich" in linked["cap"] and "data/tape_tok.json" in linked["cap"]
    bare = render_site.example_ctx(r, {})
    assert 'href="https://etherscan.io' not in bare["table"]
    assert '<span class="mono">0xt1</span>' in bare["table"]
    organic = {
        "h": "100",
        "kind": "organic",
        "rows": rows[:2],
        "highlight": ["1", "2"],
        "arithmetic": [],
    }
    filled = render_site.example_ctx(r, {}, _pool(example=organic))
    assert (
        '<tr class="leg">' in filled["table"] and "two consecutive organic prints" in filled["cap"]
    )


def test_census_ctx_notes_each_token_button_and_lists_the_other_chains():
    rt = _receipt([_pool(pairs=2)], symbol="RT")
    sw = _receipt([_pool(sandwiches=1)], symbol="SW")
    quiet = _receipt([_pool()], symbol="QUIET")
    bsc = _receipt([_pool()], symbol="USDT", platform="bsc")
    census = _census(rt, spread=SPREAD)
    census["heroes"] = [
        {"platform": "ethereum", "pair": "RT/WETH"},
        None,
        {"platform": "bsc", "pair": "USDT/WBNB"},
        {"platform": "solana", "pair": "USDC/wSOL"},
    ]
    census["rows"] = [
        {"symbol": "RT", "platform": "ethereum", "span_hours": 1.5},
        {"symbol": "SW", "platform": "ethereum", "span_hours": 4.0},
        {"symbol": "QUIET", "platform": "ethereum", "span_hours": 2.0},
        {"symbol": "USDT", "platform": "bsc", "span_hours": 0.1},
    ]
    ctx = render_site.census_ctx(census, [rt, sw, quiet, bsc])
    buttons = ctx["tokens"].split("\n")
    assert len(buttons) == 3 and 'aria-pressed="true">RT<small>2 rt</small>' in buttons[0]
    assert 'data-i="1" aria-pressed="false">SW<small>1 sw</small>' in buttons[1]
    assert "QUIET<small>quiet</small>" in buttons[2]
    assert ctx["others"] == "Also measured by the same rule: USDT/WBNB on BSC, USDC/wSOL on Solana."
    assert (ctx["chains"], ctx["pinned"], ctx["longest_symbol"], ctx["longest_span"]) == (
        2,
        2,
        "SW",
        "4",
    )
    assert (ctx["spread.symbol"], ctx["spread.ratio"], ctx["spread.high_pool"]) == (
        "TOK",
        "3.2",
        "Uniswap v3 / USDC",
    )
    census["heroes"] = [{"platform": "ethereum", "pair": "RT/WETH"}]
    census["widest_spread"] = None
    alone = render_site.census_ctx(census, [rt])
    assert alone["others"] == "" and alone["spread.low"] == "—" and alone["spread.low_pool"] == "—"


def test_receipt_ctx_falls_back_to_the_first_call_and_then_to_dashes_when_none_succeeded():
    pools_only = _receipt([_pool()], calls=[_call(POOLS_URL, sha256="cafe")])
    assert "cafe" in render_site.receipt_ctx(
        pools_only
    ) and "0 pages of 100" in render_site.receipt_ctx(pools_only)
    failed = _receipt([_pool()], calls=[_call(ok=False, status=429)])
    ctx = render_site.receipt_ctx(failed)
    assert '<span class="mono">—</span>' in ctx and 'href="#"' in ctx and "HTTP 429" in ctx


def test_proof_links_and_the_api_table_count_every_endpoint_from_the_calls():
    r = _receipt([_pool(pairs=1)], calls=[_call(), _call(), _call(POOLS_URL)])
    census = _census(r)
    census.update(tokens=1, prints=12, sandwiches=0, round_trip_pairs=1)
    links = render_site.proof_links(census, _receipt([_pool(pairs=1)]))
    assert "docs/proof/tok.json" in links and "40.0 % round-tripped" in links
    assert "the bare command ·" in links and "census.json" in links
    counts = render_site.endpoint_counts([r])
    assert counts["/v1/dex/tokens/transactions"] == 2 and counts["/v1/dex/token/pools"] == 1
    api = render_site.api_ctx([r])
    assert api["count"] == len(render_site.ENDPOINTS) and '<tr class="engine">' in api["rows"]
    assert '<td class="n">2</td>' in api["rows"] and '<td class="n">0</td>' in api["rows"]


def test_the_findings_read_the_cors_answer_and_the_worst_q_mismatch_from_the_spike(proof):
    before = render_site.findings_ctx()
    assert before["cors_allow_origin"] == "not sent" and before["cors_sent"] == 3
    assert (before["q_symbol"], before["q_v4"], before["q_v3"], before["q_bad"]) == (
        "PEPE",
        22,
        4,
        26,
    )
    _rewrite(proof / "spike.json", lambda m: m["cors"].update(allow_origin_present=True))
    assert render_site.findings_ctx()["cors_allow_origin"] == "sent"


def test_feedback_n_counts_the_numbered_headings(tmp_path, monkeypatch):
    (tmp_path / "FEEDBACK.md").write_text("# F\n\n## 1. a\n\n## 2. b\n\n### 3. not a finding\n")
    monkeypatch.setattr(render_site, "BUILD", tmp_path)
    assert render_site.feedback_n() == 2


def test_the_runs_timeline_marks_the_window_with_no_round_trips_quiet(committed):
    census, _, receipts = committed
    runs = render_site.runs_ctx(census, receipts)
    assert runs["n"] == 4 and '<div class="v quiet">0.0%</div>' in runs["cards"]
    assert "the day-1 spike" in runs["cards"] and "live_run_quiet.json" in runs["cards"]


def test_the_terminal_drops_same_transaction_when_the_legs_were_split(proof):
    def split(m):
        m["results"][0]["pools"][0]["round_trips"]["same_tx_share"] = 0.1

    _rewrite(proof / "live_run.json", split)
    term = render_site.term_ctx()["term"]
    assert "buying back what they just sold" in term and "same transaction" not in term
    assert "◀ route" in term and "▶ route via" in term


def test_the_terminal_prints_the_quiet_line_and_no_route_when_the_bare_run_found_neither(proof):
    def quiet(m):
        res = m["results"][0]
        for p in res["pools"]:
            p["round_trips"] = {"pairs": 0, "wallets": [], "share_volume": 0.0}
        res["decision"]["pool"] = None

    _rewrite(proof / "live_run.json", quiet)
    ctx = render_site.term_ctx()
    assert "no middleman found in this window — every print organic" in ctx["term"]
    assert "▶ route via" not in ctx["term"] and "◀ route" not in ctx["term"]
    assert ctx["cmd"].endswith("python3 scripts/middleman.py")


def test_slim_keeps_a_missing_example_as_none_and_trims_the_rows_of_a_present_one():
    rows = [_ex_row(i, "0xa", "buy", 1.0, 1.0) for i in range(20)]
    ex = {"h": "100", "kind": "organic", "rows": rows, "highlight": []}
    r = _receipt(
        [_pool(), _pool(quote="USDC", t1a=USDC, example=ex)], calls=[_call(ok=False), _call()]
    )
    s = render_site.slim(r)
    assert s["pools"][0]["example"] is None and len(s["pools"][1]["example"]["rows"]) == 14
    assert s["calls_n"] == 2 and s["first_sha256"] == "f00d" and "calls" not in s


def test_og_version_is_none_without_the_image_and_a_short_hash_with_it(tmp_path, monkeypatch):
    assert len(render_site.og_version()) == 8
    monkeypatch.setattr(render_site, "OG_IMAGE", tmp_path / "og-image.png")
    assert render_site.og_version() == "none"


def test_render_fills_dotted_slots_and_stops_on_an_unfilled_one():
    assert render_site.render("{{a.b}}-{{c}}", {"a.b": 1, "c": "x"}) == "1-x"
    with pytest.raises(SystemExit, match="unfilled slots"):
        render_site.render("{{a.b}}", {})


def test_the_pages_render_a_hero_with_no_route_no_coverage_no_spread_and_a_failed_call(committed):
    census, platforms, receipts = committed
    hero = render_site.hero_receipt(census, receipts)
    hero["decision"]["pool"] = None
    hero["coverage"] = None
    hero["calls"].append(
        _call("https://pro-api.coinmarketcap.com/public-api/x", ok=False, error="timed out")
    )
    census["widest_spread"] = None
    front = render_site.front_page(census, platforms, receipts)
    assert "no route —" in front and "an unknown share" in front
    evidence = render_site.evidence_page(census, platforms, receipts)
    assert '<td class="err mono">—</td>' in evidence and "timed out" in evidence
    judge = render_site.judge_page(census, platforms, receipts)
    assert "no route —" in judge
    deck = render_site.deck_page(census, platforms, receipts)
    assert "an unknown share" in deck and render_site.DECK_VERSION in deck


def test_main_writes_the_four_pages_and_check_reports_drift_only_after_a_page_is_edited(
    tmp_path, monkeypatch, capsys
):
    data = render_site.load_all()
    shutil.copy(ROOT / "FEEDBACK.md", tmp_path / "FEEDBACK.md")
    monkeypatch.setattr(render_site, "load_all", lambda: data)
    monkeypatch.setattr(render_site, "BUILD", tmp_path)
    monkeypatch.setattr(render_site, "SITE", tmp_path / "site")
    assert render_site.main(["--check"]) == 1
    assert "drift: site/index.html, site/evidence.html" in capsys.readouterr().out
    assert not (tmp_path / "site").exists()
    assert render_site.main([]) == 0
    out = capsys.readouterr().out
    assert out.startswith("wrote site/index.html (") and "wrote site/pitch/index.html" in out
    assert (tmp_path / "site" / "judge.html").exists()
    assert render_site.main(["--check"]) == 0
    assert "site/ is what docs/proof/*.json renders" in capsys.readouterr().out
    (tmp_path / "site" / "judge.html").write_text("<p>66.2 %</p>")
    assert render_site.main(["--check"]) == 1
    assert "drift: site/judge.html —" in capsys.readouterr().out


def test_main_reads_argv_from_the_process_when_run_as_a_program(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["render_site.py", "--check"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(ROOT / "scripts" / "render_site.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert e.value.code == (0 if "site/ is what docs/proof" in out else 1)
    assert "site/" in out
