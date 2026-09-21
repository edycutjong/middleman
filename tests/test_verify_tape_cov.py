"""verify_tape.py — every named drift, one at a time, against a receipt written by hand."""

import json
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import verify_tape  # noqa: E402
from conftest import USDC, make_row  # noqa: E402

from middleman import cli, tape  # noqa: E402

MOTO = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"
PAGE_URL = tape.BASE + tape.SWAPS + "?p"


def _rows():
    rows = [make_row(h, 1, f"a{h}", "buy", 10, 0.0101 + h * 1e-4) for h in range(1, 70)]
    rows += [make_row(h, 2, f"b{h}", "sell", 10, 0.0100 + h * 1e-4) for h in range(1, 70)]
    rows += [
        make_row(h, 3, f"c{h}", "buy", 5, 0.05, t1a=USDC, t1s="USDC", en="Uniswap v3")
        for h in range(1, 10)
    ]
    rows.append(make_row(80, 1, "W", "sell", 1000, 1.00, tx="0x80", v=1000))
    rows.append(make_row(80, 2, "v1", "sell", 10, 0.0099, tx="0xv1"))
    rows.append(make_row(80, 3, "W", "buy", 1000, 1.02, tx="0x80", v=1000))
    return rows


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    data, proof = tmp_path / "data", tmp_path / "docs" / "proof"
    data.mkdir()
    proof.mkdir(parents=True)
    monkeypatch.setattr(verify_tape, "ROOT", tmp_path)
    monkeypatch.setattr(verify_tape, "DATA", data)
    monkeypatch.setattr(verify_tape, "PROOF", proof)
    return tmp_path


@pytest.fixture
def record(sandbox):
    """Write a tape and the receipt the page was rendered from; return both paths."""

    def _record(name="moto", rows=None, hashes=("h0", "h1")):
        rows = _rows() if rows is None else rows
        calls = [
            {"ok": True, "url": PAGE_URL, "status": 200, "utc": "t", "sha256": h} for h in hashes
        ]
        calls.append({"ok": False, "url": PAGE_URL, "error": "HTTP 429"})
        calls.append({"ok": True, "url": "https://x/v4/dex/pairs/quotes", "sha256": "other"})
        meta = {"pages": len(hashes), "calls": [], "captured_utc": "2026-09-19T00:00:00Z"}
        receipt = cli.compute(rows, meta, "ethereum", MOTO, "MOTO", with_enrich=False)
        receipt["calls"] = calls
        tape_path = sandbox / "data" / f"tape_{name}.json"
        tape_path.write_text(
            json.dumps(
                {
                    "symbol": "MOTO",
                    "platform": "ethereum",
                    "address": MOTO,
                    "captured_utc": meta["captured_utc"],
                    "pages": meta["pages"],
                    "page_sha256": list(hashes),
                    "swaps": rows,
                }
            )
        )
        proof_path = sandbox / "docs" / "proof" / f"{name}.json"
        proof_path.write_text(json.dumps(receipt, default=str))
        return tape_path, proof_path

    return _record


def _tamper(proof_path, mutate):
    d = json.loads(proof_path.read_text())
    mutate(d)
    proof_path.write_text(json.dumps(d))


def test_a_hand_written_receipt_that_matches_its_tape_has_no_drift(record):
    tape_path, proof_path = record()
    receipt = json.loads(proof_path.read_text())
    assert receipt["pools"][0]["example"] is not None
    assert receipt["decision"]["pool"] is not None
    assert verify_tape.compare(tape_path) == []


def test_a_print_count_that_does_not_match_the_rows_is_named(record):
    tape_path, proof_path = record()
    _tamper(proof_path, lambda d: d["window"].__setitem__("prints", 1))
    assert verify_tape.compare(tape_path) == [f"moto: prints 1 != {len(_rows())}"]


