#!/usr/bin/env python3
"""Capture the tapes and the receipts the page is rendered from — by a published rule.

    python3 scripts/seed.py                 # every token below, 8 pages each, keyless
    python3 scripts/seed.py --only MOTO     # one token (the hero is re-picked by rule first)
    python3 scripts/seed.py --pages 4

WHAT THIS IS: a recording of real prints, fetched live, written with their provenance —
every request URL, HTTP status, UTC timestamp and body hash — plus the numbers the engine
derived from them at capture time. `data/tape_<sym>.json` holds the rows verbatim;
`docs/proof/<sym>.json` holds the receipt; `docs/proof/census.json` the strip across all of
them. `scripts/verify_tape.py` re-derives every receipt from its tape with the network
unplugged and fails on any drift, so a judge can check the page against the rows.

WHAT THIS IS NOT: the demo path. `scripts/middleman.py` always fetches live and reads none
of these files. Pointing the demo at a tape is the exact substitution that sinks submissions.

THE HERO IS A RULE, NOT A PICK: on each chain the token measured first is the base of the
pair CoinMarketCap itself ranks #1 by 24h transactions on that chain's flagship v2-style
venue (Uniswap v2 · PancakeSwap v2 · Raydium). Whatever that pair is on capture day is
what the page shows. The pinned Ethereum watchlist follows, so the census has breadth.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from middleman import cli, enrich, tape  # noqa: E402

DATA = ROOT / "data"
PROOF = ROOT / "docs" / "proof"

HERO_RULES = [
    ("ethereum", {"network_id": 1, "dex_slug": "uniswap-v2"}),
    ("bsc", {"network_id": 14, "dex_slug": "pancakeswap-v2"}),
    ("solana", {"network_slug": "solana", "dex_slug": "raydium"}),
]
WATCHLIST = [
    ("SHIB", "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce", "ethereum"),
    ("PEPE", "0x6982508145454ce325ddbe47a25d4ec3d2311933", "ethereum"),
    ("UNI", "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", "ethereum"),
    ("LINK", "0x514910771af9ca656af840dff83e8264ecf986ca", "ethereum"),
    ("AAVE", "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9", "ethereum"),
    ("Mog", "0xaaee1a9723aadb7afa2810263653a34ba2c21c7a", "ethereum"),
    ("SPX", "0xe0f63a424a4439cbe457d80e4f4b51ad25b2c56c", "ethereum"),
]
SPREAD_MIN_ORGANIC = 50  # a pool enters the sibling-spread comparison at the routing floor
# The spread is a routing decision between one token's pools. A stablecoin's feed (the BSC and
# Solana heroes are USDT and USDC on capture day) spans every pool on the chain, where
# "sibling" stops meaning anything — so the widest-spread line is taken over Ethereum only.
SPREAD_PLATFORM = "ethereum"


def slug(symbol, platform):
    s = "".join(ch for ch in symbol.lower() if ch.isalnum()) or "token"
    return s if platform == "ethereum" else f"{s}-{platform}"


def pick_hero(platform, params, quiet=False):
    """The hero rule on one chain: the base token of the #1 pair by 24h transactions."""
    c = tape.get(
        "/v4/dex/spot-pairs/latest",
        quiet=quiet,
        sort="no_of_transactions_24h",
        sort_dir="desc",
        limit=1,
        **params,
    )
    if not c["ok"]:
        return None, tape.receipt(c)
    rows = c["body"].get("data") or []
    if not rows:
        return None, tape.receipt(c)
    top = rows[0]
    return {
        "platform": platform,
        "symbol": top.get("base_asset_symbol"),
        "address": top.get("base_asset_contract_address"),
        "pair": top.get("name"),
        "pool": top.get("contract_address"),
        "dex_slug": top.get("dex_slug"),
        "rule": (
            f"the base token of the #1 {params['dex_slug']} pair on {platform} by "
            "24h transactions at capture time"
        ),
    }, tape.receipt(c)


