"""Compare the two orderings of an assistant action under the base model.

The chat template renders the tool call before the assistant text:

    <|tool_call>...</tool_call|>Let me start by exploring...

but the base model streams ``<|channel>thought`` first. Training against an
ordering the model finds unnatural fights its own distribution.

This measures, without training, the teacher-forced loss of the same semantic
content under both orderings:

    template  -- one assistant turn: content + tool_calls
    thought   -- assistant turn with the text, then a turn with the tool call

Lower per-token loss means the model already expects that order.

Usage:
    uv run --directory training python compare_order.py --samples 3
"""

from __future__ import annotations

import argparse
import json
import pathlib

import roundtrip_format
import torch
from smoke_qlora import DEFAULT_MODEL, load_4bit

DATASET = pathlib.Path(__file__).resolve().parent / "dataset/decisions.jsonl"


def loss_of(model, tokenizer, messages, history_len, tools) -> float:
    """Teacher-forced per-token loss over the messages after ``history_len``."""
    prefix = tokenizer.apply_chat_template(
        messages[:history_len], tools=tools, tokenize=False, add_generation_prompt=True
    )
    full = tokenizer.apply_chat_template(
        messages, tools=tools, tokenize=False, add_generation_prompt=False
    )
    prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if full_ids[: len(prefix_ids)] != prefix_ids:
        raise SystemExit("the prefix is not a token prefix of the full render")

    start = max(len(prefix_ids) - 1, 0)
    ids = torch.tensor([full_ids[start:]], device="cuda")
    with torch.no_grad():
        out = model(input_ids=ids)
    logits = out.logits[0, :-1]
    targets = ids[0, 1:]
    loss = torch.nn.functional.cross_entropy(logits.float(), targets, reduction="sum")
    return float(loss) / max(len(targets), 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(pathlib.Path(DEFAULT_MODEL))
    tools = roundtrip_format.schema()
    rows = [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][args.offset : args.offset + args.samples]
    if not rows:
        raise SystemExit("no samples")

    model = load_4bit(pathlib.Path(DEFAULT_MODEL))
    model.eval()

    totals = {"template": 0.0, "thought": 0.0}
    for row in rows:
        messages = row["messages"]
        target = messages[-1]
        history = messages[:-1]
        call = target["tool_calls"][0]
        text = target.get("content") or ""

        template_form = [*history, target]
        thought_form = [
            *history,
            {"role": "assistant", "content": text},
            {"role": "assistant", "content": "", "tool_calls": [call]},
        ]

        a = loss_of(model, tokenizer, template_form, len(history), tools)
        b = loss_of(model, tokenizer, thought_form, len(history), tools)
        totals["template"] += a
        totals["thought"] += b
        print(f"{row['task']}#{row.get('target_index')}: template {a:.4f} | thought {b:.4f}")

    n = len(rows)
    print()
    print(f"template: {totals['template'] / n:.4f} per token")
    print(f"thought : {totals['thought'] / n:.4f} per token")
    winner = "thought" if totals["thought"] < totals["template"] else "template"
    print(f"lower loss: {winner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
