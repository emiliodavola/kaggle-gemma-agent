"""Map the harness-native SWE-agent SFT dataset into the canonical record.

The dataset already uses the harness tool names and a ``tool_call_id`` on every
tool result, so this module validates rather than translates. It replaces the
teacher system prompt with the shipped one, strips null tool arguments and maps
the dataset verification vocabulary onto the canonical one.
"""

from __future__ import annotations

import json
from typing import Any

from e4b_training.data.canonical import Message, Record, ToolCall, validate_record
from e4b_training.utils.paths import REPO_ROOT

DATASET = "vishalxyzabc7527/gemma4-swe-agent-sft-harness"
REVISION = "7b3c7d619fa3c2f5d24a33bce5b413dcc48b2680"
VERIFICATION_MAP = {
    "VERIFIED": "verified",
    "PARTIALLY_VERIFIED": "declared",
    "FAILED": "failed",
    "UNVERIFIED": "unknown",
}
ROLES = {"system", "user", "assistant", "tool"}


def shipped_system_prompt() -> str:
    return (REPO_ROOT / "submission" / "prompts" / "system.md").read_text(encoding="utf-8")


def _arguments(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return {key: value for key, value in raw.items() if value is not None}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        if isinstance(parsed, dict):
            return {key: value for key, value in parsed.items() if value is not None}
    return None


def _map_message(raw: dict[str, Any], index: int) -> tuple[Message | None, str | None]:
    role = raw.get("role")
    if role not in ROLES:
        return None, f"unknown-role-{role}@{index}"
    calls: list[ToolCall] = []
    for position, call in enumerate(raw.get("tool_calls") or []):
        function = call.get("function") or {}
        name = function.get("name")
        identifier = call.get("id")
        if not identifier:
            return None, f"tool-call-id-missing@{index}.{position}"
        if not name:
            return None, f"tool-call-name-missing@{index}.{position}"
        arguments = _arguments(function.get("arguments"))
        if arguments is None:
            return None, f"tool-arguments-not-object@{index}.{position}"
        calls.append(ToolCall(id=str(identifier), name=str(name), arguments=arguments))
    return (
        Message(
            role=str(role),
            content=raw.get("content") or "",
            tool_calls=tuple(calls),
            tool_call_id=raw.get("tool_call_id"),
        ),
        None,
    )


def map_record(
    row: dict[str, Any],
    system_prompt: str | None = None,
) -> tuple[Record | None, list[str]]:
    messages = row.get("messages") or []
    if not messages or messages[0].get("role") != "system":
        return None, ["missing-system-message"]
    prompt = system_prompt if system_prompt is not None else shipped_system_prompt()
    if not prompt.strip():
        return None, ["missing-target-system-prompt"]

    mapped: list[Message] = [Message(role="system", content=prompt)]
    for index, raw in enumerate(messages[1:], start=1):
        message, error = _map_message(raw, index)
        if error:
            return None, [error]
        assert message is not None
        mapped.append(message)

    status = VERIFICATION_MAP.get(str(row.get("verification_status") or "").upper(), "unknown")
    license_info = row.get("license") or {}
    metadata = row.get("metadata") or {}
    record = Record(
        id=f"gemma4-sft:{row.get('task_id')}",
        source=DATASET,
        source_revision=REVISION,
        source_record_id=str(row.get("task_id") or ""),
        language="python",
        repository=str(row.get("repository") or "unknown"),
        task_description=next(
            (message.content for message in mapped if message.role == "user"), ""
        ),
        resolved=bool(row.get("is_successful_demonstration")) and status == "verified",
        verification_status=status,
        messages=tuple(mapped),
        tool_names=tuple(sorted({call.name for message in mapped for call in message.tool_calls})),
        patch=row.get("final_patch"),
        test_results=row.get("test_results") or {},
        license=str(license_info.get("dataset_license") or "unknown"),
        metadata={
            "source_dataset": row.get("source_dataset"),
            "source_split": row.get("source_split"),
            "dataset_split": row.get("dataset_split"),
            "teacher_model": row.get("teacher_model"),
            "teacher": row.get("teacher") or {},
            "categories": row.get("categories") or [],
            "repository_license": license_info.get("repository_license"),
            "repo_url": row.get("repo_url"),
            "pull_number": row.get("pull_number"),
            "issue_id": row.get("issue_id"),
            "is_successful_demonstration": row.get("is_successful_demonstration"),
            "diff_flags": row.get("diff_flags") or {},
            "filtering": row.get("filtering") or {},
            "language_source": "inferred: nebius/SWE-rebench Python task tested with pytest",
            **metadata,
        },
    )
    problems = validate_record(record)
    if problems:
        return None, problems
    return record, []
