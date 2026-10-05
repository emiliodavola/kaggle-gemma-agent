"""Per-task loop-shape metrics from archived host-trial runs.

Reads a ``runs/<UTC>/`` directory (any directory holding ``<task>/trace.json``
files) and reports how each task spent its tool calls: reads, edits, commands,
repeated commands, edits on a single file, calls to the first edit and to
submit, and continuation nudges. It then labels a coarse loop shape:

* ``read_loop`` — repeated commands (>= :data:`READ_LOOP_MIN_REPEATS`) with few
  edits (<= 2): the agent keeps searching instead of acting on the answer.
* ``edit_loop`` — many edits on one file (>= :data:`EDIT_LOOP_MIN_EDITS`): the
  agent keeps editing instead of verifying the edit landed.
* ``mixed`` — both signals.
* ``none`` — neither.

Stdlib only and read-only. The classifier is a documented heuristic, not a
verdict; the raw counts are the evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

READ_LOOP_MIN_REPEATS = 5
EDIT_LOOP_MIN_EDITS = 5


@dataclass
class TaskMetrics:
    """Tool-call breakdown and loop shape for one task."""

    instance_id: str
    tool_calls: int = 0
    reads: int = 0
    edits: int = 0
    writes: int = 0
    commands: int = 0
    get_status: int = 0
    calls_to_first_edit: int | None = None
    calls_to_submit: int | None = None
    repeated_commands: int = 0
    max_repeat_command: int = 0
    max_edits_same_file: int = 0
    nudges: int = 0
    resolved: bool | None = None
    loop_shape: str = "none"


def _tool_calls(step: dict[str, Any]) -> list[dict[str, Any]]:
    calls = step.get("tool_calls")
    return [call for call in calls if isinstance(call, dict)] if isinstance(calls, list) else []


def _arg_str(args: Any, *keys: str) -> str:
    if not isinstance(args, dict):
        return ""
    for key in keys:
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def classify(metrics: TaskMetrics) -> str:
    """Return the coarse loop shape for *metrics*.

    The two signals mirror the forum observation: a **read loop** repeats
    commands, an **edit loop** makes many edits on one file. When both are
    present the shape is ``mixed``; when neither is, ``none`` (which can still
    be a long, read-heavy task without exact repeats).
    """
    repeated = metrics.repeated_commands >= READ_LOOP_MIN_REPEATS
    many_edits = metrics.max_edits_same_file >= EDIT_LOOP_MIN_EDITS
    if repeated and many_edits:
        return "mixed"
    if many_edits:
        return "edit_loop"
    if repeated:
        return "read_loop"
    return "none"


def metrics_for_task(task_dir: Path) -> TaskMetrics:
    """Compute the metrics for one ``<task>/`` directory."""
    metrics = TaskMetrics(instance_id=task_dir.name)
    trace = task_dir / "trace.json"
    if not trace.is_file():
        return metrics
    try:
        data = json.loads(trace.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return metrics

    commands: list[str] = []
    edits_per_file: Counter[str] = Counter()
    call_index = 0
    for step in data.get("steps", []):
        if not isinstance(step, dict):
            continue
        extra = step.get("extra")
        if isinstance(extra, dict) and extra.get("event_type") == "continuation_nudge":
            metrics.nudges += 1
        for call in _tool_calls(step):
            call_index += 1
            metrics.tool_calls += 1
            function = call.get("function_name")
            args = call.get("arguments")
            if function == "read_file":
                metrics.reads += 1
            elif function == "edit_file":
                metrics.edits += 1
                if metrics.calls_to_first_edit is None:
                    metrics.calls_to_first_edit = call_index
                path = _arg_str(args, "filepath", "file_path", "path")
                if path:
                    edits_per_file[path] += 1
            elif function == "write_file":
                metrics.writes += 1
            elif function == "run_command":
                metrics.commands += 1
                command = _arg_str(args, "command")
                if command:
                    commands.append(command)
            elif function == "get_status":
                metrics.get_status += 1
            elif function == "submit_patch" and metrics.calls_to_submit is None:
                metrics.calls_to_submit = call_index

    if commands:
        counts = Counter(commands)
        metrics.max_repeat_command = max(counts.values())
        metrics.repeated_commands = sum(count - 1 for count in counts.values())
    if edits_per_file:
        metrics.max_edits_same_file = max(edits_per_file.values())
    metrics.loop_shape = classify(metrics)
    return metrics


def load_resolved(run_dir: Path) -> dict[str, bool]:
    """Return ``{instance_id: resolved}`` from the run-level ``report.json``."""
    report = run_dir / "report.json"
    if not report.is_file():
        return {}
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    resolved: dict[str, bool] = {}
    for task in data.get("tasks", []):
        if isinstance(task, dict) and isinstance(task.get("instance_id"), str):
            resolved[task["instance_id"]] = bool(task.get("resolved"))
    return resolved


def collect(run_dir: Path) -> list[TaskMetrics]:
    """Return the metrics for every task directory under *run_dir*."""
    resolved = load_resolved(run_dir)
    rows: list[TaskMetrics] = []
    for task_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        metrics = metrics_for_task(task_dir)
        metrics.resolved = resolved.get(metrics.instance_id)
        rows.append(metrics)
    return rows


def _as_dict(metrics: TaskMetrics) -> dict[str, Any]:
    return {
        "instance_id": metrics.instance_id,
        "resolved": metrics.resolved,
        "tool_calls": metrics.tool_calls,
        "reads": metrics.reads,
        "edits": metrics.edits,
        "writes": metrics.writes,
        "commands": metrics.commands,
        "get_status": metrics.get_status,
        "calls_to_first_edit": metrics.calls_to_first_edit,
        "calls_to_submit": metrics.calls_to_submit,
        "repeated_commands": metrics.repeated_commands,
        "max_repeat_command": metrics.max_repeat_command,
        "max_edits_same_file": metrics.max_edits_same_file,
        "nudges": metrics.nudges,
        "loop_shape": metrics.loop_shape,
    }


def render_table(rows: Sequence[TaskMetrics]) -> str:
    """Render *rows* as a fixed-width table."""
    header = (
        f"{'task':16} {'res':3} {'calls':5} {'read':4} {'edit':4} {'cmd':4} "
        f"{'rep':4} {'maxEd':5} {'1stEd':5} {'sub':4} {'nudge':5} shape"
    )
    lines = [header]
    for row in rows:
        resolved = "Y" if row.resolved else ("n" if row.resolved is False else "?")
        first = "-" if row.calls_to_first_edit is None else str(row.calls_to_first_edit)
        submit = "-" if row.calls_to_submit is None else str(row.calls_to_submit)
        lines.append(
            f"{row.instance_id:16} {resolved:3} {row.tool_calls:5} {row.reads:4} "
            f"{row.edits:4} {row.commands:4} {row.repeated_commands:4} "
            f"{row.max_edits_same_file:5} {first:>5} {submit:>4} {row.nudges:5} {row.loop_shape}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the trace metrics."""
    parser = argparse.ArgumentParser(
        prog="trace-metrics",
        description="Per-task loop-shape metrics from an archived host-trial run.",
    )
    parser.add_argument("run_dir", type=Path, help="a runs/<UTC>/ directory")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)

    run_dir: Path = args.run_dir
    if not run_dir.is_dir():
        print(f"error: {run_dir} is not a directory", file=sys.stderr)
        return 1

    rows = collect(run_dir)
    if args.json:
        print(json.dumps([_as_dict(row) for row in rows], indent=2))
    else:
        print(render_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
