"""T4: the canonical schema and the harness-native record mapper."""

from __future__ import annotations

from dataclasses import replace

from e4b_training.data.canonical import (
    Message,
    Record,
    ToolCall,
    record_from_dict,
    record_to_dict,
    validate_record,
)
from e4b_training.data.harness_records import (
    map_record,
    shipped_system_prompt,
)

SYSTEM = "You are the shipped agent."


def _call(name: str, arguments: dict, call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def _message(
    role: str,
    content: str = "",
    tool_calls=None,
    tool_call_id: str | None = None,
) -> dict:
    return {
        "role": role,
        "content": content,
        "tool_calls": tool_calls or [],
        "tool_call_id": tool_call_id,
    }


def _row(
    messages: list[dict],
    verification: str = "VERIFIED",
    successful: bool = True,
) -> dict:
    return {
        "task_id": "acme__demo-1",
        "repository": "acme/demo",
        "repo_url": "https://github.com/acme/demo",
        "pull_number": 1,
        "issue_id": "issue-1",
        "source_dataset": "nebius/SWE-rebench",
        "source_split": "train",
        "dataset_split": "train",
        "teacher_model": "claude-opus-5-5",
        "teacher": {"name": "claude"},
        "categories": ["bug_fix"],
        "license": {"dataset_license": "cc-by-4.0", "repository_license": "MIT License"},
        "verification_status": verification,
        "is_successful_demonstration": successful,
        "final_patch": "diff --git a/a.py b/a.py",
        "test_results": {"command": "pytest", "exit_code": 0},
        "diff_flags": {"touches_tests": False},
        "filtering": {"bucket": "sft"},
        "messages": messages,
    }


def _happy_messages() -> list[dict]:
    return [
        _message("system", "teacher prompt"),
        _message("user", "Fix the bug in /workspace"),
        _message(
            "assistant",
            "",
            [
                _call("run_command", {"command": "pytest -q"}, "c1"),
                _call("read_file", {"filepath": "/workspace/a.py"}, "c2"),
            ],
        ),
        _message("tool", "1 failed", tool_call_id="c2"),
        _message("tool", "failure output", tool_call_id="c1"),
        _message(
            "assistant",
            "",
            [
                _call(
                    "edit_file",
                    {
                        "filepath": "/workspace/a.py",
                        "old_string": "x",
                        "new_string": "y",
                    },
                    "c3",
                )
            ],
        ),
        _message("tool", "edited", tool_call_id="c3"),
        _message(
            "assistant",
            "",
            [
                _call(
                    "submit_patch",
                    {"command": None, "filepath": None, "content": None},
                    "c4",
                )
            ],
        ),
        _message("tool", "submitted", tool_call_id="c4"),
    ]


def test_happy_path_replaces_prompt_and_keeps_multiple_calls() -> None:
    record, reasons = map_record(_row(_happy_messages()), SYSTEM)

    assert reasons == []
    assert record is not None
    assert record.messages[0].content == SYSTEM
    assert record.tool_names == ("edit_file", "read_file", "run_command", "submit_patch")
    assert len(record.messages[2].tool_calls) == 2
    assert record.messages[2].tool_calls[0].name == "run_command"
    assert record.messages[2].tool_calls[1].name == "read_file"
    assert record.messages[3].tool_call_id == "c2"
    assert record.messages[4].tool_call_id == "c1"
    assert record.messages[7].tool_calls[0].name == "submit_patch"
    assert record.messages[7].tool_calls[0].arguments == {}
    assert record.verification_status == "verified"
    assert record.resolved is True
    assert record.patch == "diff --git a/a.py b/a.py"
    assert record.license == "cc-by-4.0"
    assert record.metadata["repository_license"] == "MIT License"


def test_verification_vocabulary_is_mapped() -> None:
    expected = {
        "VERIFIED": "verified",
        "PARTIALLY_VERIFIED": "declared",
        "FAILED": "failed",
        "UNVERIFIED": "unknown",
    }
    for source, target in expected.items():
        record, reasons = map_record(_row(_happy_messages(), verification=source), SYSTEM)
        assert reasons == []
        assert record is not None
        assert record.verification_status == target
        assert record.resolved is (target == "verified")


def test_missing_system_is_dropped() -> None:
    record, reasons = map_record(_row([_message("user", "Fix")]), SYSTEM)
    assert record is None
    assert "missing-system-message" in reasons


def test_unknown_tool_is_dropped() -> None:
    messages = [
        _message("system", "x"),
        _message("user", "Fix"),
        _message("assistant", "", [_call("execute_bash", {"command": "ls"}, "c1")]),
        _message("tool", "ok", tool_call_id="c1"),
    ]
    record, reasons = map_record(_row(messages), SYSTEM)
    assert record is None
    assert any("is not a harness tool" in reason for reason in reasons)


def test_orphan_tool_result_is_dropped() -> None:
    messages = [
        _message("system", "x"),
        _message("user", "Fix"),
        _message("tool", "ok", tool_call_id="c1"),
    ]
    record, reasons = map_record(_row(messages), SYSTEM)
    assert record is None
    assert any("does not match a pending call" in reason for reason in reasons)


def test_unmatched_tool_call_is_dropped() -> None:
    messages = [
        _message("system", "x"),
        _message("user", "Fix"),
        _message("assistant", "", [_call("run_command", {"command": "ls"}, "c1")]),
    ]
    record, reasons = map_record(_row(messages), SYSTEM)
    assert record is None
    assert any("unmatched tool calls" in reason for reason in reasons)


def test_duplicate_tool_result_is_dropped() -> None:
    messages = [
        _message("system", "x"),
        _message("user", "Fix"),
        _message("assistant", "", [_call("run_command", {"command": "ls"}, "c1")]),
        _message("tool", "ok", tool_call_id="c1"),
        _message("tool", "again", tool_call_id="c1"),
    ]
    record, reasons = map_record(_row(messages), SYSTEM)
    assert record is None
    assert any("does not match a pending call" in reason for reason in reasons)


def test_missing_call_id_is_dropped() -> None:
    messages = [
        _message("system", "x"),
        _message("user", "Fix"),
        _message("assistant", "", [_call("run_command", {"command": "ls"}, "")]),
        _message("tool", "ok", tool_call_id=""),
    ]
    record, reasons = map_record(_row(messages), SYSTEM)
    assert record is None
    assert any("tool-call-id-missing" in reason for reason in reasons)


def test_round_trip_is_lossless() -> None:
    record, _ = map_record(_row(_happy_messages()), SYSTEM)
    assert record is not None
    payload = record_to_dict(record)
    assert payload["schema_version"] == "1.0"
    assert record_from_dict(payload) == record


def test_validation_rejects_a_turn_before_tool_results() -> None:
    record, _ = map_record(_row(_happy_messages()), SYSTEM)
    assert record is not None
    broken_messages = list(record.messages)
    first_call = broken_messages[2]
    broken_messages[3] = replace(first_call, role="assistant", tool_calls=())
    broken = replace(record, messages=tuple(broken_messages))
    problems = validate_record(broken)
    assert any("assistant turn before the tool results" in problem for problem in problems)


def test_shipped_prompt_is_read_from_the_submission() -> None:
    prompt = shipped_system_prompt()
    assert "Non-negotiables" in prompt


def test_schema_supports_multiple_calls_per_turn() -> None:
    record = Record(
        id="r1",
        source="s",
        source_revision="rev",
        source_record_id="1",
        language="python",
        repository="acme/demo",
        task_description="fix",
        resolved=True,
        verification_status="verified",
        messages=(
            Message(role="system", content="sys"),
            Message(role="user", content="fix"),
            Message(
                role="assistant",
                tool_calls=(
                    ToolCall(id="a", name="run_command", arguments={"command": "ls"}),
                    ToolCall(id="b", name="read_file", arguments={"filepath": "/a.py"}),
                ),
            ),
            Message(role="tool", content="ok", tool_call_id="b"),
            Message(role="tool", content="ok", tool_call_id="a"),
        ),
        tool_names=("read_file", "run_command"),
    )
    assert validate_record(record) == []
