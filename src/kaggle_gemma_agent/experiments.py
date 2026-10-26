"""Declared A/B experiments over archived ``runs/`` directories.

A run records *what* it used; an experiment records *why* two runs may be
compared. The declaration is written before the first rollout, so the intended
change and its expected direction cannot be chosen after seeing the result
(``docs/run-analysis-vocabulary.md`` R3.4).

``finish`` refuses to compare runs that are not the same batch on the same
backend, model and budgets, or whose recorded harness hashes differ by anything
other than the one declared component. The delivery record is reported as a
descriptive signal only (R8); the resolution verdict is the official attribution.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kaggle_gemma_agent import harness_runs, run_report, subsets

SCHEMA_VERSION = "1.0"
EXPERIMENTS_DIR = Path("experiments")
COMPONENTS: tuple[str, ...] = ("prompt", "skills", "sampling", "eval_config", "repo_commit")
DIRECTIONS: tuple[str, ...] = ("helped", "hurt")
VERDICTS: tuple[str, ...] = ("helped", "hurt", "no observed effect", "confounded")
REQUIRED_KEYS: tuple[str, ...] = (
    "schema_version",
    "id",
    "created_at",
    "subset",
    "component",
    "direction",
    "change",
    "backend",
    "model",
    "budgets",
    "provenance",
    "runs",
)
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
REPO_ROOT = Path(__file__).resolve().parents[2]


class ExperimentError(Exception):
    """Raised when an experiment cannot be declared, loaded or compared."""


@dataclass(frozen=True)
class Experiment:
    """One validated experiment declaration."""

    id: str
    path: Path
    data: dict[str, Any]

    @property
    def comparison_path(self) -> Path:
        """The generated comparison beside the declaration."""
        return self.path.parent / "comparison.json"

    @property
    def subset_id(self) -> str:
        subset = self.data["subset"]
        return str(subset["id"]) if isinstance(subset, dict) else ""


def repo_root(root: Path | None = None) -> Path:
    """Return *root*, or the repository root that contains this package."""
    return Path(root) if root is not None else REPO_ROOT


def experiment_path(root: Path | None, experiment_id: str) -> Path:
    """Return ``experiments/<id>/experiment.json`` under *root*."""
    return repo_root(root) / EXPERIMENTS_DIR / experiment_id / "experiment.json"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ExperimentError(f"cannot read experiment {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ExperimentError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(loaded, dict):
        raise ExperimentError(f"{path}: expected a JSON object")
    return loaded


def _document_errors(data: Mapping[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        errors.append(f"{path}: missing key(s) {', '.join(missing)}")
    unknown = sorted(set(data) - set(REQUIRED_KEYS))
    if unknown:
        errors.append(f"{path}: unknown key(s) {', '.join(unknown)}")
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{path}: schema_version must be {SCHEMA_VERSION!r}")
    identifier = data.get("id")
    if not isinstance(identifier, str) or not _ID_RE.fullmatch(identifier):
        errors.append(f"{path}: id must match {_ID_RE.pattern}")
    if data.get("component") not in COMPONENTS:
        errors.append(f"{path}: component must be one of {', '.join(COMPONENTS)}")
    if data.get("direction") not in DIRECTIONS:
        errors.append(f"{path}: direction must be one of {', '.join(DIRECTIONS)}")
    if not isinstance(data.get("change"), str) or not data["change"].strip():
        errors.append(f"{path}: change must be a non-empty string")
    subset = data.get("subset")
    if not isinstance(subset, dict):
        errors.append(f"{path}: subset must be an object")
    else:
        for key in ("id", "sha256", "task_ids"):
            if key not in subset:
                errors.append(f"{path}: subset is missing {key!r}")
        task_ids = subset.get("task_ids")
        if not isinstance(task_ids, list) or not all(isinstance(item, str) for item in task_ids):
            errors.append(f"{path}: subset.task_ids must be a list of strings")
    for key in ("backend", "model"):
        if data.get(key) is not None and not isinstance(data[key], str):
            errors.append(f"{path}: {key} must be a string or null")
    if not isinstance(data.get("budgets"), dict):
        errors.append(f"{path}: budgets must be an object")
    if not isinstance(data.get("provenance"), dict):
        errors.append(f"{path}: provenance must be an object")
    runs = data.get("runs")
    if not isinstance(runs, dict) or set(runs) != {"base", "variant"}:
        errors.append(f"{path}: runs must be an object with exactly base and variant")
    return errors


def load_experiment(root: Path | None, experiment_id: str) -> Experiment:
    """Load and structurally validate one experiment declaration."""
    path = experiment_path(root, experiment_id)
    data = _load_object(path)
    errors = _document_errors(data, path)
    if errors:
        raise ExperimentError("\n".join(errors))
    return Experiment(id=experiment_id, path=path, data=data)


def start(
    root: Path | None,
    *,
    experiment_id: str,
    subset: str | Path,
    component: str,
    direction: str,
    change: str,
    backend: str | None = None,
    model: str | None = None,
    budgets: Mapping[str, int] | None = None,
) -> Path:
    """Write the declaration before the first rollout and return its path."""
    base = repo_root(root)
    if not _ID_RE.fullmatch(experiment_id):
        raise ExperimentError(f"experiment id must match {_ID_RE.pattern}")
    if component not in COMPONENTS:
        raise ExperimentError(f"component must be one of {', '.join(COMPONENTS)}")
    if direction not in DIRECTIONS:
        raise ExperimentError(f"direction must be one of {', '.join(DIRECTIONS)}")
    if not change.strip():
        raise ExperimentError("change must be a non-empty line")
    loaded = subsets.load_subset(subset, root=base)
    path = experiment_path(base, experiment_id)
    if path.exists():
        raise ExperimentError(f"experiment already exists: {path}")
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": experiment_id,
        "created_at": datetime.now(UTC).isoformat(),
        "subset": {
            "id": loaded.id,
            "sha256": loaded.sha256,
            "task_ids": list(loaded.task_ids),
            "counts": dict(loaded.counts),
        },
        "component": component,
        "direction": direction,
        "change": change.strip(),
        "backend": backend,
        "model": model,
        "budgets": dict(budgets) if budgets is not None else dict(run_report.DEFAULT_BUDGETS),
        "provenance": harness_runs.provenance_hashes(base),
        "runs": {"base": None, "variant": None},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _experiment_block(
    manifest: Mapping[str, Any], side: str, problems: list[str]
) -> dict[str, Any]:
    block = manifest.get("experiment")
    if not isinstance(block, dict):
        problems.append(f"{side}: manifest has no experiment block")
        return {}
    return block


def _load_report(run_dir: Path, side: str) -> dict[str, Any]:
    try:
        return run_report.load_report(run_dir)
    except run_report.RunReportError as exc:
        raise ExperimentError(f"{side}: {exc}") from exc


def _differing(base: Mapping[str, Any], variant: Mapping[str, Any]) -> list[str]:
    keys = sorted(set(base) | set(variant))
    return [key for key in keys if base.get(key) != variant.get(key)]


def _identity(
    experiment: Experiment,
    base_report: Mapping[str, Any],
    base_manifest: Mapping[str, Any],
    variant_report: Mapping[str, Any],
    variant_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Return identity facts, or raise listing every non-isolated difference."""
    problems: list[str] = []
    base_block = _experiment_block(base_manifest, "base", problems)
    variant_block = _experiment_block(variant_manifest, "variant", problems)
    declared = experiment.data["subset"]
    assert isinstance(declared, dict)
    declared_ids = [str(item) for item in declared["task_ids"]]
    declared_sha = str(declared["sha256"])

    for side, block in (("base", base_block), ("variant", variant_block)):
        if block and block.get("id") != experiment.id:
            problems.append(
                f"{side}: experiment id is {block.get('id')!r}, expected {experiment.id!r}"
            )
        subset = block.get("subset") if block else None
        if not isinstance(subset, dict):
            if block:
                problems.append(f"{side}: manifest experiment has no subset")
            continue
        if subset.get("sha256") != declared_sha:
            problems.append(f"{side}: subset sha256 differs from the declaration")
        ids = subset.get("task_ids")
        if not isinstance(ids, list) or sorted(str(i) for i in ids) != sorted(declared_ids):
            problems.append(f"{side}: subset task ids differ from the declaration")

    for side, report in (("base", base_report), ("variant", variant_report)):
        reported = sorted(str(task["instance_id"]) for task in report.get("tasks", []))
        if reported != sorted(declared_ids):
            missing = sorted(set(declared_ids) - set(reported))
            extra = sorted(set(reported) - set(declared_ids))
            problems.append(f"{side}: task set mismatch (missing={missing}, extra={extra})")

    for key in ("backend", "model", "budgets"):
        if base_block.get(key) != variant_block.get(key):
            problems.append(f"{key} differs: {base_block.get(key)!r} -> {variant_block.get(key)!r}")
    declared_budgets = experiment.data.get("budgets")
    if isinstance(declared_budgets, dict) and base_block.get("budgets") != declared_budgets:
        problems.append("the runs' budgets differ from the declaration")
    for key in ("backend", "model"):
        declared_value = experiment.data.get(key)
        if declared_value is not None and base_block.get(key) != declared_value:
            problems.append(f"{key} differs from the declaration")

    base_prov = base_manifest.get("provenance")
    variant_prov = variant_manifest.get("provenance")
    differing = _differing(
        base_prov if isinstance(base_prov, dict) else {},
        variant_prov if isinstance(variant_prov, dict) else {},
    )
    expected = [str(experiment.data["component"])]
    if differing != expected:
        problems.append(
            f"differing provenance is {differing}, expected exactly {expected}; "
            "change one declared component per experiment and keep the same commit"
        )

    if problems:
        raise ExperimentError("cannot compare these runs:\n  - " + "\n  - ".join(problems))
    return {
        "experiment_id": experiment.id,
        "subset_id": experiment.subset_id,
        "subset_sha256": declared_sha,
        "component": experiment.data["component"],
        "declared_direction": experiment.data["direction"],
        "differing_provenance": differing,
        "same_subset": True,
        "same_backend": True,
        "same_model": True,
        "same_budgets": True,
        "same_repo_commit": "repo_commit" not in differing,
    }


