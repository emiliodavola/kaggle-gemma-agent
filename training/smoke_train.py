"""T6: prove the QLoRA loop trains, saves an adapter and reloads it.

Stage T6 of ``odd/tasks/lora-sft.md``. It is deliberately small: a handful of
optimiser steps over the samples that already exist, then a fresh load of the
base model with the adapter attached. It answers one question — does this
pipeline produce a loadable adapter — and spends no teacher tokens.

Reuses the loading path from ``smoke_qlora.py`` so the memory configuration is
the measured one, not a second copy that can drift.

Usage:
    uv run --directory training python smoke_train.py [--steps 3]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from smoke_qlora import (
    DEFAULT_MODEL,
    LORA_ALPHA,
    LORA_RANK,
    LORA_TARGETS,
    bare_causal_lm,
    chunked_loss,
    downcast_large_float32,
    enable_manual_checkpointing,
    load_4bit,
    quantize_per_layer_table,
)

DATASET = Path(__file__).resolve().parent / "dataset" / "train.jsonl"


def tokenizer_for(model_dir: Path):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_dir)


def encode(tokenizer, messages: list[dict], max_tokens: int):
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    ids = tokenizer(text, add_special_tokens=False, return_tensors="pt")["input_ids"]
    return ids[:, :max_tokens].to("cuda")


def build_model(model_dir: Path, int8_embeddings: bool, wrap: bool = True):
    """Load, prepare and optionally attach a fresh adapter.

    ``wrap=False`` returns the bare base: passing an already-wrapped PeftModel to
    ``PeftModel.from_pretrained`` double-wraps it and the forward returns a
    CausalLMOutput where the code expects hidden states.
    """
    model = load_4bit(model_dir)
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model.enable_input_require_grads()
    downcast_large_float32(model)
    if int8_embeddings:
        quantize_per_layer_table(model)
    if not wrap:
        enable_manual_checkpointing(model)
        return model
    model = get_peft_model(
        model,
        LoraConfig(
            r=LORA_RANK,
            lora_alpha=LORA_ALPHA,
            target_modules=LORA_TARGETS,
            lora_dropout=0.0,
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )
    enable_manual_checkpointing(model)
    return model


def loss_of(model, input_ids) -> float:
    inner = bare_causal_lm(model)
    loss = chunked_loss(inner, inner.get_output_embeddings(), input_ids)
    return float(loss.detach())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--dataset", default=str(DATASET))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "adapters/t6"))
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()

    model_dir = Path(args.model)
    samples = [
        json.loads(line)
        for line in Path(args.dataset).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not samples:
        raise SystemExit(f"no samples in {args.dataset}; run build_dataset.py first")
    print(f"samples: {len(samples)}")

    tokenizer = tokenizer_for(model_dir)
    batches = [encode(tokenizer, sample["messages"], args.max_tokens) for sample in samples]

    model = build_model(model_dir, int8_embeddings=True)
    trainable = [p for p in model.parameters() if p.requires_grad]
    print(f"trainable tensors: {len(trainable)} | params: {sum(p.numel() for p in trainable):,}")
    optimiser = torch.optim.AdamW(trainable, lr=1e-5)

    before = loss_of(model, batches[0])
    print(f"loss before: {before:.4f}")

    model.train()
    for step in range(args.steps):
        batch = batches[step % len(batches)]
        optimiser.zero_grad(set_to_none=True)
        inner = bare_causal_lm(model)
        loss = chunked_loss(inner, inner.get_output_embeddings(), batch)
        loss.backward()
        optimiser.step()
        print(f"  step {step + 1}: loss {float(loss.detach()):.4f}")

    after = loss_of(model, batches[0])
    print(f"loss after : {after:.4f}  (delta {after - before:+.4f})")
    if abs(after - before) < 1e-6:
        raise SystemExit("the loss did not move: nothing was trained")

    out = Path(args.out)
    model.save_pretrained(out)
    files = sorted(path.name for path in out.iterdir())
    print(f"saved adapter to {out}: {files}")

    del model
    torch.cuda.empty_cache()

    started = time.perf_counter()
    base = build_model(model_dir, int8_embeddings=False, wrap=False)
    reloaded = PeftModel.from_pretrained(base, out)
    print(f"reloaded in {time.perf_counter() - started:.0f}s")
    reloaded.eval()
    reloaded_loss = loss_of(reloaded, batches[0])
    print(f"reloaded loss: {reloaded_loss:.4f} (expected close to {after:.4f})")

    delta = abs(reloaded_loss - after)
    if delta > 0.05:
        raise SystemExit(f"reloaded loss differs by {delta:.4f}; the adapter did not transfer")
    print("T6 OK: the adapter trains, saves and reloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
