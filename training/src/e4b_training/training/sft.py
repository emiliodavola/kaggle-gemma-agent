"""Full-conversation SFT on the harness-native corpus.

The corpus is the canonical JSONL written by ``prepare_sft_dataset.py``. Each
record is rendered with the local Gemma 4 tokenizer and the harness tool schema,
and the loss is masked to the assistant turns by comparing the tokenized
prefixes of consecutive messages: the delta of an assistant message is the
target, every other token is context.

The memory path is the measured one from ``smoke_train.build_model``: 4-bit NF4,
manual per-layer checkpointing, bf16 downcast, int8 embedding table and the
chunked masked loss. Nothing here changes the model or the dataset silently.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import time
from typing import Any

TRAINING = pathlib.Path(__file__).resolve().parents[3]
CONFIGS = TRAINING / "configs"
DEFAULT_MODEL = (
    pathlib.Path.home() / ".cache/kagglehub/models/google/gemma-4/transformers/gemma-4-e4b-it/1"
)
DEFAULT_TOOLS = CONFIGS / "tools.json"
DEFAULT_TRAIN = TRAINING / "data/processed/sft_train.jsonl"
DEFAULT_VALID = TRAINING / "data/processed/sft_validation.jsonl"
CHUNK = 256


def to_template_messages(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert canonical messages to the shape ``apply_chat_template`` expects."""
    id_to_name: dict[str, str] = {}
    messages: list[dict[str, Any]] = []
    for message in record["messages"]:
        role = message["role"]
        if role == "assistant":
            calls = []
            for call in message.get("tool_calls") or []:
                id_to_name[call["id"]] = call["name"]
                calls.append(
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"],
                        },
                    }
                )
            item: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
            if calls:
                item["tool_calls"] = calls
            messages.append(item)
        elif role == "tool":
            messages.append(
                {
                    "role": "tool",
                    "content": message.get("content") or "",
                    "tool_call_id": message.get("tool_call_id"),
                    "name": id_to_name.get(message.get("tool_call_id"), ""),
                }
            )
        else:
            messages.append({"role": role, "content": message.get("content") or ""})
    return messages


def _render(tokenizer, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    if not messages:
        return ""
    return tokenizer.apply_chat_template(
        messages, tools=tools, tokenize=False, add_generation_prompt=False
    )


def encode_full(
    tokenizer,
    record: dict[str, Any],
    tools: list[dict[str, Any]],
    limit: int,
) -> tuple[list[int], list[int]] | None:
    """Return ``(input_ids, labels)`` with labels only on assistant turns."""
    messages = to_template_messages(record)
    texts = [_render(tokenizer, messages[:index], tools) for index in range(len(messages) + 1)]
    token_ids = [
        tokenizer(text, add_special_tokens=False)["input_ids"] if text else [] for text in texts
    ]
    full = token_ids[-1]
    if not full or len(full) > limit:
        return None
    for index in range(len(token_ids) - 1):
        if full[: len(token_ids[index])] != token_ids[index]:
            return None
    labels = [-100] * len(full)
    for index, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        start, end = len(token_ids[index]), len(token_ids[index + 1])
        if end > start:
            labels[start:end] = full[start:end]
    if all(value == -100 for value in labels):
        return None
    return full, labels


def masked_loss(inner, head, ids, labels):
    """Cross-entropy over the target region only, chunked to bound logits."""
    import torch
    import torch.nn.functional as functional

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


def _torch():
    import torch

    return torch


def _load_tools(path: pathlib.Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(path: pathlib.Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _optimizer(trainable, lr: float):
    try:
        import bitsandbytes as bnb

        return bnb.optim.PagedAdamW8bit(trainable, lr=lr)
    except Exception:
        import torch

        return torch.optim.AdamW(trainable, lr=lr)


def lr_at(step: int, total: int, warmup: float, base: float) -> float:
    warmup_steps = max(1, int(total * warmup))
    if step < warmup_steps:
        return base * (step + 1) / warmup_steps
    progress = (step - warmup_steps) / max(1, total - warmup_steps)
    return base * 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress)))


def _first_encoded(tokenizer, tools, dataset: pathlib.Path, limit: int):
    for record in _records(dataset):
        encoded = encode_full(tokenizer, record, tools, limit)
        if encoded is not None:
            return record, encoded
    raise SystemExit(f"no encodable record in {dataset}")


