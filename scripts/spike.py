#!/usr/bin/env python3
"""Day-1 spike — the open API question, answered with real calls, before any product code.

The question (project risk register, 2026-09-19): does the keyless per-swap feed carry
enough to (a) recover POOL identity from a per-token feed and (b) join the same wallet across
both sides of one block — and how often is the A-buy / B-buy / A-sell sandwich actually there?

    python3 scripts/spike.py                    # keyless, ~15 calls, writes docs/proof/spike.json
    python3 scripts/spike.py --pages 4          # a shorter tape

Everything it writes is a measurement of the live API at the moment it ran: every request
URL, HTTP status, UTC timestamp and the sha256 of the response body, then the field facts the
engine depends on and the counts the join produced. No fixture, no key.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from middleman import detect, tape  # noqa: E402

OUT = ROOT / "docs" / "proof" / "spike.json"
PEPE = ("PEPE", "0x6982508145454ce325ddbe47a25d4ec3d2311933")
REQUIRED = ("h", "lgid", "ma", "tp", "a0", "a1", "q", "v", "tx", "t0a", "t1a")


def field_facts(rows, address):
    """The contract the engine rests on, checked on every row of a real tape."""
    n = len(rows)
    missing = {f: sum(1 for r in rows if r.get(f) in (None, "")) for f in REQUIRED}
    strings = {f: sum(1 for r in rows if isinstance(r.get(f), str)) for f in ("h", "lgid", "ts")}
    q_ok, q_mismatch = 0, {}
    for r in rows:
        a0, a1, q = float(r.get("a0") or 0), float(r.get("a1") or 0), float(r.get("q") or 0)
        if a0 > 0 and q > 0 and abs(a1 / a0 - q) <= 1e-6 * q:
            q_ok += 1
        else:
            # Uniswap v4 rows carry q rounded to 2 s.f. or 0 — the engine divides a1/a0 itself
            venue = r.get("en") or "unattributed"
            q_mismatch[venue] = q_mismatch.get(venue, 0) + 1
    v_ok = sum(
        1
        for r in rows
        if r.get("t0pu")
        and abs(float(r["a0"]) * float(r["t0pu"]) - float(r["v"]))
        <= 1e-6 * max(float(r["v"]), 1e-12)
    )
    return {
        "rows": n,
        "missing_per_field": missing,
        "string_typed": strings,
        "q_equals_a1_over_a0_within_1e-6": q_ok,
        "q_mismatch_by_venue": q_mismatch,
        "a1_over_a0_computable": sum(1 for r in rows if float(r.get("a0") or 0) > 0),
        "v_equals_a0_times_t0pu_within_1e-6": v_ok,
        "t0a_is_the_queried_token": sum(
            1 for r in rows if str(r.get("t0a", "")).lower() == address.lower()
        ),
        "en_null": sum(1 for r in rows if not r.get("en")),
        "unplaceable_h_or_lgid": detect.unplaceable(rows),
        "distinct_tx": len({r.get("tx") for r in rows}),
        "distinct_lgid": len({r.get("lgid") for r in rows}),
        "distinct_tx_lgid": len({(r.get("tx"), r.get("lgid")) for r in rows}),
    }


def join_counts(rows):
    pools = detect.group(rows)
    out = []
    for key, prints in pools.items():
        rt, sw, organic = detect.middlemen(prints)
        blocks = {}
        for r in prints:
            blocks[r["h"]] = blocks.get(r["h"], 0) + 1
        vol = sum(float(r.get("v") or 0) for r in prints)
        rt_vol = sum(float(leg.get("v") or 0) for m in rt for leg in m["legs"])
        out.append(
            {
                "pool": list(key),
                "quote": prints[0].get("t1s"),
                "prints": len(prints),
                "blocks": len(blocks),
                "blocks_with_2_or_more_prints": sum(1 for c in blocks.values() if c >= 2),
                "makers": len({r.get("ma") for r in prints}),
                "sandwiches_A_B_A": len(sw),
                "round_trips_A_A": len(rt),
                "round_trip_wallets": detect.wallets(rt),
                "round_trip_share_of_volume": round(rt_vol / vol, 4) if vol else None,
                "organic_prints": len(organic),
            }
        )
    return sorted(out, key=lambda p: -p["prints"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    started = time.time()
    calls = []
    print("day-1 spike — keyless, live\n")

    # 1. the hero rule: CMC's own ranking of Ethereum Uniswap v2 pairs by 24h transactions
    c = tape.get(
        "/v4/dex/spot-pairs/latest",
        network_id=1,
        dex_slug="uniswap-v2",
        sort="no_of_transactions_24h",
        sort_dir="desc",
        limit=1,
    )
    calls.append(tape.receipt(c))
    if not c["ok"]:
        sys.exit(f"hero rule failed: {c['error']}")
    top = (c["body"].get("data") or [{}])[0]
    spot_rows = len(c["body"].get("data") or [])
    hero = (top.get("base_asset_symbol"), top.get("base_asset_contract_address"))
    print(f"hero rule  #1 Uniswap v2 pair by 24h tx: {top.get('name')}")
    print(f"           pool {top.get('contract_address')}")
    print(f"           rows returned for limit=1: {len(c['body'].get('data') or [])}")

    # 2. CORS: does the keyless surface send Access-Control-Allow-Origin? (it does not)
    import urllib.request

    req = urllib.request.Request(
        tape.BASE + "/v1/dex/platform/list",
        headers={"Accept": "application/json", "Origin": "https://example.org"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        cors = {k: v for k, v in resp.headers.items() if k.lower().startswith("access-control")}
        body = resp.read()
    import hashlib

    calls.append(
        {
            "ok": True,
            "url": req.full_url,
            "status": 200,
            "utc": tape._utc(),
            "sha256": hashlib.sha256(body).hexdigest(),
            "note": "sent with an Origin header to read the CORS response",
        }
    )
    platforms = json.loads(body).get("data") or []
    eth = next((p for p in platforms if p.get("id") == 1), {})
    allow_origin = "access-control-allow-origin" in {k.lower() for k in cors}
    print(f"CORS       allow-origin present: {allow_origin}  (sent: {sorted(cors)})")
    print(f"explorer   ethereum txuf: {eth.get('txuf')}")

    # 3. the tapes
    tapes = {}
    for sym, addr, pages in ((hero[0], hero[1], a.pages), (PEPE[0], PEPE[1], min(a.pages, 4))):
        print(f"\npulling {sym} {addr} — {pages} page(s)")
        rows, meta = tape.pull("ethereum", addr, pages=pages)
        calls += meta["calls"]
        print(
            f"  {len(rows)} prints in {meta['pages']} page(s), {meta['wall_s']} s"
            + (f" — {meta['error']}" if meta["error"] else "")
        )
        if not rows:
            continue
        facts = field_facts(rows, addr)
        pools = join_counts(rows)
        tapes[sym] = {
            "address": addr,
            "pages": meta["pages"],
            "throttled": meta["throttled"],
            "error": meta["error"],
            "fields": facts,
            "pools": pools,
        }
        print(
            f"  fields: h/lgid strings {facts['string_typed']}, q==a1/a0 on "
            f"{facts['q_equals_a1_over_a0_within_1e-6']}/{facts['rows']} "
            f"(mismatch {facts['q_mismatch_by_venue']}), en null {facts['en_null']}, "
            f"t0a==token {facts['t0a_is_the_queried_token']}/{facts['rows']}"
        )
        for p in pools[:6]:
            print(
                f"  {p['pool'][0]:<24} /{p['quote']:<5} prints {p['prints']:>4}  "
                f"blocks {p['blocks']:>4} (>=2: {p['blocks_with_2_or_more_prints']:>3})  "
                f"makers {p['makers']:>3}  sandwiches {p['sandwiches_A_B_A']}  "
                f"round-trips {p['round_trips_A_A']:>3}  rt vol {p['round_trip_share_of_volume']}"
            )

    # 4. enrichment for the hero: pools, tax, 24h counts
    enrich = {}
    c = tape.get("/v1/dex/token/pools", platform="ethereum", address=hero[1], size=20)
    calls.append(tape.receipt(c))
    if c["ok"]:
        pools = c["body"].get("data") or []
        enrich["token_pools"] = [
            {
                "addr": p.get("addr"),
                "exn": p.get("exn"),
                "liqUsd": p.get("liqUsd"),
                "t1": (p.get("t1") or {}).get("sym"),
            }
            for p in pools[:8]
        ]
        enrich["token_pools_liqUsd_is_string"] = isinstance(
            (pools[0] if pools else {}).get("liqUsd"), str
        )
    c = tape.get("/v1/dex/security/detail", platformName="ethereum", address=hero[1])
    calls.append(tape.receipt(c))
    if c["ok"]:
        d = c["body"].get("data")
        d0 = d[0] if isinstance(d, list) and d else (d or {})
        enrich["security"] = {"data_is_list": isinstance(d, list), "extra": d0.get("extra")}
    c = tape.get(
        "/v4/dex/pairs/quotes/latest",
        network_slug="ethereum",
        contract_address=top.get("contract_address"),
        aux="24h_no_of_buys,24h_no_of_sells,num_transactions_24h",
    )
    calls.append(tape.receipt(c))
    if c["ok"]:
        row = (c["body"].get("data") or [{}])[0]
        enrich["pair_quotes"] = {
            "row_level": {
                k: row.get(k) for k in ("num_transactions_24h", "24h_no_of_buys", "24h_no_of_sells")
            },
            "quote_level": {
                k: (row.get("quote") or [{}])[0].get(k)
                for k in ("24h_no_of_buys", "liquidity", "price")
            },
        }
    print(f"\nenrich     {json.dumps(enrich, default=str)[:400]}")

    hero_pools = tapes.get(hero[0], {}).get("pools", [])
    total_sw = sum(p["sandwiches_A_B_A"] for t in tapes.values() for p in t["pools"])
    total_rt = sum(p["round_trips_A_A"] for t in tapes.values() for p in t["pools"])
    total_prints = sum(t["fields"]["rows"] for t in tapes.values())
    answer = {
        "pool_identity_recoverable": all(
            p["pool"][1] and p["pool"][2] for t in tapes.values() for p in t["pools"]
        ),
        "maker_join_possible": all(
            t["fields"]["missing_per_field"]["ma"] == 0 for t in tapes.values()
        ),
        "prints_scanned": total_prints,
        "sandwiches_A_B_A": total_sw,
        "round_trips_A_A": total_rt,
        "hero_pool": hero_pools[0] if hero_pools else None,
    }
    payload = {
        "question": (
            "Does the keyless per-swap feed carry pool identity (en, t0a, t1a) and a maker "
            "address stable across a wallet's legs, so A-A and A-B-A can be joined inside one "
            "block — and how many sandwiches are there?"
        ),
        "answer": answer,
        "captured_utc": tape._utc(started),
        "wall_clock_s": round(time.time() - started, 1),
        "auth": "none — CoinMarketCap keyless /public-api surface",
        "credits_used": 0,
        "hero_rule": {
            "endpoint": "/v4/dex/spot-pairs/latest",
            "params": "network_id=1&dex_slug=uniswap-v2&sort=no_of_transactions_24h&sort_dir=desc",
            "picked": {
                "name": top.get("name"),
                "base": hero[1],
                "pool": top.get("contract_address"),
            },
            "rows_returned_for_limit_1": spot_rows,
        },
        "cors": {
            "headers_sent": cors,
            "allow_origin_present": "access-control-allow-origin" in {k.lower() for k in cors},
        },
        "explorer": {"ethereum_txuf": eth.get("txuf")},
        "tapes": tapes,
        "enrich": enrich,
        "calls": calls,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    print(f"\nanswer     {json.dumps(answer, default=str)}")
    print(f"wrote {a.out}  ({payload['wall_clock_s']} s, {len(calls)} calls, 0 credits — keyless)")


if __name__ == "__main__":
    main()
