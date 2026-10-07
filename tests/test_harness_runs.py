"""Focused tests for the swegemma run archiver."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from kaggle_gemma_agent import harness_runs, journal, run_report


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
        [
            str(results),
            "--runs-root",
            str(tmp_path / "runs"),
            "--timestamp",
            "ts",
            "--no-journal",
        ]
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
            "--no-journal",
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

    rebuilt = harness_runs.main(
        ["report", str(run_dir), "--rebuild", "--tasks", "none.jsonl", "--no-journal"]
    )
    assert rebuilt == 0
    assert "PARTIAL" in capsys.readouterr().out

    assert harness_runs.main(["report", str(run_dir), "--no-journal"]) == 0
    out = capsys.readouterr().out
    assert "schema" in out
    assert (run_dir / "report.json").is_file()


def test_main_report_errors_on_missing_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert harness_runs.main(["report", str(tmp_path / "nope")]) == 1
    assert "error:" in capsys.readouterr().err


def _sha256_text(text: str) -> str:
    """Return the hex ``sha256`` of *text* as the tests compute it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_submission(root: Path) -> dict[str, str]:
    """Write the three hashed submission files and return their expected digests."""
    files = {
        harness_runs.PROMPT_FILE: "prompt-body\n",
        harness_runs.SAMPLING_FILE: "temperature: 0\n",
        harness_runs.EVAL_CONFIG_FILE: "budget: 1\n",
    }
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return {relative: _sha256_text(text) for relative, text in files.items()}


def _archived_failing_run(root: Path) -> Path:
    """Archive a synthetic one-task failing run so the report has a failure kind."""
    results = root / "results" / "run_01"
    for subdir in ("traces", "logs", "patches", "test_outputs"):
        (results / subdir).mkdir(parents=True, exist_ok=True)
    (results / "logs" / "a__1.log").write_text("agent transcript\n", encoding="utf-8")
    (results / "patches" / "a__1.patch").write_text("--- a\n+++ b\n", encoding="utf-8")
    (results / "test_outputs" / "a__1.log").write_text(
        "=== FAILURES ===\ntest_x failed\n", encoding="utf-8"
    )
    (results / "summary.json").write_text('{"resolved": 0, "total": 1}\n', encoding="utf-8")
    (results / "task_results.jsonl").write_text(
        '{"id": "a__1", "resolved": false}\n', encoding="utf-8"
    )
    return harness_runs.archive_run(
        results,
        runs_root=root / "runs",
        timestamp="20260101T000000Z",
        backend="test-backend",
    )


def _git(_root: Path, *_args: str) -> None:
    """Run a git command in a throwaway repository for the repo_commit test."""
    subprocess.run(["git", *_args], cwd=_root, check=True, capture_output=True, text=True)


def test_emit_run_finished_records_hashes_counts_and_evidence(tmp_path: Path) -> None:
    run_dir = _archived_failing_run(tmp_path)
    expected = _write_submission(tmp_path)
    journal_root = tmp_path / "journal"

    assert harness_runs.emit_run_finished(run_dir, journal_root=journal_root, repo_root=tmp_path)

    events = journal.read_events(journal_root)
    assert len(events) == 1
    event = events[0]
    assert tuple(event.keys()) == journal.EVENT_KEYS
    assert event["type"] == "run_finished"
    assert event["actor"] == "runner"
    assert event["status"] == "applied"
    assert event["refs"]["run_id"] == "20260101T000000Z"
    assert event["hashes"]["prompt"] == expected[harness_runs.PROMPT_FILE]
    assert event["hashes"]["sampling"] == expected[harness_runs.SAMPLING_FILE]
    assert event["hashes"]["eval_config"] == expected[harness_runs.EVAL_CONFIG_FILE]
    assert event["hashes"]["repo_commit"] is None
    assert event["counts"] == {
        "tasks": 1,
        "resolved": 0,
        "rate": 0.0,
        "test_failure": 1,
    }
    assert event["evidence"] == [
        str(run_dir / "report.json"),
        str(run_dir / "STATUS"),
        str(tmp_path / "runs" / "index.jsonl"),
    ]


