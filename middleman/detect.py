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

    round-trip  A-A    rows[i], rows[i+1]: same ma, same h, opposite tp, |Δa0| / a0 ≤ 5 %
                       — the same wallet selling and buying back the same size in one block
    sandwich    A-B-A  rows[i] … rows[k]: same ma at i and k, same h throughout, opposite tp at
                       i and k, |Δa0| / a0 ≤ 5 %, and every row between is ANOTHER maker
                       printing in rows[i]'s direction (1 ≤ victims ≤ 4)
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

    Scans left to right. A leg belongs to at most one match; victims are never consumed.
    Each match records the row positions so the receipt can quote the rows verbatim.
    """
    n = len(rows)
    consumed = set()
    round_trips, sandwiches = [], []
    i = 0
    while i < n - 1:
        if i in consumed:
            i += 1
            continue
        a = rows[i]
        # Round-trip: the very next print is the same wallet coming back.
        if i + 1 not in consumed and _legs_match(a, rows[i + 1], tol):
            b = rows[i + 1]
            round_trips.append(
                {
                    "i": i,
                    "k": i + 1,
                    "ma": a.get("ma"),
                    "h": a.get("h"),
                    "same_tx": a.get("tx") is not None and a.get("tx") == b.get("tx"),
                    "legs": [a, b],
                }
            )
            consumed.update((i, i + 1))
            i += 2
            continue
        # Sandwich: other makers print in A's direction, then A comes back the other way.
        k = i + 1
        victims = []
        while k < n and len(victims) < max_victims:
            r = rows[k]
            if k in consumed or _int(r.get("h")) != _int(a.get("h")):
                break
            if r.get("ma") == a.get("ma"):
                break  # A prints again — the return leg is checked below, at k
            if side(r) != side(a):
                break  # someone printed the other way — the pattern is broken
            victims.append(r)
            k += 1
        if victims and k < n and k not in consumed and _legs_match(a, rows[k], tol):
            b = rows[k]
            sandwiches.append(
                {
                    "i": i,
                    "k": k,
                    "ma": a.get("ma"),
                    "h": a.get("h"),
                    "victims": victims,
                    "legs": [a, b],
                    "take_quote": _take(a, b),
                }
            )
            consumed.update((i, k))
            i += 1
            continue
        i += 1
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
