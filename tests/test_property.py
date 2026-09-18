"""One property-based verification of the join, over its whole input space.

Coverage says the lines ran. This says that across PROPERTY_CASES generated blocks of prints,
`middlemen()` never once broke its own definition. The case count is published in README.md."""

import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import make_row  # noqa: E402

from middleman import cost, detect  # noqa: E402

PROPERTY_CASES = 1000  # keep in sync with README.md / DEMO.md

_print = st.tuples(
    st.integers(min_value=1, max_value=3),  # block — few values so blocks fill up
    st.sampled_from(["A", "B", "C", "D"]),  # maker — few values so wallets repeat
    st.sampled_from(["buy", "sell"]),
    st.floats(min_value=1.0, max_value=200.0, allow_nan=False),  # a0
    st.floats(min_value=0.001, max_value=10.0, allow_nan=False),  # a1
)


@settings(max_examples=PROPERTY_CASES, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.lists(_print, min_size=0, max_size=14))
def test_the_join_never_violates_its_own_definition(prints):
    rows = detect.order(
        [make_row(h, i, ma, tp, a0, a1) for i, (h, ma, tp, a0, a1) in enumerate(prints)]
    )
    rt, sw, organic = detect.middlemen(rows)
    legs = [leg for m in rt + sw for leg in m["legs"]]
    # 1. every print is either a leg or organic, and a leg belongs to exactly one match
    assert len(legs) + len(organic) == len(rows)
    assert len({id(r) for r in legs}) == len(legs)
    # 2. every match is what its name says
    for m in rt + sw:
        a, b = m["legs"]
        assert a["ma"] == b["ma"] and a["h"] == b["h"] and a["tp"] != b["tp"]
        assert abs(b["a0"] - a["a0"]) / a["a0"] <= detect.SIZE_TOL
    for m in rt:
        assert rows.index(m["legs"][1]) == rows.index(m["legs"][0]) + 1
    for m in sw:
        a = m["legs"][0]
        assert 1 <= len(m["victims"]) <= detect.MAX_VICTIMS
        for v in m["victims"]:
            assert v["ma"] != a["ma"] and v["tp"] == a["tp"] and v["h"] == a["h"]
            assert v in organic  # a victim's fill is real and stays in the sample
    # 3. the price side: one measurement per priced print with a predecessor, p90 >= p50
    q2f = cost.quote_to_fill(organic)
    assert len(q2f) <= max(len(organic) - 1, 0)
    bps = [e["bps"] for e in q2f]
    if bps:
        assert cost.percentile(bps, 90) >= cost.percentile(bps, 50)
        assert cost.percentile(bps, 90) in bps
    # 4. the row is internally consistent
    row = cost.pool_row(("v", "t", "q"), rows, rt, sw, organic)
    assert row["n"] == len(rows) and row["n_organic"] == len(organic)
    assert row["round_trips"]["pairs"] == len(rt) and row["sandwiches"]["count"] == len(sw)
    assert 0.0 <= row["round_trips"]["share_volume"] <= 1.0 + 1e-9
    assert 0.0 <= row["round_trips"]["share_prints"] <= 1.0 + 1e-9
