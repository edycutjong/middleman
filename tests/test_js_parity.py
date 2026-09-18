"""The browser engine and the Python engine agree, row for row, on the committed tapes.

site/middleman.js is the port the paste box runs. If it drifted from the Python engine the
live table and the committed table would be two different products. Skipped where node is
not installed; CI installs it."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from middleman import cli  # noqa: E402

NODE = shutil.which("node")
HARNESS = """
const MM = require(process.argv[1]);
const t = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const r = MM.compute(t.swaps);
process.stdout.write(JSON.stringify({
  pools: r.pools.map((p) => ({ key: p.key, n: p.n, n_organic: p.n_organic, makers: p.makers,
    rt: p.round_trips.pairs, rt_wallets: p.round_trips.wallets,
    rt_share: p.round_trips.share_volume,
    sw: p.sandwiches.count, sw_victims: p.sandwiches.victims,
    p50: p.q2f.p50_bps, p90: p.q2f.p90_bps, naive50: p.naive.p50_bps, naive90: p.naive.p90_bps,
    ex: p.example && [p.example.kind, p.example.h, p.example.highlight, p.example.victims] })),
  decision: [r.decision.pool, r.decision.p90_bps, r.decision.cap_pct, r.decision.candidates],
  window: [r.window.prints, r.window.first_block, r.window.last_block, r.window.unplaceable],
}));
"""


def _python(tape):
    meta = {"pages": tape["pages"], "calls": [], "captured_utc": tape["captured_utc"]}
    r = cli.compute(
        tape["swaps"], meta, tape["platform"], tape["address"], tape["symbol"], with_enrich=False
    )
    return {
        "pools": [
            {
                "key": p["key"],
                "n": p["n"],
                "n_organic": p["n_organic"],
                "makers": p["makers"],
                "rt": p["round_trips"]["pairs"],
                "rt_wallets": p["round_trips"]["wallets"],
                "rt_share": p["round_trips"]["share_volume"],
                "sw": p["sandwiches"]["count"],
                "sw_victims": p["sandwiches"]["victims"],
                "p50": p["q2f"]["p50_bps"],
                "p90": p["q2f"]["p90_bps"],
                "naive50": p["naive"]["p50_bps"],
                "naive90": p["naive"]["p90_bps"],
                "ex": p["example"]
                and [
                    p["example"]["kind"],
                    p["example"]["h"],
                    p["example"]["highlight"],
                    p["example"]["victims"],
                ],
            }
            for p in r["pools"]
        ],
        "decision": [
            r["decision"]["pool"],
            r["decision"]["p90_bps"],
            r["decision"]["cap_pct"],
            r["decision"]["candidates"],
        ],
        "window": [
            r["window"]["prints"],
            r["window"]["first_block"],
            r["window"]["last_block"],
            r["window"]["unplaceable"],
        ],
    }


@pytest.mark.skipif(NODE is None, reason="node is not installed; the parity check runs in CI")
@pytest.mark.parametrize(
    "tape_path", sorted((ROOT / "data").glob("tape_*.json")), ids=lambda p: p.stem
)
def test_the_javascript_engine_matches_the_python_engine_on_every_committed_tape(tape_path):
    out = subprocess.run(
        [NODE, "-e", HARNESS, str(ROOT / "site" / "middleman.js"), str(tape_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    js = json.loads(out.stdout)
    py = _python(json.loads(tape_path.read_text()))
    assert js["window"] == py["window"]
    assert js["decision"] == py["decision"]
    assert len(js["pools"]) == len(py["pools"])
    for a, b in zip(js["pools"], py["pools"], strict=True):
        assert a == b, f"{tape_path.name} · {a['key']}: js {a} != py {b}"
