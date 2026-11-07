"""Measure held-out loss: does the adapter generalise or memorise?

The 300-step run took each sample about once over a shuffled corpus, so a final
per-sample loss of 0.25 is close to memorisation of that target. The only number
that answers the question is loss on samples the optimizer never touched.

This reproduces the trainer's shuffle exactly, takes the rows it never reached,
and measures the same samples twice: once with the adapter disabled, once with it
active. Same weights, same tokens, one variable.

Usage:
    uv run --directory training python eval_holdout.py --adapter runs/t8-long --samples 10
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random

import roundtrip_format
import torch
from smoke_qlora import DEFAULT_MODEL
from smoke_train import build_model
from train_lora import DATASET, encode, masked_loss


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adapter", default=str(pathlib.Path(__file__).resolve().parent / "runs/t8-long")
    )
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--trained", type=int, default=300, help="rows the run consumed")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--tokens", type=int, default=524288, help="tokens the run consumed (300 steps)"
    )
    parser.add_argument("--max-tokens", type=int, default=10240)
    args = parser.parse_args()

    from peft import PeftModel
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(pathlib.Path(DEFAULT_MODEL))
    tools = roundtrip_format.schema()

    rows = [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    random.Random(args.seed).shuffle(rows)
    unseen = rows[args.trained :]
    print(f"rows: {len(rows)} | unseen: {len(unseen)}")

    base = build_model(pathlib.Path(DEFAULT_MODEL), int8_embeddings=True, wrap=False)
    model = PeftModel.from_pretrained(base, args.adapter)
    inner = model.base_model.model
    head = inner.get_output_embeddings()
    model.eval()

    taken = 0
    plain: list[float] = []
    tuned: list[float] = []
    for row in unseen:
        encoded = encode(tokenizer, row, tools, args.max_tokens)
        if encoded is None:
            continue
        ids, labels = encoded
        with torch.no_grad():
            with model.disable_adapter():
                plain.append(float(masked_loss(inner, head, ids, labels)))
            tuned.append(float(masked_loss(inner, head, ids, labels)))
        taken += 1
        if taken >= args.samples:
            break

    if not taken:
        raise SystemExit("no usable held-out sample")

    mean_plain = sum(plain) / taken
    mean_tuned = sum(tuned) / taken
    print(f"samples: {taken}")
    print(f"base    : {mean_plain:.4f}")
    print(f"adapter : {mean_tuned:.4f}")
    delta = (mean_tuned - mean_plain) / mean_plain
    print(f"change  : {delta:+.1%}")
    for a, b in zip(plain, tuned):
        print(f"  {a:.4f} -> {b:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
