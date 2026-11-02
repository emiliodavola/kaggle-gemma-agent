# training/

Isolated environment for the LoRA SFT described in
`docs/proposals/20261101-lora-sft.md`. It trains `gemma-4-e4b-it` on one
RTX 3090 (24 GB) with QLoRA.

## Why a separate project

The repository root is pinned to Python 3.14 for the competition tooling: the
packer, the gate, the notebook helpers and CI. `bitsandbytes` and the CUDA build
of `torch` do not ship reliable wheels for 3.14, and the training stack is ~3 GB
that neither CI nor the submission needs. This directory is its own uv project
with its own `pyproject.toml`, `uv.lock` and `.python-version` (3.12), so
`uv sync` inside it never touches the root environment or lock.

## Usage

```sh
uv sync --directory training          # create training/.venv
uv run --directory training python -c "import torch; print(torch.cuda.is_available())"
```

`uv` resolves the nearest `pyproject.toml`, so running `uv` from inside
`training/` uses this project; running it from the repository root ignores this
directory entirely.

## Versions that matter

Recorded by `uv.lock`, verified on 2026-11-01:

| Package | Version |
|---------|---------|
| python | 3.12.13 |
| torch | 2.11.0+cu128 |
| transformers | 5.22.1 |
| peft | 0.21.2 |
| bitsandbytes | 0.50.2 |
| accelerate | 1.15.0 |

`torch` comes from the `pytorch-cu128` index declared in `pyproject.toml`; the
default PyPI wheel for Windows is CPU-only.

## Measured configuration (2026-11-02)

`smoke_qlora.py` loads the checkpoint in 4-bit NF4, attaches a rank-16 adapter and
runs one forward+backward per sequence length. On the RTX 3090:

| Sequence | Peak VRAM | Forward | Backward |
|---------:|----------:|--------:|---------:|
| 1024 | 20.9 GB | 0.8 s | 0.9 s |
| 2048 | 26.4 GB, over the card | 1.1 s | 7.6 s |
| 4096 | 37.4 GB, over the card | 1.4 s | 211.7 s |

Two findings that change how training is written:

- `gradient_checkpointing_enable()` is a **no-op** on this architecture: a
  1024-token step peaks at 32.1 GB and spills to system memory. Each language
  layer has to be wrapped in `torch.utils.checkpoint` by hand, which is what
  `enable_manual_checkpointing()` does.
- The vision and audio towers wrap their projections in `Gemma4ClippableLinear`,
  which peft cannot inject into, so the adapter targets a regex over
  `language_model.layers.*` only.

`smoke_qlora.json` holds the last measurement verbatim.

## What is not here yet

Dataset generation, the training script and the adapter live in stages S1-S7 of
the proposal and land in this directory as they are built. Nothing here ships
inside `submission/`.