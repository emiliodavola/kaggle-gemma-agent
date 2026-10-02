"""Tests for the file-based run report handoff (``run_report``)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from kaggle_gemma_agent import run_report

JUNIT_ALL = """\
<testsuites>
  <testsuite name="suite">
    <testcase classname="tests.t" name="test_a"/>
    <testcase classname="tests.t" name="test_b"><failure message="boom"/></testcase>
    <testcase classname="tests.t" name="test_c"><error message="err"/></testcase>
    <testcase classname="tests.t" name="test_d"><skipped/></testcase>
  </testsuite>
</testsuites>
"""


def _make_run(root: Path, *, status: str = "done") -> Path:
    """Build an archived run directory resembling ``harness_runs.archive_run``."""
    run_dir = root / "runs" / "20260101T000000Z"
    task_a = run_dir / "a__1"
    task_b = run_dir / "b__2"
    task_a.mkdir(parents=True)
    task_b.mkdir(parents=True)

    (task_a / "agent_patch.diff").write_text("--- a\n+++ b\n+fixed\n", encoding="utf-8")
    (task_a / "test_output.log").write_text("1 passed\n", encoding="utf-8")
    (task_a / "trace.json").write_text('{"steps": []}\n', encoding="utf-8")
    (task_b / "session.log").write_text("only transcript\n", encoding="utf-8")

    if status == "done":
        (task_a / "junit.xml").write_text(
            '<testsuite><testcase classname="tests.t" name="test_ok"/></testsuite>\n',
            encoding="utf-8",
        )
        (run_dir / "summary.json").write_text(
            json.dumps({"resolution_rate": 1.0, "resolved": 1, "total": 2, "errors": []}),
            encoding="utf-8",
        )
        (run_dir / "task_results.jsonl").write_text(
            json.dumps(
                {
                    "instance_id": "a__1",
                    "resolved": True,
                    "tool_calls_used": 12,
                    "turns": 5,
                    "agent_elapsed_seconds": 120.0,
                }
            )
            + "\n"
            + json.dumps({"instance_id": "b__2", "resolved": False, "error": "patch failed"})
            + "\n",
            encoding="utf-8",
        )
    return run_dir


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #
def test_detect_environment_redacts_credentials() -> None:
    environ = {
        "ROBOTINA_HERMES_MODEL": "muse-spark",
        "ROBOTINA_HERMES_MODEL_BASE_URL": "https://api.example.com/v1?token=leak",
        "OPENCODE_GO_API_KEY": "super-secret-value",
        "SOME_PASSWORD": "hunter2",
        "PATH": "/usr/bin",
    }

    info = run_report.detect_environment(environ, docker_version="27.3.1")

    assert info["backend"] == "muse-spark"
    assert info["backend_base_host"] == "api.example.com"
    assert info["docker"] == "27.3.1"
    assert info["safe_env_names"] == [
        "ROBOTINA_HERMES_MODEL",
        "ROBOTINA_HERMES_MODEL_BASE_URL",
    ]
    assert info["credential_vars_present"] == ["OPENCODE_GO_API_KEY", "SOME_PASSWORD"]
    assert "super-secret-value" not in json.dumps(info)
    assert "hunter2" not in json.dumps(info)


def test_detect_environment_defaults_and_docker_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        stdout = "Docker version 27.0\n"
        stderr = ""

    monkeypatch.setattr(run_report.subprocess, "run", lambda *a, **k: _Proc())
    assert run_report._detect_docker_version() == "Docker version 27.0"

    def _boom(*a: object, **k: object) -> object:
        raise OSError("docker missing")

    monkeypatch.setattr(run_report.subprocess, "run", _boom)
    assert run_report._detect_docker_version() == "unknown"

    info = run_report.detect_environment({}, docker_version="unknown")
    assert info["backend"] == "unknown"
    assert info["backend_base_host"] is None


def test_url_host_returns_none_on_invalid_url() -> None:
    assert run_report._url_host("https://user:pw@example.com:8443/x") == "example.com"
    assert run_report._url_host("http://[::1") is None


# --------------------------------------------------------------------------- #
# junit + helpers
# --------------------------------------------------------------------------- #
def test_parse_junit_counts_and_outcomes(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text(JUNIT_ALL, encoding="utf-8")

    parsed = run_report.parse_junit(path)

    assert parsed["tests"] == 4
    assert parsed["failures"] == 1
    assert parsed["errors"] == 1
    assert parsed["skipped"] == 1
    assert parsed["passed"] == 1
    assert [case["status"] for case in parsed["testcases"]] == [
        "passed",
        "failed",
        "error",
        "skipped",
    ]
    assert parsed["cases_truncated"] is False


def test_parse_junit_handles_namespaces_and_truncation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_report, "JUNIT_MAX_CASES", 1)
    path = tmp_path / "junit.xml"
    path.write_text(
        '<ns:testsuite xmlns:ns="x"><ns:testcase name="a"/><ns:testcase name="b"/></ns:testsuite>',
        encoding="utf-8",
    )

    parsed = run_report.parse_junit(path)

    assert parsed["tests"] == 2
    assert len(parsed["testcases"]) == 1
    assert parsed["cases_truncated"] is True


def test_parse_junit_invalid_raises(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text("<not xml", encoding="utf-8")
    with pytest.raises(run_report.RunReportError):
        run_report.parse_junit(path)


def test_read_tail_and_missing(tmp_path: Path) -> None:
    path = tmp_path / "log.log"
    path.write_text("abcdefghij", encoding="utf-8")

    assert run_report._read_tail(path, cap=4) == ("ghij", True)
    assert run_report._read_tail(path, cap=100) == ("abcdefghij", False)
    assert run_report._read_tail(tmp_path / "nope") == ("", False)


def test_as_list_variants() -> None:
    assert run_report._as_list(None) == []
    assert run_report._as_list("") == []
    assert run_report._as_list("a b,c") == ["a", "b", "c"]
    assert run_report._as_list('["x", "y"]') == ["x", "y"]
    assert run_report._as_list(["z"]) == ["z"]
    assert run_report._as_list(5) == ["5"]
    assert run_report._as_list("[not json") == ["[not", "json"]


def test_load_task_metadata_and_patch_ids(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(
        json.dumps(
            {
                "instance_id": "a__1",
                "repo": "org/repo",
                "test_patch": "+def test_new():\n+    assert True\n old line\n",
            }
        )
        + "\nnot json\n",
        encoding="utf-8",
    )

    meta = run_report.load_task_metadata(tasks)

    assert meta["a__1"]["repo"] == "org/repo"
    assert run_report.extract_patch_test_ids(meta["a__1"]["test_patch"]) == ["test_new"]
    assert run_report.load_task_metadata(None) == {}


def test_coercion_helpers() -> None:
    assert run_report._coerce_bool("yes") is True
    assert run_report._coerce_bool("failed") is False
    assert run_report._coerce_bool("maybe") is None
    assert run_report._coerce_bool(1) is True
    assert run_report._coerce_bool(0) is False
    assert run_report._coerce_float("12.5") == 12.5
    assert run_report._coerce_float(True) is None
    assert run_report._coerce_int("3") == 3
    assert run_report._first({"Resolved": True}, ("resolved",)) is True
    assert run_report._string_or_none({"a": 1}) == '{"a": 1}'


def test_annotate_required_reports_missing_node() -> None:
    annotated = run_report._annotate_required(["test_absent"], {"tests.t::test_a": "passed"})
    assert annotated["missing"] == ["test_absent"]
    assert annotated["observed"] == {}


# --------------------------------------------------------------------------- #
# build_report
# --------------------------------------------------------------------------- #
def test_build_report_done(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)

    report = run_report.build_report(
        run_dir, backend="test-backend", environ={}, docker_version="test"
    )

    assert report["status"] == run_report.STATUS_DONE
    assert report["schema_version"] == run_report.SCHEMA_VERSION
    assert report["env"]["backend"] == "test-backend"
    assert report["totals"]["tasks"] == 2
    assert report["totals"]["resolved"] == 1
    assert report["totals"]["resolution_rate"] == 0.5
    assert report["totals"]["tool_calls"] == 12
    assert report["totals"]["wall_seconds"] == 120.0

    task_a = next(task for task in report["tasks"] if task["instance_id"] == "a__1")
    assert task_a["status"] == "pass"
    assert task_a["patch_sha256"] is not None
    assert task_a["failure_tail"] is None
    assert "a__1/agent_patch.diff" in task_a["artifacts"]
    assert task_a["artifacts"]["a__1/agent_patch.diff"]["size"] > 0
    assert task_a["junit"]["passed"] == 1
    assert task_a["pass_to_pass"]["passed"] == ["tests.t::test_ok"]

    task_b = next(task for task in report["tasks"] if task["instance_id"] == "b__2")
    assert task_b["status"] == "fail"
    assert task_b["error"] == "patch failed"
    assert task_b["failure_tail"]["source"] == "session.log"


def test_build_report_partial_and_blocked(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path, status="partial")
    partial = run_report.build_report(run_dir, environ={}, docker_version="test")
    assert partial["status"] == run_report.STATUS_PARTIAL
    assert any("summary.json missing" in reason for reason in partial["status_reasons"])

    empty = tmp_path / "empty"
    empty.mkdir()
    blocked = run_report.build_report(empty, environ={}, docker_version="test")
    assert blocked["status"] == run_report.STATUS_BLOCKED
    assert blocked["totals"]["tasks"] == 0


def test_build_report_explicit_fail_to_pass(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    (run_dir / "a__1" / "junit.xml").write_text(JUNIT_ALL, encoding="utf-8")
    (run_dir / "task_results.jsonl").write_text(
        json.dumps(
            {
                "instance_id": "a__1",
                "resolved": False,
                "FAIL_TO_PASS": ["test_b"],
                "PASS_TO_PASS": ["test_a"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_report.build_report(run_dir, environ={}, docker_version="test")
    task_a = report["tasks"][0]

    assert task_a["fail_to_pass"]["failed"] == ["test_b"]
    assert task_a["pass_to_pass"]["passed"] == ["test_a"]


def test_build_report_truncates_failure_tail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_report, "FAILURE_TAIL_CHARS", 10)
    run_dir = _make_run(tmp_path)
    (run_dir / "b__2" / "session.log").write_text("x" * 50, encoding="utf-8")

    report = run_report.build_report(run_dir, environ={}, docker_version="test")
    task_b = next(task for task in report["tasks"] if task["instance_id"] == "b__2")

    assert task_b["failure_tail"]["truncated"] is True
    assert task_b["failure_tail"]["chars"] == 10


def test_classify_failure_variants() -> None:
    assert run_report._classify_failure("") is None
    assert run_report._classify_failure("1 passed\n") == "unknown"

    collection = (
        "ERROR collecting tests/test_sse.py\n"
        "ImportError while importing test module '/workspace/tests/test_sse.py'.\n"
        "E   ModuleNotFoundError: No module named 'starlette'\n"
        "!!!! Interrupted: 1 error during collection !!!!\n"
    )
    assert run_report._classify_failure(collection) == "collection_error"
    assert (
        run_report._classify_failure("===== FAILURES =====\nFAILED tests/t.py::test_a\n")
        == "test_failure"
    )
    assert run_report._classify_failure("pytest-timeout: timed out after 300s\n") == "timeout"


def test_build_report_classifies_collection_error(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    (run_dir / "b__2" / "test_output.log").write_text(
        "ERROR collecting tests/test_sse.py\n"
        "E   ModuleNotFoundError: No module named 'starlette'\n"
        "!!!! Interrupted: 1 error during collection !!!!\n",
        encoding="utf-8",
    )

    report = run_report.build_report(run_dir, environ={}, docker_version="test")
    task_a = next(task for task in report["tasks"] if task["instance_id"] == "a__1")
    task_b = next(task for task in report["tasks"] if task["instance_id"] == "b__2")

    assert task_a["failure_kind"] is None
    assert task_b["failure_kind"] == "collection_error"

    text = run_report.render_summary(report)
    assert "failures 1" in text
    assert "kinds collection_error=1" in text


def test_build_report_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(run_report.RunReportError):
        run_report.build_report(tmp_path / "nope")


def test_build_report_uses_tasks_metadata_test_sets(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    (run_dir / "a__1" / "junit.xml").write_text(JUNIT_ALL, encoding="utf-8")
    meta = {"a__1": {"repo": "org/repo", "FAIL_TO_PASS": ["test_c"], "PASS_TO_PASS": ["test_a"]}}

    report = run_report.build_report(run_dir, tasks_meta=meta, environ={}, docker_version="test")
    task_a = report["tasks"][0]

    assert task_a["repo"] == "org/repo"
    assert task_a["fail_to_pass"]["observed"]["test_c"] == "error"
    assert task_a["pass_to_pass"]["passed"] == ["test_a"]


def test_build_report_summary_errors_make_partial(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    (run_dir / "summary.json").write_text(
        json.dumps({"resolved": 1, "total": 2, "errors": ["boom"]}), encoding="utf-8"
    )

    report = run_report.build_report(run_dir, environ={}, docker_version="test")

    assert report["status"] == run_report.STATUS_PARTIAL
    assert any("harness error" in reason for reason in report["status_reasons"])


def test_build_report_notes_invalid_task_results(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    (run_dir / "task_results.jsonl").write_text(
        "not json\n" + json.dumps([1, 2]) + "\n" + json.dumps({"no_id": True}) + "\n" + "\n",
        encoding="utf-8",
    )

    report = run_report.build_report(run_dir, environ={}, docker_version="test")

    assert len(report["notes"]) == 3


# --------------------------------------------------------------------------- #
# write / load / render
# --------------------------------------------------------------------------- #
def test_write_report_splits_and_load_report_reassembles(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    report: dict[str, Any] = {
        "schema_version": run_report.SCHEMA_VERSION,
        "run_id": "run",
        "tasks": [{"instance_id": f"t{i}"} for i in range(5)],
    }

    run_report.write_report(run_dir, report, max_tasks=2)

    written = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert written["parts"] == 3
    assert written["part_files"] == ["report.part0002.json", "report.part0003.json"]
    assert (run_dir / "report.part0002.json").is_file()
    assert len(report["tasks"]) == 5

    loaded = run_report.load_report(run_dir)
    assert len(loaded["tasks"]) == 5
    assert loaded["tasks"][0]["instance_id"] == "t0"


def test_write_report_empty_tasks(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run_report.write_report(run_dir, {"run_id": "run", "tasks": []})
    assert (run_dir / "report.json").is_file()
    assert run_report.load_report(run_dir)["tasks"] == []


def test_load_report_missing_raises(tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    with pytest.raises(run_report.RunReportError):
        run_report.load_report(tmp_path / "run")


def test_load_report_skips_malformed_part(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps({"run_id": "run", "tasks": [], "part_files": ["report.part0002.json"]}),
        encoding="utf-8",
    )
    (run_dir / "report.part0002.json").write_text("not json", encoding="utf-8")

    assert run_report.load_report(run_dir)["tasks"] == []


def test_render_summary_lines(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    report = run_report.build_report(run_dir, environ={}, docker_version="test")
    report["report_path"] = str(run_dir / "report.json")
    report["index_path"] = str(tmp_path / "runs" / "index.jsonl")

    text = run_report.render_summary(report)

    lines = text.strip().splitlines()
    assert len(lines) == 6
    assert lines[0] == run_report.STATUS_DONE
    assert "rate 0.500" in text
    assert "tool_calls 12/200" in text
    assert "failures 1" in text
    assert "schema 1.0" in text


def test_render_summary_without_metrics() -> None:
    text = run_report.render_summary({"status": run_report.STATUS_BLOCKED, "tasks": []})
    assert text.startswith(run_report.STATUS_BLOCKED)
    assert "rate n/a" in text


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #
def test_append_index_and_compaction(tmp_path: Path) -> None:
    index = tmp_path / "runs" / "index.jsonl"
    compacted = False

    for number in range(4):
        compacted = run_report.append_index(
            index,
            {"run_id": f"r{number}", "tasks": number},
            max_lines=3,
            keep=2,
        )

    assert compacted is True
    lines = [line for line in index.read_text(encoding="utf-8").splitlines() if line]
    assert [json.loads(line)["run_id"] for line in lines] == ["r2", "r3"]
    archive = tmp_path / "runs" / run_report.INDEX_ARCHIVE_DIR
    assert {path.name for path in archive.iterdir()} == {"r0__r1.jsonl"}


def test_line_run_id_invalid() -> None:
    assert run_report._line_run_id("not json") == ""
    assert run_report._line_run_id(json.dumps({"run_id": "x"})) == "x"


def test_index_entry_from_report() -> None:
    entry = run_report.index_entry(
        {
            "run_id": "r",
            "generated_at": "t",
            "status": run_report.STATUS_DONE,
            "env": {"backend": "b"},
            "totals": {"tasks": 2, "resolved": 1, "resolution_rate": 0.5},
        }
    )
    assert entry["report"] == "r/report.json"
    assert entry["rate"] == 0.5


# --------------------------------------------------------------------------- #
# finalize + read_status
# --------------------------------------------------------------------------- #
def test_finalize_run_writes_handoff(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)

    report = run_report.finalize_run(
        run_dir, runs_root=tmp_path / "runs", environ={}, docker_version="test"
    )

    assert (run_dir / "report.json").is_file()
    assert (run_dir / run_report.STATUS_FILE).is_file()
    index = tmp_path / "runs" / run_report.INDEX_FILE
    assert index.is_file()
    entry = json.loads(index.read_text(encoding="utf-8").strip())
    assert entry["run_id"] == report["run_id"]
    assert "DONE" in run_report.read_status(run_dir)


def test_read_status_regenerates_without_status_file(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    report = run_report.build_report(run_dir, environ={}, docker_version="test")
    run_report.write_report(run_dir, report)

    assert run_report.read_status(run_dir).startswith(run_report.STATUS_DONE)


def test_budgets_override_is_respected(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    report = run_report.build_report(
        run_dir,
        budgets={"tool_calls": 50, "time_minutes": 30, "turns": 100},
        environ={},
        docker_version="test",
    )
    task_a: Mapping[str, object] = report["tasks"][0]
    assert task_a["tool_calls_budget"] == 50
    assert report["budgets"]["time_minutes"] == 30
