"""Tests for the change-journal CI guard."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_journal_entry.py"
_spec = importlib.util.spec_from_file_location("check_journal_entry", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
guard = importlib.util.module_from_spec(_spec)
sys.modules["check_journal_entry"] = guard
_spec.loader.exec_module(guard)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo on ``main`` checked out on a ``feature`` branch."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "ci@example.com")
    _git(root, "config", "user.name", "CI")
    _write(root, "README.md", "base\n")
    _commit(root, "initial")
    _git(root, "checkout", "-b", "feature")
    return root


def _run(repo: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.chdir(repo)
    return guard.main(["--base", "main", "--head", "feature", *args])


def test_guarded_path_without_journal_entry_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "docs/notes.md", "note\n")
    _commit(repo, "docs change")

    assert _run(repo, monkeypatch) == 1

    captured = capsys.readouterr()
    assert "docs/notes.md" in captured.err
    assert "without a journal entry" in captured.err


def test_guarded_path_with_journal_entry_passes(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "docs/notes.md", "note\n")
    _write(repo, "docs/journal/events.jsonl", '{"id": "J-20261007-01"}\n')
    _commit(repo, "docs change with journal")

    assert _run(repo, monkeypatch) == 0

    assert "OK" in capsys.readouterr().out


def test_only_unguarded_paths_pass(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "README.md", "base\nmore\n")
    _commit(repo, "readme change")

    assert _run(repo, monkeypatch) == 0

    assert "OK" in capsys.readouterr().out


def test_run_report_is_guarded() -> None:
    assert guard.is_guarded("src/kaggle_gemma_agent/run_report.py") is True
    assert "src/kaggle_gemma_agent/run_report.py" in guard.GUARDED_FILES


def test_run_report_change_without_journal_entry_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "src/kaggle_gemma_agent/run_report.py", "x = 1\n")
    _commit(repo, "run_report change")

    assert _run(repo, monkeypatch) == 1

    assert "run_report.py" in capsys.readouterr().err


def test_no_journal_escape_passes_with_warning(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "submission/agent.yaml", "agent: x\n")
    _commit(repo, "submission change")

    code = _run(repo, monkeypatch, "--pr-title", "chore: bump [no-journal]")

    assert code == 0
    captured = capsys.readouterr()
    assert "no-journal" in captured.err
    assert "SKIPPED" in captured.err
