"""The day-1 spike end to end, every live call replaced, the receipt written under tmp_path."""

import json
import runpy
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import spike  # noqa: E402
from conftest import BASE, WETH, make_row  # noqa: E402

from middleman import tape  # noqa: E402

SCRIPT = ROOT / "scripts" / "spike.py"
POOL = "0x000000000000000000000000000000000000d00d"
SPOT_PAIRS = "/v4/dex/spot-pairs/latest"
TOKEN_POOLS = "/v1/dex/token/pools"
SECURITY = "/v1/dex/security/detail"
PAIR_QUOTES = "/v4/dex/pairs/quotes/latest"

BODIES = {
    SPOT_PAIRS: [
        {
            "name": "MOTO/WETH",
            "contract_address": POOL,
            "base_asset_symbol": "MOTO",
            "base_asset_contract_address": BASE,
        }
    ],
    TOKEN_POOLS: [{"addr": POOL, "exn": "Uniswap v2", "liqUsd": "12345.6", "t1": {"sym": "WETH"}}],
    SECURITY: [{"extra": {"buyTax": "0"}}],
    PAIR_QUOTES: [
        {
            "num_transactions_24h": 5,
            "24h_no_of_buys": 3,
            "24h_no_of_sells": 2,
            "quote": [{"24h_no_of_buys": 3, "liquidity": 1.0, "price": 2.0}],
        }
    ],
}


def _tape_rows():
    rows, lg = [], 1
    for h in range(100, 110):
        rows.append(make_row(h, lg, "W", "buy", 1000, 1.00, tx=f"0x{h}a", v=1000))
        rows.append(make_row(h, lg + 1, f"v{h}", "buy", 10, 0.0101, v=10))
        rows.append(make_row(h, lg + 2, "W", "sell", 1000, 1.02, tx=f"0x{h}b", v=1000))
        lg += 3
    rows[1]["q"] = 0.0
    return rows


class FakeApi:
    def __init__(self, ok_paths, rows_for, cors_headers):
        self.ok_paths = set(ok_paths)
        self.rows_for = rows_for
        self.cors_headers = cors_headers
        self.gets = []
        self.pulls = []
        self.origin_sent = None

    def get(self, path, retries=3, quiet=False, **params):
        self.gets.append((path, params))
        if path not in self.ok_paths:
            return {
                "ok": False,
                "url": tape.BASE + path,
                "status": 429,
                "utc": "t",
                "elapsed_ms": 1,
                "error": "HTTP 429: Too Many Requests",
                "throttled": True,
                "attempts": retries,
            }
        return {
            "ok": True,
            "url": tape.BASE + path,
            "status": 200,
            "utc": "t",
            "elapsed_ms": 1,
            "sha256": "deadbeef",
            "credit_count": 0,
            "body": {"data": BODIES[path]},
        }

    def pull(self, platform, address, pages=8, quiet=False):
        self.pulls.append((platform, address, pages))
        rows, error = self.rows_for(address)
        meta = {
            "pages": pages if rows else 0,
            "error": error,
            "throttled": error is not None,
            "calls": [{"ok": True, "url": "u", "status": 200, "utc": "t", "sha256": "s"}],
            "wall_s": 0.1,
        }
        return rows, meta

    def urlopen(self, req, timeout=None):
        self.origin_sent = req.get_header("Origin")
        body = json.dumps({"data": [{"id": 1, "txuf": "https://etherscan.io/tx/{}"}]}).encode()
        return _Response(self.cors_headers, body)


class _Response:
    def __init__(self, headers, body):
        self.headers = headers
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


@pytest.fixture
def wire(monkeypatch):
    def install(ok_paths=tuple(BODIES), rows_for=None, cors_headers=None):
        api = FakeApi(
            ok_paths,
            rows_for or (lambda address: (_tape_rows() if address == BASE else [], None)),
            cors_headers if cors_headers is not None else {"Content-Type": "application/json"},
        )
        monkeypatch.setattr(tape, "get", api.get)
        monkeypatch.setattr(tape, "pull", api.pull)
        monkeypatch.setattr(urllib.request, "urlopen", api.urlopen)
        return api

    return install


