"""Turn an archived ``runs/<UTC>/`` directory into a portable, comparable report.

``harness_runs.archive_run`` re-keys a ``swegemma --results-dir`` so the raw
artifacts live one directory per task. This module adds the **handoff layer**
that a host operator and a poller (Hermes) agree on:

``runs/<UTC>/report.json``
    Machine-readable report: schema version, environment names (never secret
    *values*), run totals, and one record per task (backend, wall time, tool
    calls vs the 100-call budget, turns, pass/fail, JUnit outcomes, patch
    ``sha256``, artifact paths/sizes/hashes, and a truncated failure tail).

``runs/<UTC>/STATUS``
    One status token (``DONE`` / ``BLOCKED`` / ``PARTIAL``) followed by a
    five-line human summary. This is the **polling signal**.

``runs/index.jsonl``
    Append-only, one JSON line per finished run, for cross-run comparison
    without re-reading every report.

Everything is stdlib-only, matching ``harness_runs.py``, so it runs off-Kaggle.

Scale caps (see ``docs/run-reports.md``):

* :data:`FAILURE_TAIL_CHARS` — max characters kept from a failing log tail.
* :data:`JUNIT_MAX_CASES` — max ``<testcase>`` rows inlined per task.
* :data:`REPORT_MAX_TASKS` — max task records before a report is split into
  ``report.part0002.json`` … sidecars.
* :data:`INDEX_MAX_LINES` / :data:`INDEX_KEEP_LINES` — index compaction rule.

The report never stores credential values. Only variable *names* matching a
freshness-sensitive list (:data:`_SECRET_MARKERS`) are recorded, and only the
``ROBOTINA_HERMES_MODEL`` / ``ROBOTINA_HERMES_MODEL_BASE_URL`` names are read.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree

SCHEMA_VERSION = "1.0"

#: The archiver writes these per-task files; the report indexes whatever exists.
ARTIFACT_FILES: tuple[str, ...] = (
    "trace.json",
    "session.log",
    "agent_patch.diff",
    "test_output.log",
    "junit.xml",
    "metadata.json",
)

STATUS_DONE = "DONE"
STATUS_PARTIAL = "PARTIAL"
STATUS_BLOCKED = "BLOCKED"

STATUS_FILE = "STATUS"
REPORT_FILE = "report.json"
INDEX_FILE = "index.jsonl"
INDEX_ARCHIVE_DIR = "index-archive"
PART_TEMPLATE = "report.part{n:04d}.json"

#: Characters kept from the tail of a failing log (cap documented in docs).
FAILURE_TAIL_CHARS = 4000
#: ``<testcase>`` rows inlined into a report before the list is marked truncated.
JUNIT_MAX_CASES = 2000
#: Task records per report before the remainder moves to ``report.part*.json``.
REPORT_MAX_TASKS = 400
#: Append one more line and, once the index exceeds this, compact it.
INDEX_MAX_LINES = 1000
#: Number of newest index lines retained after compaction.
INDEX_KEEP_LINES = 500

#: Per-task harness budgets (``AGENTS.md`` / ``HARNESS_README.md`` section 7.1).
DEFAULT_BUDGETS: dict[str, int] = {"tool_calls": 100, "time_minutes": 60, "turns": 500}

_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")
_SAFE_ENV_NAMES = ("ROBOTINA_HERMES_MODEL", "ROBOTINA_HERMES_MODEL_BASE_URL")

_ID_KEYS = ("instance_id", "id", "task_id", "task", "name")
_RESOLVED_KEYS = ("resolved", "is_resolved", "passed", "pass", "success")
_TOOL_CALL_KEYS = ("tool_calls_used", "tool_calls", "num_tool_calls", "tool_call_count")
_TURN_KEYS = ("turns", "num_turns", "turn_count", "iterations")
_WALL_KEYS = (
    "agent_elapsed_seconds",
    "elapsed_seconds",
    "wall_seconds",
    "duration_seconds",
    "wall_time_seconds",
)
_ERROR_KEYS = ("error", "error_message", "failure", "exit_error")
_BACKEND_KEYS = ("backend", "model", "model_name", "agent_backend")
_PATCH_KEYS = ("patch_path", "patch_file", "agent_patch")
_SUMMARY_RATE_KEYS = ("resolution_rate", "rate", "score")
_SUMMARY_RESOLVED_KEYS = ("resolved", "resolved_count", "num_resolved")
_SUMMARY_TOTAL_KEYS = ("total", "total_tasks", "num_tasks", "task_count", "tasks")
_FTP_KEYS = ("fail_to_pass", "FAIL_TO_PASS", "fail_to_pass_tests")
_PTP_KEYS = ("pass_to_pass", "PASS_TO_PASS", "pass_to_pass_tests")

_ADDED_TEST_RE = re.compile(r"^\+\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(")
_MISSING_MODULE_RE = re.compile(r"No module named ['\"](?P<module>[A-Za-z_][\w.]*)['\"]")


class RunReportError(Exception):
    """Raised when a run directory cannot be turned into a report."""


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _localname(tag: str) -> str:
    """Return an XML tag without its ``{namespace}`` prefix."""
    return tag.rsplit("}", 1)[-1]


def _sha256_file(path: Path) -> str:
    """Return the hex ``sha256`` digest of *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_tail(path: Path, cap: int = FAILURE_TAIL_CHARS) -> tuple[str, bool]:
    """Return the last *cap* characters of *path* and whether it was truncated.

    Reads the whole file in binary and decodes with ``errors="replace"`` so a
    corrupt log never raises. Returns ``("", False)`` when *path* is not a file.
    """
    if not path.is_file():
        return "", False
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    if len(text) <= cap:
        return text, False
    return text[-cap:], True


