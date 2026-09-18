"""The four endpoints that label the row — every one keyless, none load-bearing for the join.

    hero_pair()    /v4/dex/spot-pairs/latest    the hero rule: #1 pair by 24h transactions
    token_pools()  /v1/dex/token/pools          pool address, venue, liqUsd per (en, t0a, t1a) group
    security()     /v1/dex/security/detail      extra.buyTax / extra.sellTax — the tax guard
    pair_quotes()  /v4/dex/pairs/quotes/latest  24h buy/sell counts — the window's share of a day
    platforms()    /v1/dex/platform/list        explorer URL templates for the tx links

Each returns (value, receipt). A failure is a None value and a receipt with the error — the
table still renders; the label is just blank. Context must never take down a run that
already has its number.

Slugs, verified live: the swap feed and token/pools take `platform=ethereum|bsc|solana`;
security/detail takes `platformName`; pairs/quotes/latest takes `network_slug=ethereum|solana`
but BSC only as `network_id=14`; spot-pairs/latest needs `dex_slug` and takes `network_id`.
"""

from . import tape

PLATFORMS = {
    "ethereum": {"id": 1, "network_slug": "ethereum"},
    "bsc": {"id": 14, "network_slug": None},  # network_slug=bsc is "not supported"
    "solana": {"id": 16, "network_slug": "solana"},
}
HERO_PARAMS = {
    "network_id": 1,
    "dex_slug": "uniswap-v2",
    "sort": "no_of_transactions_24h",
    "sort_dir": "desc",
    "limit": 1,
}
HERO_RULE = "the base token of the #1 Ethereum Uniswap v2 pair by 24h transactions at capture time"


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def hero_pair(quiet=False):
    """The token the hero rule picks right now, or None. (value, receipt)."""
    c = tape.get("/v4/dex/spot-pairs/latest", quiet=quiet, **HERO_PARAMS)
    if not c["ok"]:
        return None, tape.receipt(c)
    rows = c["body"].get("data") or []
    if not rows:
        return None, tape.receipt(c)
    top = rows[0]
    return {
        "name": top.get("name"),
        "symbol": top.get("base_asset_symbol"),
        "address": top.get("base_asset_contract_address"),
        "quote_symbol": top.get("quote_asset_symbol"),
        "pool": top.get("contract_address"),
        "dex_slug": top.get("dex_slug"),
        "rule": HERO_RULE,
        "rows_returned": len(rows),  # limit=1 is ignored — 100 come back (FEEDBACK.md)
    }, tape.receipt(c)


def token_pools(platform, address, quiet=False):
    """Every pool of the token: [{addr, venue, liq_usd, quote_symbol, quote_address, ...}]."""
    c = tape.get("/v1/dex/token/pools", quiet=quiet, platform=platform, address=address, size=50)
    if not c["ok"]:
        return None, tape.receipt(c)
    out = []
    for p in c["body"].get("data") or []:
        t0, t1 = p.get("t0") or {}, p.get("t1") or {}
        out.append(
            {
                "addr": p.get("addr"),
                "venue": p.get("exn"),
                "liq_usd": _f(p.get("liqUsd")),  # a STRING in the response
                "base_address": t0.get("addr"),
                "quote_symbol": t1.get("sym"),
                "quote_address": t1.get("addr"),
                "factory": p.get("fa"),
            }
        )
    return out, tape.receipt(c)


def label_pools(rows, pools, address):
    """Attach pool address, liquidity and merged-tier count to each table row in place.

    A row's key is (venue, base, quote); token/pools gives (exn, t0.addr, t1.addr) with the
    token on EITHER side (MOTO/USDC lists USDC as t0 — spike 2026-09-19), so the two contracts
    are matched as a set. Several pools can share one key — Uniswap v3 fee tiers of one pair —
    so the row carries the count and the sum of their liquidity, and the deepest one's address.
    """
    for r in rows:
        venue, base, quote = r["key"]
        want = {str(base or "").lower(), str(quote or "").lower()}
        matches = [
            p
            for p in pools or []
            if (p["venue"] or "unattributed") == venue
            and {str(p["base_address"] or "").lower(), str(p["quote_address"] or "").lower()}
            == want
        ]
        matches.sort(key=lambda p: -(p["liq_usd"] or 0.0))
        r["pools_merged"] = len(matches)
        r["addr"] = matches[0]["addr"] if matches else None
        r["liq_usd"] = round(sum(p["liq_usd"] or 0.0 for p in matches), 2) if matches else None
    return rows


def security(platform, address, quiet=False):
    """{"buy_tax", "sell_tax", "level"} from extra.buyTax / extra.sellTax (camelCase strings)."""
    c = tape.get("/v1/dex/security/detail", quiet=quiet, platformName=platform, address=address)
    if not c["ok"]:
        return None, tape.receipt(c)
    d = c["body"].get("data")
    d0 = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})
    extra = d0.get("extra") or {}
    return {
        "buy_tax": _f(extra.get("buyTax")),
        "sell_tax": _f(extra.get("sellTax")),
        "level": d0.get("securityLevel"),
    }, tape.receipt(c)


def pair_quotes(platform, pool_addr, quiet=False):
    """24h buy / sell counts and liquidity for one pool. The aux counts land on the ROW, not
    inside quote[0] like every other number (FEEDBACK.md)."""
    meta = PLATFORMS.get(platform)
    if not meta or not pool_addr:
        return None, {"ok": False, "error": f"no network mapping for platform {platform!r}"}
    net = (
        {"network_slug": meta["network_slug"]}
        if meta["network_slug"]
        else {"network_id": meta["id"]}
    )
    c = tape.get(
        "/v4/dex/pairs/quotes/latest",
        quiet=quiet,
        contract_address=pool_addr,
        aux="24h_no_of_buys,24h_no_of_sells,num_transactions_24h",
        **net,
    )
    if not c["ok"]:
        return None, tape.receipt(c)
    rows = c["body"].get("data") or []
    if not rows:
        return None, tape.receipt(c)
    row = rows[0]
    q = (row.get("quote") or [{}])[0]
    buys, sells = row.get("24h_no_of_buys"), row.get("24h_no_of_sells")
    return {
        "num_transactions_24h": row.get("num_transactions_24h"),
        "buys_24h": buys,
        "sells_24h": sells,
        "liquidity_usd": q.get("liquidity"),
        "volume_24h_usd": q.get("volume_24h"),
        "price_usd": q.get("price"),
    }, tape.receipt(c)


def platforms(quiet=False):
    """{platform id: {name, txuf, addr_url}} — the explorer templates."""
    c = tape.get("/v1/dex/platform/list", quiet=quiet)
    if not c["ok"]:
        return None, tape.receipt(c)
    out = {}
    for p in c["body"].get("data") or []:
        out[p.get("id")] = {"name": p.get("n"), "txuf": p.get("txuf"), "addr_url": p.get("addrUrl")}
    return out, tape.receipt(c)


def explorer_tx(platform, tx, table=None):
    """An explorer link for a transaction, from platform/list's `txuf` template."""
    meta = PLATFORMS.get(platform)
    if not meta or not tx:
        return None
    entry = (table or {}).get(meta["id"]) or {}
    tmpl = entry.get("txuf")
    return tmpl.replace("%s", str(tx)) if tmpl else None
