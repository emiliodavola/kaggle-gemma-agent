#!/usr/bin/env python3
"""Four-rollout falsifier for the swegemma harness2 adapter.

Two tasks (``requests_6644`` and ``requests_7315``) are rolled against the base
submission and against the same tree plus one INV edit. The falsifier passes
only when all four rollouts are archived, the two trees have different
fingerprints, and at least one task differs in ``delivered`` or ``patch_sha256``.
It is a plumbing test, not a claim that the edit helps.

Run from the repository root, in WSL, with the backend env exported. It writes
``runs/harness2-falsifier/<tag>.json`` and prints a table.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tmp" / "harness2"))

from harness2.benchmarks.swegemma import (  # noqa: E402
    SwegemmaAdapter,
    SwegemmaError,
)
from harness2.core import tree as ht  # noqa: E402

TASKS = tuple(
    item.strip()
    for item in os.environ.get("FALSIFIER_TASKS", "requests_6644,requests_7315").split(",")
    if item.strip()
)
INV_EDIT = (
    "\n- Before diagnosing a source/disk mismatch, spend one call resolving which file the "
    'import loaded (`python -c "import module; print(module.__file__)"`); diagnose the module '
    "the interpreter actually uses.\n"
)


def _patch_sha(run_dir: Path) -> str | None:
    try:
        lines = (run_dir / "task_results.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        task_id = str(record.get("instance_id") or "")
        patch = run_dir / "patches" / f"{task_id}.patch"
        return hashlib.sha256(patch.read_bytes()).hexdigest() if patch.is_file() else None
    return None


def _fingerprint(run_dir: Path) -> str | None:
    try:
        payload = json.loads((run_dir / "harness.json").read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    value = payload.get("tree_fingerprint")
    return str(value) if value else None


def _edit_prompt(tree: Path) -> None:
    prompt = tree / "prompts" / "system.md"
    text = prompt.read_text(encoding="utf-8")
    if INV_EDIT.strip() in text:
        return
    prompt.write_text(text.rstrip() + INV_EDIT, encoding="utf-8")


def main() -> int:
    os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    tag = os.environ.get("FALSIFIER_RUN_TAG") or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    try:
        adapter = SwegemmaAdapter()
        base = adapter.base_harness()
        variant = Path(tempfile.mkdtemp(prefix="swegemma-falsifier-variant-"))
        shutil.copytree(base, variant, dirs_exist_ok=True)
        _edit_prompt(variant)
        surface = adapter.substrate.surface()
        adapter.validate_tree(ht.read_tree(surface, base))
        adapter.validate_tree(ht.read_tree(surface, variant))
    except (SwegemmaError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rows: list[dict[str, object]] = []
    for task in TASKS:
        for label, tree in (("base", base), ("variant", variant)):
            run_id = f"falsifier-{tag}/{task}/{label}"
            try:
                run_dir = adapter.execute(task, tree, run_id)
            except SwegemmaError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            rows.append(
                {
                    "task": task,
                    "label": label,
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "archived": (run_dir / "summary.json").is_file(),
                    "delivered": adapter.delivered(run_dir),
                    "patch_sha256": _patch_sha(run_dir),
                    "tree_fingerprint": _fingerprint(run_dir),
                    "score": adapter.score(run_dir, task),
                }
            )

    by_key = {(str(row["task"]), str(row["label"])): row for row in rows}
    four_archived = len(rows) == 4 and all(bool(row["archived"]) for row in rows)
    fingerprints_differ = all(
        by_key[(task, "base")]["tree_fingerprint"] != by_key[(task, "variant")]["tree_fingerprint"]
        for task in TASKS
    )
    signal = any(
        by_key[(task, "base")]["delivered"] != by_key[(task, "variant")]["delivered"]
        or by_key[(task, "base")]["patch_sha256"] != by_key[(task, "variant")]["patch_sha256"]
        for task in TASKS
    )
    failures: list[str] = []
    if not four_archived:
        failures.append("one or more rollouts are not archived (summary.json missing)")
    if not fingerprints_differ:
        failures.append("base and variant report the same tree fingerprint; the tree was not used")
    if not signal:
        failures.append("no task differs in delivered or patch_sha256; k=1 carries no signal")

    result = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "tag": tag,
        "tasks": list(TASKS),
        "inv_edit": INV_EDIT.strip(),
        "base_tree": str(base),
        "variant_tree": str(variant),
        "rows": rows,
        "assertions": {
            "four_archived": four_archived,
            "fingerprints_differ": fingerprints_differ,
            "signal": signal,
        },
        "passed": not failures,
        "failures": failures,
    }
    out = REPO / "runs" / "harness2-falsifier" / f"{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"tag {tag}")
    print(f"{'task':<18} {'label':<8} {'delivered':<10} {'resolved':<9} {'patch':<10}")
    for row in rows:
        score = row["score"] if isinstance(row["score"], dict) else {}
        resolved = score.get("resolved")
        patch = row["patch_sha256"]
        print(
            f"{row['task']:<18} {row['label']:<8} {row['delivered']!s:<10} "
            f"{resolved!s:<9} {(patch or '-')[:10]:<10}"
        )
    print(
        f"four_archived={four_archived} fingerprints_differ={fingerprints_differ} signal={signal}"
    )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"result: {out}")
        return 1
    print(f"PASS: adapter plumbing carries a measurable difference; result: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
