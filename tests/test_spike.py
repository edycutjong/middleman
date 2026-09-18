"""The day-1 spike's own arithmetic, on synthetic rows, so its receipt can be trusted."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import spike  # noqa: E402
from conftest import BASE, make_row  # noqa: E402

PROOF = Path(__file__).resolve().parents[1] / "docs" / "proof" / "spike.json"


def test_field_facts_count_what_the_engine_depends_on():
    rows = [make_row(1, 1, "a", "buy", 100, 1), make_row(1, 2, "b", "buy", 100, 1, en=None)]
    rows[1]["q"] = 0.0  # a Uniswap v4-style row: q unusable, a1/a0 fine
    f = spike.field_facts(rows, BASE)
    assert f["rows"] == 2 and f["missing_per_field"]["ma"] == 0
    assert f["string_typed"] == {"h": 2, "lgid": 2, "ts": 2}
    assert f["q_equals_a1_over_a0_within_1e-6"] == 1 and f["q_mismatch_by_venue"] == {
        "unattributed": 1
    }
    assert f["a1_over_a0_computable"] == 2 and f["en_null"] == 1
    assert f["t0a_is_the_queried_token"] == 2 and f["distinct_tx_lgid"] == 2


def test_join_counts_report_per_pool_shapes_largest_pool_first():
    rows = [
        make_row(10, 1, "A", "sell", 100, 1, tx="0x1", v=100),
        make_row(10, 2, "A", "buy", 100, 1, tx="0x1", v=100),
        make_row(10, 3, "C", "buy", 10, 1, v=10),
        make_row(11, 1, "z", "buy", 10, 1, en="Uniswap v3 (Ethereum)"),
    ]
    v2, v3 = spike.join_counts(rows)
    assert v2["prints"] == 3 and v2["round_trips_A_A"] == 1 and v2["round_trip_wallets"] == ["A"]
    assert v2["round_trip_share_of_volume"] == round(200 / 210, 4) and v2["organic_prints"] == 1
    assert v2["blocks_with_2_or_more_prints"] == 1 and v3["prints"] == 1


def test_the_committed_spike_receipt_answers_the_question_it_was_asked():
    d = json.loads(PROOF.read_text())
    assert d["answer"]["pool_identity_recoverable"] is True
    assert d["answer"]["maker_join_possible"] is True
    assert d["answer"]["prints_scanned"] >= 1000 and d["answer"]["sandwiches_A_B_A"] == 0
    assert d["cors"]["allow_origin_present"] is False
    assert d["credits_used"] == 0 and all(c.get("status") == 200 for c in d["calls"] if c.get("ok"))
