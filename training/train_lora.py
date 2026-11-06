"""Train the LoRA adapter on decision-point samples.

Loss is masked to the target region: everything before ``target_index`` is
context the model gets for free, and only the thought plus the call it has to
produce carry gradient. That is the difference between teaching "what does a
trajectory look like" and "what should I do next".

Reuses the measured model path from ``smoke_train`` so the memory configuration
stays in one place.

Usage:
    uv run --directory training python train_lora.py --steps 20
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import time

import roundtrip_format
import torch
import torch.nn.functional as functional
from smoke_qlora import DEFAULT_MODEL
from smoke_train import build_model

DATASET = pathlib.Path(__file__).resolve().parent / "dataset/decisions.jsonl"
CHUNK = 256


def masked_loss(inner, head, ids: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
    """Cross-entropy over the target region only, chunked to bound logits."""
    hidden = inner.model(input_ids=ids).last_hidden_state
    total = torch.zeros((), device=ids.device)
    count = torch.zeros((), device=ids.device)
    for start in range(0, hidden.shape[1] - 1, CHUNK):
        width = min(CHUNK, hidden.shape[1] - 1 - start)
        block = hidden[:, start : start + width]
        target = labels[:, start + 1 : start + 1 + width]
        if not bool((target != -100).any()):
            continue
        logits = head(block).float()
        total = total + functional.cross_entropy(
            logits.reshape(-1, logits.shape[-1]),
            target.reshape(-1),
            ignore_index=-100,
            reduction="sum",
        )
        count = count + (target != -100).sum()
    return total / count.clamp(min=1)


def encode(
    tokenizer, sample: dict, tools: list[dict], limit: int
) -> tuple[torch.Tensor, torch.Tensor] | None:
    messages = sample["messages"]
    cut = sample["target_index"]
    prefix = tokenizer.apply_chat_template(
        messages[:cut], tools=tools, tokenize=False, add_generation_prompt=True
    )
    full = tokenizer.apply_chat_template(
        messages, tools=tools, tokenize=False, add_generation_prompt=False
    )
    prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
    ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if len(ids) > limit or ids[: len(prefix_ids)] != prefix_ids:
        return None
    if len(ids) - len(prefix_ids) < 2:
        return None
    labels = [-100] * len(prefix_ids) + ids[len(prefix_ids) :]
    return (
        torch.tensor([ids], device="cuda"),
        torch.tensor([labels], device="cuda"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DATASET))
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--max-tokens", type=int, default=10240)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--out", default=str(pathlib.Path(__file__).resolve().parent / "adapters/t8")
    )
    args = parser.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(pathlib.Path(DEFAULT_MODEL))
    tools = roundtrip_format.schema()

    rows = [
        json.loads(line)
        for line in pathlib.Path(args.dataset).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        rows = rows[: args.limit]
    random.Random(args.seed).shuffle(rows)

    print(f"rows: {len(rows)}")
    model = build_model(pathlib.Path(DEFAULT_MODEL), int8_embeddings=True)
    trainable = [p for p in model.parameters() if p.requires_grad]
    print(f"trainable: {sum(p.numel() for p in trainable):,}")
    optimiser = torch.optim.AdamW(trainable, lr=args.lr)
    inner = model.base_model.model
    head = inner.get_output_embeddings()

    model.train()
    done = 0
    skipped = 0
    started = time.perf_counter()
    while done < args.steps:
        for row in rows:
            encoded = encode(tokenizer, row, tools, args.max_tokens)
            if encoded is None:
                skipped += 1
                continue
            ids, labels = encoded
            optimiser.zero_grad(set_to_none=True)
            loss = masked_loss(inner, head, ids, labels)
            loss.backward()
            optimiser.step()
            done += 1
            if done % 5 == 0 or done == 1:
                elapsed = time.perf_counter() - started
                print(
                    f"step {done}: loss {float(loss.detach()):.4f} | {elapsed / done:.1f}s/step",
                    flush=True,
                )
            if done >= args.steps:
                break
    print(f"skipped: {skipped}")

    out = pathlib.Path(args.out)
    model.save_pretrained(out)
    print(f"saved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
