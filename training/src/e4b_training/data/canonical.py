"""Canonical trajectory schema shared by every dataset loader.

One record is one task trajectory. It keeps the source identity, the license and
the verification status so a filtered corpus can always be traced back, and it
keeps tool calls and tool results in separate messages so the loss mask can tell
assistant output from environment output.

A single assistant turn may carry several tool calls; every result pairs back by
``tool_call_id`` and may arrive in any order, as long as no call is left
unmatched and no result arrives without a call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"
ROLES = ("system", "user", "assistant", "tool")
VERIFICATION_STATUSES = ("verified", "declared", "failed", "incomplete", "unknown")
HARNESS_TOOLS = (
    "run_command",
    "submit_patch",
    "get_status",
    "read_file",
    "edit_file",
    "write_file",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: str
    content: str = ""
    reasoning: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class Record:
    id: str
    source: str
    source_revision: str
    source_record_id: str
    language: str
    repository: str
    task_description: str
    resolved: bool
    verification_status: str
    messages: tuple[Message, ...]
    tool_names: tuple[str, ...] = ()
    patch: str | None = None
    test_results: dict[str, Any] = field(default_factory=dict)
    license: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


def validate_record(record: Record) -> list[str]:
    problems: list[str] = []
    if record.verification_status not in VERIFICATION_STATUSES:
        problems.append(f"unknown verification_status: {record.verification_status}")
    if not record.messages:
        problems.append("record has no messages")
        return problems
    if record.messages[0].role != "system":
        problems.append("first message must be system")

    pending: dict[str, int] = {}
    seen_calls: set[str] = set()
    seen_tools: set[str] = set()
    for index, message in enumerate(record.messages):
        if message.role not in ROLES:
            problems.append(f"message {index}: unknown role {message.role}")
            continue
        if message.role == "assistant":
            if pending:
                problems.append(
                    f"message {index}: assistant turn before the tool results for {sorted(pending)}"
                )
            for call in message.tool_calls:
                if call.name not in HARNESS_TOOLS:
                    problems.append(f"message {index}: tool {call.name} is not a harness tool")
                if not call.id:
                    problems.append(f"message {index}: tool call has no id")
                elif call.id in seen_calls:
                    problems.append(f"message {index}: duplicate tool call id {call.id}")
                try:
                    json.dumps(call.arguments)
                except (TypeError, ValueError):
                    problems.append(f"message {index}: tool arguments are not JSON serializable")
                if call.id:
                    pending[call.id] = index
                    seen_calls.add(call.id)
                seen_tools.add(call.name)
        elif message.role == "tool":
            if message.tool_call_id is None:
                problems.append(f"message {index}: tool result has no tool_call_id")
            elif message.tool_call_id not in pending:
                problems.append(
                    f"message {index}: tool result {message.tool_call_id} "
                    "does not match a pending call"
                )
            else:
                del pending[message.tool_call_id]
        elif message.tool_calls:
            problems.append(f"message {index}: only an assistant message may carry tool calls")

    if pending:
        problems.append(f"unmatched tool calls {sorted(pending)}")
    if tuple(sorted(seen_tools)) != tuple(record.tool_names):
        problems.append("tool_names does not match the tool calls in messages")
    return problems


def is_valid(record: Record) -> bool:
    return not validate_record(record)


def _tool_call_to_dict(call: ToolCall) -> dict[str, Any]:
    return {"id": call.id, "name": call.name, "arguments": call.arguments}


def _message_to_dict(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": message.role,
        "content": message.content,
        "tool_calls": [_tool_call_to_dict(call) for call in message.tool_calls],
    }
    if message.reasoning is not None:
        payload["reasoning"] = message.reasoning
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    return payload


def record_to_dict(record: Record) -> dict[str, Any]:
    problems = validate_record(record)
    if problems:
        raise ValueError("invalid record: " + "; ".join(problems))
    return {
        "schema_version": SCHEMA_VERSION,
        "id": record.id,
        "source": record.source,
        "source_revision": record.source_revision,
        "source_record_id": record.source_record_id,
        "language": record.language,
        "repository": record.repository,
        "task_description": record.task_description,
        "resolved": record.resolved,
        "verification_status": record.verification_status,
        "messages": [_message_to_dict(message) for message in record.messages],
        "tool_names": list(record.tool_names),
        "patch": record.patch,
        "test_results": record.test_results,
        "license": record.license,
        "metadata": record.metadata,
    }


def record_from_dict(payload: dict[str, Any]) -> Record:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {payload.get('schema_version')!r}")
    messages = tuple(
        Message(
            role=item["role"],
            content=item.get("content", ""),
            reasoning=item.get("reasoning"),
            tool_calls=tuple(
                ToolCall(id=call["id"], name=call["name"], arguments=call["arguments"])
                for call in item.get("tool_calls", ())
            ),
            tool_call_id=item.get("tool_call_id"),
        )
        for item in payload.get("messages", ())
    )
    record = Record(
        id=payload["id"],
        source=payload["source"],
        source_revision=payload["source_revision"],
        source_record_id=payload["source_record_id"],
        language=payload.get("language", "unknown"),
        repository=payload.get("repository", "unknown"),
        task_description=payload.get("task_description", ""),
        resolved=bool(payload.get("resolved", False)),
        verification_status=payload.get("verification_status", "unknown"),
        messages=messages,
        tool_names=tuple(payload.get("tool_names", ())),
        patch=payload.get("patch"),
        test_results=payload.get("test_results", {}),
        license=payload.get("license", "unknown"),
        metadata=payload.get("metadata", {}),
    )
    problems = validate_record(record)
    if problems:
        raise ValueError("invalid record: " + "; ".join(problems))
    return record
