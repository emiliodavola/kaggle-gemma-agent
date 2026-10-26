"""Focused tests for the WSL -> Windows artifact copy script."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "host-trial" / "copy_run_artifacts.py"
)
_spec = importlib.util.spec_from_file_location("copy_run_artifacts", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
copier = importlib.util.module_from_spec(_spec)
sys.modules["copy_run_artifacts"] = copier
_spec.loader.exec_module(copier)

OLD_MTIME = 1_600_000_000.0


def _write(path: Path, text: str, *, mtime: float = OLD_MTIME) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _source_repo(root: Path) -> Path:
    _write(root / "docs" / "journal" / "events.jsonl", '{"id": "J-1"}\n')
    _write(root / "docs" / "journal" / "20261026.md", "# Change journal\n")
    _write(root / "results" / "run_01" / "summary.json", "{}\n")
    _write(root / "results" / "run_01" / "patches" / "task_a.patch", "diff\n")
    _write(root / "runs" / "20261026T122756Z" / "report.json", '{"status": "DONE"}\n')
    return root


def test_copy_artifacts_copies_the_three_trees(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    dest = tmp_path / "windows-repo"

    summary = copier.copy_artifacts(source, dest, dry_run=False)

    copied_events = (dest / "docs" / "journal" / "events.jsonl").read_text(encoding="utf-8")
    assert copied_events == '{"id": "J-1"}\n'
    assert (dest / "docs" / "journal" / "20261026.md").is_file()
    assert (dest / "results" / "run_01" / "summary.json").is_file()
    assert (dest / "results" / "run_01" / "patches" / "task_a.patch").is_file()
    assert (dest / "runs" / "20261026T122756Z" / "report.json").is_file()
    assert summary.copied_files == 5
    assert summary.missing_trees == ()
    trees = {tree.name: tree for tree in summary.trees}
    assert [tree.name for tree in summary.trees] == ["docs/journal", "results", "runs"]
    assert [entry.relative for entry in trees["results"].copied] == [
        "results/run_01/patches/task_a.patch",
        "results/run_01/summary.json",
    ]
    assert trees["runs"].copied[0].relative == "runs/20261026T122756Z/report.json"


def test_copy_artifacts_preserves_mtime_so_a_rerun_skips(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    dest = tmp_path / "windows-repo"
    original = source / "runs" / "20261026T122756Z" / "report.json"

    copier.copy_artifacts(source, dest, dry_run=False)
    copied = dest / "runs" / "20261026T122756Z" / "report.json"
    assert copied.stat().st_mtime == pytest.approx(original.stat().st_mtime, abs=1.0)

    again = copier.copy_artifacts(source, dest, dry_run=False)
    assert again.copied_files == 0
    assert again.unchanged_files == 5


def test_copy_artifacts_recopies_an_updated_file(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    dest = tmp_path / "windows-repo"
    copier.copy_artifacts(source, dest, dry_run=False)

    _write(source / "results" / "run_01" / "summary.json", '{"rate": 0.5}\n')
    # Same byte count, newer mtime: the mtime branch must trigger the copy.
    _write(source / "runs" / "20261026T122756Z" / "report.json", '{"status": "PARTIALx"}\n')

    summary = copier.copy_artifacts(source, dest, dry_run=False)

    assert summary.copied_files == 2
    assert summary.unchanged_files == 3
    assert (dest / "results" / "run_01" / "summary.json").read_text(encoding="utf-8") == (
        '{"rate": 0.5}\n'
    )


def test_copy_artifacts_reports_a_missing_tree_without_failing(tmp_path: Path) -> None:
    source = tmp_path / "wsl-repo"
    _write(source / "runs" / "R1" / "report.json", "{}\n")
    dest = tmp_path / "windows-repo"

    summary = copier.copy_artifacts(source, dest, dry_run=False)

    trees = {tree.name: tree for tree in summary.trees}
    assert trees["docs/journal"].missing is True
    assert trees["results"].missing is True
    assert trees["runs"].missing is False
    assert summary.copied_files == 1
    assert summary.missing_trees == ("docs/journal", "results")
    assert (dest / "runs" / "R1" / "report.json").is_file()


def test_copy_artifacts_rejects_a_missing_source(tmp_path: Path) -> None:
    with pytest.raises(copier.CopyError, match="source repository not found"):
        copier.copy_artifacts(tmp_path / "nope", tmp_path / "windows-repo", dry_run=False)


def test_copy_artifacts_rejects_a_source_without_artifact_dirs(tmp_path: Path) -> None:
    source = tmp_path / "unrelated"
    _write(source / "README.md", "not a repo\n")

    with pytest.raises(copier.CopyError, match="docs/journal"):
        copier.copy_artifacts(source, tmp_path / "windows-repo", dry_run=False)


def test_copy_artifacts_rejects_identical_roots(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")

    with pytest.raises(copier.CopyError, match="same directory"):
        copier.copy_artifacts(source, source, dry_run=False)


def test_copy_artifacts_rejects_a_dest_inside_the_source(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")

    with pytest.raises(copier.CopyError, match="overlap"):
        copier.copy_artifacts(source, source / "runs" / "mirror", dry_run=False)


def test_copy_artifacts_dry_run_writes_nothing(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    dest = tmp_path / "windows-repo"

    summary = copier.copy_artifacts(source, dest, dry_run=True)

    assert summary.dry_run is True
    assert summary.copied_files == 5
    assert not dest.exists()


def test_copy_artifacts_force_recopies_unchanged_files(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    dest = tmp_path / "windows-repo"
    copier.copy_artifacts(source, dest, dry_run=False)

    summary = copier.copy_artifacts(source, dest, dry_run=False, force=True)

    assert summary.copied_files == 5
    assert summary.unchanged_files == 0


def test_format_summary_names_both_roots_and_the_totals(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    dest = tmp_path / "windows-repo"
    summary = copier.copy_artifacts(source, dest, dry_run=False)

    text = copier.format_summary(summary)

    assert str(source) in text
    assert str(dest) in text
    assert "total" in text
    assert "5 file(s)" in text
    assert "docs/journal" in text


def test_format_summary_marks_a_dry_run(tmp_path: Path) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    summary = copier.copy_artifacts(source, tmp_path / "windows-repo", dry_run=True)

    text = copier.format_summary(summary)

    assert "dry run" in text
    assert "would copy" in text


def test_main_copies_and_returns_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _source_repo(tmp_path / "wsl-repo")
    dest = tmp_path / "windows-repo"

    exit_code = copier.main(["--source", str(source), "--dest", str(dest)])

    assert exit_code == 0
    assert (dest / "runs" / "20261026T122756Z" / "report.json").is_file()
    assert "total" in capsys.readouterr().out


def test_main_returns_two_on_a_bad_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = copier.main(["--source", str(tmp_path / "nope"), "--dest", str(tmp_path / "out")])

    assert exit_code == 2
    assert "ERROR" in capsys.readouterr().err