def _task_signal(task: Mapping[str, Any]) -> dict[str, Any]:
    delivery = task.get("delivery")
    delivery = delivery if isinstance(delivery, dict) else {}
    return {
        "resolved": task.get("resolved"),
        "failure_kind": task.get("failure_kind"),
        "patch_scope": delivery.get("patch_scope"),
        "submitted": bool(delivery.get("submitted")),
        "tool_calls": task.get("tool_calls"),
        "wall_seconds": task.get("wall_seconds"),
        "patch_sha256": task.get("patch_sha256"),
    }


def _tasks_by_id(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for task in report.get("tasks", []):
        if isinstance(task, dict) and isinstance(task.get("instance_id"), str):
            tasks[str(task["instance_id"])] = task
    return tasks


def _rows(
    experiment: Experiment,
    base_report: Mapping[str, Any],
    variant_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    base_tasks = _tasks_by_id(base_report)
    variant_tasks = _tasks_by_id(variant_report)
    declared = experiment.data["subset"]
    assert isinstance(declared, dict)
    rows: list[dict[str, Any]] = []
    for instance_id in [str(item) for item in declared["task_ids"]]:
        rows.append(
            {
                "instance_id": instance_id,
                "base": _task_signal(base_tasks[instance_id]),
                "variant": _task_signal(variant_tasks[instance_id]),
            }
        )
    return rows


def _totals(signals: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    scopes = dict.fromkeys(run_report.PATCH_SCOPES, 0)
    for signal in signals:
        scope = signal.get("patch_scope")
        if isinstance(scope, str) and scope in scopes:
            scopes[scope] += 1
    return {
        "tasks": len(signals),
        "resolved": sum(1 for signal in signals if signal.get("resolved") is True),
        "unknown": sum(1 for signal in signals if signal.get("resolved") is None),
        "submitted": sum(1 for signal in signals if signal.get("submitted") is True),
        **{f"scope_{scope}": count for scope, count in scopes.items()},
    }


def _verdict(
    rows: Sequence[Mapping[str, Any]],
    base_totals: Mapping[str, int],
    variant_totals: Mapping[str, int],
) -> tuple[str, str]:
    base_resolved = int(base_totals["resolved"])
    variant_resolved = int(variant_totals["resolved"])
    if variant_resolved != base_resolved:
        verdict = "helped" if variant_resolved > base_resolved else "hurt"
        return (
            verdict,
            f"resolved {base_resolved} -> {variant_resolved} under an isolated contrast",
        )
    identical = all(
        row["base"]["resolved"] == row["variant"]["resolved"]
        and row["base"]["failure_kind"] == row["variant"]["failure_kind"]
        for row in rows
    )
    if identical:
        return (
            "no observed effect",
            f"resolved {base_resolved} -> {variant_resolved}; "
            f"failure_kind identical on {len(rows)}/{len(rows)}",
        )
    changed = [
        str(row["instance_id"])
        for row in rows
        if row["base"]["failure_kind"] != row["variant"]["failure_kind"]
    ]
    return (
        "confounded",
        f"resolved {base_resolved} -> {variant_resolved} but failure_kind changed on "
        f"{', '.join(changed)}",
    )


def finish(
    root: Path | None,
    *,
    experiment_id: str,
    base_run: Path,
    variant_run: Path,
) -> dict[str, Any]:
    """Compare two archived runs and write ``comparison.json``; return it."""
    experiment = load_experiment(root, experiment_id)
    base_report = _load_report(Path(base_run), "base")
    variant_report = _load_report(Path(variant_run), "variant")
    identity = _identity(
        experiment,
        base_report,
        run_report.load_manifest(Path(base_run)),
        variant_report,
        run_report.load_manifest(Path(variant_run)),
    )
    rows = _rows(experiment, base_report, variant_report)
    base_totals = _totals([row["base"] for row in rows])
    variant_totals = _totals([row["variant"] for row in rows])
    verdict, reason = _verdict(rows, base_totals, variant_totals)
    delivery_signal = {
        key: variant_totals[key] - base_totals[key]
        for key in (
            "submitted",
            "scope_src_only",
            "scope_edits_tests",
            "scope_config_only",
            "scope_scratch",
            "scope_none",
            "scope_corrupted",
        )
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "experiment": experiment.id,
        "generated_at": datetime.now(UTC).isoformat(),
        "base_run": base_report.get("run_id", Path(base_run).name),
        "variant_run": variant_report.get("run_id", Path(variant_run).name),
        "change": experiment.data["change"],
        "identity": identity,
        "totals": {"base": base_totals, "variant": variant_totals},
        "delivery_signal": delivery_signal,
        "resolution_verdict": verdict,
        "resolution_reason": reason,
        "tasks": rows,
    }
    experiment.comparison_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _resolved_text(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def render_comparison(result: Mapping[str, Any]) -> str:
    """Render the comparison as the Markdown a reviewer reads."""
    identity = result.get("identity", {})
    totals = result.get("totals", {})
    base = totals.get("base", {}) if isinstance(totals, Mapping) else {}
    variant = totals.get("variant", {}) if isinstance(totals, Mapping) else {}
    signal = result.get("delivery_signal", {})
    lines = [
        f"# Experiment {result.get('experiment', '?')}",
        "",
        f"- Subset: `{identity.get('subset_id', '?')}` "
        f"({base.get('tasks', 0)} tasks, sha256 `{str(identity.get('subset_sha256', ''))[:8]}`)",
        f"- Change: {result.get('change', '')}",
        f"- Declared component: `{identity.get('component', '?')}` "
        f"(expected `{identity.get('declared_direction', '?')}`)",
        f"- Base run: `{result.get('base_run', '?')}` | "
        f"Variant run: `{result.get('variant_run', '?')}`",
        f"- Differing provenance: `{', '.join(identity.get('differing_provenance', []))}`",
        "",
        "## Delivery signal (descriptive, never a verdict - R8)",
        "",
        f"submitted {base.get('submitted', 0)} -> {variant.get('submitted', 0)} "
        f"(delta {signal.get('submitted', 0):+d}); "
        f"clean_src_only {base.get('scope_src_only', 0)} -> "
        f"{variant.get('scope_src_only', 0)} "
        f"(delta {signal.get('scope_src_only', 0):+d}); "
        f"edits_tests {base.get('scope_edits_tests', 0)} -> "
        f"{variant.get('scope_edits_tests', 0)}; "
        f"scratch {base.get('scope_scratch', 0)} -> {variant.get('scope_scratch', 0)}",
        "",
        "## Resolution verdict",
        "",
        f"**{result.get('resolution_verdict', 'confounded')}** - "
        f"{result.get('resolution_reason', '')}",
        "",
        "| Task | resolved | failure_kind | patch_scope | submitted |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in result.get("tasks", []):
        base_task = row["base"]
        variant_task = row["variant"]
        lines.append(
            f"| `{row['instance_id']}` | "
            f"{_resolved_text(base_task.get('resolved'))} -> "
            f"{_resolved_text(variant_task.get('resolved'))} | "
            f"{base_task.get('failure_kind') or '-'} -> "
            f"{variant_task.get('failure_kind') or '-'} | "
            f"{base_task.get('patch_scope') or '-'} -> "
            f"{variant_task.get('patch_scope') or '-'} | "
            f"{base_task.get('submitted')!s} -> {variant_task.get('submitted')!s} |"
        )
    return "\n".join(lines) + "\n"


def _main_start(args: argparse.Namespace) -> int:
    try:
        path = start(
            args.root,
            experiment_id=args.id,
            subset=args.subset,
            component=args.component,
            direction=args.direction,
            change=args.change,
            backend=args.backend,
            model=args.model,
        )
    except (ExperimentError, subsets.SubsetError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"declared {args.id} at {path}")
    return 0


def _main_finish(args: argparse.Namespace) -> int:
    try:
        result = finish(
            args.root,
            experiment_id=args.id,
            base_run=args.base,
            variant_run=args.variant,
        )
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_comparison(result), end="")
    return 0


def _main_show(args: argparse.Namespace) -> int:
    try:
        experiment = load_experiment(args.root, args.id)
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(experiment.data, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for declared experiments."""
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-experiments",
        description="Declare and compare A/B experiments over archived runs.",
    )
    parser.add_argument("--root", type=Path, default=None, help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    start_parser = sub.add_parser("start", help="declare an experiment before its runs")
    start_parser.add_argument("--id", required=True)
    start_parser.add_argument("--subset", required=True, help="subset name or path")
    start_parser.add_argument("--component", required=True, choices=COMPONENTS)
    start_parser.add_argument("--direction", required=True, choices=DIRECTIONS)
    start_parser.add_argument("--change", required=True, help="one line: what changes")
    start_parser.add_argument("--backend", default=None)
    start_parser.add_argument("--model", default=None)
    start_parser.set_defaults(handler=_main_start)

    finish_parser = sub.add_parser("finish", help="compare two archived runs")
    finish_parser.add_argument("--id", required=True)
    finish_parser.add_argument("--base", required=True, type=Path)
    finish_parser.add_argument("--variant", required=True, type=Path)
    finish_parser.set_defaults(handler=_main_finish)

    show_parser = sub.add_parser("show", help="print one declaration")
    show_parser.add_argument("--id", required=True)
    show_parser.set_defaults(handler=_main_show)

    args = parser.parse_args(list(argv) if argv is not None else None)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
