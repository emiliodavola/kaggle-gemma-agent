"""Measure one QLoRA training step of gemma-4-e4b-it on a single RTX 3090.

Stage S4 of ``docs/proposals/20261101-lora-sft.md``: replace the derived memory
and time figures with observed ones before a dataset exists.

It loads the unquantized checkpoint in 4-bit NF4, attaches a rank-16 LoRA
adapter over the attention and MLP projections, and runs one forward+backward at
increasing sequence lengths, reporting peak VRAM and step time for each. A length
that does not fit is reported as such and the run continues; the point is to find
the ceiling, not to pick the pretty number.

Measured on an RTX 3090 (24 GB) on 2026-11-02:

    standard gradient_checkpointing_enable() is a NO-OP on this architecture:
    forward peaks are identical with it on and off, a step at 1024 tokens needs
    32.1 GB and spills to system memory (14 s forward, 17 s backward).

    Wrapping each language layer's forward in torch.utils.checkpoint brings a
    1024-token step to 20.9 GB at 1.1 s forward and 1.1 s backward. 2048 tokens
    needs 26.4 GB and exceeds the card.

The manual wrapper is therefore part of the measured configuration, not an
optimization to try later.

The bigger lever is not the towers, which hold 0.10 and 0.14 GiB.
``prepare_model_for_kbit_training`` upcasts every non-quantized parameter to
fp32, and this model carries a per-layer embedding table: 13.0 GiB of fp32
embeddings. Casting the large fp32 tensors back to bf16 frees 6.5 GiB and takes a
2048-token step to 17.4 GB at 0.4 s forward and 1.7 s backward.

Usage:
    uv run --directory training python smoke_qlora.py [--seq 1024,2048,4096,8192]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from functools import partial
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.checkpoint import checkpoint
from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, BitsAndBytesConfig

DEFAULT_MODEL: Path = (
    Path.home() / ".cache/kagglehub/models/google/gemma-4/transformers/gemma-4-e4b-it/1"
)
#: The vision and audio towers wrap their projections in ``Gemma4ClippableLinear``,
#: which peft cannot inject into. Only the language model matters for a coding
#: agent, and its projections are plain ``Linear4bit``.
LORA_TARGETS: str = (
    r".*language_model\.layers\.\d+\.(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj)$"
)
LORA_RANK = 16
LORA_ALPHA = 32


def resolve_model_dir() -> Path:
    override: str | None = os.environ.get("E4B_MODEL_DIR")
    path: Path = Path(override) if override else DEFAULT_MODEL
    if not (path / "config.json").is_file():
        raise SystemExit(f"model not found at {path}; set E4B_MODEL_DIR")
    return path


def load_4bit(model_dir: Path):
    config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    kwargs = dict(quantization_config=config, dtype=torch.bfloat16, device_map={"": 0})
    try:
        return AutoModelForCausalLM.from_pretrained(model_dir, **kwargs)
    except (ValueError, TypeError) as exc:
        print(
            f"AutoModelForCausalLM refused the checkpoint ({type(exc).__name__}); trying the "
            "image-text class"
        )
        return AutoModelForImageTextToText.from_pretrained(model_dir, **kwargs)


def downcast_large_float32(model, min_elements: int = 50_000_000) -> float:
    """Cast the big fp32 tensors back to bf16 and return the GiB freed.

    ``prepare_model_for_kbit_training`` upcasts every non-quantized parameter to
    fp32. Here that means 13 GiB of embedding tables, including the per-layer
    table the MatFormer architecture carries. Small tensors stay fp32, where the
    extra precision is worth more than the bytes.
    """
    freed = 0
    for param in model.parameters():
        if param.dtype == torch.float32 and param.numel() > min_elements:
            freed += param.numel() * 2
            param.data = param.data.to(torch.bfloat16)
    return freed / 1024**3


def enable_manual_checkpointing(model) -> int:
    """Wrap every language layer in ``torch.utils.checkpoint``.

    ``gradient_checkpointing_enable()`` reports success and changes nothing on
    this architecture (see the module docstring), so the layers are wrapped by
    hand. Returns the number of layers patched.
    """
    layers = model.base_model.model.model.language_model.layers
    for layer in layers:
        original = layer.forward
        layer.forward = partial(checkpoint, original, use_reentrant=False)
    return len(layers)


def step(model, seq_len: int) -> dict:
    input_ids = torch.randint(0, 1024, (1, seq_len), device="cuda")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    started: float = time.perf_counter()
    out = model(input_ids=input_ids, labels=input_ids)
    torch.cuda.synchronize()
    forward_s: float = time.perf_counter() - started

    started: float = time.perf_counter()
    out.loss.backward()
    torch.cuda.synchronize()
    backward_s: float = time.perf_counter() - started

    peak_gb = torch.cuda.max_memory_allocated() / 1024**3
    reserved_gb = torch.cuda.max_memory_reserved() / 1024**3
    loss = float(out.loss.detach())

    model.zero_grad(set_to_none=True)
    del out, input_ids
    torch.cuda.empty_cache()
    return {
        "seq_len": seq_len,
        "forward_s": round(number=forward_s, ndigits=1),
        "backward_s": round(number=backward_s, ndigits=1),
        "loss": round(number=loss, ndigits=4),
        "peak_allocated_gb": round(number=peak_gb, ndigits=2),
        "peak_reserved_gb": round(number=reserved_gb, ndigits=2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seq", default="1024,2048,4096,8192", help="comma-separated sequence lengths"
    )
    parser.add_argument("--out", default=None, help="write the measurements as JSON to this path")
    args: argparse.Namespace = parser.parse_args()
    lengths: list[int] = [int(value) for value in args.seq.split(",") if value.strip()]

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available in this environment")
    props = torch.cuda.get_device_properties(0)
    print(f"gpu: {props.name} | vram {props.total_memory / 1024**3:.1f} GiB")

    model_dir: Path = resolve_model_dir()
    print(f"model: {model_dir}")
    started: float = time.perf_counter()
    model = load_4bit(model_dir)
    print(
        f"loaded in {time.perf_counter() - started:.0f}s | resident "
        f"{torch.cuda.memory_allocated() / 1024**3:.2f} GiB"
    )

    model.config.use_cache = False
    model.get_output_embeddings().to(torch.bfloat16)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model.enable_input_require_grads()
    freed: float = downcast_large_float32(model)
    torch.cuda.empty_cache()
    print(
        f"downcast: freed {freed:.2f} GiB | "
        f"resident {torch.cuda.memory_allocated() / 1024**3:.2f} GiB"
    )
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
    patched: int = enable_manual_checkpointing(model)
    print(f"manual checkpointing: {patched} language layers wrapped")

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(
        f"lora: rank {LORA_RANK} | trainable {trainable:,} / {total:,} "
        f"({100 * trainable / total:.2f}%)"
    )

    results = []
    for seq_len in lengths:
        print(f"\n--- seq {seq_len} ---")
        try:
            row = step(model, seq_len)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            print(f"seq {seq_len}: OUT OF MEMORY, skipped")
            results.append({"seq_len": seq_len, "ok": False})
            continue
        row["ok"] = True
        results.append(row)
        print(json.dumps(obj=row))

    if args.out:
        Path(args.out).write_text(data=json.dumps(obj=results, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