def capture(symbol, address, platform, pages, quiet=False):
    """One token: pull live, compute, freeze the tape and the receipt. Returns the receipt."""
    prints, meta = tape.pull(platform, address, pages=pages, quiet=quiet)
    if not prints:
        return {"symbol": symbol, "platform": platform, "address": address, "error": meta["error"]}
    result = cli.compute(prints, meta, platform, address, symbol, pages, with_enrich=True)
    name = slug(symbol, platform)
    DATA.mkdir(parents=True, exist_ok=True)
    PROOF.mkdir(parents=True, exist_ok=True)
    (DATA / f"tape_{name}.json").write_text(
        json.dumps(
            {
                "_note": (
                    "A RECORDING, not the demo path. scripts/middleman.py always fetches live. "
                    "verify_tape.py re-derives docs/proof/<sym>.json from these rows offline."
                ),
                "symbol": symbol,
                "platform": platform,
                "address": address,
                "captured_utc": meta["captured_utc"],
                "source": f"{tape.active_base()}{tape.SWAPS}",
                "pages": meta["pages"],
                "page_sha256": [c["sha256"] for c in meta["calls"] if c["ok"]],
                "swap_count": len(prints),
                "swaps": prints,
            },
            indent=1,
            sort_keys=True,
        )
    )
    result["tape"] = f"data/tape_{name}.json"
    (PROOF / f"{name}.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    return result


def census(results, heroes):
    """The strip: tokens · prints · sandwiches · round-trip wallets · the widest sibling spread."""
    ok = [r for r in results if "pools" in r]
    rt_wallets, spreads = set(), []
    for r in ok:
        for p in r["pools"]:
            rt_wallets.update(p["round_trips"]["wallets"])
        if r["platform"] != SPREAD_PLATFORM:
            continue
        priced = [
            p
            for p in r["pools"]
            if p["n_organic"] >= SPREAD_MIN_ORGANIC and (p["q2f"]["p50_bps"] or 0) > 0
        ]
        if len(priced) >= 2:
            lo = min(priced, key=lambda p: p["q2f"]["p50_bps"])
            hi = max(priced, key=lambda p: p["q2f"]["p50_bps"])
            spreads.append(
                {
                    "symbol": r["symbol"],
                    "platform": r["platform"],
                    "ratio": round(hi["q2f"]["p50_bps"] / lo["q2f"]["p50_bps"], 2),
                    "low": {
                        "pool": f"{lo['venue']} / {lo['quote']}",
                        "p50_bps": lo["q2f"]["p50_bps"],
                    },
                    "high": {
                        "pool": f"{hi['venue']} / {hi['quote']}",
                        "p50_bps": hi["q2f"]["p50_bps"],
                    },
                }
            )
    eth_hero = next((h for h in heroes if h and h["platform"] == "ethereum"), None)
    hero_result = next((r for r in ok if eth_hero and r["address"] == eth_hero["address"]), None)
    hero_pool = None
    fired = "none"
    if hero_result:
        with_rt = [p for p in hero_result["pools"] if p["round_trips"]["pairs"]]
        if with_rt:
            hero_pool = max(with_rt, key=lambda p: p["round_trips"]["share_volume"])
            fired = "round-trip share"
    widest = max(spreads, key=lambda s: s["ratio"]) if spreads else None
    if fired == "none" and widest:
        fired = "sibling-pool spread"
    return {
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tokens": len(ok),
        "prints": sum(r["window"]["prints"] for r in ok),
        "pools": sum(len(r["pools"]) for r in ok),
        "sandwiches": sum(p["sandwiches"]["count"] for r in ok for p in r["pools"]),
        "round_trip_pairs": sum(p["round_trips"]["pairs"] for r in ok for p in r["pools"]),
        "round_trip_wallets": sorted(rt_wallets),
        "widest_spread": widest,
        "spread_scope": (
            f"{SPREAD_PLATFORM} tokens, pools with ≥ {SPREAD_MIN_ORGANIC} organic prints"
        ),
        "spreads": sorted(spreads, key=lambda s: -s["ratio"]),
        "hero": {
            "rule": eth_hero["rule"] if eth_hero else None,
            "symbol": eth_hero["symbol"] if eth_hero else None,
            "address": eth_hero["address"] if eth_hero else None,
            "pair": eth_hero["pair"] if eth_hero else None,
            "fired": fired,
            "pool": (
                {
                    "venue": hero_pool["venue"],
                    "quote": hero_pool["quote"],
                    "share_volume": hero_pool["round_trips"]["share_volume"],
                    "pairs": hero_pool["round_trips"]["pairs"],
                    "wallets": hero_pool["round_trips"]["wallets"],
                }
                if hero_pool
                else None
            ),
        },
        "heroes": [h for h in heroes if h],
        "rows": [
            {
                "symbol": r["symbol"],
                "platform": r["platform"],
                "file": f"docs/proof/{slug(r['symbol'], r['platform'])}.json",
                "prints": r["window"]["prints"],
                "span_hours": r["window"]["span_hours"],
                "pools": len(r["pools"]),
                "sandwiches": sum(p["sandwiches"]["count"] for p in r["pools"]),
                "round_trips": sum(p["round_trips"]["pairs"] for p in r["pools"]),
                "route": (
                    f"{r['decision']['venue']} / {r['decision']['quote']}"
                    if r["decision"]["pool"]
                    else None
                ),
                "cap_pct": r["decision"]["cap_pct"],
            }
            for r in ok
        ],
        "errors": [
            {"symbol": r["symbol"], "platform": r["platform"], "error": r["error"]}
            for r in results
            if "pools" not in r
        ],
    }


def rebuild_census():
    """The strip from the receipts already on disk — the heroes are read back from the old strip."""
    old = (
        json.loads((PROOF / "census.json").read_text()) if (PROOF / "census.json").exists() else {}
    )
    heroes = old.get("heroes") or []
    results = []
    for row in old.get("rows") or []:
        path = ROOT / row["file"]
        if path.exists():
            results.append(json.loads(path.read_text()))
    if not results:
        sys.exit("no receipts to rebuild from — run: python3 scripts/seed.py")
    strip = census(results, heroes)
    strip["captured_utc"] = old.get("captured_utc", strip["captured_utc"])
    (PROOF / "census.json").write_text(json.dumps(strip, indent=1, sort_keys=True, default=str))
    print(f"rebuilt docs/proof/census.json from {len(results)} receipt(s), no network")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--only", help="capture just this symbol (the hero rule still runs first)")
    ap.add_argument("--no-heroes", action="store_true", help="skip the hero rules, watchlist only")
    ap.add_argument(
        "--census-only",
        action="store_true",
        help="rebuild docs/proof/census.json from the committed receipts, no network",
    )
    a = ap.parse_args(argv)
    if a.census_only:
        return rebuild_census()
    if tape.api_key():
        sys.exit("a CMC key is exported — the receipts are keyless by definition; unset it")

    started = time.time()
    print(f"seed — keyless, {a.pages} page(s) x {tape.PAGE} prints per token\n")

    table, c = enrich.platforms()
    if table:
        PROOF.mkdir(parents=True, exist_ok=True)
        (PROOF / "platforms.json").write_text(
            json.dumps(
                {
                    "captured_utc": c["utc"],
                    "source": c["url"],
                    "sha256": c["sha256"],
                    "platforms": {
                        name: table[meta["id"]]
                        for name, meta in enrich.PLATFORMS.items()
                        if meta["id"] in table
                    },
                },
                indent=1,
                sort_keys=True,
            )
        )

    heroes, targets = [], []
    if not a.no_heroes:
        for platform, params in HERO_RULES:
            hero, receipt = pick_hero(platform, params)
            heroes.append(hero)
            if hero:
                print(f"hero rule · {platform:<9} {hero['pair']:<14} {hero['address']}")
                targets.append((hero["symbol"], hero["address"], platform))
            else:
                print(f"hero rule · {platform:<9} failed: {receipt.get('error')}")
    targets += [t for t in WATCHLIST if not any(t[1] == x[1] for x in targets)]
    if a.only:
        targets = [t for t in targets if t[0].lower() == a.only.lower()]

    results = []
    for sym, addr, platform in targets:
        print(f"\n{sym} · {platform}")
        r = capture(sym, addr, platform, a.pages)
        results.append(r)
        if "pools" not in r:
            print(f"  failed: {r['error']}")
            continue
        top, d = r["pools"][0], r["decision"]
        route = f"route {d['venue']} / {d['quote']} cap {d['cap_pct']}" if d["pool"] else "no route"
        print(
            f"  {r['window']['prints']} prints · {len(r['pools'])} pools · "
            f"{sum(p['sandwiches']['count'] for p in r['pools'])} sandwiches · "
            f"{sum(p['round_trips']['pairs'] for p in r['pools'])} round-trips · "
            f"top pool {top['venue']} / {top['quote']} p50 {top['q2f']['p50_bps']} bps · {route}"
        )

    strip = census(results, heroes)
    (PROOF / "census.json").write_text(json.dumps(strip, indent=1, sort_keys=True, default=str))
    print(
        f"\ncensus · {strip['tokens']} tokens · {strip['prints']} prints · "
        f"{strip['sandwiches']} sandwiches · {strip['round_trip_pairs']} round-trips by "
        f"{len(strip['round_trip_wallets'])} wallet(s)"
    )
    if strip["widest_spread"]:
        w = strip["widest_spread"]
        print(
            f"widest sibling spread · {w['symbol']} {w['ratio']}× "
            f"({w['low']['pool']} {w['low']['p50_bps']} bps vs "
            f"{w['high']['pool']} {w['high']['p50_bps']} bps)"
        )
    print(f"hero · {strip['hero']['symbol']} · fired: {strip['hero']['fired']}")
    print(f"\nwrote {len(results)} tape(s) + receipts, {time.time() - started:.0f} s, 0 credits")


if __name__ == "__main__":
    main()
