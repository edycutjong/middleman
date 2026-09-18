"""The command line: one token in, one table and one line out. Live, keyless, no install.

    python3 scripts/middleman.py                         # the hero rule picks the token, live
    python3 scripts/middleman.py --address 0x… --symbol MOTO --pages 8 --json moto.json
    python3 scripts/middleman.py --watchlist             # the pinned tokens, --pages each
    python3 scripts/middleman.py --address … --platform bsc

Every number printed comes from the calls the run just made; `--json` writes the receipt —
URLs, statuses, hashes, the rows behind the example, the rule — in the shape docs/proof/ uses.
"""

import argparse
import json
import sys
import time

from . import __version__, cost, detect, enrich, recommend, tape

WATCHLIST = [
    ("SHIB", "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce", "ethereum"),
    ("PEPE", "0x6982508145454ce325ddbe47a25d4ec3d2311933", "ethereum"),
    ("UNI", "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", "ethereum"),
]
RULES = {
    "order": "sort prints by (int(h), int(lgid)) — both fields arrive as strings",
    "pool": "(en or 'unattributed', t0a, t1a) — no pool address on a row; v3 fee tiers merge",
    "round_trip": (
        f"adjacent prints, same ma, same h, opposite tp, |Δa0| / a0 ≤ {detect.SIZE_TOL:.0%}"
        " — the same wallet buying back what it just sold"
    ),
    "sandwich": (
        f"same ma at both legs, same h, opposite tp, |Δa0| / a0 ≤ {detect.SIZE_TOL:.0%}, "
        f"1–{detect.MAX_VICTIMS} other makers printing in leg 1's direction between them"
    ),
    "organic": "every print that is neither leg of a match; victims stay organic",
    "quote_to_fill": (
        "bps of a1/a0 against the previous organic print in the pool, adverse-signed: "
        "buy q/q_prev − 1, sell 1 − q/q_prev"
    ),
    "route": recommend.RULE,
    "cap": f"that p90 rounded up to the next {recommend.CAP_STEP_PCT} %",
}


def analyse(platform, address, symbol, pages=8, with_enrich=True, quiet=False):
    """Pull, order, group, join, price, decide. Returns the receipt dict (or one with 'error')."""
    started = time.time()
    prints, meta = tape.pull(platform, address, pages=pages, quiet=quiet)
    calls = list(meta["calls"])
    if not prints:
        return {
            "symbol": symbol,
            "address": address,
            "platform": platform,
            "error": meta["error"] or "no swaps returned",
            "throttled": meta["throttled"],
            "calls": calls,
            "wall_s": round(time.time() - started, 2),
        }
    pools = detect.group(prints)
    rows = []
    for key, ordered in pools.items():
        rt, sw, organic = detect.middlemen(ordered)
        rows.append(cost.pool_row(key, ordered, rt, sw, organic))
    rows.sort(key=lambda r: -r["n"])
    taxes, coverage = None, None
    if with_enrich:
        pool_list, c = enrich.token_pools(platform, address, quiet=quiet)
        calls.append(c)
        enrich.label_pools(rows, pool_list, address)
        taxes, c = enrich.security(platform, address, quiet=quiet)
        calls.append(c)
    for r in rows:
        r["buy_tax"] = taxes["buy_tax"] if taxes else None
        r["sell_tax"] = taxes["sell_tax"] if taxes else None
        r.setdefault("pools_merged", None)
        r.setdefault("addr", None)
        r.setdefault("liq_usd", None)
    decision = recommend.route(rows)
    if with_enrich and decision["pool"]:
        routed = next(r for r in rows if r["key"] == decision["pool"])
        if routed.get("addr"):
            coverage, c = enrich.pair_quotes(platform, routed["addr"], quiet=quiet)
            calls.append(c)
            if coverage and coverage.get("num_transactions_24h"):
                coverage["window_share_of_24h"] = round(
                    routed["n"] / float(coverage["num_transactions_24h"]), 4
                )
    ordered_all = detect.order(prints)
    return {
        "symbol": symbol,
        "address": address,
        "platform": platform,
        "captured_utc": tape._utc(started),
        "wall_s": round(time.time() - started, 2),
        "auth": (
            f"X-CMC_PRO_API_KEY from ${tape.api_key_var()} — keyed escape hatch, not the default"
            if meta["keyed"]
            else "none — CoinMarketCap keyless /public-api surface"
        ),
        "credits_used": meta["credits"] if meta["keyed"] else 0,
        "source": f"{tape.active_base()}{tape.SWAPS}",
        "window": {
            "prints": len(prints),
            "pages": meta["pages"],
            "pages_requested": pages,
            "partial": bool(meta["error"]),
            "throttled": meta["throttled"],
            "error": meta["error"],
            "span_hours": round(cost.span_hours(prints), 2),
            "first_block": ordered_all[0].get("h") if ordered_all else None,
            "last_block": ordered_all[-1].get("h") if ordered_all else None,
            "unplaceable": detect.unplaceable(prints),
        },
        "rules": RULES,
        "pools": rows,
        "taxes": taxes,
        "coverage": coverage,
        "decision": decision,
        "calls": calls,
        "engine": f"middleman {__version__}",
    }


