"""The join: order the prints, recover the pools, name the middleman.

Three pure functions over a list of swap rows as CoinMarketCap returns them:

    order(rows)      sort by (int(h), int(lgid)) — the position inside the chain, exactly.
                     Both fields arrive as STRINGS; sorted as text, "99" > "1000".
    group(rows)      {pool_key: ordered rows} where pool_key = (en or "unattributed", t0a, t1a).
                     The feed is per TOKEN and carries no pool address; the venue name and the
                     two contracts are what identify a pool. Uniswap v3 fee tiers of one pair
                     share a key and merge — stated on every surface, not hidden.
    middlemen(rows)  (round_trips, sandwiches, organic) for ONE pool's ordered rows.

The two shapes, in block order, joined on the maker address `ma`:

    round-trip  A-A    A's next print in the block is the other side of the same size:
                       |Δa0| / a0 ≤ 5 % — the same wallet buying back what it just sold,
                       usually inside one transaction, sometimes around other makers' prints
    sandwich    A-B-A  the same shape, but every print between the legs is ANOTHER maker in
                       leg 1's direction (1–4 of them) and A came out ahead (take > 0):
                       the prints between were front-run
    organic            every print that is neither leg of a match. Victims stay organic —
                       they are real fills, and what they paid is exactly the question.

A round-trip is a SHAPE, not a verdict: the function prints the rows and the definition and
never a label on a person. Nothing here touches the network.
"""

SIZE_TOL = 0.05  # the second leg's base amount within 5 % of the first
MAX_VICTIMS = 4  # rows a sandwich may hold between its two legs
UNATTRIBUTED = "unattributed"  # `en` is null on ~4 % of Ethereum rows (ex: true)


def _int(value):
    """int("26006311") -> 26006311; anything else -> None. The fields are strings."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sort_key(row):
    """(block, log index) as integers, or None when the row cannot be placed."""
    h, lgid = _int(row.get("h")), _int(row.get("lgid"))
    if h is None or lgid is None:
        return None
    return (h, lgid)


def order(rows):
    """Rows with a valid (h, lgid), in chain order. Rows that cannot be placed are dropped —
    see unplaceable() for the count, which every receipt states."""
    keyed = [(sort_key(r), r) for r in rows]
    return [r for k, r in sorted(((k, r) for k, r in keyed if k is not None), key=lambda kr: kr[0])]


def unplaceable(rows):
    """How many rows lack an integer h or lgid and were left out of the join."""
    return sum(1 for r in rows if sort_key(r) is None)


def pool_key(row):
    return (row.get("en") or UNATTRIBUTED, row.get("t0a"), row.get("t1a"))


def group(rows):
    """{pool_key: rows in chain order}. Insertion order follows the first print of each pool."""
    pools = {}
    for r in order(rows):
        pools.setdefault(pool_key(r), []).append(r)
    return pools


def side(row):
    return str(row.get("tp", "")).lower()


def size_match(a, b, tol=SIZE_TOL):
    """|a0_b − a0_a| / a0_a ≤ tol, with a0_a > 0. Base amounts, so a buy and a sell compare."""
    a0a, a0b = _float(a.get("a0")), _float(b.get("a0"))
    if a0a is None or a0b is None or a0a <= 0:
        return False
    return abs(a0b - a0a) / a0a <= tol


def _legs_match(a, b, tol):
    """Two rows that could be the two legs of one middleman: same wallet, same block,
    opposite sides, matched size."""
    return (
        a.get("ma") is not None
        and a.get("ma") == b.get("ma")
        and _int(a.get("h")) is not None
        and _int(a.get("h")) == _int(b.get("h"))
        and side(a) in ("buy", "sell")
        and side(b) in ("buy", "sell")
        and side(a) != side(b)
        and size_match(a, b, tol)
    )


def middlemen(rows, tol=SIZE_TOL, max_victims=MAX_VICTIMS):
    """(round_trips, sandwiches, organic) for one pool's rows, already in chain order.

    For each print by wallet A, look for A's NEXT print in the same block. If it is the other
    side and size-matched, A stood on both sides of the block, and the prints between the two
    legs decide which shape it is:

        sandwich    every print between is another maker in leg 1's direction, there are 1–4
                    of them, and A came out ahead (take > 0) — the victims were front-run
        round-trip  anything else: no print between (the classic same-tx wash), or prints
                    between that are mixed, or a return that extracted nothing. Two wallets
                    washing around each other (B sell · C sell · B buy · C buy — USDT/DGAI on
                    PancakeSwap v3, 2026-09-19) are two round-trips, not sandwiches.

    A leg belongs to at most one match; victims are never consumed. Each match records the
    row positions so the receipt can quote the rows verbatim.
    """
    n = len(rows)
    consumed = set()
    round_trips, sandwiches = [], []
    for i in range(n):
        if i in consumed:
            continue
        a = rows[i]
        if a.get("ma") is None or side(a) not in ("buy", "sell"):
            continue
        h = _int(a.get("h"))
        k, between = None, []
        for j in range(i + 1, n):
            r = rows[j]
            if _int(r.get("h")) != h:
                break
            if r.get("ma") == a.get("ma"):
                k = j
                break
            between.append(j)
        if k is None or k in consumed or not _legs_match(a, rows[k], tol):
            continue
        b = rows[k]
        take = _take(a, b)
        victims = [rows[j] for j in between]
        is_sandwich = (
            1 <= len(between) <= max_victims
            and all(j not in consumed and side(rows[j]) == side(a) for j in between)
            and take is not None
            and take > 0
        )
        if is_sandwich:
            sandwiches.append(
                {
                    "i": i,
                    "k": k,
                    "ma": a.get("ma"),
                    "h": a.get("h"),
                    "victims": victims,
                    "legs": [a, b],
                    "take_quote": take,
                }
            )
        else:
            round_trips.append(
                {
                    "i": i,
                    "k": k,
                    "ma": a.get("ma"),
                    "h": a.get("h"),
                    "same_tx": a.get("tx") is not None and a.get("tx") == b.get("tx"),
                    "between": len(between),
                    "take_quote": take,
                    "legs": [a, b],
                }
            )
        consumed.update((i, k))
    organic = [r for idx, r in enumerate(rows) if idx not in consumed]
    return round_trips, sandwiches, organic


def _take(first, second):
    """What the attacker's two legs netted in quote units: quote received minus quote paid.
    A-buy then A-sell: a1 of the sell minus a1 of the buy. Mirror for the sell-first case."""
    a1f, a1s = _float(first.get("a1")), _float(second.get("a1"))
    if a1f is None or a1s is None:
        return None
    return a1s - a1f if side(first) == "buy" else a1f - a1s


def wallets(matches):
    """Distinct makers behind a list of matches, first seen first."""
    seen, out = set(), []
    for m in matches:
        if m["ma"] not in seen:
            seen.add(m["ma"])
            out.append(m["ma"])
    return out
