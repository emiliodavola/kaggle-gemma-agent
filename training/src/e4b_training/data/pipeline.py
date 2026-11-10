"""Filter, deduplicate and split the harness-native SFT corpus.

The pipeline streams the dataset, maps each row through the canonical mapper,
applies the competition-bound filters, deduplicates on four keys and writes one
manifest plus two JSONL splits. A row that fails a filter or a validator is
counted with its reason; nothing is fabricated or silently repaired.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from e4b_training.data.audit import EXCLUDED_REPOS, holdout_repositories
from e4b_training.data.canonical import Record, record_to_dict
from e4b_training.data.harness_records import DATASET, REVISION, map_record

LICENSE_ALLOWLIST = {
    "MIT License",
    "Apache License 2.0",
    'BSD 3-Clause "New" or "Revised" License',
    "BSD License",
    'BSD 2-Clause "Simplified" License',
    "BSD",
    "Zope Public License 2.1",
    "BSD 3-Clause",
    "BSD-3-Clause",
    "ISC License",
    "BSD 2-clause license",
    "Creative Commons Zero v1.0 Universal",
    "Apache License 2.0 or MIT License",
    "New BSD License",
    "The Unlicense",
    "MIT/X Consortium license",
    "MIT/Apache-2.0 Dual License",
    "Apache 2.0 or BSD3",
    "BSD 3-Clause License",
}


def _reason_category(reason: str) -> str:
    if "assistant turn before the tool results" in reason:
        return "assistant-before-tool-result"
    if "is not a harness tool" in reason:
        return "unknown-tool"
    if "does not match a pending call" in reason:
        return "orphan-tool-result"
    if "unmatched tool calls" in reason:
        return "unmatched-tool-call"
    if "tool result has no tool_call_id" in reason:
        return "tool-result-without-id"
    if "duplicate tool call id" in reason:
        return "duplicate-tool-call-id"
    if "tool call has no id" in reason:
        return "tool-call-without-id"
    if "tool arguments are not JSON serializable" in reason:
        return "tool-arguments-not-json"
    if "unknown role" in reason:
        return "unknown-role"
    if "first message must be system" in reason:
        return "missing-system"
    return reason


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def conversation_hash(record: Record) -> str:
    payload = [
        {
            "role": message.role,
            "content": message.content,
            "reasoning": message.reasoning,
            "tool_calls": [
                {"id": call.id, "name": call.name, "arguments": call.arguments}
                for call in message.tool_calls
            ],
            "tool_call_id": message.tool_call_id,
        }
        for message in record.messages
    ]
    return _hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def dedup_keys(record: Record) -> dict[str, str]:
    keys = {
        "conversation": conversation_hash(record),
        "task": _hash(record.source_record_id),
    }
    issue_id = record.metadata.get("issue_id")
    if issue_id:
        keys["issue"] = _hash(f"{record.repository}#{issue_id}")
    if record.patch:
        keys["patch"] = _hash(record.patch)
    return keys


def filter_record(record: Record, holdout: set[str]) -> tuple[bool, str]:
    if record.verification_status != "verified":
        return False, f"verification:{record.verification_status}"
    if not record.resolved:
        return False, "not-resolved"
    license_name = str(record.metadata.get("repository_license") or "")
    if license_name not in LICENSE_ALLOWLIST:
        return False, f"license:{license_name}"
    if record.repository in EXCLUDED_REPOS:
        return False, f"excluded-repo:{record.repository}"
    if record.repository in holdout:
        return False, f"holdout-repo:{record.repository}"
    return True, "kept"


@dataclass
class PipelineResult:
    records: dict[str, list[Record]] = field(
        default_factory=lambda: {"train": [], "validation": []}
    )
    manifest: dict[str, Any] = field(default_factory=dict)


def _new_counters() -> dict[str, Any]:
    return {
        "source_rows": 0,
        "mapped_ok": 0,
        "reasons": Counter(),
        "tool_names": Counter(),
        "multi_call_turns": 0,
        "licenses": Counter(),
        "repositories": set(),
        "conversations": set(),
    }


def prepare(
    rows: Iterable[tuple[str, dict[str, Any]]],
    system_prompt: str,
    holdout: set[str] | None = None,
) -> PipelineResult:
    holdout_repos = holdout if holdout is not None else holdout_repositories()
    counters = _new_counters()
    seen: set[str] = set()
    result = PipelineResult()

    for split, row in rows:
        counters["source_rows"] += 1
        record, problems = map_record(row, system_prompt)
        if record is None:
            counters["reasons"][_reason_category(problems[0])] += 1
            continue
        counters["mapped_ok"] += 1
        keep, reason = filter_record(record, holdout_repos)
        if not keep:
            counters["reasons"][reason] += 1
            continue

        keys = dedup_keys(record)
        duplicate = next((name for name, value in keys.items() if value in seen), None)
        if duplicate:
            counters["reasons"][f"duplicate-{duplicate}"] += 1
            continue
        seen.update(keys.values())

        counters["tool_names"].update(record.tool_names)
        counters["licenses"][str(record.metadata.get("repository_license") or "unknown")] += 1
        counters["repositories"].add(record.repository)
        counters["conversations"].add(keys["conversation"])
        counters["multi_call_turns"] += sum(
            1 for message in record.messages if len(message.tool_calls) > 1
        )
        result.records["train" if split == "train" else "validation"].append(record)

    kept = sum(len(records) for records in result.records.values())
    result.manifest = {
        "schema_version": "1.0",
        "dataset": DATASET,
        "revision": REVISION,
        "source_rows": counters["source_rows"],
        "mapped": counters["source_rows"],
        "mapped_ok": counters["mapped_ok"],
        "invalid": counters["source_rows"] - counters["mapped_ok"],
        "kept": kept,
        "dropped": counters["source_rows"] - kept,
        "drop_reasons": dict(counters["reasons"].most_common()),
        "splits": {name: len(records) for name, records in result.records.items()},
        "tool_names": dict(counters["tool_names"].most_common()),
        "multi_call_turns": counters["multi_call_turns"],
        "distinct_repositories": len(counters["repositories"]),
        "distinct_conversations": len(counters["conversations"]),
        "license_counts": dict(counters["licenses"].most_common()),
        "excluded_repositories": sorted(EXCLUDED_REPOS),
        "holdout_repositories": sorted(holdout_repos),
        "system_prompt_sha256": _hash(system_prompt),
    }
    return result


def write_jsonl(records: list[Record], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record_to_dict(record), ensure_ascii=False) + "\n")
    return len(records)