def _short(addr, n=10):
    a = str(addr or "")
    return a[:n] + "…" if len(a) > n else a


def _usd(v):
    if v is None:
        return "—"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}k"
    return f"${v:.0f}"


def _bps(v):
    return "—" if v is None else f"{v:.1f}"


def hero_line(result):
    """The one sentence the run is for: the largest middleman share, or the widest pool spread."""
    rows = result["pools"]
    with_rt = [r for r in rows if r["round_trips"]["pairs"]]
    if with_rt:
        top = max(with_rt, key=lambda r: r["round_trips"]["share_volume"])
        rt = top["round_trips"]
        return (
            f"{rt['share_volume']:.1%} of {top['venue']} / {top['quote']} volume is "
            f"{len(rt['wallets'])} wallet(s) buying back what they just sold "
            f"({rt['pairs']} round-trips"
            + (", same transaction" if (rt["same_tx_share"] or 0) >= 0.5 else "")
            + ")"
        )
    with_sw = [r for r in rows if r["sandwiches"]["count"]]
    if with_sw:
        top = max(with_sw, key=lambda r: r["sandwiches"]["count"])
        return (
            f"{top['sandwiches']['count']} sandwich(es) in {top['venue']} / {top['quote']} — "
            f"{top['sandwiches']['victims']} victim print(s)"
        )
    priced = [r for r in rows if r["q2f"]["p50_bps"] is not None and r["n_organic"] >= 10]
    if len(priced) >= 2:
        lo = min(priced, key=lambda r: r["q2f"]["p50_bps"])
        hi = max(priced, key=lambda r: r["q2f"]["p50_bps"])
        if lo["q2f"]["p50_bps"] and lo["q2f"]["p50_bps"] > 0:
            ratio = hi["q2f"]["p50_bps"] / lo["q2f"]["p50_bps"]
            return (
                f"no middleman found — but a fill pays {ratio:.1f}× more in "
                f"{hi['venue']} / {hi['quote']} ({_bps(hi['q2f']['p50_bps'])} bps) than in "
                f"{lo['venue']} / {lo['quote']} ({_bps(lo['q2f']['p50_bps'])} bps)"
            )
    return "no middleman found in this window — drop the paranoid cap"


