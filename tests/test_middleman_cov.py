"""scripts/middleman.py — the door: importable without running, and running means cli.main."""

import importlib.util
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOOR = ROOT / "scripts" / "middleman.py"

from middleman import cli  # noqa: E402


@pytest.fixture
def engine(monkeypatch):
    """cli.main replaced by a recorder, so the door can be opened with the socket unplugged."""
    calls = []
    monkeypatch.setattr(cli, "main", lambda argv=None: calls.append(argv))
    return calls


def test_importing_the_door_puts_the_engine_on_the_path_without_running_it(engine, monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location("middleman_door", DOOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main is cli.main and sys.path[0] == str(ROOT)
    assert engine == []


def test_running_the_door_as_a_script_hands_the_command_line_to_the_engine(engine, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["middleman.py", "--address", "0xabc", "--pages", "1"])
    runpy.run_path(str(DOOR), run_name="__main__")
    assert engine == [None]
