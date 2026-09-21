"""bench.py — the hero lookup fallbacks, the keyed live path, and the script entrypoint."""

import json
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import bench  # noqa: E402
from conftest import make_row  # noqa: E402

from middleman import tape  # noqa: E402

MOTO = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"


def _rows():
    rows, lg = [], 1
    for h in range(100, 110):
        rows.append(make_row(h, lg, "W", "sell", 1000, 1.00, tx=f"0x{h}", v=1000))
        rows.append(make_row(h, lg + 1, "W", "buy", 1000, 1.02, tx=f"0x{h}", v=1000))
        lg += 2
    return rows


def _meta(pages=1, **over):
    m = {
        "captured_utc": "2026-09-19T00:00:00Z",
        "pages": pages,
        "error": None,
        "throttled": False,
        "stalled": False,
        "credits": 0,
        "keyed": False,
        "calls": [],
        "wall_s": 0.1,
    }
    m.update(over)
    return m


def _tape_file(data, name, rows):
    data.mkdir(parents=True, exist_ok=True)
    path = data / f"tape_{name}.json"
    path.write_text(
        json.dumps(
            {
                "symbol": name.upper(),
                "platform": "ethereum",
                "address": MOTO,
                "captured_utc": "2026-09-19T00:00:00Z",
                "pages": 1,
                "swaps": rows,
            }
        )
    )
    return path


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    for var in tape.KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "DATA", tmp_path / "data")
    monkeypatch.setattr(tape.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    return tmp_path


def _census(sandbox, body):
    proof = sandbox / "docs" / "proof"
    proof.mkdir(parents=True)
    (proof / "census.json").write_text(json.dumps(body))


def test_a_census_without_a_hero_symbol_falls_back_to_the_largest_tape(sandbox):
    _census(sandbox, {"hero": {}})
    _tape_file(sandbox / "data", "small", _rows()[:2])
    big = _tape_file(sandbox / "data", "big", _rows())
    assert bench.hero_tape() == big


def test_a_hero_whose_tape_is_missing_falls_back_to_the_largest_tape(sandbox):
    _census(sandbox, {"hero": {"symbol": "GONE"}})
    only = _tape_file(sandbox / "data", "only", _rows())
    assert bench.hero_tape() == only


def test_the_named_hero_wins_over_a_larger_tape(sandbox):
    _census(sandbox, {"hero": {"symbol": "Mo-To"}})
    hero = _tape_file(sandbox / "data", "moto", _rows()[:2])
    _tape_file(sandbox / "data", "big", _rows())
    assert bench.hero_tape() == hero


def test_no_census_and_no_tapes_means_no_hero(sandbox):
    assert bench.hero_tape() is None


def test_replay_without_json_prints_the_summary_and_writes_nothing(sandbox, capsys):
    _tape_file(sandbox / "data", "moto", _rows())
    bench.main(["--replay", "--iterations", "2"])
    out = capsys.readouterr().out
    assert "replay — 20 prints of MOTO" in out and "no network" in out
    assert "wrote" not in out and list(sandbox.rglob("*.json")) == [
        sandbox / "data" / "tape_moto.json"
    ]


def test_a_keyed_live_run_counts_credits_and_names_the_escape_hatch(sandbox, monkeypatch, capsys):
    monkeypatch.setenv(tape.KEY_VARS[0], "secret")
    monkeypatch.setattr(tape, "pull", lambda *a, **k: (_rows(), _meta(credits=3)))
    out = sandbox / "b.json"
    bench.main(["--iterations", "2", "--json", str(out)])
    d = json.loads(out.read_text())
    printed = capsys.readouterr().out
    assert d["credits_used"] == 6 and d["mode"] == "live" and d["prints"] == 20
    assert f"keyed fetch via ${tape.KEY_VARS[0]}" in printed and "6 credits — keyed" in printed
    assert "secret" not in printed


def test_running_the_file_as_a_script_replays_the_committed_tape(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tape.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    out = tmp_path / "bench.json"
    monkeypatch.setattr(
        sys, "argv", ["bench.py", "--replay", "--iterations", "1", "--json", str(out)]
    )
    runpy.run_path(str(ROOT / "scripts" / "bench.py"), run_name="__main__")
    d = json.loads(out.read_text())
    assert d["mode"] == "replay" and d["iterations"] == 1 and d["tape"].startswith("data/tape_")
    assert f"wrote {out}" in capsys.readouterr().out