def _load_json(path: Path) -> dict[str, Any] | None:
    """Return *path* parsed as a JSON object, or ``None`` when absent/invalid."""
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _lower_map(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Return *mapping* keyed by lower-cased names, first occurrence winning."""
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        result.setdefault(str(key).lower(), value)
    return result


def _first(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    """Return the first present, non-``None`` value among *keys*."""
    low = _lower_map(mapping)
    for key in keys:
        value = low.get(key.lower())
        if value is not None:
            return value
    return None


def _coerce_float(value: Any) -> float | None:
    """Return *value* as ``float`` when it is numeric, else ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    """Return *value* as ``int`` when it is numeric, else ``None``."""
    number = _coerce_float(value)
    return None if number is None else int(number)


def _coerce_bool(value: Any) -> bool | None:
    """Return *value* as ``bool`` when it is a recognized truthy/falsy token."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "pass", "passed", "resolved", "ok"}:
            return True
        if token in {"false", "0", "no", "fail", "failed", "unresolved"}:
            return False
    return None


def _as_list(value: Any) -> list[str]:
    """Normalize *value* into a list of strings for FAIL/PASS_TO_PASS fields."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        return [part for part in re.split(r"[\s,]+", text) if part]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return [str(value)]


# --------------------------------------------------------------------------- #
# environment (names only, never credential values)
# --------------------------------------------------------------------------- #
def _detect_docker_version() -> str:
    """Best-effort ``docker --version`` string; ``"unknown"`` when unavailable."""
    try:
        proc = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return "unknown"
    output = (proc.stdout or proc.stderr).strip()
    return output or "unknown"


def _url_host(url: str) -> str | None:
    """Return only the host of *url* (never the path or query)."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    return host


def detect_environment(
    environ: Mapping[str, str] | None = None,
    *,
    docker_version: str | None = None,
) -> dict[str, Any]:
    """Describe the host without ever capturing secret *values*.

    Only :data:`_SAFE_ENV_NAMES` are read. Every other variable whose name looks
    secret (:data:`_SECRET_MARKERS`) is recorded by **name only** so the report
    proves credentials existed without leaking them.
    """
    env = os.environ if environ is None else environ
    backend = env.get("ROBOTINA_HERMES_MODEL") or "unknown"
    base_url = env.get("ROBOTINA_HERMES_MODEL_BASE_URL")
    credential_names = sorted(
        name for name in env if any(marker in name.upper() for marker in _SECRET_MARKERS)
    )
    return {
        "os": f"{platform.system()} {platform.release()}",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "docker": docker_version if docker_version is not None else _detect_docker_version(),
        "backend": backend,
        "backend_base_host": _url_host(base_url) if base_url else None,
        "safe_env_names": [name for name in _SAFE_ENV_NAMES if name in env],
        "credential_vars_present": credential_names,
    }


# --------------------------------------------------------------------------- #
# inputs: task_results.jsonl, junit.xml, tasks.jsonl
# --------------------------------------------------------------------------- #
def _load_task_results(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse ``task_results.jsonl`` into ``{instance_id: record}`` plus notes.

    The harness schema is unpublished, so keys are matched case-insensitively
    through aliases and unparseable lines are recorded (never raised). Later
    lines for the same id win, matching append-only semantics.
    """
    records: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    if not path.is_file():
        return records, [f"{path.name} missing"]
    for lineno, raw in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            notes.append(f"task_results.jsonl:{lineno} invalid JSON")
            continue
        if not isinstance(entry, dict):
            notes.append(f"task_results.jsonl:{lineno} not an object")
            continue
        instance_id = _first(entry, _ID_KEYS)
        if instance_id is None:
            notes.append(f"task_results.jsonl:{lineno} missing instance id")
            continue
        records[str(instance_id)] = entry
    return records, notes


def parse_junit(path: Path) -> dict[str, Any]:
    """Parse a JUnit XML report into counts and (capped) per-test outcomes.

    Recognizes ``<testsuites>`` and bare ``<testsuite>`` roots and strips XML
    namespaces. Counts are computed from every ``<testcase>``; ``testcases`` is
    capped at :data:`JUNIT_MAX_CASES` with ``cases_truncated`` set accordingly.
    """
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError) as exc:
        raise RunReportError(f"cannot parse JUnit XML {path}: {exc}") from exc

    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    all_cases: list[dict[str, str]] = []
    for element in root.iter():
        if _localname(element.tag) != "testcase":
            continue
        counts["tests"] += 1
        status = "passed"
        for child in element:
            child_name = _localname(child.tag)
            if child_name == "failure":
                status = "failed"
            elif child_name == "error":
                status = "error"
            elif child_name == "skipped" and status == "passed":
                status = "skipped"
        if status == "failed":
            counts["failures"] += 1
        elif status == "error":
            counts["errors"] += 1
        elif status == "skipped":
            counts["skipped"] += 1
        all_cases.append(
            {
                "name": element.get("name", ""),
                "classname": element.get("classname", ""),
                "status": status,
            }
        )

    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    return {
        **counts,
        "testcases": all_cases[:JUNIT_MAX_CASES],
        "cases_truncated": len(all_cases) > JUNIT_MAX_CASES,
    }


