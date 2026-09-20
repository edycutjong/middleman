"""The fetch contract — the cursor, the identity, the throttle, the key boundary.

Every network call is intercepted at urllib.request.urlopen, so these run with the socket
unplugged and pin how the tool behaves when CoinMarketCap misbehaves. The real contract is
asserted by tests/test_live.py (-m live).
"""

import http.client
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleman import tape  # noqa: E402

ALL_KEY_VARS = (*tape.KEY_VARS, "X_CMC_PRO_API_KEY", "API_KEY")


class _Resp:
    def __init__(self, body, status=200):
        self._raw = json.dumps(body).encode()
        self.status = status
        self.headers = {}

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, body=None, reason="err"):
    raw = json.dumps(body).encode() if body is not None else b"<html>not json</html>"
    return urllib.error.HTTPError("http://x", code, reason, {}, io.BytesIO(raw))


def _swap(tx, lgid):
    return {"tx": tx, "lgid": str(lgid), "h": "1", "ma": "m", "tp": "buy", "a0": 1, "a1": 1}


def _page(swaps, last_id):
    return {"data": {"swaps": swaps, "lastId": last_id}, "status": {"credit_count": 1}}


@pytest.fixture(autouse=True)
def _no_sleep_no_keys(monkeypatch):
    monkeypatch.setattr(tape.time, "sleep", lambda s: None)
    for var in ALL_KEY_VARS:
        monkeypatch.delenv(var, raising=False)


def _serve(monkeypatch, responses):
    """Feed urlopen a queue of responses / exceptions; record every request."""
    seen = []

    def fake(req, timeout=60):
        seen.append(req)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(tape.urllib.request, "urlopen", fake)
    return seen


# ── pagination ───────────────────────────────────────────────────────────────────────────────


def test_the_cursor_is_read_from_the_envelope_not_from_the_last_swap(monkeypatch):
    """An earlier paginator on this feed read txId off the last swap; the server
    accepted it and returned page 1 again. The cursor is data.lastId on the envelope."""
    seen = _serve(
        monkeypatch,
        [
            _Resp(_page([_swap("a", 1), _swap("b", 2)], "CURSOR-1")),
            _Resp(_page([_swap("c", 3)], None)),
        ],
    )
    swaps, meta = tape.pull("ethereum", "0xt", pages=3)
    assert [s["tx"] for s in swaps] == ["a", "b", "c"]
    assert "lastId=CURSOR-1" in seen[1].full_url and "lastId" not in seen[0].full_url
    assert meta["pages"] == 2 and meta["error"] is None and not meta["stalled"]


def test_swaps_are_keyed_by_tx_and_log_index_together(monkeypatch):
    """One tx carries several swaps and one lgid repeats across txs; either alone drops rows."""
    _serve(monkeypatch, [_Resp(_page([_swap("a", 1), _swap("a", 2), _swap("b", 1)], None))])
    swaps, _ = tape.pull("ethereum", "0xt", pages=1)
    assert len(swaps) == 3


def test_a_page_that_only_repeats_stops_the_walk_instead_of_spinning(monkeypatch):
    _serve(
        monkeypatch,
        [_Resp(_page([_swap("a", 1)], "C1")), _Resp(_page([_swap("a", 1)], "C2"))],
    )
    swaps, meta = tape.pull("ethereum", "0xt", pages=5)
    assert len(swaps) == 1 and meta["stalled"] is True and meta["pages"] == 2


def test_an_empty_page_ends_the_walk_cleanly(monkeypatch):
    _serve(monkeypatch, [_Resp(_page([], None))])
    swaps, meta = tape.pull("ethereum", "0xt", pages=3)
    assert swaps == [] and meta["error"] is None and meta["pages"] == 1


def test_limit_is_the_documented_hundred_and_the_platform_and_address_travel(monkeypatch):
    seen = _serve(monkeypatch, [_Resp(_page([], None))])
    tape.pull("bsc", "0xabc", pages=1)
    assert "limit=100" in seen[0].full_url
    assert "platform=bsc" in seen[0].full_url and "address=0xabc" in seen[0].full_url
    assert seen[0].full_url.startswith(tape.BASE + tape.SWAPS)


# ── throttling ───────────────────────────────────────────────────────────────────────────────


def test_a_rate_limited_fetch_is_returned_as_an_error_not_as_an_empty_tape(monkeypatch):
    body = {"status": {"error_code": "1022", "error_message": "You've reached the limit"}}
    _serve(monkeypatch, [_http_error(429, body) for _ in range(4)])
    swaps, meta = tape.pull("ethereum", "0xt", pages=1)
    assert swaps == []
    assert meta["error"].startswith("HTTP 429 (error 1022)") and meta["throttled"] is True


def test_a_transient_throttle_is_retried_before_the_page_is_failed(monkeypatch):
    _serve(monkeypatch, [_http_error(429, {}), _Resp(_page([_swap("a", 1)], None))])
    swaps, meta = tape.pull("ethereum", "0xt", pages=1)
    assert len(swaps) == 1 and meta["error"] is None


def test_a_500_is_the_same_throttle_wearing_a_different_status(monkeypatch):
    body = {"status": {"error_code": "500", "error_message": "The system is busy"}}
    _serve(monkeypatch, [_http_error(500, body), _Resp(_page([_swap("a", 1)], None))])
    swaps, meta = tape.pull("ethereum", "0xt", pages=1)
    assert len(swaps) == 1 and meta["error"] is None