def test_emit_run_finished_rounds_rate_to_four_decimals(tmp_path: Path) -> None:
    results = tmp_path / "results" / "run_01"
    for subdir in ("traces", "logs", "patches", "test_outputs"):
        (results / subdir).mkdir(parents=True, exist_ok=True)
    for instance_id in ("a__1", "b__2", "c__3"):
        (results / "logs" / f"{instance_id}.log").write_text("agent transcript\n", encoding="utf-8")
        (results / "patches" / f"{instance_id}.patch").write_text(
            "--- a\n+++ b\n", encoding="utf-8"
        )
        (results / "test_outputs" / f"{instance_id}.log").write_text(
            "=== FAILURES ===\ntest_x failed\n", encoding="utf-8"
        )
    (results / "summary.json").write_text('{"resolved": 1, "total": 3}\n', encoding="utf-8")
    (results / "task_results.jsonl").write_text(
        '{"id": "a__1", "resolved": true}\n'
        '{"id": "b__2", "resolved": false}\n'
        '{"id": "c__3", "resolved": false}\n',
        encoding="utf-8",
    )
    run_dir = harness_runs.archive_run(
        results,
        runs_root=tmp_path / "runs",
        timestamp="20260101T000000Z",
        backend="test-backend",
    )
    journal_root = tmp_path / "journal"

    assert harness_runs.emit_run_finished(run_dir, journal_root=journal_root, repo_root=tmp_path)

    event = journal.read_events(journal_root)[0]
    assert event["counts"]["tasks"] == 3
    assert event["counts"]["resolved"] == 1
    assert event["counts"]["rate"] == 0.3333
    assert event["counts"]["rate"] != 1 / 3


def test_emit_run_finished_uses_null_for_missing_files(tmp_path: Path) -> None:
    run_dir = _archived_failing_run(tmp_path)
    journal_root = tmp_path / "journal"

    assert harness_runs.emit_run_finished(run_dir, journal_root=journal_root, repo_root=tmp_path)

    event = journal.read_events(journal_root)[0]
    assert event["hashes"] == {
        "prompt": None,
        "sampling": None,
        "eval_config": None,
        "repo_commit": None,
    }


def test_emit_run_finished_is_idempotent(tmp_path: Path) -> None:
    run_dir = _archived_failing_run(tmp_path)
    journal_root = tmp_path / "journal"

    assert harness_runs.emit_run_finished(run_dir, journal_root=journal_root, repo_root=tmp_path)
    assert harness_runs.emit_run_finished(run_dir, journal_root=journal_root, repo_root=tmp_path)

    assert len(journal.read_events(journal_root)) == 1


def test_emit_run_finished_warns_when_journal_unwritable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = _archived_failing_run(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory\n", encoding="utf-8")

    recorded = harness_runs.emit_run_finished(
        run_dir, journal_root=blocker / "journal", repo_root=tmp_path
    )

    assert recorded is False
    assert "warning:" in capsys.readouterr().err


def test_repo_commit_is_clean_sha_then_dirty(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-m", "init")

    clean = harness_runs.repo_commit(tmp_path)
    assert clean is not None
    assert len(clean) == 40

    (tmp_path / "f.txt").write_text("y\n", encoding="utf-8")
    assert harness_runs.repo_commit(tmp_path) == f"{clean}-dirty"

    assert harness_runs.repo_commit(tmp_path / "not-a-repo") is None


def test_main_archive_no_journal_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    results = _make_results(tmp_path)
    calls: list[Path] = []
    monkeypatch.setattr(
        harness_runs,
        "emit_run_finished",
        lambda run_dir, **kwargs: calls.append(run_dir) or True,
    )

    assert (
        harness_runs.main(
            [str(results), "--runs-root", str(tmp_path / "runs"), "--timestamp", "ts"]
        )
        == 0
    )
    assert calls == [tmp_path / "runs" / "ts"]

    calls.clear()
    assert (
        harness_runs.main(
            [
                str(results),
                "--runs-root",
                str(tmp_path / "runs"),
                "--timestamp",
                "ts2",
                "--no-journal",
            ]
        )
        == 0
    )
    assert calls == []


def test_main_report_no_journal_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    results = _make_results(tmp_path)
    run_dir = harness_runs.archive_run(
        results, runs_root=tmp_path / "runs", timestamp="ts", finalize=True
    )
    calls: list[Path] = []
    monkeypatch.setattr(
        harness_runs,
        "emit_run_finished",
        lambda run_dir, **kwargs: calls.append(run_dir) or True,
    )

    assert harness_runs.main(["report", str(run_dir)]) == 0
    assert calls == [run_dir]

    calls.clear()
    assert harness_runs.main(["report", str(run_dir), "--no-journal"]) == 0
    assert calls == []
