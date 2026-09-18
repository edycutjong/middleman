"""The price: what an organic print paid versus the print before it, per pool.

    q_i    = a1 / a0                    quote units per base unit — the print's effective price.
                                        Computed here, never read from `q`: on Uniswap v4 rows the
                                        feed's `q` is rounded to 2 s.f. or 0 (spike 2026-09-19).
    q2f_i  = q_i / q_{i-1} − 1  (buy)   adverse-signed basis points against the previous ORGANIC
             1 − q_i / q_{i-1}  (sell)  print in the same pool: positive = you paid more (or
                                        received less) than the print before you.
    pool row   = p50, p90 of q2f · round-trip share of volume · sandwiches · span · makers

The invariant this rests on: an AMM pool's price moves only when someone prints in it, so the
previous print IS the quote the next fill saw. It is a realised print-to-print move, not a
marginal impact curve — it includes the previous print's own footprint — and it is used
COMPARATIVELY, across pools of one token in one window, where that bias is shared.
"""

from . import detect

BPS = 10_000.0


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def price(row):
    """a1 / a0, or None when either amount is missing or a0 is not positive."""
    a0, a1 = _f(row.get("a0")), _f(row.get("a1"))
    if a0 is None or a1 is None or a0 <= 0:
        return None
    return a1 / a0


def quote_to_fill(rows):
    """Adverse-signed bps of every print against the print before it, for rows in chain order.

    Returns [{"idx", "bps", "tp", "q", "q_prev"}, ...] — one entry per print that has a priced
    predecessor. The first print of a pool has no quote to compare against and is skipped.
    """
    out, prev = [], None
    for idx, r in enumerate(rows):
        q = price(r)
        if q is None or q <= 0:
            continue
        if prev is not None and prev > 0:
            tp = detect.side(r)
            if tp == "buy":
                bps = (q / prev - 1.0) * BPS
            elif tp == "sell":
                bps = (1.0 - q / prev) * BPS
            else:
                prev = q
                continue
            out.append({"idx": idx, "bps": bps, "tp": tp, "q": q, "q_prev": prev})
        prev = q
    return out


def percentile(values, p):
    """Nearest-rank percentile — no interpolation, so a p90 is always a real observation."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(p / 100.0 * len(ordered) + 0.5))))
    return ordered[rank - 1]


def span_hours(rows):
    ts = [_f(r.get("ts")) for r in rows]
    ts = [t for t in ts if t is not None]
    if len(ts) < 2:
        return 0.0
    return (max(ts) - min(ts)) / 3_600_000.0


def _example(rows, rt, sw, organic_q2f, organic):
    """The block a judge re-derives by hand: the first round-trip or sandwich, with its whole
    block verbatim; or, when the pool has no middleman, the first two consecutive organic prints
    in one block with the bps between them."""
    if rt or sw:
        m = rt[0] if rt else sw[0]
        kind = "round-trip" if rt else "sandwich"
        h = detect._int(m["h"])
        block = [r for r in rows if detect._int(r.get("h")) == h]
        legs = m["legs"]
        a, b = legs
        qa, qb = price(a), price(b)
        a0a, a0b = _f(a.get("a0")), _f(b.get("a0"))
        delta = abs(a0b - a0a) / a0a if a0a else None
        lines = [
            f"leg 1  lgid {a.get('lgid')}  {a.get('ma')}  {detect.side(a)}  a1/a0 = "
            f"{_f(a.get('a1'))} / {a0a} = {qa}",
            f"leg 2  lgid {b.get('lgid')}  {b.get('ma')}  {detect.side(b)}  a1/a0 = "
            f"{_f(b.get('a1'))} / {a0b} = {qb}",
            f"same wallet · same block {m['h']}"
            + (" · same tx" if m.get("same_tx") else "")
            + (f" · |Δa0| / a0 = {delta:.4f} ≤ 0.05" if delta is not None else "")
            + f" → {kind}",
        ]
        if sw and not rt:
            lines.append(
                f"{len(m['victims'])} other maker(s) printed {detect.side(a)} between the legs"
            )
        return {
            "kind": kind,
            "h": m["h"],
            "rows": block,
            "highlight": [r.get("lgid") for r in legs],
            "victims": [r.get("lgid") for r in m.get("victims", [])],
            "arithmetic": lines,
        }
    for e in organic_q2f:
        r, i = organic[e["idx"]], e["idx"]
        p = organic[i - 1]
        if detect._int(r.get("h")) == detect._int(p.get("h")):
            return {
                "kind": "organic",
                "h": r.get("h"),
                "rows": [p, r],
                "highlight": [r.get("lgid")],
                "victims": [],
                "arithmetic": [
                    f"previous print  lgid {p.get('lgid')}  {detect.side(p)}  "
                    f"a1/a0 = {e['q_prev']}",
                    f"this print      lgid {r.get('lgid')}  {detect.side(r)}  a1/a0 = {e['q']}",
                    f"{'q/q_prev − 1' if e['tp'] == 'buy' else '1 − q/q_prev'} = "
                    f"{e['bps']:.1f} bps adverse",
                ],
            }
    return None


def pool_row(key, rows, rt, sw, organic):
    """Everything the table shows for one pool, from its ordered rows and the join's output."""
    vol = sum(_f(r.get("v")) or 0.0 for r in rows)
    rt_legs = [leg for m in rt for leg in m["legs"]]
    rt_vol = sum(_f(r.get("v")) or 0.0 for r in rt_legs)
    organic_q2f = quote_to_fill(organic)
    naive_q2f = quote_to_fill(rows)
    o_bps = [e["bps"] for e in organic_q2f]
    n_bps = [e["bps"] for e in naive_q2f]
    return {
        "key": list(key),
        "venue": key[0],
        "quote": (rows[0].get("t1s") if rows else None) or key[2],
        "n": len(rows),
        "n_organic": len(organic),
        "makers": len({r.get("ma") for r in rows}),
        "volume_usd": round(vol, 2),
        "span_hours": round(span_hours(rows), 2),
        "round_trips": {
            "pairs": len(rt),
            "wallets": detect.wallets(rt),
            "share_prints": round(len(rt_legs) / len(rows), 4) if rows else 0.0,
            "share_volume": round(rt_vol / vol, 4) if vol else 0.0,
            "same_tx_share": round(sum(1 for m in rt if m["same_tx"]) / len(rt), 4) if rt else None,
            "volume_usd": round(rt_vol, 2),
        },
        "sandwiches": {
            "count": len(sw),
            "wallets": detect.wallets(sw),
            "victims": sum(len(m["victims"]) for m in sw),
            "take_quote": round(sum(m["take_quote"] or 0.0 for m in sw), 8),
        },
        "q2f": {
            "n": len(o_bps),
            "p50_bps": round(percentile(o_bps, 50), 2) if o_bps else None,
            "p90_bps": round(percentile(o_bps, 90), 2) if o_bps else None,
        },
        "naive": {
            "n": len(n_bps),
            "p50_bps": round(percentile(n_bps, 50), 2) if n_bps else None,
            "p90_bps": round(percentile(n_bps, 90), 2) if n_bps else None,
        },
        "example": _example(rows, rt, sw, organic_q2f, organic),
    }
