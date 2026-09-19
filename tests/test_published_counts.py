"""What the judge-facing surfaces claim about this repository is checked against it."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import check_submission_readiness as readiness  # noqa: E402

SURFACES = ["README.md", "DEMO.md", "JUDGE.md", "ARCHITECTURE.md", "site/judge.html"]


def test_every_surface_publishes_the_same_test_count_as_the_suite():
    """'134 tests' on a README that has 133 is the cheapest way to look careless."""
    counts = readiness.collected()
    assert counts["total"] and counts["offline"]
    for name in SURFACES:
        text = (ROOT / name).read_text()
        published = {int(n) for m in readiness.COUNT.findall(text) for n in m if n}
        assert published, f"{name} publishes no test count"
        assert published <= {counts["total"], counts["offline"]}, (name, published, counts)


def test_the_readiness_scan_is_clean_on_this_submission():
    scanned, findings = readiness.scan(readiness.collected())
    assert "README.md" in scanned and findings == []


def test_the_property_case_count_the_docs_quote_is_the_one_the_suite_runs():
    from test_property import PROPERTY_CASES

    for name in ("README.md", "DEMO.md", "JUDGE.md", "site/judge.html"):
        assert f"{PROPERTY_CASES:,} generated blocks" in (ROOT / name).read_text(), name
    import render_site

    assert render_site.PROPERTY_CASES == PROPERTY_CASES


def test_every_endpoint_the_code_calls_is_named_on_the_readme_and_the_page():
    code = "".join(p.read_text() for p in (ROOT / "middleman").glob("*.py"))
    called = set(re.findall(r'"(/v\d/dex/[a-z/-]+)"', code))
    assert len(called) >= 6, called
    readme = (ROOT / "README.md").read_text()
    evidence = (ROOT / "site" / "evidence.html").read_text()
    for path in called:
        assert path in readme, f"{path} is called but not named in README.md"
        assert path in evidence, f"{path} is called but not on /evidence"


def test_no_key_variable_is_referenced_by_the_deployment():
    """The proxy and the health check hold no secret — by inspection, every deploy."""
    for name in ("api/swaps.js", "api/health.js", "vercel.json"):
        text = (ROOT / name).read_text()
        assert "CMC_API_KEY" not in text and "X-CMC_PRO_API_KEY" not in text, name
        assert "process.env" not in text, name
