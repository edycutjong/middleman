"""The join: order, group, and the two shapes — each test named for what it pins."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import USDC, WETH, make_row  # noqa: E402

from middleman import detect  # noqa: E402

# ── order ────────────────────────────────────────────────────────────────────────────────────


def test_block_and_log_index_are_sorted_as_integers_not_as_the_strings_they_arrive_as():
    """h and lgid are strings in the response. Sorted as text, "99" > "1000" and "9" > "10",
    which puts a later print before an earlier one and breaks every 'between'."""
    rows = [
        make_row(1000, 5, "a", "buy", 1, 1),
        make_row(99, 10, "b", "buy", 1, 1),
        make_row(99, 9, "c", "buy", 1, 1),
    ]
    assert [r["ma"] for r in detect.order(rows)] == ["c", "b", "a"]


def test_a_row_without_an_integer_block_is_left_out_of_the_join_and_counted():
    rows = [make_row(10, 1, "a", "buy", 1, 1), make_row(11, 2, "b", "buy", 1, 1)]
    rows[1]["h"] = None
    assert len(detect.order(rows)) == 1
    assert detect.unplaceable(rows) == 1


# ── group ────────────────────────────────────────────────────────────────────────────────────


def test_pools_are_recovered_from_venue_and_the_two_contracts():
    rows = [
        make_row(1, 1, "a", "buy", 1, 1),
        make_row(1, 2, "b", "buy", 1, 1, t1a=USDC, t1s="USDC"),
        make_row(1, 3, "c", "buy", 1, 1, en="Uniswap v3 (Ethereum)"),
    ]
    pools = detect.group(rows)
    assert set(pools) == {
        ("Uniswap v2", make_row(1, 1, "a", "buy", 1, 1)["t0a"], WETH),
        ("Uniswap v2", make_row(1, 1, "a", "buy", 1, 1)["t0a"], USDC),
        ("Uniswap v3 (Ethereum)", make_row(1, 1, "a", "buy", 1, 1)["t0a"], WETH),
    }


def test_a_null_venue_becomes_an_unattributed_pool_rather_than_a_crash_or_a_merge():
    """`en` is null on ~4 % of Ethereum rows (ex: true). They are a pool of their own."""
    rows = [make_row(1, 1, "a", "buy", 1, 1, en=None), make_row(1, 2, "b", "buy", 1, 1)]
    pools = detect.group(rows)
    assert (detect.UNATTRIBUTED, rows[0]["t0a"], WETH) in pools
    assert len(pools) == 2


def test_rows_inside_a_pool_keep_chain_order():
    rows = [make_row(2, 1, "a", "buy", 1, 1), make_row(1, 7, "b", "buy", 1, 1)]
    (prints,) = detect.group(rows).values()
    assert [r["ma"] for r in prints] == ["b", "a"]


# ── round-trips ──────────────────────────────────────────────────────────────────────────────


def test_a_wallet_selling_and_buying_back_the_same_size_in_one_block_is_a_round_trip():
    rows = [
        make_row(10, 433, "A", "sell", 570251.66, 0.7083, tx="0xt1"),
        make_row(10, 442, "A", "buy", 561203.00, 0.7012, tx="0xt1"),
    ]
    rt, sw, organic = detect.middlemen(rows)
    assert len(rt) == 1 and not sw and not organic
    assert rt[0]["ma"] == "A" and rt[0]["same_tx"] is True
    assert rt[0]["legs"] == rows


def test_legs_six_percent_apart_are_two_prints_not_a_round_trip():
    rows = [make_row(10, 1, "A", "sell", 100, 1), make_row(10, 2, "A", "buy", 106, 1)]
    rt, sw, organic = detect.middlemen(rows)
    assert not rt and len(organic) == 2


def test_legs_exactly_five_percent_apart_still_match():
    rows = [make_row(10, 1, "A", "sell", 100, 1), make_row(10, 2, "A", "buy", 105, 1)]
    rt, _, _ = detect.middlemen(rows)
    assert len(rt) == 1


def test_the_same_wallet_on_both_sides_in_two_different_blocks_is_not_a_round_trip():
    rows = [make_row(10, 1, "A", "sell", 100, 1), make_row(11, 1, "A", "buy", 100, 1)]
    rt, sw, organic = detect.middlemen(rows)
    assert not rt and not sw and len(organic) == 2


def test_the_same_wallet_printing_twice_in_the_same_direction_is_not_a_round_trip():
    rows = [make_row(10, 1, "A", "sell", 100, 1), make_row(10, 2, "A", "sell", 100, 1)]
    rt, _, organic = detect.middlemen(rows)
    assert not rt and len(organic) == 2


def test_a_leg_belongs_to_at_most_one_match():
    """A sell, A buy, A sell: the first two pair; the third is organic, not a second pair."""
    rows = [
        make_row(10, 1, "A", "sell", 100, 1),
        make_row(10, 2, "A", "buy", 100, 1),
        make_row(10, 3, "A", "sell", 100, 1),
    ]
    rt, _, organic = detect.middlemen(rows)
    assert len(rt) == 1 and [r["lgid"] for r in organic] == ["3"]


def test_round_trip_wallets_are_distinct_and_in_first_seen_order():
    rows = [
        make_row(10, 1, "B", "sell", 100, 1),
        make_row(10, 2, "B", "buy", 100, 1),
        make_row(11, 1, "A", "sell", 100, 1),
        make_row(11, 2, "A", "buy", 100, 1),
        make_row(12, 1, "B", "sell", 100, 1),
        make_row(12, 2, "B", "buy", 100, 1),
    ]
    rt, _, _ = detect.middlemen(rows)
    assert detect.wallets(rt) == ["B", "A"]


# ── sandwiches ───────────────────────────────────────────────────────────────────────────────


def test_a_buy_b_buy_a_sell_in_one_block_is_a_sandwich_with_b_as_the_victim():
    rows = [
        make_row(10, 1, "A", "buy", 100, 1.00),
        make_row(10, 2, "B", "buy", 50, 0.52),
        make_row(10, 3, "A", "sell", 100, 1.03),
    ]
    rt, sw, organic = detect.middlemen(rows)
    assert not rt and len(sw) == 1
    assert sw[0]["ma"] == "A" and [v["ma"] for v in sw[0]["victims"]] == ["B"]
    assert sw[0]["take_quote"] == 1.03 - 1.00
    assert [r["ma"] for r in organic] == ["B"]  # the victim's fill is real and stays


def test_a_sandwich_with_two_victims_counts_both():
    rows = [
        make_row(10, 1, "A", "buy", 100, 1),
        make_row(10, 2, "B", "buy", 10, 0.1),
        make_row(10, 3, "C", "buy", 10, 0.1),
        make_row(10, 4, "A", "sell", 99, 1),
    ]
    _, sw, organic = detect.middlemen(rows)
    assert len(sw) == 1 and len(sw[0]["victims"]) == 2 and len(organic) == 2


def test_the_mirror_sell_first_sandwich_is_detected_too():
    rows = [
        make_row(10, 1, "A", "sell", 100, 1.00),
        make_row(10, 2, "B", "sell", 10, 0.09),
        make_row(10, 3, "A", "buy", 100, 0.97),
    ]
    _, sw, _ = detect.middlemen(rows)
    assert len(sw) == 1 and sw[0]["take_quote"] == 1.00 - 0.97


def test_a_triple_split_across_two_blocks_is_not_a_sandwich():
    rows = [
        make_row(10, 1, "A", "buy", 100, 1),
        make_row(10, 2, "B", "buy", 10, 0.1),
        make_row(11, 1, "A", "sell", 100, 1),
    ]
    rt, sw, organic = detect.middlemen(rows)
    assert not rt and not sw and len(organic) == 3


def test_a_print_the_other_way_between_the_legs_breaks_the_sandwich():
    rows = [
        make_row(10, 1, "A", "buy", 100, 1),
        make_row(10, 2, "B", "sell", 10, 0.1),
        make_row(10, 3, "A", "sell", 100, 1),
    ]
    _, sw, organic = detect.middlemen(rows)
    assert not sw and len(organic) == 3


def test_more_than_four_victims_is_not_matched_as_one_sandwich():
    rows = [make_row(10, 1, "A", "buy", 100, 1)]
    rows += [make_row(10, 2 + i, f"V{i}", "buy", 10, 0.1) for i in range(5)]
    rows += [make_row(10, 9, "A", "sell", 100, 1)]
    _, sw, organic = detect.middlemen(rows)
    assert not sw and len(organic) == 7


def test_a_return_leg_six_percent_off_is_not_a_sandwich():
    rows = [
        make_row(10, 1, "A", "buy", 100, 1),
        make_row(10, 2, "B", "buy", 10, 0.1),
        make_row(10, 3, "A", "sell", 106, 1),
    ]
    _, sw, _ = detect.middlemen(rows)
    assert not sw


def test_a_round_trip_and_a_sandwich_in_one_block_are_both_found():
    rows = [
        make_row(10, 1, "R", "sell", 100, 1),
        make_row(10, 2, "R", "buy", 100, 1),
        make_row(10, 3, "A", "buy", 100, 1),
        make_row(10, 4, "B", "buy", 10, 0.1),
        make_row(10, 5, "A", "sell", 100, 1),
    ]
    rt, sw, organic = detect.middlemen(rows)
    assert len(rt) == 1 and len(sw) == 1 and [r["ma"] for r in organic] == ["B"]


def test_a_row_with_no_maker_never_joins_to_another_row_with_no_maker():
    rows = [make_row(10, 1, None, "sell", 100, 1), make_row(10, 2, None, "buy", 100, 1)]
    rt, sw, organic = detect.middlemen(rows)
    assert not rt and not sw and len(organic) == 2


def test_size_match_needs_a_positive_first_leg():
    assert not detect.size_match({"a0": 0}, {"a0": 0})
    assert not detect.size_match({"a0": "x"}, {"a0": 1})
    assert detect.size_match({"a0": 100}, {"a0": 104.9})
