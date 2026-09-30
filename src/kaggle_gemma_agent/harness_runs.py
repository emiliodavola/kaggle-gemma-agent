"""Collect ``swegemma`` evaluation artifacts into a reusable ``runs/`` archive.

The scored harness already writes trajectory material into its ``--results-dir``
(``data/raw/HARNESS_README.md`` section 9.2)::

    results/run_01/
    ├── summary.json
    ├── task_results.jsonl
    ├── patches/<instance_id>.patch
    ├── test_outputs/<instance_id>.log
    ├── traces/trace_<instance_id>.json   # ATIF v1.7 trajectory
    └── logs/<instance_id>.log

That layout is git-ignored and keyed by run name, which is awkward to feed to
the off-Kaggle SFT/RLVR pipelines and easy to lose when a new run reuses the
directory. This module adds the one piece of wiring the harness does not
provide: it re-keys those artifacts per task under
``runs/<UTC timestamp>/<instance_id>/`` with a ``manifest.json``, folds in the
JUnit XML left inside Container B at ``/tmp/_swegemma_junit_<id>.xml`` when a
copy is supplied via ``--junit-dir``, and then writes the file-based handoff
(``report.json`` + ``STATUS`` + ``runs/index.jsonl``) via
:mod:`kaggle_gemma_agent.run_report`.

The harness never persists JUnit XML to ``--results-dir`` and its warm-pooled
containers are wiped after each phase, so extract it before teardown, e.g.::

    docker cp <container>:/tmp/_swegemma_junit_<id>.xml junit/
    python -m kaggle_gemma_agent.harness_runs results/run_01 --junit-dir junit

Then the host or a poller reads the rolling status without parsing artifacts::

    python -m kaggle_gemma_agent.harness_runs report runs/<UTC>

``runs/`` is git-ignored; never commit results. See ``docs/run-reports.md`` for
the schema, STATUS protocol, and scale caps. Stdlib only, so it runs off-Kaggle
like the other helpers.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from kaggle_gemma_agent import run_report

# (archive filename, results subdir, filename template with ``{id}``).
ARTIFACT_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("trace.json", "traces", "trace_{id}.json"),
    ("session.log", "logs", "{id}.log"),
    ("agent_patch.diff", "patches", "{id}.patch"),
    ("test_output.log", "test_outputs", "{id}.log"),
)
JUNIT_TEMPLATES: tuple[str, ...] = ("{id}.xml", "_swegemma_junit_{id}.xml")
RUN_SUMMARY = "summary.json"
RUN_TASKS = "task_results.jsonl"
MANIFEST = "manifest.json"

ARCHIVE_COMMAND = "archive"
REPORT_COMMAND = "report"


class HarnessRunsError(Exception):
    """Raised when a results directory cannot be archived."""


def _template_parts(template: str) -> tuple[str, str]:
    """Split a ``{id}`` template into its (prefix, suffix) around the placeholder."""
    prefix, _, rest = template.partition("{id}")
    return prefix, rest


def _ids_from_dir(base: Path, template: str) -> list[str]:
    """Return instance ids recoverable from *template* under *base*."""
    if not base.is_dir():
        return []
    prefix, suffix = _template_parts(template)
    ids: list[str] = []
    for path in sorted(base.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if not (name.startswith(prefix) and name.endswith(suffix)):
            continue
        end = len(name) - len(suffix) if suffix else len(name)
        instance_id = name[len(prefix) : end]
        if instance_id:
            ids.append(instance_id)
    return ids


def discover_instance_ids(results_dir: Path) -> list[str]:
    """Return the sorted union of instance ids across every artifact directory."""
    results_dir = Path(results_dir)
    found: set[str] = set()
    for _, subdir, template in ARTIFACT_SOURCES:
        found.update(_ids_from_dir(results_dir / subdir, template))
    return sorted(found)


def _copy(src: Path, dest: Path) -> int | None:
    """Copy *src* to *dest* and return its byte size, or ``None`` when absent."""
    if not src.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest.stat().st_size


def _find_junit(junit_dir: Path, instance_id: str) -> Path | None:
    """Return the first existing JUnit XML for *instance_id* under *junit_dir*."""
    for template in JUNIT_TEMPLATES:
        candidate = junit_dir / template.format(id=instance_id)
        if candidate.is_file():
            return candidate
    return None


def archive_run(
    results_dir: Path,
    *,
    runs_root: Path = Path("runs"),
    junit_dir: Path | None = None,
    timestamp: str | None = None,
    finalize: bool = True,
    tasks_path: Path | None = None,
    backend: str | None = None,
    budgets: Mapping[str, int] | None = None,
    index_path: Path | None = None,
) -> Path:
    """Archive a ``swegemma --results-dir`` under ``runs_root/<timestamp>/``.

    Returns the created run directory. Raises :class:`HarnessRunsError` when
    *results_dir* does not exist or the destination already exists. Unless
    ``finalize`` is false, the file-based handoff (``report.json`` + ``STATUS``
    + ``runs/index.jsonl``) is written by :func:`run_report.finalize_run`.
    """
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        raise HarnessRunsError(f"results directory does not exist: {results_dir}")

    runs_root = Path(runs_root)
    stamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = runs_root / stamp
    if run_dir.exists():
        raise HarnessRunsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    junit_root = Path(junit_dir) if junit_dir is not None else None
    tasks: list[dict[str, object]] = []
    for instance_id in discover_instance_ids(results_dir):
        task_dir = run_dir / instance_id
        task_dir.mkdir()
        artifacts: dict[str, int] = {}
        for arcname, subdir, template in ARTIFACT_SOURCES:
            size = _copy(
                results_dir / subdir / template.format(id=instance_id),
                task_dir / arcname,
            )
            if size is not None:
                artifacts[arcname] = size
        if junit_root is not None:
            junit_src = _find_junit(junit_root, instance_id)
            if junit_src is not None:
                size = _copy(junit_src, task_dir / "junit.xml")
                if size is not None:
                    artifacts["junit.xml"] = size
        task_meta: dict[str, object] = {"instance_id": instance_id, "artifacts": artifacts}
        (task_dir / "metadata.json").write_text(
            json.dumps(task_meta, indent=2) + "\n", encoding="utf-8"
        )
        tasks.append(task_meta)

    for name in (RUN_SUMMARY, RUN_TASKS):
        _copy(results_dir / name, run_dir / name)

    manifest = {
        "schema_version": run_report.SCHEMA_VERSION,
        "created_at": stamp,
        "source_results_dir": str(results_dir.resolve()),
        "junit_dir": str(junit_root.resolve()) if junit_root is not None else None,
        "task_count": len(tasks),
        "tasks": tasks,
    }
    (run_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if finalize:
        run_report.finalize_run(
            run_dir,
            runs_root=runs_root,
            index_path=index_path,
            tasks_path=tasks_path,
            backend=backend,
            budgets=budgets,
            generated_at=stamp,
        )
    return run_dir


def _main_archive(argv: Sequence[str]) -> int:
    """Run the archive subcommand (also the backward-compatible bare form)."""
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-runs archive",
        description="Archive a swegemma results directory under runs/<timestamp>/.",
    )
    parser.add_argument("results_dir", type=Path, help="path to the swegemma --results-dir")
    parser.add_argument("--runs-root", default="runs", type=Path)
    parser.add_argument(
        "--junit-dir",
        default=None,
        type=Path,
        help="directory holding JUnit XML copied out of Container B",
    )
    parser.add_argument("--timestamp", default=None, help="override the UTC stamp")
    parser.add_argument("--tasks", default=None, type=Path, help="tasks.jsonl for test sets")
    parser.add_argument("--backend", default=None, help="backend/model name for the report")
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="archive artifacts only; skip report.json/STATUS/index.jsonl",
    )
    args = parser.parse_args(list(argv))

    try:
        run_dir = archive_run(
            args.results_dir,
            runs_root=args.runs_root,
            junit_dir=args.junit_dir,
            timestamp=args.timestamp,
            finalize=not args.no_report,
            tasks_path=args.tasks,
            backend=args.backend,
        )
    except HarnessRunsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"archived {args.results_dir} -> {run_dir}")
    if not args.no_report:
        print(run_report.read_status(run_dir), end="")
    return 0


def _main_report(argv: Sequence[str]) -> int:
    """Run the report subcommand: print STATUS (optionally rebuild it first)."""
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-runs report",
        description="Print the human STATUS summary for an archived run.",
    )
    parser.add_argument("run_dir", type=Path, help="path to runs/<UTC>")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="regenerate report.json/STATUS/index.jsonl from the archived artifacts",
    )
    parser.add_argument("--tasks", default=None, type=Path, help="tasks.jsonl for test sets")
    parser.add_argument("--backend", default=None, help="backend/model name override")
    parser.add_argument("--runs-root", default=None, type=Path)
    args = parser.parse_args(list(argv))

    try:
        if args.rebuild:
            run_report.finalize_run(
                args.run_dir,
                runs_root=args.runs_root,
                tasks_path=args.tasks,
                backend=args.backend,
            )
        print(run_report.read_status(args.run_dir), end="")
    except run_report.RunReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the run archiver and the report reader."""
    args = list(sys.argv[1:] if argv is None else argv)
    command = ARCHIVE_COMMAND
    if args and args[0] in {ARCHIVE_COMMAND, REPORT_COMMAND}:
        command = args.pop(0)
    if command == REPORT_COMMAND:
        return _main_report(args)
    return _main_archive(args)


if __name__ == "__main__":
    raise SystemExit(main())
