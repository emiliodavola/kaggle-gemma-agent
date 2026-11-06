"""Round-trip check: does the base model emit the template's tool-call syntax?

The training target for T7 is the tokenizer's native tool-call rendering. That
only works if the base model can already produce it: teaching a syntax the model
cannot express produces an adapter that emits something the harness cannot parse.

This feeds a real prefix (shipped system prompt, real problem statement, the
first turns of a real trajectory) with the derived tool schema attached, and
checks whether the generation opens a ``<|tool_call>`` block.

Usage:
    uv run --directory training python roundtrip_format.py [--turns 3]
"""

from __future__ import annotations

import argparse
import json
import pathlib

import torch
from smoke_qlora import DEFAULT_MODEL, load_4bit

REPO = pathlib.Path(__file__).resolve().parent.parent
RUN = REPO / "runs/20261102T214038Z"
TURNS = RUN / "turns.jsonl"
CORPUS = REPO / "data/raw/tasks.jsonl"
SYSTEM = REPO / "submission/prompts/system.md"

# Derived from the 5304 calls in the archived traces; optional arguments are the
# ones that appeared in some calls but not all.
TOOLS = [
    ("run_command", "Run a shell command inside /workspace.", {"command": "string"}, ["command"]),
    (
        "read_file",
        "Read a file inside /workspace.",
        {"filepath": "string", "start_line": "integer", "end_line": "integer"},
        ["filepath"],
    ),
    (
        "edit_file",
        "Replace old_string with new_string in a file.",
        {"filepath": "string", "old_string": "string", "new_string": "string"},
        ["filepath", "old_string", "new_string"],
    ),
    (
        "write_file",
        "Create a file with content.",
        {"filepath": "string", "content": "string"},
        ["filepath", "content"],
    ),
    ("submit_patch", "Submit the final source-only patch.", {}, []),
]


def schema() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {key: {"type": kind} for key, kind in properties.items()},
                    "required": required,
                },
            },
        }
        for name, description, properties, required in TOOLS
    ]


def problem_for(task: str) -> str:
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("instance_id") == task:
            return record["problem_statement"].strip()
    raise SystemExit(f"{task} not in {CORPUS}")


def messages_for(task: str, turns: int) -> list[dict]:
    record = next(
        json.loads(line)
        for line in TURNS.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["task"] == task
    )
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM.read_text(encoding="utf-8").strip()},
        {"role": "user", "content": problem_for(task)},
    ]
    emitted = 0
    for turn in record["turns"]:
        if turn["role"] == "thought":
            messages.append({"role": "assistant", "content": turn["text"]})
            emitted += 1
        elif turn["role"] == "assistant" and turn.get("tool"):
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": turn["tool"],
                                "arguments": {"command": turn["text"]},
                            },
                        }
                    ],
                }
            )
            emitted += 1
        if emitted >= turns:
            break
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="fastapi_11355")
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument("--max-new-tokens", type=int, default=120)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    model_dir = pathlib.Path(DEFAULT_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    messages = messages_for(args.task, args.turns)
    prompt = tokenizer.apply_chat_template(
        messages, tools=schema(), tokenize=False, add_generation_prompt=True
    )
    print(f"task={args.task} messages={len(messages)} prompt_chars={len(prompt)}")
    print("prompt tail:", repr(prompt[-120:]))

    model = load_4bit(model_dir)
    model.eval()
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    print(f"prompt tokens: {inputs['input_ids'].shape[-1]}")
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
        )
    text = tokenizer.decode(out[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=False)
    print("=== generation ===")
    print(text)
    ok = "<|tool_call>" in text
    print("=== verdict ===")
    print(f"tool_call block present: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