@pytest.fixture
def out(tmp_path):
    return tmp_path / "proof" / "spike.json"


def test_a_full_spike_writes_a_receipt_that_answers_the_question(wire, out, monkeypatch, capsys):
    api = wire()
    monkeypatch.setattr(sys, "argv", ["spike.py", "--out", str(out)])

    spike.main()

    d = json.loads(out.read_text())
    assert d["answer"]["pool_identity_recoverable"] is True
    assert d["answer"]["maker_join_possible"] is True
    assert d["answer"]["prints_scanned"] == 30 and d["answer"]["sandwiches_A_B_A"] == 10
    assert d["answer"]["hero_pool"]["pool"] == ["Uniswap v2", BASE, WETH]
    assert d["tapes"]["MOTO"]["fields"]["q_mismatch_by_venue"] == {"Uniswap v2": 1}
    assert d["hero_rule"]["picked"] == {"name": "MOTO/WETH", "base": BASE, "pool": POOL}
    assert d["hero_rule"]["rows_returned_for_limit_1"] == 1
    assert d["cors"]["allow_origin_present"] is False and api.origin_sent == "https://example.org"
    assert d["explorer"]["ethereum_txuf"] == "https://etherscan.io/tx/{}"
    assert list(d["tapes"]) == ["MOTO"] and d["tapes"]["MOTO"]["pages"] == 8
    assert d["enrich"]["token_pools"][0]["t1"] == "WETH"
    assert d["enrich"]["token_pools_liqUsd_is_string"] is True
    assert d["enrich"]["security"] == {"data_is_list": True, "extra": {"buyTax": "0"}}
    assert d["enrich"]["pair_quotes"]["quote_level"]["liquidity"] == 1.0
    assert d["credits_used"] == 0 and len(d["calls"]) == 1 + 1 + 2 + 3
    assert api.pulls == [("ethereum", BASE, 8), ("ethereum", spike.PEPE[1], 4)]
    assert api.gets[-1][1]["contract_address"] == POOL
    text = capsys.readouterr().out
    assert "hero rule  #1 Uniswap v2 pair by 24h tx: MOTO/WETH" in text
    assert "sandwiches 10" in text and "wrote " in text


def test_failed_enrichment_calls_are_kept_as_receipts_and_left_out_of_enrich(
    wire, out, monkeypatch
):
    def rows_for(address):
        return _tape_rows(), ("throttled after 8 page(s)" if address == spike.PEPE[1] else None)

    api = wire(
        ok_paths=(SPOT_PAIRS,),
        rows_for=rows_for,
        cors_headers={"Access-Control-Allow-Origin": "*"},
    )
    monkeypatch.setattr(sys, "argv", ["spike.py", "--pages", "2", "--out", str(out)])

    spike.main()

    d = json.loads(out.read_text())
    assert d["enrich"] == {}
    assert sorted(d["tapes"]) == ["MOTO", "PEPE"]
    assert d["tapes"]["PEPE"]["throttled"] is True
    assert d["tapes"]["PEPE"]["error"] == "throttled after 8 page(s)"
    assert d["cors"]["allow_origin_present"] is True
    assert [c["ok"] for c in d["calls"]].count(False) == 3
    assert api.pulls == [("ethereum", BASE, 2), ("ethereum", spike.PEPE[1], 2)]


def test_a_failed_hero_rule_stops_the_spike_before_any_tape_is_pulled(wire, out, monkeypatch):
    api = wire(ok_paths=())
    monkeypatch.setattr(sys, "argv", ["spike.py", "--out", str(out)])

    with pytest.raises(SystemExit, match="hero rule failed: HTTP 429"):
        spike.main()

    assert api.pulls == [] and not out.exists()


def test_running_the_script_as_a_program_reads_its_own_argv(wire, out, monkeypatch):
    api = wire()
    monkeypatch.setattr(sys, "argv", ["spike.py", "--pages", "3", "--out", str(out)])

    runpy.run_path(str(SCRIPT), run_name="__main__")

    assert api.pulls == [("ethereum", BASE, 3), ("ethereum", spike.PEPE[1], 3)]
    assert json.loads(out.read_text())["tapes"]["MOTO"]["pages"] == 3