def _node_id(case: Mapping[str, str]) -> str:
    """Return the ``class::name`` node id for a JUnit testcase."""
    classname = case.get("classname", "")
    name = case.get("name", "")
    return f"{classname}::{name}" if classname else name


def load_task_metadata(path: Path | None) -> dict[str, dict[str, Any]]:
    """Index a ``tasks.jsonl`` by ``instance_id`` for repo / test-set lookups."""
    meta: dict[str, dict[str, Any]] = {}
    if path is None or not path.is_file():
        return meta
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        instance_id = _first(entry, _ID_KEYS)
        if instance_id is not None:
            meta[str(instance_id)] = entry
    return meta


def extract_patch_test_ids(test_patch: str) -> list[str]:
    """Return the ``test_*`` function names added by a unified ``test_patch``.

    Heuristic used only when the harness exposes no explicit FAIL_TO_PASS list.
    """
    seen: dict[str, None] = {}
    for line in test_patch.splitlines():
        match = _ADDED_TEST_RE.match(line)
        if match:
            seen.setdefault(match.group(1), None)
    return list(seen)


# --------------------------------------------------------------------------- #
# report construction
# --------------------------------------------------------------------------- #
def _task_dirs(run_dir: Path) -> list[Path]:
    """Return per-task subdirectories of *run_dir*, excluding bookkeeping dirs."""
    if not run_dir.is_dir():
        return []
    return sorted(
        path
        for path in run_dir.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name != INDEX_ARCHIVE_DIR
    )