def render(result, out=None):
    """The table and the line, for humans. Every value is in the receipt too."""
    out = out or sys.stdout  # resolved at call time, so a captured stdout is honoured
    w = result["window"]
    print(
        f"{result['symbol']} · {result['platform']} · {w['prints']} prints · "
        f"{w['span_hours']} h · blocks {w['first_block']}–{w['last_block']} · "
        f"captured {result['captured_utc']} · "
        f"{'keyed' if 'keyed' in result['auth'] else 'keyless'}",
        file=out,
    )
    if w["partial"]:
        print(
            f"  note: {w['pages']} of {w['pages_requested']} page(s) landed — "
            f"{'throttled' if w['throttled'] else 'the fetch stopped early'} "
            f"({w['error']}). This is that shorter window.",
            file=out,
        )
    print(f"\n  {hero_line(result)}\n", file=out)
    print(
        f"  {'pool':<28}{'prints':>7}{'organic':>8}  {'round-trips':<26}{'sandw':>6}"
        f"  {'q→fill p50 / p90':<18}{'tax':>6}{'liq':>8}",
        file=out,
    )
    print("  " + "-" * 112, file=out)
    routed = result["decision"]["pool"]
    for r in result["pools"]:
        rt = r["round_trips"]
        rt_txt = (
            f"{rt['pairs']} · {len(rt['wallets'])} wallet(s) · {rt['share_volume']:.1%}"
            if rt["pairs"]
            else "—"
        )
        tax = (
            f"{r['buy_tax']:.0f}/{r['sell_tax']:.0f}"
            if r.get("buy_tax") is not None and r.get("sell_tax") is not None
            else "—"
        )
        name = f"{r['venue']} / {r['quote']}"
        if r.get("pools_merged") and r["pools_merged"] > 1:
            name += f" ×{r['pools_merged']}"
        mark = "  ◀ route" if r["key"] == routed else ""
        q2f = f"{_bps(r['q2f']['p50_bps'])} / {_bps(r['q2f']['p90_bps'])} bps"
        print(
            f"  {name[:27]:<28}{r['n']:>7}{r['n_organic']:>8}  {rt_txt:<26}"
            f"{r['sandwiches']['count']:>6}  {q2f:<18}{tax:>6}{_usd(r.get('liq_usd')):>8}{mark}",
            file=out,
        )
    d = result["decision"]
    if d["pool"]:
        print(
            f"\n  ▶ route via {d['venue']} / {d['quote']} · cap slippage at {d['cap_pct']:.2f} %"
            f"   (organic p90 {_bps(d['p90_bps'])} bps, {d['candidates']} candidate pool(s))",
            file=out,
        )
    else:
        print(f"\n  ▶ no route — {d['why']}", file=out)
    print(f"    rule: {recommend.RULE}", file=out)
    cov = result.get("coverage")
    if cov and cov.get("num_transactions_24h"):
        print(
            f"    coverage: this window is {cov['window_share_of_24h']:.0%} of the routed pool's "
            f"24h transactions ({cov['num_transactions_24h']}: {cov['buys_24h']} buys / "
            f"{cov['sells_24h']} sells)",
            file=out,
        )
    ex = next((r["example"] for r in result["pools"] if r["key"] == routed), None) or next(
        (r["example"] for r in result["pools"] if r["example"]), None
    )
    if ex:
        legs = set(ex["highlight"])
        victims = set(ex.get("victims") or [])
        print(f"\n  block {ex['h']} — raw rows ({ex['kind']})", file=out)
        for r in ex["rows"][:12]:
            lg = r.get("lgid")
            tag = "  ◀ leg" if lg in legs else ("  ◀ victim" if lg in victims else "")
            a0, a1 = cost._f(r.get("a0")), cost._f(r.get("a1"))
            q = cost.price(r)
            print(
                f"    lgid {str(lg):>5}  {_short(r.get('ma'), 12):<14} {detect.side(r):<4} "
                f"a0 {a0:>18,.4f}  a1 {a1:>14.6f}  a1/a0 {q:.4e}{tag}",
                file=out,
            )
        for line in ex["arithmetic"]:
            print(f"    {line}", file=out)
    print(file=out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="who stands between your quote and your fill")
    ap.add_argument("--address", help="token contract; default: the hero rule picks it live")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--platform", default="ethereum", choices=sorted(enrich.PLATFORMS))
    ap.add_argument(
        "--pages", type=int, default=None, help="100 prints each (default 8; 3 for --watchlist)"
    )
    ap.add_argument("--watchlist", action="store_true", help="run the pinned tokens instead")
    ap.add_argument(
        "--no-enrich", action="store_true", help="skip token/pools, security, pair quotes"
    )
    ap.add_argument("--json", metavar="PATH", help="write the receipt here")
    a = ap.parse_args(argv)

    started = time.time()
    var = tape.api_key_var()
    mode = f"keyed via ${var} (escape hatch — the default is keyless)" if var else "keyless"
    print(f"middleman {__version__} — {mode}, live\n")

    targets, hero, hero_call = [], None, None
    if a.address:
        targets = [(a.symbol or "TOKEN", a.address, a.platform)]
    elif a.watchlist:
        targets = WATCHLIST
    else:
        hero, hero_call = enrich.hero_pair()
        if not hero:
            print(tape.throttle_advice(hero_call.get("error")), file=sys.stderr)
            sys.exit(75 if hero_call.get("throttled") else 1)
        print(f"hero rule: {enrich.HERO_RULE}\n  → {hero['name']}  {hero['address']}\n")
        targets = [(hero["symbol"], hero["address"], "ethereum")]
    pages = a.pages or (3 if a.watchlist else 8)

    results, errors = [], []
    for sym, addr, platform in targets:
        r = analyse(platform, addr, sym, pages=pages, with_enrich=not a.no_enrich)
        if "error" in r and "pools" not in r:
            errors.append(r)
            print(f"{sym} · {platform} — API error: {r['error']}\n")
            continue
        results.append(r)
        render(r)

    elapsed = time.time() - started
    if not results:
        if errors and all(e.get("throttled") for e in errors):
            print(tape.throttle_advice(errors[0]["error"]), file=sys.stderr)
            sys.exit(75)  # EX_TEMPFAIL: a rate limit is a fact about this IP at this minute
        sys.exit(f"no token produced a table — first error: {errors[0]['error']}")

    if len(results) > 1:
        prints = sum(r["window"]["prints"] for r in results)
        sw = sum(p["sandwiches"]["count"] for r in results for p in r["pools"])
        rtw = {w for r in results for p in r["pools"] for w in p["round_trips"]["wallets"]}
        print(
            f"census · {len(results)} tokens · {prints} prints · {sw} sandwiches · "
            f"{len(rtw)} round-trip wallet(s)\n"
        )

    if a.json:
        payload = {
            "captured_utc": tape._utc(started),
            "wall_clock_s": round(elapsed, 2),
            "hero_rule": hero,
            "hero_call": hero_call,
            "results": results,
            "errors": errors,
            "credits_used": sum(r["credits_used"] for r in results),
        }
        with open(a.json, "w") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, default=str)
        credits = payload["credits_used"]
        cost_txt = f"{credits} credits — keyed via ${var}" if var else "0 credits — keyless"
        print(f"wrote {a.json}  ({elapsed:.1f}s wall clock, {cost_txt})")
