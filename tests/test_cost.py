"""The price: a1/a0, the adverse-signed move, the percentiles, the row and its example."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import make_row  # noqa: E402

from middleman import cost, detect  # noqa: E402


def test_the_price_is_a1_over_a0_and_never_the_feeds_rounded_q():
    """Uniswap v4 rows carry q rounded to 2 s.f. or 0 (spike 2026-09-19). The engine divides."""
    r = make_row(1, 1, "a", "buy", 3903271.04, 0.005769)
    r["q"] = 1.5e-9  # what the feed said; wrong at the 2nd significant figure
    assert abs(cost.price(r) - 0.005769 / 3903271.04) < 1e-18
    assert cost.price({"a0": 0, "a1": 1}) is None
    assert cost.price({"a0": "x", "a1": 1}) is None


def test_a_buy_that_pays_more_than_the_previous_print_is_adverse_positive():
    rows = [make_row(1, 1, "a", "buy", 100, 1.000), make_row(1, 2, "b", "buy", 100, 1.010)]
    (e,) = cost.quote_to_fill(rows)
    assert abs(e["bps"] - 100.0) < 1e-9 and e["tp"] == "buy"


def test_a_sell_that_receives_less_than_the_previous_print_is_adverse_positive():
    rows = [make_row(1, 1, "a", "buy", 100, 1.000), make_row(1, 2, "b", "sell", 100, 0.990)]
    (e,) = cost.quote_to_fill(rows)
    assert abs(e["bps"] - 100.0) < 1e-9 and e["tp"] == "sell"


def test_a_fill_better_than_the_previous_print_is_negative_not_clipped():
    rows = [make_row(1, 1, "a", "buy", 100, 1.000), make_row(1, 2, "b", "buy", 100, 0.990)]
    (e,) = cost.quote_to_fill(rows)
    assert e["bps"] < 0


def test_the_first_print_of_a_pool_has_no_quote_and_is_skipped():
    assert cost.quote_to_fill([make_row(1, 1, "a", "buy", 100, 1)]) == []


def test_an_unpriceable_print_neither_measures_nor_moves_the_quote():
    rows = [
        make_row(1, 1, "a", "buy", 100, 1.00),
        make_row(1, 2, "b", "buy", 0, 1.00),
        make_row(1, 3, "c", "buy", 100, 1.01),
    ]
    (e,) = cost.quote_to_fill(rows)
    assert e["idx"] == 2 and abs(e["bps"] - 100.0) < 1e-9


def test_a_print_with_an_unknown_side_is_skipped_but_still_becomes_the_quote():
    rows = [
        make_row(1, 1, "a", "buy", 100, 1.00),
        make_row(1, 2, "b", "??", 100, 1.10),
        make_row(1, 3, "c", "buy", 100, 1.10),
    ]
    (e,) = cost.quote_to_fill(rows)
    assert e["idx"] == 3 - 1 and abs(e["bps"]) < 1e-9


def test_percentiles_are_real_observations_never_interpolations():
    vals = [5.0, 1.0, 3.0, 2.0, 4.0]
    assert cost.percentile(vals, 50) == 3.0
    assert cost.percentile(vals, 90) == 5.0
    assert cost.percentile([7.0], 90) == 7.0
    assert cost.percentile([], 50) is None


def test_span_is_hours_between_first_and_last_timestamp():
    rows = [make_row(1, 1, "a", "buy", 1, 1, ts=0), make_row(2, 1, "b", "buy", 1, 1, ts=7_200_000)]
    assert cost.span_hours(rows) == 2.0
    assert cost.span_hours(rows[:1]) == 0.0


def _moto_like():
    """A pool where one wallet round-trips at a wide spread and everyone else fills tightly."""
    rows = []
    lg = 1
    for h in range(100, 110):
        rows.append(make_row(h, lg, "W", "sell", 1000, 0.95, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 1, "W", "buy", 1000, 1.05, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 2, f"o{h}", "buy", 10, 0.0101, v=10))
        rows.append(make_row(h, lg + 3, f"p{h}", "buy", 10, 0.01012, v=10))
        lg += 4
    return detect.order(rows)


def test_the_naive_number_is_wrong_until_the_round_trips_are_removed():
    rows = _moto_like()
    rt, sw, organic = detect.middlemen(rows)
    row = cost.pool_row(("Uniswap v2", rows[0]["t0a"], rows[0]["t1a"]), rows, rt, sw, organic)
    assert row["round_trips"]["pairs"] == 10 and row["round_trips"]["wallets"] == ["W"]
    assert row["round_trips"]["same_tx_share"] == 1.0
    assert row["round_trips"]["share_volume"] > 0.98
    # the legs print a 1,000-bps swing every block; with them in, the tape's p90 is that swing
    assert row["naive"]["p90_bps"] > 1000 > 30 > row["q2f"]["p90_bps"]
    assert row["naive"]["p50_bps"] >= row["q2f"]["p50_bps"]
    assert row["n"] == 40 and row["n_organic"] == 20 and row["makers"] == 21


def test_the_example_block_quotes_the_first_round_trip_verbatim_with_its_arithmetic():
    rows = _moto_like()
    rt, sw, organic = detect.middlemen(rows)
    row = cost.pool_row(("Uniswap v2", rows[0]["t0a"], rows[0]["t1a"]), rows, rt, sw, organic)
    ex = row["example"]
    assert ex["kind"] == "round-trip" and ex["h"] == "100"
    assert ex["highlight"] == ["1", "2"] and len(ex["rows"]) == 4
    assert ex["rows"][0] is rows[0]
    assert any("→ round-trip" in line for line in ex["arithmetic"])
    assert any("same tx" in line for line in ex["arithmetic"])


def test_the_example_block_of_a_clean_pool_is_two_consecutive_organic_prints_in_one_block():
    rows = detect.order(
        [
            make_row(5, 1, "a", "buy", 100, 1.00),
            make_row(6, 1, "b", "buy", 100, 1.01),
            make_row(6, 2, "c", "sell", 100, 1.00),
        ]
    )
    rt, sw, organic = detect.middlemen(rows)
    row = cost.pool_row(("Uniswap v2", "t", "q"), rows, rt, sw, organic)
    ex = row["example"]
    assert ex["kind"] == "organic" and ex["h"] == "6" and ex["highlight"] == ["2"]
    assert any("bps adverse" in line for line in ex["arithmetic"])


def test_a_pool_with_one_print_has_no_example_and_no_percentiles():
    rows = [make_row(5, 1, "a", "buy", 100, 1.00)]
    row = cost.pool_row(("Uniswap v2", "t", "q"), rows, [], [], rows)
    assert row["example"] is None
    assert row["q2f"]["p50_bps"] is None and row["q2f"]["n"] == 0
    assert row["round_trips"]["same_tx_share"] is None


def test_a_sandwich_example_names_its_victims():
    rows = detect.order(
        [
            make_row(10, 1, "A", "buy", 100, 1.00),
            make_row(10, 2, "B", "buy", 50, 0.52),
            make_row(10, 3, "A", "sell", 100, 1.03),
        ]
    )
    rt, sw, organic = detect.middlemen(rows)
    row = cost.pool_row(("Uniswap v2", "t", "q"), rows, rt, sw, organic)
    assert row["sandwiches"] == {"count": 1, "wallets": ["A"], "victims": 1, "take_quote": 0.03}
    assert row["example"]["kind"] == "sandwich" and row["example"]["victims"] == ["2"]