def _artifact_index(task_dir: Path, run_dir: Path) -> dict[str, dict[str, Any]]:
    """Return ``{relative_path: {size, sha256}}`` for every file under *task_dir*."""
    artifacts: dict[str, dict[str, Any]] = {}
    for path in sorted(task_dir.rglob("*")):
        if not path.is_file():
            continue
        artifacts[str(path.relative_to(run_dir))] = {
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    return artifacts


def _annotate_required(expected: Sequence[str], outcomes: Mapping[str, str]) -> dict[str, Any]:
    """Annotate expected test nodes with their observed JUnit status."""
    passed: list[str] = []
    failed: list[str] = []
    missing: list[str] = []
    observed: dict[str, str] = {}
    for node in expected:
        status = outcomes.get(node)
        if status is None:
            suffix_match = next(
                (value for key, value in outcomes.items() if key.endswith(f"::{node}")), None
            )
            status = suffix_match
        if status is None:
            missing.append(node)
        else:
            observed[node] = status
            (passed if status == "passed" else failed).append(node)
    return {
        "expected": list(expected),
        "observed": observed,
        "passed": passed,
        "failed": failed,
        "missing": missing,
    }


def _test_sets(
    record: Mapping[str, Any],
    meta: Mapping[str, Any] | None,
    junit: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return ``(fail_to_pass, pass_to_pass)`` annotations, or ``(None, None)``."""
    if junit is None:
        return None, None
    outcomes = {_node_id(case): case.get("status", "") for case in junit.get("testcases", [])}
    failed_nodes = [node for node, status in outcomes.items() if status != "passed"]

    explicit_fail = _as_list(_first(record, _FTP_KEYS))
    explicit_pass = _as_list(_first(record, _PTP_KEYS))
    if meta is not None:
        explicit_fail = explicit_fail or _as_list(_first(meta, _FTP_KEYS))
        explicit_pass = explicit_pass or _as_list(_first(meta, _PTP_KEYS))

    fail_nodes = explicit_fail
    if not fail_nodes:
        patch = _first(meta, ("test_patch",)) if meta is not None else None
        fail_nodes = extract_patch_test_ids(str(patch)) if patch else []
    if not fail_nodes:
        fail_nodes = failed_nodes

    pass_nodes = explicit_pass or [node for node, status in outcomes.items() if status == "passed"]
    return _annotate_required(fail_nodes, outcomes), _annotate_required(pass_nodes, outcomes)


def _infer_resolved(record: Mapping[str, Any], junit: Mapping[str, Any] | None) -> bool | None:
    """Infer a task verdict from the record, falling back to JUnit counts."""
    explicit = _coerce_bool(_first(record, _RESOLVED_KEYS))
    if explicit is not None:
        return explicit
    if junit is None:
        return None
    return bool(
        junit.get("passed", 0) > 0
        and junit.get("failures", 0) == 0
        and junit.get("errors", 0) == 0
        and junit.get("skipped", 0) == 0
    )


_COLLECTION_ERROR_MARKERS: tuple[str, ...] = (
    "error during collection",
    "error collecting",
    "import while importing test module",
)
_TIMEOUT_MARKERS: tuple[str, ...] = ("pytest-timeout", "timed out")
_FAILURE_MARKERS: tuple[str, ...] = ("failures", "failed ", "assertionerror")


def _classify_failure(text: str) -> str | None:
    """Classify a failing ``test_output.log`` tail into a coarse failure kind.

    ``collection_error`` (import/collection failure, usually an environment or
    import breakage) is checked first: pytest prints no ``FAILURES`` banner in
    that case, so a naive "failed" match would be wrong. ``timeout`` needs an
    explicit marker so a test named ``test_timeout`` is not misread. Returns
    ``None`` for empty input.
    """
    if not text.strip():
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _COLLECTION_ERROR_MARKERS):
        return "collection_error"
    if any(marker in lowered for marker in _TIMEOUT_MARKERS):
        return "timeout"
    if any(marker in lowered for marker in _FAILURE_MARKERS):
        return "test_failure"
    return "unknown"


def _failure_kind(task_dir: Path, status: str) -> str | None:
    """Classify the task's ``test_output.log`` when the task is not passing."""
    if status == "pass":
        return None
    test_log = task_dir / "test_output.log"
    if not test_log.is_file():
        return None
    text, _ = _read_tail(test_log, FAILURE_TAIL_CHARS)
    return _classify_failure(text)


def _failure_tail(task_dir: Path) -> dict[str, Any] | None:
    """Return the truncated tail of the richest failing log, or ``None``."""
    for name in ("test_output.log", "session.log"):
        text, truncated = _read_tail(task_dir / name, FAILURE_TAIL_CHARS)
        if text:
            return {"source": name, "chars": len(text), "truncated": truncated, "text": text}
    return None


def _missing_modules(task_dir: Path, status: str) -> list[str]:
    """Return unique ``No module named '...'`` modules from a failing test log.

    Reads the ``test_output.log`` tail only; a passing task or a task without a
    test log yields an empty list. The result is sorted for deterministic output.
    """
    if status == "pass":
        return []
    text, _ = _read_tail(task_dir / "test_output.log", FAILURE_TAIL_CHARS)
    if not text:
        return []
    return sorted({match.group("module") for match in _MISSING_MODULE_RE.finditer(text)})


def _build_task(
    run_dir: Path,
    task_dir: Path,
    record: Mapping[str, Any],
    meta: Mapping[str, Any] | None,
    *,
    run_backend: str,
    budget_tool_calls: int,
    budget_turns: int,
) -> dict[str, Any]:
    """Build one task record from the archived artifacts and its result line."""
    instance_id = task_dir.name
    junit_path = task_dir / "junit.xml"
    junit = parse_junit(junit_path) if junit_path.is_file() else None
    resolved = _infer_resolved(record, junit)
    fail_to_pass, pass_to_pass = _test_sets(record, meta, junit)

    patch_path = task_dir / "agent_patch.diff"
    explicit_patch = _first(record, _PATCH_KEYS)
    backend = _first(record, _BACKEND_KEYS)
    status = "unknown" if resolved is None else ("pass" if resolved else "fail")
    failure_kind = _failure_kind(task_dir, status)

    return {
        "instance_id": instance_id,
        "backend": str(backend) if backend is not None else run_backend,
        "repo": _first(meta, ("repo",)) if meta is not None else None,
        "wall_seconds": _coerce_float(_first(record, _WALL_KEYS)),
        "tool_calls": _coerce_int(_first(record, _TOOL_CALL_KEYS)),
        "tool_calls_budget": budget_tool_calls,
        "turns": _coerce_int(_first(record, _TURN_KEYS)),
        "turns_budget": budget_turns,
        "resolved": resolved,
        "status": status,
        "junit": junit,
        "fail_to_pass": fail_to_pass,
        "pass_to_pass": pass_to_pass,
        "error": _string_or_none(_first(record, _ERROR_KEYS)),
        "patch_sha256": _sha256_file(patch_path) if patch_path.is_file() else None,
        "patch_path": str(explicit_patch)
        if explicit_patch is not None
        else (f"{instance_id}/agent_patch.diff" if patch_path.is_file() else None),
        "artifacts": _artifact_index(task_dir, run_dir),
        "failure_kind": failure_kind,
        "missing_modules": _missing_modules(task_dir, status),
        "failure_tail": _failure_tail(task_dir) if status != "pass" else None,
    }


def _string_or_none(value: Any) -> str | None:
    """Return ``str(value)`` or ``None`` for null-ish inputs."""
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text or None


def build_report(
    run_dir: Path,
    *,
    backend: str | None = None,
    tasks_meta: Mapping[str, Mapping[str, Any]] | None = None,
    budgets: Mapping[str, int] | None = None,
    generated_at: str | None = None,
    environ: Mapping[str, str] | None = None,
    docker_version: str | None = None,
) -> dict[str, Any]:
    """Build the report dict for an archived *run_dir* without writing anything."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise RunReportError(f"run directory does not exist: {run_dir}")

    budget_map = {**DEFAULT_BUDGETS, **(budgets or {})}
    summary = _load_json(run_dir / "summary.json")
    records, notes = _load_task_results(run_dir / "task_results.jsonl")
    env = detect_environment(environ, docker_version=docker_version)
    run_backend = backend or str(env["backend"])
    env["backend"] = run_backend

    task_dirs = {path.name: path for path in _task_dirs(run_dir)}
    for instance_id in records:
        task_dirs.setdefault(instance_id, run_dir / instance_id)

    tasks: list[dict[str, Any]] = []
    for instance_id in sorted(task_dirs):
        task_dir = task_dirs[instance_id]
        meta = tasks_meta.get(instance_id) if tasks_meta else None
        tasks.append(
            _build_task(
                run_dir,
                task_dir,
                records.get(instance_id, {}),
                meta,
                run_backend=run_backend,
                budget_tool_calls=budget_map["tool_calls"],
                budget_turns=budget_map["turns"],
            )
        )

    resolved = sum(1 for task in tasks if task["resolved"] is True)
    unknown = sum(1 for task in tasks if task["resolved"] is None)
    rate = (resolved / len(tasks)) if tasks else None
    wall = [task["wall_seconds"] for task in tasks if task["wall_seconds"] is not None]
    tool_calls = [task["tool_calls"] for task in tasks if task["tool_calls"] is not None]
    turns = [task["turns"] for task in tasks if task["turns"] is not None]

    reasons: list[str] = []
    if summary is None:
        reasons.append("summary.json missing")
    else:
        summary_errors = summary.get("errors") or []
        if isinstance(summary_errors, list) and summary_errors:
            reasons.append(f"{len(summary_errors)} harness error(s)")
    if unknown:
        reasons.append(f"{unknown} task(s) without verdict")

    module_tasks: dict[str, int] = {}
    for task in tasks:
        if task.get("status") == "pass":
            continue
        for module in task.get("missing_modules", []):
            module_tasks[module] = module_tasks.get(module, 0) + 1
    missing_modules = sorted(module_tasks)
    environment_blocked = False
    for module, count in sorted(module_tasks.items()):
        if count >= 2:
            environment_blocked = True
            reasons.append(
                f"environment failure: missing module(s) {module} ({count}/{len(tasks)} tasks)"
            )

    status = STATUS_BLOCKED if not tasks else (STATUS_PARTIAL if reasons else STATUS_DONE)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "status": status,
        "status_reasons": reasons,
        "environment_blocked": environment_blocked,
        "missing_modules": missing_modules,
        "env": env,
        "budgets": dict(budget_map),
        "totals": {
            "tasks": len(tasks),
            "resolved": resolved,
            "unresolved": len(tasks) - resolved - unknown,
            "unknown": unknown,
            "resolution_rate": rate,
            "wall_seconds": sum(wall) if wall else None,
            "tool_calls": sum(tool_calls) if tool_calls else None,
            "turns": sum(turns) if turns else None,
        },
        "summary": {
            "resolution_rate": _coerce_float(_first(summary or {}, _SUMMARY_RATE_KEYS)),
            "resolved": _coerce_int(_first(summary or {}, _SUMMARY_RESOLVED_KEYS)),
            "total": _coerce_int(_first(summary or {}, _SUMMARY_TOTAL_KEYS)),
        },
        "notes": notes,
        "tasks": tasks,
        "parts": 1,
        "part_files": [],
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def render_summary(report: Mapping[str, Any]) -> str:
    """Render the ``STATUS`` text: status token plus a five-line summary."""
    env = report.get("env", {})
    totals: Mapping[str, Any] = report.get("totals", {})
    budgets: Mapping[str, int] = report.get("budgets", DEFAULT_BUDGETS)
    tasks = _coerce_int(totals.get("tasks", 0)) or 0
    rate = totals.get("resolution_rate")
    rate_text = f"{rate:.3f}" if isinstance(rate, (int, float)) else "n/a"

    def _budget_total(key: str) -> int:
        return int(budgets.get(key, 0)) * max(tasks, 1)

    wall = totals.get("wall_seconds")
    wall_text = f"{wall / 60:.1f}" if isinstance(wall, (int, float)) else "n/a"
    tool_calls = totals.get("tool_calls")
    turns = totals.get("turns")
    failed = [
        task["instance_id"] for task in report.get("tasks", []) if task.get("status") != "pass"
    ]
    top = ", ".join(failed[:5]) if failed else "none"
    kinds: dict[str, int] = {}
    for task in report.get("tasks", []):
        if task.get("status") == "pass":
            continue
        kind = str(task.get("failure_kind") or "unknown")
        kinds[kind] = kinds.get(kind, 0) + 1
    kind_text = ""
    if kinds:
        kind_pairs = " ".join(f"{kind}={count}" for kind, count in sorted(kinds.items()))
        kind_text = f" | kinds {kind_pairs}"
    env_text = ""
    if report.get("environment_blocked"):
        env_names = ", ".join(str(name) for name in report.get("missing_modules", []))
        env_text = f" | env missing: {env_names}"

    lines = [
        str(report.get("status", STATUS_BLOCKED)),
        f"run {report.get('run_id', '?')} | backend {env.get('backend', 'unknown')} "
        f"| docker {env.get('docker', 'unknown')} | os {env.get('os', 'unknown')}",
        f"tasks {tasks} | resolved {totals.get('resolved', 0)} | rate {rate_text} "
        f"| unknown {totals.get('unknown', 0)}",
        f"tool_calls {tool_calls}/{_budget_total('tool_calls')} "
        f"| wall {wall_text}/{_budget_total('time_minutes')} min "
        f"| turns {turns}/{_budget_total('turns')}",
        f"failures {len(failed)}{kind_text}{env_text} | top: {top}",
        f"schema {report.get('schema_version', SCHEMA_VERSION)} "
        f"| report {report.get('report_path', REPORT_FILE)} "
        f"| index {report.get('index_path', INDEX_FILE)}",
    ]
    return "\n".join(lines) + "\n"


def write_status(run_dir: Path, report: Mapping[str, Any]) -> Path:
    """Write the ``STATUS`` polling signal for *report* and return its path."""
    path = Path(run_dir) / STATUS_FILE
    path.write_text(render_summary(report), encoding="utf-8")
    return path


def write_report(
    run_dir: Path, report: dict[str, Any], *, max_tasks: int = REPORT_MAX_TASKS
) -> Path:
    """Write ``report.json`` (splitting tasks past *max_tasks*) and return it.

    ``report`` is not mutated: the caller keeps the full task list for STATUS
    rendering while the on-disk file holds the first chunk plus sidecars.
    """
    run_dir = Path(run_dir)
    tasks = list(report.get("tasks", []))
    chunks = [tasks[index : index + max_tasks] for index in range(0, len(tasks), max_tasks)]
    if not chunks:
        chunks = [[]]

    out = dict(report)
    out["tasks"] = chunks[0]
    out["parts"] = len(chunks)
    out["part_files"] = []
    for offset, chunk in enumerate(chunks[1:], start=2):
        part_name = PART_TEMPLATE.format(n=offset)
        part = {
            "schema_version": report.get("schema_version", SCHEMA_VERSION),
            "run_id": report.get("run_id"),
            "part": offset,
            "tasks": chunk,
        }
        (run_dir / part_name).write_text(json.dumps(part, indent=2) + "\n", encoding="utf-8")
        out["part_files"].append(part_name)

    report_path = run_dir / REPORT_FILE
    report_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return report_path


def load_report(run_dir: Path) -> dict[str, Any]:
    """Load ``report.json`` and reassemble every task from its part sidecars."""
    run_dir = Path(run_dir)
    report = _load_json(run_dir / REPORT_FILE)
    if report is None:
        raise RunReportError(f"no {REPORT_FILE} under {run_dir}")
    for part_name in report.get("part_files", []):
        part = _load_json(run_dir / str(part_name))
        if part is not None:
            report.setdefault("tasks", []).extend(part.get("tasks", []))
    return report


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #
def index_entry(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build the one-line index entry for a finished run."""
    totals = report.get("totals", {})
    env = report.get("env", {})
    return {
        "run_id": report.get("run_id"),
        "timestamp": report.get("generated_at"),
        "status": report.get("status"),
        "backend": env.get("backend"),
        "tasks": totals.get("tasks", 0),
        "resolved": totals.get("resolved", 0),
        "rate": totals.get("resolution_rate"),
        "report": report.get("report_path", f"{report.get('run_id')}/{REPORT_FILE}"),
    }


def append_index(
    index_path: Path,
    entry: Mapping[str, Any],
    *,
    max_lines: int = INDEX_MAX_LINES,
    keep: int = INDEX_KEEP_LINES,
) -> bool:
    """Append *entry* to *index_path*; compact when it exceeds *max_lines*.

    Returns ``True`` when compaction ran. Dropped lines are preserved verbatim
    under ``index-archive/`` beside the index so history is never lost.
    """
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        index_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if index_path.is_file()
        else []
    )
    existing = [line for line in existing if line.strip()]
    existing.append(json.dumps(entry, default=str))

    compacted = len(existing) > max_lines
    if compacted:
        overflow = existing[: len(existing) - keep]
        retained = existing[len(existing) - keep :]
        _archive_index_lines(index_path, overflow)
        existing = retained

    index_path.write_text("\n".join(existing) + "\n", encoding="utf-8")
    return compacted


def _archive_index_lines(index_path: Path, lines: Sequence[str]) -> None:
    """Persist compacted index *lines* next to the index, named by their span."""
    if not lines:
        return
    archive_dir = index_path.parent / INDEX_ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)
    first = _line_run_id(lines[0])
    last = _line_run_id(lines[-1])
    name = f"{first}__{last}.jsonl" if first and last else "index.jsonl"
    archive = archive_dir / name
    existing = archive.read_text(encoding="utf-8") if archive.is_file() else ""
    archive.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")


