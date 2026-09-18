"""Shared row builders. Rows look exactly like /v1/dex/tokens/transactions rows: h, lgid and
ts are STRINGS, amounts are floats, and the pool is (en, t0a, t1a)."""

import pytest

TOKEN = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


def make_row(
    h, lgid, ma, tp, a0, a1, tx=None, en="Uniswap v2", t1a=WETH, t1s="WETH", ts=None, v=None
):
    return {
        "h": str(h),
        "lgid": str(lgid),
        "ma": ma,
        "tp": tp,
        "a0": float(a0),
        "a1": float(a1),
        "q": float(a1) / float(a0) if a0 else 0.0,
        "v": float(v if v is not None else a0),
        "tx": tx or f"0x{h}{lgid}{ma}",
        "en": en,
        "t0a": TOKEN,
        "t1a": t1a,
        "t0s": "TOKEN",
        "t1s": t1s,
        "ts": str(ts if ts is not None else int(h) * 12_000),
        "t0pu": 1.0,
    }


@pytest.fixture
def row():
    return make_row
