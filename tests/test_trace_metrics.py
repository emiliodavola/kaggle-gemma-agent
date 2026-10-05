"""Focused tests for the trace loop-shape metrics."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "host-trial" / "trace_metrics.py"
_spec = importlib.util.spec_from_file_location("trace_metrics", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
metrics = importlib.util.module_from_spec(_spec)
sys.modules["trace_metrics"] = metrics
_spec.loader.exec_module(metrics)


def _call(function: str, **args: Any) -> dict[str, Any]:
    return {"function_name": function, "arguments": args}


def _write_trace(task_dir: Path, steps: list[dict[str, Any]]) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "trace.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")


def test_counts_first_edit_and_submit(tmp_path: Path) -> None:
    task = tmp_path / "t1"
    _write_trace(
        task,
        [
            {"tool_calls": [_call("read_file", filepath="a.py")]},
            {"tool_calls": [_call("run_command", command="grep x a.py")]},
            {"tool_calls": [_call("edit_file", filepath="a.py")]},
            {"tool_calls": [_call("edit_file", filepath="a.py")]},
            {"tool_calls": [_call("submit_patch")]},
        ],
    )

    row = metrics.metrics_for_task(task)

    assert row.tool_calls == 5
    assert row.reads == 1
    assert row.edits == 2
    assert row.commands == 1
    assert row.calls_to_first_edit == 3
    assert row.calls_to_submit == 5
    assert row.max_edits_same_file == 2


def test_repeated_commands_are_a_read_loop(tmp_path: Path) -> None:
    task = tmp_path / "t2"
    steps = [{"tool_calls": [_call("run_command", command="python3 -c x")]} for _ in range(6)]
    steps.append({"tool_calls": [_call("read_file", filepath="a.py")]})
    _write_trace(task, steps)

    row = metrics.metrics_for_task(task)

    assert row.repeated_commands == 5
    assert row.max_repeat_command == 6
    assert row.loop_shape == "read_loop"


def test_many_edits_on_one_file_are_an_edit_loop(tmp_path: Path) -> None:
    task = tmp_path / "t3"
    _write_trace(task, [{"tool_calls": [_call("edit_file", filepath="a.py")]} for _ in range(6)])

    row = metrics.metrics_for_task(task)

    assert row.max_edits_same_file == 6
    assert row.loop_shape == "edit_loop"


def test_mixed_and_none(tmp_path: Path) -> None:
    mixed = tmp_path / "mixed"
    _write_trace(
        mixed,
        [{"tool_calls": [_call("run_command", command="x")]} for _ in range(6)]
        + [{"tool_calls": [_call("edit_file", filepath="a.py")]} for _ in range(6)],
    )
    assert metrics.metrics_for_task(mixed).loop_shape == "mixed"

    clean = tmp_path / "clean"
    _write_trace(
        clean,
        [
            {"tool_calls": [_call("read_file", filepath="a.py")]},
            {"tool_calls": [_call("edit_file", filepath="a.py")]},
            {"tool_calls": [_call("submit_patch")]},
        ],
    )
    assert metrics.metrics_for_task(clean).loop_shape == "none"


def test_nudges_are_counted(tmp_path: Path) -> None:
    task = tmp_path / "t4"
    _write_trace(
        task,
        [
            {"extra": {"event_type": "continuation_nudge"}},
            {"extra": {"event_type": "continuation_nudge"}},
        ],
    )

    assert metrics.metrics_for_task(task).nudges == 2


def test_missing_trace_is_all_zeros(tmp_path: Path) -> None:
    row = metrics.metrics_for_task(tmp_path / "absent")

    assert row.tool_calls == 0
    assert row.loop_shape == "none"


def test_collect_reads_resolved_from_report(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_trace(run / "t1", [{"tool_calls": [_call("read_file", filepath="a.py")]}])
    (run / "report.json").write_text(
        json.dumps({"tasks": [{"instance_id": "t1", "resolved": True}]}), encoding="utf-8"
    )

    rows = metrics.collect(run)

    assert len(rows) == 1
    assert rows[0].resolved is True


def test_cli_table_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = tmp_path / "run"
    _write_trace(run / "t1", [{"tool_calls": [_call("edit_file", filepath="a.py")]}])

    assert metrics.main([str(run)]) == 0
    table = capsys.readouterr().out
    assert "t1" in table
    assert "shape" in table

    assert metrics.main([str(run), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["instance_id"] == "t1"


def test_cli_missing_dir_returns_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert metrics.main([str(tmp_path / "nope")]) == 1
    assert "error:" in capsys.readouterr().err
