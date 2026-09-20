#!/usr/bin/env python3
"""Reproducible benchmark: how long does naming the middleman actually take?

Two things are timed separately, because they have different characters:

    fetch    one keyless page of /v1/dex/tokens/transactions (network-bound, variable)
    detect   order → group → join → price → route over a whole tape (CPU-bound, deterministic)

Reporting them together would hide the only interesting fact: the product's own work is
milliseconds, and every second a judge waits is network — or the anonymous tier's backoff.

    python3 scripts/bench.py                       # live fetch + detect, 8 iterations
    python3 scripts/bench.py --replay              # detect only, over the committed hero tape
    python3 scripts/bench.py --replay --json docs/proof/bench_replay.json

--replay needs no network and is deterministic, which makes it right for CI. It is NOT the
product: it measures the engine over a captured tape. The live path is the judged one.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from middleman import cli, cost, tape  # noqa: E402

DATA = ROOT / "data"
PEPE = "0x6982508145454ce325ddbe47a25d4ec3d2311933"


def report(label, samples, unit="ms"):
    print(
        f"  {label:22} n={len(samples):<4} "
        f"p50 {cost.percentile(samples, 50):9.3f}{unit}   "
        f"p95 {cost.percentile(samples, 95):9.3f}{unit}   "
        f"max {max(samples):9.3f}{unit}"
    )
    return {
        "n": len(samples),
        "p50": round(cost.percentile(samples, 50), 4),
        "p95": round(cost.percentile(samples, 95), 4),
        "max": round(max(samples), 4),
        "unit": unit,
    }


def hero_tape():
    """The tape the census names as the hero, or the largest tape on disk."""
    census = ROOT / "docs" / "proof" / "census.json"
    if census.exists():
        sym = (json.loads(census.read_text()).get("hero") or {}).get("symbol")
        if sym:
            cand = DATA / f"tape_{''.join(c for c in sym.lower() if c.isalnum())}.json"
            if cand.exists():
                return cand
    tapes = sorted(DATA.glob("tape_*.json"), key=lambda p: p.stat().st_size, reverse=True)
    return tapes[0] if tapes else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=None)
    ap.add_argument("--replay", action="store_true", help="detect only, over the committed tape")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args(argv)
    iterations = a.iterations or (200 if a.replay else 8)
    out = {"iterations": iterations, "mode": "replay" if a.replay else "live"}

    if a.replay:
        path = hero_tape()
        if not path:
            sys.exit(f"no tape under {DATA} — run: python3 scripts/seed.py")
        t = json.loads(path.read_text())
        swaps = t["swaps"]
        print(f"replay — {len(swaps)} prints of {t['symbol']}, captured {t['captured_utc']}")
        print("no network\n")
        detect_ms = []
        meta = {"pages": t["pages"], "calls": [], "captured_utc": t["captured_utc"]}
        for _ in range(iterations):
            t0 = time.perf_counter()
            cli.compute(swaps, meta, t["platform"], t["address"], t["symbol"], with_enrich=False)
            detect_ms.append((time.perf_counter() - t0) * 1000)
        out["detect"] = report("detect (engine)", detect_ms)
        out["prints"] = len(swaps)
        out["tape"] = str(path.relative_to(ROOT))
        cost_txt = "no network"
    else:
        var = tape.escape_hatch_var()
        surface = f"keyed fetch via ${var} (escape hatch)" if var else "keyless fetch"
        print(f"live — {surface} + detect, {iterations} iterations against PEPE, one page each\n")
        fetch_ms, detect_ms, counts, credits = [], [], [], 0
        for i in range(iterations):
            t0 = time.perf_counter()
            swaps, meta = tape.pull("ethereum", PEPE, pages=1, quiet=True)
            fetch_ms.append((time.perf_counter() - t0) * 1000)
            credits += meta["credits"]
            if meta["error"]:
                print(f"  iteration {i + 1}: API error — {meta['error'][:70]}")
                continue
            t0 = time.perf_counter()
            cli.compute(swaps, meta, "ethereum", PEPE, "PEPE", with_enrich=False)
            detect_ms.append((time.perf_counter() - t0) * 1000)
            counts.append(len(swaps))
        if not detect_ms:
            sys.exit("every iteration failed — the keyless surface is rate-limiting; exit 75")
        out["fetch"] = report("fetch (one page)", fetch_ms)
        out["detect"] = report("detect (engine)", detect_ms)
        out["prints"] = int(statistics.median(counts))
        out["credits_used"] = credits if var else 0
        cost_txt = f"{credits} credits — keyed" if var else "0 credits — keyless"
    out["captured_utc"] = tape._utc()
    print(f"\n  {out['prints']} prints per iteration · {cost_txt}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, sort_keys=True))
        print(f"  wrote {a.json}")


if __name__ == "__main__":
    main()
