"""T8: encoding helpers and learning-rate schedule."""

from __future__ import annotations

from e4b_training.training.sft import lr_at, to_template_messages


def test_to_template_messages_maps_tools() -> None:
    record = {
        "messages": [
            {"role": "system", "content": "sys", "tool_calls": [], "tool_call_id": None},
            {"role": "user", "content": "fix", "tool_calls": [], "tool_call_id": None},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "run_command",
                        "arguments": {"command": "ls"},
                    }
                ],
                "tool_call_id": None,
            },
            {"role": "tool", "content": "ok", "tool_calls": [], "tool_call_id": "c1"},
        ]
    }
    messages = to_template_messages(record)
    assert messages[2]["tool_calls"][0]["function"]["name"] == "run_command"
    assert messages[3]["name"] == "run_command"
    assert messages[3]["tool_call_id"] == "c1"


def test_lr_at_warmup_and_cosine() -> None:
    assert lr_at(0, 100, 0.1, 1e-4) == 1e-5
    assert lr_at(10, 100, 0.1, 1e-4) == 1e-4
    assert lr_at(100, 100, 0.1, 1e-4) < 1e-5
    assert lr_at(55, 100, 0.1, 1e-4) == 5e-5