def preflight(args: argparse.Namespace) -> int:
    torch = _torch()
    from peft import PeftModel
    from smoke_qlora import bare_causal_lm
    from smoke_train import build_model
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    tools = _load_tools(args.tools)
    record, (ids, labels) = _first_encoded(tokenizer, tools, args.train, args.max_length)
    targets = sum(value != -100 for value in labels)
    print(f"preflight record: {record['id']} tokens={len(ids)} targets={targets}")

    ids_t = torch.tensor([ids], device="cuda")
    labels_t = torch.tensor([labels], device="cuda")
    model = build_model(args.model_dir, int8_embeddings=True, rank=args.rank, alpha=args.alpha)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    print(f"trainable params: {sum(parameter.numel() for parameter in trainable):,}")
    optimiser = _optimizer(trainable, args.lr)
    inner = bare_causal_lm(model)
    head = inner.get_output_embeddings()

    torch.cuda.reset_peak_memory_stats()
    model.train()
    optimiser.zero_grad(set_to_none=True)
    loss = masked_loss(inner, head, ids_t, labels_t)
    loss.backward()
    optimiser.step()
    torch.cuda.synchronize()
    model.eval()
    with torch.no_grad():
        post_loss = float(masked_loss(inner, head, ids_t, labels_t))
    peak_gb = torch.cuda.max_memory_allocated() / 1024**3
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    headroom_mib = free_bytes / 1024**2

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    del model
    torch.cuda.empty_cache()

    started = time.perf_counter()
    base = build_model(
        args.model_dir, int8_embeddings=False, wrap=False, rank=args.rank, alpha=args.alpha
    )
    reloaded = PeftModel.from_pretrained(base, out)
    reloaded_inner = bare_causal_lm(reloaded)
    reloaded_head = reloaded_inner.get_output_embeddings()
    reloaded.eval()
    with torch.no_grad():
        reloaded_loss = float(masked_loss(reloaded_inner, reloaded_head, ids_t, labels_t))
    delta = abs(reloaded_loss - post_loss)

    report = {
        "schema_version": "1.0",
        "record_id": record["id"],
        "tokens": len(ids),
        "target_tokens": sum(value != -100 for value in labels),
        "trainable_params": sum(parameter.numel() for parameter in trainable),
        "loss_before_step": float(loss.detach()),
        "loss": post_loss,
        "reloaded_loss": reloaded_loss,
        "delta": delta,
        "peak_allocated_gib": round(peak_gb, 2),
        "headroom_mib": round(headroom_mib, 1),
        "device_total_mib": round(total_bytes / 1024**2, 1),
        "reload_seconds": round(time.perf_counter() - started, 1),
        "rank": args.rank,
        "alpha": args.alpha,
        "max_length": args.max_length,
        "ok": headroom_mib >= 2048 and delta < 0.05,
    }
    report_path = TRAINING / "artifacts/reports/sft_preflight.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {report_path}")
    return 0 if report["ok"] else 1


def train(args: argparse.Namespace) -> int:
    torch = _torch()
    from smoke_qlora import bare_causal_lm
    from smoke_train import build_model
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    tools = _load_tools(args.tools)
    records = _records(args.train)
    if args.limit:
        records = records[: args.limit]
    model = build_model(args.model_dir, int8_embeddings=True, rank=args.rank, alpha=args.alpha)
    inner = bare_causal_lm(model)
    head = inner.get_output_embeddings()
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimiser = _optimizer(trainable, args.lr)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    total_steps = max(1, args.epochs * math.ceil(len(records) / args.grad_accum))
    cache: dict[int, tuple[list[int], list[int]] | None] = {}
    step = 0
    accumulated = 0
    started = time.perf_counter()
    model.train()
    stop = False

    for epoch in range(args.epochs):
        if stop:
            break
        order = list(range(len(records)))
        random.Random(args.seed + epoch).shuffle(order)
        for index in order:
            if index not in cache:
                cache[index] = encode_full(tokenizer, records[index], tools, args.max_length)
            encoded = cache[index]
            if encoded is None:
                continue
            ids, labels = encoded
            ids_t = torch.tensor([ids], device="cuda")
            labels_t = torch.tensor([labels], device="cuda")
            loss = masked_loss(inner, head, ids_t, labels_t) / args.grad_accum
            loss.backward()
            accumulated += 1
            if accumulated < args.grad_accum:
                continue
            torch.nn.utils.clip_grad_norm_(trainable, args.max_grad_norm)
            for group in optimiser.param_groups:
                group["lr"] = lr_at(step, total_steps, args.warmup, args.lr)
            optimiser.step()
            optimiser.zero_grad(set_to_none=True)
            step += 1
            accumulated = 0
            if step % args.log_every == 0 or step == 1:
                elapsed = time.perf_counter() - started
                print(
                    f"step {step}/{total_steps} loss {float(loss.detach()) * args.grad_accum:.4f} "
                    f"{elapsed / step:.1f}s/step",
                    flush=True,
                )
            if step % args.save_every == 0:
                checkpoint = out / f"step-{step}"
                model.save_pretrained(checkpoint)
                print(f"saved {checkpoint}", flush=True)
            if args.max_steps and step >= args.max_steps:
                stop = True
                break

    final = out / "final"
    model.save_pretrained(final)
    print(f"saved {final}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full-conversation SFT.")
    parser.add_argument("--model-dir", type=pathlib.Path, default=DEFAULT_MODEL)
    parser.add_argument("--train", type=pathlib.Path, default=DEFAULT_TRAIN)
    parser.add_argument("--tools", type=pathlib.Path, default=DEFAULT_TOOLS)
    parser.add_argument("--out", type=pathlib.Path, default=TRAINING / "adapters/t8")
    parser.add_argument("--max-length", type=int, default=10240)
    parser.add_argument("--rank", type=int, default=32)
    parser.add_argument("--alpha", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--warmup", type=float, default=0.03)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--save-every", type=int, default=250)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    return preflight(args) if args.preflight else train(args)


if __name__ == "__main__":
    raise SystemExit(main())
