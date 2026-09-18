"""The decision: the rule, its floor, and the cap rounding."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleman import recommend  # noqa: E402


def _row(key, n_organic, p90):
    return {
        "key": key,
        "venue": key[0],
        "quote": key[2],
        "n_organic": n_organic,
        "q2f": {"p90_bps": p90},
    }


def test_the_cap_is_the_p90_rounded_up_to_the_next_five_hundredths_of_a_percent():
    assert recommend.cap_pct(61.2) == 0.65
    assert recommend.cap_pct(60.0) == 0.60
    assert recommend.cap_pct(60.01) == 0.65
    assert recommend.cap_pct(4.0) == 0.05


def test_the_cap_never_goes_below_one_step_even_when_fills_beat_their_quote():
    assert recommend.cap_pct(-12.0) == 0.05
    assert recommend.cap_pct(0.0) == 0.05
    assert recommend.cap_pct(None) is None


def test_the_route_is_the_lowest_organic_p90_among_pools_with_enough_organic_prints():
    rows = [
        _row(["Uniswap v2", "t", "WETH"], 600, 61.2),
        _row(["ShibaSwap", "t", "USDC"], 46, 12.0),  # tighter, but too thin to trust
        _row(["Uniswap v3 (Ethereum)", "t", "WETH"], 254, 64.0),
    ]
    d = recommend.route(rows)
    assert d["pool"] == ["Uniswap v2", "t", "WETH"]
    assert d["cap_pct"] == 0.65 and d["candidates"] == 2
    assert d["why"] == recommend.RULE


def test_a_tie_on_p90_goes_to_the_pool_with_more_organic_prints():
    rows = [_row(["a", "t", "q"], 80, 50.0), _row(["b", "t", "q"], 200, 50.0)]
    assert recommend.route(rows)["pool"] == ["b", "t", "q"]


def test_when_no_pool_qualifies_the_rule_is_stated_not_widened():
    d = recommend.route([_row(["a", "t", "q"], 49, 5.0)])
    assert d["pool"] is None and d["cap_pct"] is None
    assert "≥ 50" in d["why"] and "more pages" in d["why"]


def test_a_pool_with_no_priced_prints_cannot_be_routed_to():
    d = recommend.route([_row(["a", "t", "q"], 500, None)])
    assert d["pool"] is None
