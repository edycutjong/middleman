"""The permission boundary of the one deployed function, proven rather than described.

api/swaps.js is the only code in this project that runs with any privilege at all — it is a
public, unauthenticated endpoint on a shared IP — and its whole contract is least-privilege:
it can reach exactly one keyless CoinMarketCap URL, with exactly the query it validated, and
it can never carry a caller's credential upstream. Each of those is asserted here by driving
the real function under node with `fetch` stubbed to record what it was asked to do."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

# Drives api/swaps.js exactly as Vercel does (module.exports = async (req, res)), with a fetch
# that records every call and answers like the keyless surface. Prints one JSON per case.
HARNESS = r"""
const fn = require(process.argv[1]);
const cases = JSON.parse(process.argv[2]);
(async () => {
  const out = [];
  for (const c of cases) {
    const calls = [];
    globalThis.fetch = async (url, opts) => {
      calls.push({ url: String(url), headers: (opts && opts.headers) || {} });
      return new Response('{"data":{"transactions":[],"lastId":null},"status":{"credit_count":1}}',
        { status: 200, headers: { 'content-type': 'application/json' } });
    };
    const headers = {};
    const res = {
      statusCode: 200, body: '',
      setHeader(k, v) { headers[k] = v; },
      end(b) { this.body = b || ''; },
    };
    await fn({ method: 'GET', query: c.query, headers: c.headers || {} }, res);
    out.push({ name: c.name, status: res.statusCode, body: res.body, headers, calls });
  }
  process.stdout.write(JSON.stringify(out));
})();
"""

CALLER = {  # what a hostile or careless caller might send along
    "x-cmc_pro_api_key": "leaked-key-must-not-travel",
    "authorization": "Bearer leaked-token-must-not-travel",
    "cookie": "session=must-not-travel",
    "x-forwarded-host": "evil.example",
}
GOOD = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"


def drive(cases):
    if NODE is None:
        pytest.skip("node is not installed; the boundary is exercised in CI")
    p = subprocess.run(
        [NODE, "-e", HARNESS, str(ROOT / "api" / "swaps.js"), json.dumps(cases)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )
    assert p.returncode == 0, p.stderr
    return {r["name"]: r for r in json.loads(p.stdout)}


def test_the_proxy_can_only_ever_reach_one_keyless_coinmarketcap_url():
    """No caller input reaches the host or the path — only the three validated parameters."""
    eth = {"platform": "ethereum", "address": GOOD}
    r = drive(
        [
            {"name": "ok", "query": {**eth, "lastId": "abc123"}},
            {"name": "host-in-address", "query": {**eth, "address": f"{GOOD}@evil.example/x"}},
            {"name": "path-in-address", "query": {**eth, "address": "../../v1/key/info"}},
            {"name": "platform", "query": {**eth, "platform": "evil.example"}},
            {"name": "cursor", "query": {**eth, "lastId": "<script>x</script>"}},
        ]
    )
    ok = r["ok"]
    assert ok["status"] == 200 and len(ok["calls"]) == 1
    url = ok["calls"][0]["url"]
    assert url.startswith(
        "https://pro-api.coinmarketcap.com/public-api/v1/dex/tokens/transactions?"
    )
    assert "platform=ethereum" in url and f"address={GOOD}" in url
    assert json.loads(ok["body"])["credit_count"] == 0  # keyless: nothing was charged to anyone
    for name in ("host-in-address", "path-in-address", "platform", "cursor"):
        assert r[name]["status"] == 400, name
        assert r[name]["calls"] == [], f"{name}: the proxy called upstream on a refused input"


def test_a_callers_credential_or_cookie_is_never_forwarded_upstream():
    """The deployment holds no secret, and it will not carry yours either — by test, not by
    paragraph. Whatever a browser or a curl attaches, CoinMarketCap sees `Accept` and nothing
    else, so the function cannot be used to spend a key, replay a session or spoof a host."""
    query = {"platform": "ethereum", "address": GOOD}
    r = drive([{"name": "ok", "query": query, "headers": CALLER}])
    (call,) = r["ok"]["calls"]
    assert set(k.lower() for k in call["headers"]) == {"accept"}
    assert "must-not-travel" not in json.dumps(call)
    assert "must-not-travel" not in r["ok"]["body"]  # nor echoed back to the next visitor
    source = (ROOT / "api" / "swaps.js").read_text()
    assert "req.headers" not in source and "process.env" not in source


def test_the_proxy_refuses_an_address_that_is_not_a_contract_address_without_a_call():
    """The paste box is public; a bad paste is answered with the CLI command, not with a
    request to CoinMarketCap on the shared IP's quota."""
    r = drive(
        [
            {"name": "empty", "query": {"platform": "ethereum", "address": ""}},
            {"name": "short", "query": {"platform": "ethereum", "address": "0xdeadbeef"}},
            {
                "name": "spaces",
                "query": {"platform": "solana", "address": "So1 111111111111111111111"},
            },
        ]
    )
    for name, case in r.items():
        assert case["status"] == 400 and case["calls"] == [], name
        body = json.loads(case["body"])
        assert body["ok"] is False and "contract address" in body["error"]
