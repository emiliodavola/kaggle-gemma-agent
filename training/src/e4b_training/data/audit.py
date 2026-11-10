"""Audit the harness-native SFT dataset without downloading it.

The dataset is JSONL. This module streams each line from the Hugging Face
resolve URL, counts the fields the training and evaluation plan depend on, and
persists only the JSON report. No JSONL file is written to disk.

It measures the facts the dataset card asserts, so the pipeline does not have to
trust them: verification status, successful demonstrations, per-repository
leakage, tool names, tool-result pairing and license fields.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from e4b_training.utils.paths import ARTIFACTS_DIR, REPO_ROOT

DATASET = "vishalxyzabc7527/gemma4-swe-agent-sft-harness"
REVISION = "7b3c7d619fa3c2f5d24a33bce5b413dcc48b2680"
SPLITS = {
    "train": "data/sft_train.jsonl",
    "validation": "data/sft_val.jsonl",
}
HARNESS_TOOLS = {
    "run_command",
    "submit_patch",
    "get_status",
    "read_file",
    "edit_file",
    "write_file",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
}
EXCLUDED_REPOS = {
    "fastapi/fastapi",
    "Textualize/rich",
    "psf/requests",
    "encode/httpx",
}
HOLDOUT_REPOS = {
    "fastapi": "fastapi/fastapi",
    "rich": "Textualize/rich",
    "requests": "psf/requests",
    "httpx": "encode/httpx",
}


def resolve_url(path: str) -> str:
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{path}"


def stream_rows(path: str) -> Iterator[dict[str, Any]]:
    with urllib.request.urlopen(resolve_url(path), timeout=120) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            yield json.loads(line)


def holdout_repositories() -> set[str]:
    path = REPO_ROOT / "experiments" / "subsets" / "ft-holdout.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    repositories = set()
    for task_id in payload.get("task_ids", []):
        prefix = task_id.split("_", 1)[0]
        if prefix in HOLDOUT_REPOS:
            repositories.add(HOLDOUT_REPOS[prefix])
    return repositories


def _tool_call_names(message: dict[str, Any]) -> list[str]:
    names = []
    for call in message.get("tool_calls") or []:
        name = (call.get("function") or {}).get("name")
        if name:
            names.append(name)
    return names


def audit_row(row: dict[str, Any], split: str, counters: dict[str, Any]) -> None:
    counters["rows"] += 1
    counters["splits"][split] += 1
    counters["task_ids"].add(row.get("task_id"))
    counters["repositories"][row.get("repository") or "unknown"] += 1
    counters["source_datasets"][row.get("source_dataset") or "unknown"] += 1
    counters["dataset_splits"][row.get("dataset_split") or "unknown"] += 1
    counters["verification_status"][row.get("verification_status") or "unknown"] += 1
    counters["successful"][str(bool(row.get("is_successful_demonstration")))] += 1
    counters["teacher_models"][row.get("teacher_model") or "unknown"] += 1

    license_info = row.get("license") or {}
    counters["dataset_licenses"][license_info.get("dataset_license") or "unknown"] += 1
    counters["repository_licenses"][license_info.get("repository_license") or "unknown"] += 1

    if row.get("final_patch"):
        counters["patches"] += 1
    test_results = row.get("test_results") or {}
    if test_results:
        counters["test_results"] += 1
        counters["test_exit_codes"][str(test_results.get("exit_code"))] += 1

    messages = row.get("messages") or []
    counters["roles"].update(message.get("role") or "unknown" for message in messages)
    counters["message_counts"][str(len(messages))] += 1

    pending: set[str] = set()
    for message in messages:
        role = message.get("role")
        names = _tool_call_names(message)
        if names:
            counters["tool_calls"] += len(names)
            counters["tool_names"].update(names)
            if len(names) > 1:
                counters["multiple_calls_in_turn"] += 1
            for name in names:
                if name not in HARNESS_TOOLS:
                    counters["unknown_tool_names"][name] += 1
            pending.update(
                str(call.get("id")) for call in message.get("tool_calls") or [] if call.get("id")
            )
        if role == "tool":
            tool_call_id = message.get("tool_call_id")
            if tool_call_id is None:
                counters["tool_results_without_id"] += 1
            elif str(tool_call_id) not in pending:
                counters["orphan_tool_results"] += 1
            else:
                pending.discard(str(tool_call_id))
        if role not in {"system", "user", "assistant", "tool"}:
            counters["unknown_roles"][role or "unknown"] += 1
        if role == "assistant":
            counters["assistant_messages"] += 1
        if role == "tool":
            counters["tool_messages"] += 1

    if pending:
        counters["unmatched_tool_calls"] += 1
    if not messages or messages[0].get("role") != "system":
        counters["missing_system"] += 1
    if not any(message.get("role") == "user" for message in messages):
        counters["missing_user"] += 1
    if row.get("repository") in EXCLUDED_REPOS:
        counters["excluded_repo_rows"][row.get("repository")] += 1


def build_report(counters: dict[str, Any], holdout: set[str]) -> dict[str, Any]:
    overlap = sorted(set(counters["repositories"]) & holdout)
    rows = counters["rows"]
    successful = counters["successful"].get("True", 0)
    verified = counters["verification_status"].get("VERIFIED", 0)
    return {
        "schema_version": "1.0",
        "dataset": DATASET,
        "revision": REVISION,
        "read_mode": "streamed-jsonl",
        "splits": dict(counters["splits"]),
        "rows": rows,
        "distinct_task_ids": len(counters["task_ids"]),
        "distinct_repositories": len(counters["repositories"]),
        "verification_status": dict(counters["verification_status"].most_common()),
        "is_successful_demonstration": dict(counters["successful"].most_common()),
        "successful_and_verified": min(successful, verified),
        "test_results_rows": counters["test_results"],
        "test_exit_codes": dict(counters["test_exit_codes"].most_common()),
        "patches": counters["patches"],
        "assistant_messages": counters["assistant_messages"],
        "tool_messages": counters["tool_messages"],
        "tool_calls": counters["tool_calls"],
        "tool_names": dict(counters["tool_names"].most_common()),
        "multiple_calls_in_turn": counters["multiple_calls_in_turn"],
        "unknown_tool_names": dict(counters["unknown_tool_names"]),
        "orphan_tool_results": counters["orphan_tool_results"],
        "tool_results_without_id": counters["tool_results_without_id"],
        "unmatched_tool_calls": counters["unmatched_tool_calls"],
        "missing_system": counters["missing_system"],
        "missing_user": counters["missing_user"],
        "unknown_roles": dict(counters["unknown_roles"]),
        "dataset_licenses": dict(counters["dataset_licenses"].most_common()),
        "repository_licenses": dict(counters["repository_licenses"].most_common(25)),
        "source_datasets": dict(counters["source_datasets"].most_common()),
        "dataset_splits": dict(counters["dataset_splits"].most_common()),
        "teacher_models": dict(counters["teacher_models"].most_common()),
        "top_repositories": dict(counters["repositories"].most_common(25)),
        "excluded_repo_rows": dict(counters["excluded_repo_rows"]),
        "holdout_repository_overlap": overlap,
        "disk_note": "no JSONL file is persisted; rows are streamed from the resolve URL",
    }


def new_counters() -> dict[str, Any]:
    return {
        "rows": 0,
        "splits": Counter(),
        "task_ids": set(),
        "repositories": Counter(),
        "source_datasets": Counter(),
        "dataset_splits": Counter(),
        "verification_status": Counter(),
        "successful": Counter(),
        "teacher_models": Counter(),
        "dataset_licenses": Counter(),
        "repository_licenses": Counter(),
        "patches": 0,
        "test_results": 0,
        "test_exit_codes": Counter(),
        "roles": Counter(),
        "message_counts": Counter(),
        "assistant_messages": 0,
        "tool_messages": 0,
        "tool_calls": 0,
        "tool_names": Counter(),
        "multiple_calls_in_turn": 0,
        "unknown_tool_names": Counter(),
        "orphan_tool_results": 0,
        "tool_results_without_id": 0,
        "unmatched_tool_calls": 0,
        "missing_system": 0,
        "missing_user": 0,
        "unknown_roles": Counter(),
        "excluded_repo_rows": Counter(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the harness-native SFT dataset.")
    parser.add_argument(
        "--split",
        action="append",
        choices=sorted(SPLITS),
        help="audit only this split; repeatable; default both",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="stop after N rows per split (0 = all)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ARTIFACTS_DIR / "reports" / "dataset_audit.json",
    )
    args = parser.parse_args(argv)

    splits = args.split or sorted(SPLITS)
    counters = new_counters()
    for split in splits:
        for index, row in enumerate(stream_rows(SPLITS[split]), start=1):
            audit_row(row, split, counters)
            if args.max_rows and index >= args.max_rows:
                break

    report = build_report(counters, holdout_repositories())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        f"rows={report['rows']} verified={report['verification_status'].get('VERIFIED', 0)} "
        f"successful={report['is_successful_demonstration'].get('True', 0)} "
        f"repos={report['distinct_repositories']} tools={sorted(report['tool_names'])} "
        f"orphans={report['orphan_tool_results']} unknown_tools={report['unknown_tool_names']} "
        f"excluded={report['excluded_repo_rows']} "
        f"holdout_overlap={report['holdout_repository_overlap']}"
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
