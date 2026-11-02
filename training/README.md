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

## What is not here yet

Dataset generation, the training script and the adapter live in stages S1-S7 of
the proposal and land in this directory as they are built. Nothing here ships
inside `submission/`.