def test_only_successful_transaction_page_hashes_are_compared_with_the_tape(record):
    tape_path, proof_path = record()

    def swap_hash(d):
        d["calls"][1]["sha256"] = "forged"

    _tamper(proof_path, swap_hash)
    assert verify_tape.compare(tape_path) == [
        "moto: page hashes in the receipt differ from the tape's"
    ]


def test_a_pool_missing_from_the_receipt_is_counted(record):
    tape_path, proof_path = record()
    _tamper(proof_path, lambda d: d["pools"].pop())
    assert verify_tape.compare(tape_path) == ["moto: 1 pools published, 2 derived"]


def test_pools_published_out_of_order_are_reported_once_per_pool_and_not_field_by_field(record):
    tape_path, proof_path = record()
    _tamper(proof_path, lambda d: d["pools"].reverse())
    drifts = verify_tape.compare(tape_path)
    assert len(drifts) == 2
    assert all("pool order differs" in d for d in drifts)
    assert drifts[0].startswith("moto · Uniswap v3 / USDC")


def test_a_changed_highlight_in_the_example_block_is_a_drift(record):
    tape_path, proof_path = record()
    _tamper(proof_path, lambda d: d["pools"][0]["example"].__setitem__("highlight", [0]))
    assert verify_tape.compare(tape_path) == ["moto · Uniswap v2 / WETH: the example block differs"]


def test_a_changed_kind_in_the_example_block_is_a_drift(record):
    tape_path, proof_path = record()
    _tamper(proof_path, lambda d: d["pools"][0]["example"].__setitem__("kind", "other"))
    assert verify_tape.compare(tape_path) == ["moto · Uniswap v2 / WETH: the example block differs"]


def test_an_example_block_dropped_from_the_receipt_is_a_drift(record):
    tape_path, proof_path = record()
    _tamper(proof_path, lambda d: d["pools"][0].__setitem__("example", None))
    assert verify_tape.compare(tape_path) == ["moto · Uniswap v2 / WETH: the example block differs"]


def test_a_changed_checked_field_and_a_changed_decision_are_both_named(record):
    tape_path, proof_path = record()

    def mutate(d):
        d["pools"][1]["makers"] = 0
        d["decision"]["candidates"] = 99

    _tamper(proof_path, mutate)
    drifts = verify_tape.compare(tape_path)
    assert drifts == [
        "moto · Uniswap v3 / USDC: makers 0 != 9",
        "moto: decision.candidates 99 != 1",
    ]


def test_a_tape_with_no_receipt_names_the_missing_file(record):
    tape_path, proof_path = record()
    proof_path.unlink()
    assert verify_tape.compare(tape_path) == ["moto: no receipt at docs/proof/moto.json"]


def test_main_without_tapes_says_how_to_record_one(sandbox):
    with pytest.raises(SystemExit) as e:
        verify_tape.main([])
    assert "seed.py" in str(e.value.code)


def test_main_says_so_when_every_receipt_re_derives(record, capsys):
    record()
    assert verify_tape.main([]) == 0
    assert "every published number re-derives from its tape" in capsys.readouterr().out


def test_main_prints_one_line_per_tape_and_lists_every_drift(record, capsys):
    record("moto")
    _, proof_path = record("pepe", hashes=("p0",))
    _tamper(proof_path, lambda d: d["window"].__setitem__("prints", 1))
    assert verify_tape.main([]) == 1
    out = capsys.readouterr().out
    assert "verify — 2 tape(s) re-derived offline" in out
    assert "  ok   tape_moto.json" in out and "  DRIFT tape_pepe.json" in out
    assert "1 drift(s):" in out and "pepe: prints 1 !=" in out


def test_run_as_a_script_exits_with_the_verdict(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["verify_tape.py", "--json"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(ROOT / "scripts" / "verify_tape.py"), run_name="__main__")
    report = json.loads(capsys.readouterr().out)
    assert e.value.code == (1 if report["drifts"] else 0)
    assert report["tapes"] and all(row["ok"] for row in report["tapes"])
