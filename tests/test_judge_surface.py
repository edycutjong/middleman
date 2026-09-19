"""The page built for one reader is reachable by that reader: /judge, no credentials, no session.

A /judge page that breaks on submission day is worse than none, so the route is exercised the
way a judge reaches it — through the same static server + function router the deployment uses,
over plain HTTP, with no cookie, no header and no key — and its claim sentence is checked
against JUDGE.md so the repository and the page cannot disagree."""

import html
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
PORT = 8101  # the one port local testing is allowed to use


def _claim_from_judge_md():
    text = (ROOT / "JUDGE.md").read_text()
    block = text.split("## The claim", 1)[1].split("##", 1)[0]
    return " ".join(block.replace("**", "").split())


def _claim_from_html(page):
    m = re.search(r'<p class="claim">(.*?)</p>', page, re.S)
    assert m, "no .claim paragraph on the judge page"
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).split())


def _claim_from_judge_html():
    return _claim_from_html((ROOT / "site" / "judge.html").read_text())


def test_the_judge_page_and_judge_md_make_the_same_claim_sentence():
    """Two surfaces, one sentence — the elevator pitch may not vary between them."""
    assert _claim_from_judge_html() == _claim_from_judge_md()
    assert "cannot tell what stood between them" in _claim_from_judge_md()


def test_the_judge_page_is_generated_from_the_receipts_and_carries_the_hero_numbers():
    census = json.loads((ROOT / "docs" / "proof" / "census.json").read_text())
    page = (ROOT / "site" / "judge.html").read_text()
    share = f"{census['hero']['pool']['share_volume'] * 100:.1f} %"
    assert share in page and str(census["sandwiches"]) in page
    assert "python3 scripts/middleman.py" in page  # the real reproduce command
    assert "replay — not the product" in page  # the deterministic path, labelled apart
    assert "Honest limitations" in page


@pytest.fixture
def served():
    if NODE is None:
        pytest.skip("node is not installed; the served route is probed in CI")
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            pytest.skip(f"port {PORT} is already in use")
    proc = subprocess.Popen(
        [NODE, str(ROOT / "scripts" / "serve.js")],
        env={"PORT": str(PORT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", PORT)) == 0:
                    break
            time.sleep(0.1)
        yield f"http://127.0.0.1:{PORT}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _get(url):
    req = urllib.request.Request(url)  # no cookie, no auth header, no key — a stranger
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, dict(resp.headers), resp.read().decode()


def test_slash_judge_answers_200_with_the_claim_to_a_client_carrying_no_credentials(served):
    """The route a judge clicks: clean URL, no session, and the sentence is on it."""
    status, headers, body = _get(served + "/judge")
    assert status == 200
    assert headers.get("Content-Type", "").startswith("text/html")
    assert "Set-Cookie" not in headers  # nothing to accept, nothing to refuse
    assert "cannot tell what stood between them" in body
    assert _claim_from_html(body) == _claim_from_judge_md()
    for path in ("/", "/evidence", "/judge.html"):
        assert _get(served + path)[0] == 200, path
    status, _, health = _get(served + "/api/health")
    assert status == 200 and json.loads(health)["keyless"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
