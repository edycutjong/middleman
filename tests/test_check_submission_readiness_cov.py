"""check_submission_readiness.py — the placeholder and stale-count gate, run against a fake
repo under tmp_path with the pytest collection stubbed out."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_submission_readiness as readiness  # noqa: E402

SCRIPT = ROOT / "scripts" / "check_submission_readiness.py"


class _Proc:
    def __init__(self, stdout="", stderr=""):
        self.stdout, self.stderr = stdout, stderr


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / "site" / "pitch").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def stub_collection(monkeypatch):
    calls = []

    def fake_run(cmd, cwd, capture_output, text):
        calls.append(cmd)
        if "not live" in cmd:
            return _Proc(stderr="128 tests collected")
        return _Proc(stdout="134/136 tests collected")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


# ── collected ────────────────────────────────────────────────────────────────────────────────


def test_collected_reads_total_and_offline_from_the_two_pytest_runs(repo, stub_collection):
    assert readiness.collected() == {"total": 134, "offline": 128}
    assert len(stub_collection) == 2
    assert stub_collection[1][-2:] == ["-m", "not live"]
    assert all(c[:3] == [sys.executable, "-m", "pytest"] for c in stub_collection)


def test_collected_reports_none_when_pytest_prints_no_count(repo, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout="no tests ran"))
    assert readiness.collected() == {"total": None, "offline": None}


def test_collected_accepts_the_singular_form_for_one_test(repo, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout="1 test collected"))
    assert readiness.collected() == {"total": 1, "offline": 1}


# ── scan ─────────────────────────────────────────────────────────────────────────────────────


def test_scan_lists_only_the_judge_facing_files_that_exist(repo):
    _write(repo, "README.md", "clean")
    _write(repo, "site/judge.html", "<p>clean</p>")
    _write(repo, "docs/b.md", "clean")
    _write(repo, "docs/a.md", "clean")
    _write(repo, ".github/PULL_REQUEST_TEMPLATE.md", "clean")
    _write(repo, "middleman/tape.py", "TODO: never scanned")
    scanned, findings = readiness.scan()
    assert scanned == [
        ".github/PULL_REQUEST_TEMPLATE.md",
        "README.md",
        "docs/a.md",
        "docs/b.md",
        "site/judge.html",
    ]
    assert findings == []


def test_scan_on_an_empty_repo_scans_nothing_and_finds_nothing(repo):
    assert readiness.scan() == ([], [])


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("send to 0x... on mainnet", "unfilled address"),
        ("watch https://youtu.be/xxx now", "placeholder video"),
        ("watch https://YOUTU.BE/VIDEO_ID now", "placeholder video"),
        ("https://www.youtube.com/watch?v=your-video", "placeholder video"),
        ("TODO write this", "TODO marker"),
        ("FIXME later", "TODO marker"),
        ("# [[FILL]]", "unreplaced template token"),
        ("# [Project Name]", "unreplaced template token"),
        ("git clone OWNER/REPO", "unreplaced template token"),
        ("deploy to [your-domain]", "unreplaced template token"),
        ("https://[domain]/app", "placeholder URL"),
        ("see example.com/your-org for details", "placeholder URL"),
    ],
)
def test_each_pattern_is_reported_with_its_kind_line_and_text(repo, text, kind):
    _write(repo, "README.md", f"ok\n{text}\n")
    _, findings = readiness.scan()
    assert findings == [{"file": "README.md", "line": 2, "kind": kind, "text": text}]


def test_a_line_with_several_hits_is_reported_once_under_the_first_pattern(repo):
    _write(repo, "DEMO.md", "TODO 0x... [[FILL]]")
    _, findings = readiness.scan()
    assert [f["kind"] for f in findings] == ["unfilled address"]


def test_todo_is_matched_as_a_whole_word_and_case_sensitively(repo):
    _write(repo, "JUDGE.md", "todos are fine\nTODOS too\nnoTODO\n")
    assert readiness.scan()[1] == []


def test_a_line_that_defines_a_pattern_is_not_a_violation(repo):
    _write(
        repo,
        "FEEDBACK.md",
        "the placeholder 0x... is rejected\n"
        "the readiness gate rejects TODO\n"
        "the scanner rejects [[FILL]]\n"
        "check_submission_readiness rejects OWNER/REPO\n",
    )
    assert readiness.scan()[1] == []


def test_reported_text_is_stripped_and_capped_at_110_characters(repo):
    _write(repo, "ARCHITECTURE.md", "   TODO " + "x" * 200 + "   \n")
    (_, [finding]) = readiness.scan()
    assert len(finding["text"]) == 110
    assert finding["text"].startswith("TODO x")


def test_undecodable_bytes_are_replaced_rather_than_crashing_the_scan(repo):
    (repo / "README.md").write_bytes(b"\xff\xfe TODO\n")
    assert readiness.scan()[1][0]["kind"] == "TODO marker"


def test_stale_counts_are_only_checked_when_a_total_is_known(repo):
    _write(repo, "README.md", "**999** tests pass\n")
    assert readiness.scan()[1] == []
    assert readiness.scan({"total": None, "offline": None})[1] == []
    assert readiness.scan({})[1] == []
    (finding,) = readiness.scan({"total": 134, "offline": 128})[1]
    assert finding["file"] == "README.md"
    assert finding["kind"] == "stale test count (suite has 134)"
    assert finding["text"] == "**999** tests pass"


def test_a_stale_count_finding_reports_the_line_it_was_found_on(repo):
    """The count loop once rebound `n`, so `line` carried the published number (999) instead
    of the line number; a reader chasing README.md:999 found nothing."""
    _write(repo, "README.md", "\n\n**999** tests pass\n")
    (finding,) = readiness.scan({"total": 134, "offline": 128})[1]
    assert finding["line"] == 3 and "999" in finding["text"]


def test_a_published_count_matching_total_or_offline_is_accepted(repo):
    _write(
        repo,
        "README.md",
        "**134** tests (128 offline)\n"
        "128 offline tests\n"
        "![ci](https://img.shields.io/badge/tests-134-green)\n"
        "| Tests | **128** |\n",
    )
    assert readiness.scan({"total": 134, "offline": 128})[1] == []


def test_every_count_form_is_recognised_and_flagged_when_stale(repo):
    _write(
        repo,
        "DEMO.md",
        "**135** tests\n"
        "129 offline tests\n"
        "https://img.shields.io/badge/tests-200-green\n"
        "| Tests | **77** |\n",
    )
    _, findings = readiness.scan({"total": 134, "offline": 128})
    assert [f["text"] for f in findings] == [
        "**135** tests",
        "129 offline tests",
        "https://img.shields.io/badge/tests-200-green",
        "| Tests | **77** |",
    ]
    assert {f["kind"] for f in findings} == {"stale test count (suite has 134)"}


def test_a_count_that_only_matches_the_total_passes_without_an_offline_number(repo):
    _write(repo, "README.md", "134 tests\n")
    assert readiness.scan({"total": 134})[1] == []


def test_a_placeholder_and_a_stale_count_on_the_same_line_are_both_reported(repo):
    _write(repo, "README.md", "TODO bump to **999** tests\n")
    _, findings = readiness.scan({"total": 134, "offline": 128})
    assert [f["kind"] for f in findings] == [
        "TODO marker",
        "stale test count (suite has 134)",
    ]


def test_two_stale_counts_on_one_line_are_each_reported(repo):
    _write(repo, "README.md", "**10** tests and 20 tests\n")
    _, findings = readiness.scan({"total": 134, "offline": 128})
    assert len(findings) == 2


# ── main ─────────────────────────────────────────────────────────────────────────────────────


def test_main_prints_the_scanned_files_the_suite_size_and_clean_and_exits_zero(
    repo, stub_collection, capsys
):
    _write(repo, "README.md", "**134** tests\n")
    assert readiness.main([]) == 0
    out = capsys.readouterr().out
    assert "scanned 1 judge-facing file(s)" in out
    assert "  · README.md" in out
    assert "suite: 134 tests (128 offline)" in out
    assert out.rstrip().endswith("template tokens, stale counts")


def test_main_lists_findings_and_exits_one(repo, stub_collection, capsys):
    _write(repo, "README.md", "fine\nTODO fix\n")
    assert readiness.main([]) == 1
    out = capsys.readouterr().out
    assert "1 finding(s):" in out
    assert "  README.md:2  [TODO marker]  TODO fix" in out
    assert "clean" not in out


def test_no_count_skips_the_pytest_collection_and_the_suite_line(repo, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("pytest must not be collected with --no-count")

    monkeypatch.setattr(subprocess, "run", boom)
    _write(repo, "README.md", "**999** tests\n")
    assert readiness.main(["--no-count"]) == 0
    assert "suite:" not in capsys.readouterr().out


def test_json_output_carries_scanned_counts_and_findings(repo, stub_collection, capsys):
    _write(repo, "README.md", "0x...\n")
    assert readiness.main(["--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["scanned"] == ["README.md"]
    assert doc["counts"] == {"total": 134, "offline": 128}
    assert doc["findings"] == [
        {"file": "README.md", "line": 1, "kind": "unfilled address", "text": "0x..."}
    ]


def test_json_output_with_no_count_reports_null_counts(repo, capsys):
    assert readiness.main(["--json", "--no-count"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "scanned": [],
        "counts": None,
        "findings": [],
    }


def test_running_the_script_directly_exits_with_the_readiness_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["check_submission_readiness.py", "--no-count"])
    _write(tmp_path, "README.md", "TODO finish\n")
    code = compile(SCRIPT.read_text(), str(SCRIPT), "exec")
    scope = {"__name__": "__main__", "__file__": str(tmp_path / "scripts" / SCRIPT.name)}
    with pytest.raises(SystemExit) as exc:
        exec(code, scope)  # noqa: S102
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "scanned" in out and "[TODO marker]" in out
