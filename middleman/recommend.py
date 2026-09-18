"""The decision: where to route, and what slippage cap to set.

    candidates = pools with at least MIN_ORGANIC organic prints in the window
    route      = the candidate with the lowest organic p90 quote-to-fill
    cap        = that p90, rounded UP to the next 0.05 %

The rule is published on every surface so the recommendation is a screen, not a pick. When no
pool qualifies the function says so rather than widening the rule — a thinner window is a
reason to pull more pages, not to lower the bar.
"""

import math

MIN_ORGANIC = 50
CAP_STEP_PCT = 0.05
RULE = f"lowest organic p90 quote-to-fill among pools with ≥ {MIN_ORGANIC} organic prints"


def cap_pct(p90_bps):
    """A slippage cap in percent: p90 bps rounded up to the next 0.05 %, never below 0.05 %."""
    if p90_bps is None:
        return None
    steps = math.ceil(max(p90_bps, 0.0) / (CAP_STEP_PCT * 100.0))
    return round(max(steps, 1) * CAP_STEP_PCT, 2)


def route(rows, min_organic=MIN_ORGANIC):
    """{"pool": key | None, "venue", "quote", "p90_bps", "cap_pct", "why", "candidates"}."""
    candidates = [
        r for r in rows if r["n_organic"] >= min_organic and r["q2f"]["p90_bps"] is not None
    ]
    if not candidates:
        return {
            "pool": None,
            "venue": None,
            "quote": None,
            "p90_bps": None,
            "cap_pct": None,
            "candidates": 0,
            "why": (
                f"no pool has ≥ {min_organic} organic prints in this window — "
                "pull more pages rather than lower the bar"
            ),
        }
    best = min(candidates, key=lambda r: (r["q2f"]["p90_bps"], -r["n_organic"]))
    return {
        "pool": best["key"],
        "venue": best["venue"],
        "quote": best["quote"],
        "p90_bps": best["q2f"]["p90_bps"],
        "cap_pct": cap_pct(best["q2f"]["p90_bps"]),
        "candidates": len(candidates),
        "why": RULE,
    }
