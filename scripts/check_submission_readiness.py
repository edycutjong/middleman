#!/usr/bin/env python3
"""Refuse to let a placeholder — or a stale number — reach a judge.

Scans every judge-facing file for the things that quietly survive into a submission and
destroy it on sight: an unfilled address, a fake video link, a TODO, a template token nobody
replaced — and a published test count that no longer matches the suite.

    python3 scripts/check_submission_readiness.py          # exit 1 on any finding
    python3 scripts/check_submission_readiness.py --json

Exit 0 = clean. Exit 1 = something is not ready. Wired into `make check`.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files a judge actually opens. Deliberately narrow: a TODO in a source comment is ordinary
# engineering, a TODO in the README is an unfinished submission.
TARGETS = [
    "README.md",
    "DEMO.md",
    "JUDGE.md",
    "FEEDBACK.md",
    "ARCHITECTURE.md",
    "site/judge.html",
    "site/pitch/index.html",
]
TARGET_GLOBS = ["docs/*.md", ".github/*.md"]

PATTERNS = [
    ("unfilled address", r"0x\.\.\."),
    ("placeholder video", r"youtu\.be/(xxx|your-video|VIDEO_ID)\b"),
    ("placeholder video", r"youtube\.com/watch\?v=(xxx|your-video|VIDEO_ID)\b"),
    ("TODO marker", r"\bTODO\b"),
    ("TODO marker", r"\bFIXME\b"),
    ("unreplaced template token", r"\[\[FILL\]\]"),
    ("unreplaced template token", r"\[Project Name\]"),
    ("unreplaced template token", r"\bOWNER/REPO\b"),
    ("unreplaced template token", r"\[your-[a-z-]+\]"),
    ("placeholder URL", r"https?://\[[a-z-]+\]"),
    ("placeholder URL", r"example\.com/(your|placeholder)"),
]
# A line that is itself the definition of a pattern is not a violation.
SELF_REFERENTIAL = re.compile(r"placeholder|readiness|scanner|check_submission")
# "134 tests" / "134 tests (128 offline" — the count every judge-facing surface publishes
COUNT = re.compile(
    r"\*{0,2}(\d{2,4})\*{0,2} (?:offline )?tests\b|tests-(\d{2,4})-|[Tt]ests \| \*\*(\d{2,4})\*\*"
)


def collected():
    """What pytest would run: (total, offline) — the numbers the docs must match."""
    out = {}
    for label, args in (("total", []), ("offline", ["-m", "not live"])):
        p = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-p", "no:cacheprovider", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        m = re.search(r"(\d+)(?:/\d+)? tests? collected", p.stdout + p.stderr)
        out[label] = int(m.group(1)) if m else None
    return out


def scan(counts=None):
    files = [ROOT / t for t in TARGETS if (ROOT / t).exists()]
    for g in TARGET_GLOBS:
        files += sorted(ROOT.glob(g))
    findings = []
    for f in sorted(set(files)):
        for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            if SELF_REFERENTIAL.search(line):
                continue
            for label, pat in PATTERNS:
                if re.search(pat, line, re.IGNORECASE if "youtu" in pat else 0):
                    findings.append(
                        {
                            "file": str(f.relative_to(ROOT)),
                            "line": n,
                            "kind": label,
                            "text": line.strip()[:110],
                        }
                    )
                    break
            if counts and counts.get("total"):
                for m in COUNT.finditer(line):
                    n = int(next(g for g in m.groups() if g))
                    if n not in (counts["total"], counts.get("offline")):
                        findings.append(
                            {
                                "file": str(f.relative_to(ROOT)),
                                "line": n,
                                "kind": f"stale test count (suite has {counts['total']})",
                                "text": line.strip()[:110],
                            }
                        )
    return [str(f.relative_to(ROOT)) for f in sorted(set(files))], findings


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-count", action="store_true", help="skip the pytest collection")
    a = ap.parse_args(argv)
    counts = None if a.no_count else collected()
    scanned, findings = scan(counts)
    if a.json:
        print(json.dumps({"scanned": scanned, "counts": counts, "findings": findings}, indent=2))
    else:
        print(f"submission readiness — scanned {len(scanned)} judge-facing file(s)")
        for s in scanned:
            print(f"  · {s}")
        if counts:
            print(f"  suite: {counts['total']} tests ({counts['offline']} offline)")
        if findings:
            print(f"\n{len(findings)} finding(s):\n")
            for f in findings:
                print(f"  {f['file']}:{f['line']}  [{f['kind']}]  {f['text']}")
        else:
            print(
                "\nclean — no unfilled addresses, fake links, TODOs, template tokens, stale counts"
            )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
