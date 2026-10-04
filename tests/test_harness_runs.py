"""Focused tests for the swegemma run archiver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kaggle_gemma_agent import harness_runs, run_report


def _make_results(root: Path) -> Path:
    """Build a synthetic ``--results-dir`` mirroring HARNESS_README section 9.2."""
    results = root / "results" / "run_01"
    for subdir in ("traces", "logs", "patches", "test_outputs"):
        (results / subdir).mkdir(parents=True, exist_ok=True)
    (results / "traces" / "trace_a__1.json").write_text('{"steps": []}\n', encoding="utf-8")
    (results / "logs" / "a__1.log").write_text("agent transcript\n", encoding="utf-8")
    (results / "patches" / "a__1.patch").write_text("--- a\n+++ b\n", encoding="utf-8")
    (results / "test_outputs" / "a__1.log").write_text("pytest output\n", encoding="utf-8")
    (results / "logs" / "b__2.log").write_text("only a log\n", encoding="utf-8")
    (results / "summary.json").write_text('{"resolved": 1}\n', encoding="utf-8")
    (results / "task_results.jsonl").write_text('{"id": "a__1"}\n', encoding="utf-8")
    return results


def test_discover_instance_ids_unions_artifact_dirs(tmp_path: Path) -> None:
    results = _make_results(tmp_path)

    assert harness_runs.discover_instance_ids(results) == ["a__1", "b__2"]
    assert harness_runs.discover_instance_ids(results / "missing") == []


def test_archive_run_rekeys_artifacts_and_writes_manifest(tmp_path: Path) -> None:
    results = _make_results(tmp_path)

    run_dir = harness_runs.archive_run(
        results,
        runs_root=tmp_path / "runs",
        timestamp="20260101T000000Z",
        finalize=False,
    )

    assert run_dir == tmp_path / "runs" / "20260101T000000Z"
    assert (run_dir / "a__1" / "trace.json").read_text(encoding="utf-8") == '{"steps": []}\n'
    assert (run_dir / "a__1" / "agent_patch.diff").is_file()
    assert (run_dir / "a__1" / "junit.xml").exists() is False
    assert (run_dir / harness_runs.RUN_SUMMARY).is_file()
    assert (run_dir / harness_runs.RUN_TASKS).is_file()

    manifest = json.loads((run_dir / harness_runs.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["task_count"] == 2
    assert manifest["junit_dir"] is None
    ids = {task["instance_id"] for task in manifest["tasks"]}
    assert ids == {"a__1", "b__2"}

    meta = json.loads((run_dir / "a__1" / "metadata.json").read_text(encoding="utf-8"))
    assert "trace.json" in meta["artifacts"]
    assert "junit.xml" not in meta["artifacts"]


def test_archive_run_records_sandbox_deps_mode(tmp_path: Path) -> None:
    results = _make_results(tmp_path)

    run_dir = harness_runs.archive_run(
        results,
        runs_root=tmp_path / "runs",
        timestamp="repaired",
        finalize=False,
        sandbox_deps_mode="repaired",
    )

    manifest = json.loads((run_dir / harness_runs.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["sandbox_deps_mode"] == "repaired"


def test_archive_run_records_absent_sandbox_deps_mode_as_none(tmp_path: Path) -> None:
    results = _make_results(tmp_path)

    run_dir = harness_runs.archive_run(
        results, runs_root=tmp_path / "runs", timestamp="faithful", finalize=False
    )

    manifest = json.loads((run_dir / harness_runs.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["sandbox_deps_mode"] is None


def test_archive_run_folds_in_junit_xml(tmp_path: Path) -> None:
    results = _make_results(tmp_path)
    junit = tmp_path / "junit"
    junit.mkdir()
    (junit / "_swegemma_junit_a__1.xml").write_text("<testsuite/>\n", encoding="utf-8")

    run_dir = harness_runs.archive_run(
        results, runs_root=tmp_path / "runs", junit_dir=junit, timestamp="ts", finalize=False
    )

    assert (run_dir / "a__1" / "junit.xml").read_text(encoding="utf-8") == "<testsuite/>\n"
    meta = json.loads((run_dir / "a__1" / "metadata.json").read_text(encoding="utf-8"))
    assert "junit.xml" in meta["artifacts"]


def test_archive_run_rejects_missing_source_and_existing_run(tmp_path: Path) -> None:
    with pytest.raises(harness_runs.HarnessRunsError):
        harness_runs.archive_run(tmp_path / "nope", runs_root=tmp_path / "runs")

    results = _make_results(tmp_path)
    harness_runs.archive_run(results, runs_root=tmp_path / "runs", timestamp="dup", finalize=False)
    with pytest.raises(harness_runs.HarnessRunsError):
        harness_runs.archive_run(
            results, runs_root=tmp_path / "runs", timestamp="dup", finalize=False
        )


def test_main_prints_archive_path_and_reports_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = _make_results(tmp_path)

    code = harness_runs.main(
        [str(results), "--runs-root", str(tmp_path / "runs"), "--timestamp", "ts"]
    )

    assert code == 0
    assert "archived" in capsys.readouterr().out
    assert harness_runs.main([str(tmp_path / "missing")]) == 1
    assert "error:" in capsys.readouterr().err


def test_archive_run_finalize_writes_report_status_and_index(tmp_path: Path) -> None:
    results = _make_results(tmp_path)
    junit = tmp_path / "junit"
    junit.mkdir()
    (junit / "_swegemma_junit_a__1.xml").write_text(
        '<testsuite tests="1"><testcase classname="t" name="test_ok"/></testsuite>\n',
        encoding="utf-8",
    )

    run_dir = harness_runs.archive_run(
        results,
        runs_root=tmp_path / "runs",
        junit_dir=junit,
        timestamp="ts",
        backend="test-backend",
    )

    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == run_report.SCHEMA_VERSION
    assert report["env"]["backend"] == "test-backend"
    assert (run_dir / "STATUS").is_file()
    assert (tmp_path / "runs" / "index.jsonl").is_file()

    index_line = (tmp_path / "runs" / "index.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(index_line)["run_id"] == "ts"


def test_main_archive_no_report_skips_handoff(tmp_path: Path) -> None:
    results = _make_results(tmp_path)

    code = harness_runs.main(
        [
            "archive",
            str(results),
            "--runs-root",
            str(tmp_path / "runs"),
            "--timestamp",
            "ts",
            "--no-report",
        ]
    )

    assert code == 0
    assert not (tmp_path / "runs" / "ts" / "report.json").exists()
    assert not (tmp_path / "runs" / "index.jsonl").exists()


def test_main_report_prints_status_and_rebuilds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = _make_results(tmp_path)
    run_dir = harness_runs.archive_run(
        results, runs_root=tmp_path / "runs", timestamp="ts", finalize=False
    )

    assert harness_runs.main(["report", str(run_dir), "--rebuild", "--tasks", "none.jsonl"]) == 0
    assert "PARTIAL" in capsys.readouterr().out

    assert harness_runs.main(["report", str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert "schema" in out
    assert (run_dir / "report.json").is_file()


def test_main_report_errors_on_missing_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert harness_runs.main(["report", str(tmp_path / "nope")]) == 1
    assert "error:" in capsys.readouterr().err