def test_a_400_is_permanent_and_is_not_retried(monkeypatch):
    seen = _serve(monkeypatch, [_http_error(400, {"status": {"error_message": "bad limit"}})])
    swaps, meta = tape.pull("ethereum", "0xt", pages=1)
    assert len(seen) == 1 and meta["throttled"] is False and "HTTP 400" in meta["error"]


def test_pages_that_landed_before_the_throttle_are_kept_and_the_window_is_marked_partial(
    monkeypatch,
):
    _serve(
        monkeypatch,
        [_Resp(_page([_swap("a", 1)], "C1")), *([_http_error(429, {})] * 4)],
    )
    swaps, meta = tape.pull("ethereum", "0xt", pages=2)
    assert len(swaps) == 1 and meta["pages"] == 1 and meta["throttled"] and meta["error"]


def test_a_dropped_connection_is_congestion_and_earns_the_backoff(monkeypatch):
    _serve(
        monkeypatch,
        [http.client.RemoteDisconnected("closed"), _Resp(_page([_swap("a", 1)], None))],
    )
    swaps, meta = tape.pull("ethereum", "0xt", pages=1)
    assert len(swaps) == 1 and meta["error"] is None


def test_a_dropped_connection_on_every_retry_is_reported_as_throttled(monkeypatch):
    _serve(monkeypatch, [http.client.RemoteDisconnected("closed")] * 4)
    _, meta = tape.pull("ethereum", "0xt", pages=1)
    assert meta["throttled"] is True and "RemoteDisconnected" in meta["error"]


def test_an_unreachable_host_is_not_a_rate_limit(monkeypatch):
    seen = _serve(monkeypatch, [urllib.error.URLError("dns")])
    _, meta = tape.pull("ethereum", "0xt", pages=1)
    assert len(seen) == 1 and meta["throttled"] is False and "URLError" in meta["error"]


def test_malformed_json_is_a_contract_problem_not_congestion(monkeypatch):
    class Bad(_Resp):
        def read(self):
            return b"<html>"

    seen = _serve(monkeypatch, [Bad({})])
    _, meta = tape.pull("ethereum", "0xt", pages=1)
    assert len(seen) == 1 and meta["throttled"] is False and "JSONDecodeError" in meta["error"]


def test_an_http_error_is_described_by_its_message_never_by_its_body():
    e = _http_error(429, {"status": {"error_code": "1022", "error_message": "  slow   down "}})
    assert tape.describe_http_error(e) == "HTTP 429 (error 1022): slow down"
    assert tape.describe_http_error(_http_error(502, None, reason="Bad Gateway")) == (
        "HTTP 502: Bad Gateway"
    )
    plain = _http_error(400, {"status": {"error_code": "0"}}, reason="Bad Request")
    assert tape.describe_http_error(plain) == "HTTP 400: Bad Request"


# ── receipts ─────────────────────────────────────────────────────────────────────────────────


def test_every_call_leaves_a_receipt_with_its_url_status_hash_and_timing(monkeypatch):
    _serve(monkeypatch, [_Resp(_page([_swap("a", 1)], "C1")), _http_error(400, {})])
    _, meta = tape.pull("ethereum", "0xt", pages=2)
    ok, bad = meta["calls"]
    assert ok["ok"] and ok["status"] == 200 and len(ok["sha256"]) == 64 and "body" not in ok
    assert ok["utc"].endswith("Z") and ok["elapsed_ms"] >= 0
    assert not bad["ok"] and bad["status"] == 400 and bad["attempts"] == 1


def test_the_keyless_receipt_reports_the_credit_count_cmc_sends_and_charges_nothing(monkeypatch):
    _serve(monkeypatch, [_Resp(_page([_swap("a", 1)], None))])
    _, meta = tape.pull("ethereum", "0xt", pages=1)
    assert meta["calls"][0]["credit_count"] == 1  # what the envelope says
    assert meta["credits"] == 0 and meta["keyed"] is False  # what a keyless run is charged


# ── the key boundary ─────────────────────────────────────────────────────────────────────────


def test_with_every_key_variable_unset_no_credential_header_is_sent():
    """The judged path is keyless. This is the R5 mechanical check as a test."""
    assert tape.api_key() is None and tape.escape_hatch_var() is None
    assert tape.active_base() == tape.BASE


def test_an_exported_key_moves_the_same_call_to_the_keyed_host_and_is_never_printed(
    monkeypatch, capsys
):
    monkeypatch.setenv("CMC_API_KEY", "sekrit-value")
    seen = _serve(monkeypatch, [_Resp(_page([_swap("a", 1)], None))])
    _, meta = tape.pull("ethereum", "0xt", pages=1)
    assert seen[0].full_url.startswith(tape.BASE_KEYED)
    assert seen[0].get_header("X-cmc_pro_api_key") == "sekrit-value"
    assert meta["keyed"] is True and meta["credits"] == 1
    assert tape.escape_hatch_var() == "CMC_API_KEY"
    advice = tape.throttle_advice("HTTP 429")
    assert "CMC_API_KEY" in advice and "sekrit" not in advice
    assert "sekrit" not in capsys.readouterr().out


def test_the_keyless_throttle_advice_names_both_status_codes_and_the_way_through():
    advice = tape.throttle_advice("HTTP 429 (error 1022): limit")
    assert "429" in advice and "500" in advice and "CMC_API_KEY" in advice
    assert "escape hatch" in advice
