"""T5-T7: filters, deduplication and splits for the harness-native corpus."""

from __future__ import annotations

import json

from e4b_training.data.harness_records import map_record
from e4b_training.data.pipeline import (
    conversation_hash,
    filter_record,
    prepare,
    write_jsonl,
)

SYSTEM = "You are the shipped agent."


def _row(
    task_id: str = "t1",
    repo: str = "acme/demo",
    license_name: str = "MIT License",
    verification: str = "VERIFIED",
    successful: bool = True,
    split: str = "train",
    tool: str = "run_command",
) -> dict:
    arguments = {"command": "ls"} if tool == "run_command" else {"filepath": "/a.py"}
    return {
        "task_id": task_id,
        "repository": repo,
        "issue_id": f"issue-{task_id}",
        "source_dataset": "nebius/SWE-rebench",
        "source_split": split,
        "dataset_split": split,
        "teacher_model": "claude-opus-5-5",
        "license": {"dataset_license": "cc-by-4.0", "repository_license": license_name},
        "verification_status": verification,
        "is_successful_demonstration": successful,
        "final_patch": f"diff-{task_id}" if successful else "",
        "test_results": {"exit_code": 0},
        "messages": [
            {"role": "system", "content": "teacher", "tool_calls": [], "tool_call_id": None},
            {"role": "user", "content": "fix", "tool_calls": [], "tool_call_id": None},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": tool, "arguments": arguments},
                    }
                ],
                "tool_call_id": None,
            },
            {"role": "tool", "content": "ok", "tool_calls": [], "tool_call_id": "c1"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c2",
                        "type": "function",
                        "function": {"name": "submit_patch", "arguments": {}},
                    }
                ],
                "tool_call_id": None,
            },
            {"role": "tool", "content": "submitted", "tool_calls": [], "tool_call_id": "c2"},
        ],
    }


def _record(**kwargs):
    record, reasons = map_record(_row(**kwargs), SYSTEM)
    assert reasons == []
    assert record is not None
    return record


def test_filter_keeps_a_verified_permissive_record() -> None:
    keep, reason = filter_record(_record(), set())
    assert keep is True
    assert reason == "kept"


def test_filter_drops_failed_license_and_repositories() -> None:
    assert filter_record(_record(verification="FAILED"), set())[0] is False
    assert filter_record(_record(license_name="GPL-3.0"), set())[0] is False
    assert filter_record(_record(repo="fastapi/fastapi"), set())[0] is False
    assert filter_record(_record(repo="acme/demo"), {"acme/demo"})[0] is False


def test_conversation_hash_is_stable() -> None:
    first = conversation_hash(_record())
    second = conversation_hash(_record())
    assert first == second
    assert len(first) == 64


def test_dedup_keeps_one_copy() -> None:
    result = prepare([("train", _row()), ("train", _row())], SYSTEM, holdout=set())
    assert len(result.records["train"]) == 1
    assert result.manifest["kept"] == 1
    assert result.manifest["drop_reasons"] == {"duplicate-conversation": 1}


def test_split_follows_the_source_split() -> None:
    train_row = _row(task_id="a")
    validation_row = _row(task_id="b", split="val")
    validation_row["messages"][1]["content"] = "fix another bug"
    result = prepare(
        [("train", train_row), ("validation", validation_row)],
        SYSTEM,
        holdout=set(),
    )
    assert len(result.records["train"]) == 1
    assert len(result.records["validation"]) == 1
    assert result.manifest["splits"] == {"train": 1, "validation": 1}


def test_invalid_row_is_counted_not_fabricated() -> None:
    result = prepare([("train", _row(tool="execute_bash"))], SYSTEM, holdout=set())
    assert result.records["train"] == []
    assert result.manifest["kept"] == 0
    assert "unknown-tool" in result.manifest["drop_reasons"]


def test_manifest_records_provenance() -> None:
    result = prepare([("train", _row())], SYSTEM, holdout=set())
    manifest = result.manifest
    assert manifest["dataset"] == "vishalxyzabc7527/gemma4-swe-agent-sft-harness"
    assert manifest["source_rows"] == 1
    assert manifest["mapped"] == 1
    assert manifest["mapped_ok"] == 1
    assert manifest["invalid"] == 0
    assert manifest["distinct_repositories"] == 1
    assert len(manifest["system_prompt_sha256"]) == 64
    assert "run_command" in manifest["tool_names"]
    assert "submit_patch" in manifest["tool_names"]


def test_write_jsonl_round_trip(tmp_path) -> None:
    result = prepare([("train", _row())], SYSTEM, holdout=set())
    path = tmp_path / "sft_train.jsonl"
    assert write_jsonl(result.records["train"], path) == 1
    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["schema_version"] == "1.0"
    assert payload["source_record_id"] == "t1"
