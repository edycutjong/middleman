"""Middleman — who stands between your quote and your fill, per pool.

Six pure functions over CoinMarketCap's keyless per-swap feed:

    tape.pull        paginate /v1/dex/tokens/transactions, keyless, with receipts
    detect.order     sort prints by (int(h), int(lgid)) — both arrive as strings
    detect.group     recover pools from (en, t0a, t1a) — the feed carries no pool address
    detect.middlemen round-trips (A-A) and sandwiches (A-B-A) by joining on the maker, in one block
    cost.pool_row    what an organic print pays versus the print before it: p50 / p90 in bps
    recommend.route  the pool with the lowest organic p90, and that p90 as the slippage cap

Stdlib only. No key, no install, no network on anything but tape.pull and enrich.*.
"""

__version__ = "0.1.0"
