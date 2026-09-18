"""The external side effect — the real keyless contract, asserted on a real response (R11).

    pytest -q -m live

Every test here would fail if CoinMarketCap changed the row shape, and none of them can be
satisfied with the network unplugged. A throttle is reported as a skip, not a failure: it is
a fact about this IP at this minute, not about the contract.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleman import cost, detect, enrich, tape  # noqa: E402

pytestmark = pytest.mark.live
PEPE = "0x6982508145454ce325ddbe47a25d4ec3d2311933"


@pytest.fixture(scope="module")
def page():
    for var in tape.KEY_VARS:
        assert not __import__("os").environ.get(var), f"{var} is set — the live test is keyless"
    rows, meta = tape.pull("ethereum", PEPE, pages=1, quiet=True)
    if meta["throttled"]:
        pytest.skip(f"anonymous tier throttled this IP: {meta['error']}")
    assert meta["error"] is None, meta["error"]
    assert rows, "a real page carries rows"
    return rows


def test_live_rows_carry_the_fields_the_join_rests_on(page):
    for r in page:
        for f in ("h", "lgid", "ma", "tp", "a0", "a1", "tx", "t0a", "t1a"):
            assert r.get(f) not in (None, ""), f"{f} missing on a live row"
        assert r["tp"] in ("buy", "sell")


def test_live_h_and_lgid_are_strings_that_parse_as_integers(page):
    for r in page:
        assert isinstance(r["h"], str) and isinstance(r["lgid"], str)
        assert int(r["h"]) > 0 and int(r["lgid"]) >= 0
    assert detect.unplaceable(page) == 0


def test_live_effective_price_is_computable_on_every_row_and_matches_q_where_q_is_precise(page):
    priced, agree = 0, 0
    for r in page:
        q = cost.price(r)
        if q is None:
            continue
        priced += 1
        if float(r.get("q") or 0) > 0 and abs(q - float(r["q"])) <= 1e-6 * float(r["q"]):
            agree += 1
    assert priced >= 0.95 * len(page)
    # v4 rows carry a rounded q (docs/proof/spike.json); v2/v3 rows agree to 6 s.f.
    assert agree >= 0.8 * priced


def test_live_t0a_is_the_queried_token_so_pools_can_be_recovered(page):
    assert all(r["t0a"].lower() == PEPE for r in page)
    assert len(detect.group(page)) >= 1


def test_live_hero_rule_returns_an_ethereum_address_from_cmcs_own_ranking():
    hero, receipt = enrich.hero_pair(quiet=True)
    if hero is None and receipt.get("throttled"):
        pytest.skip("throttled")
    assert hero["address"].startswith("0x") and len(hero["address"]) == 42
    assert hero["dex_slug"] == "uniswap-v2"


def test_live_token_pools_returns_addresses_with_liquidity():
    pools, receipt = enrich.token_pools("ethereum", PEPE, quiet=True)
    if pools is None and receipt.get("throttled"):
        pytest.skip("throttled")
    assert pools and pools[0]["addr"] and pools[0]["liq_usd"] > 0