def _line_run_id(line: str) -> str:
    """Return the ``run_id`` of an index line, or an empty string."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return ""
    return str(entry.get("run_id", "")) if isinstance(entry, dict) else ""


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def finalize_run(
    run_dir: Path,
    *,
    runs_root: Path | None = None,
    index_path: Path | None = None,
    tasks_path: Path | None = None,
    backend: str | None = None,
    budgets: Mapping[str, int] | None = None,
    generated_at: str | None = None,
    environ: Mapping[str, str] | None = None,
    docker_version: str | None = None,
    max_tasks: int = REPORT_MAX_TASKS,
) -> dict[str, Any]:
    """Build and persist ``report.json`` + ``STATUS`` and append ``index.jsonl``."""
    run_dir = Path(run_dir)
    runs_root = Path(runs_root) if runs_root is not None else run_dir.parent
    index_path = Path(index_path) if index_path is not None else runs_root / INDEX_FILE
    tasks_meta = load_task_metadata(tasks_path)

    report = build_report(
        run_dir,
        backend=backend,
        tasks_meta=tasks_meta,
        budgets=budgets,
        generated_at=generated_at,
        environ=environ,
        docker_version=docker_version,
    )
    report["report_path"] = str(run_dir / REPORT_FILE)
    report["index_path"] = str(index_path)
    write_report(run_dir, report, max_tasks=max_tasks)
    write_status(run_dir, report)
    append_index(index_path, index_entry(report))
    return report


def read_status(run_dir: Path) -> str:
    """Return the ``STATUS`` text for *run_dir*, regenerating it if needed."""
    run_dir = Path(run_dir)
    status_path = run_dir / STATUS_FILE
    if status_path.is_file():
        return status_path.read_text(encoding="utf-8", errors="replace")
    report = load_report(run_dir)
    return render_summary(report)
