---
Date: 2026-10-26
Genre: living reference
Status: current
Scope: The Kaggle notebook that runs the tuned `submission/` tree through `swegemma eval` remotely: inputs, accelerator, model serving, budgets, artifacts and known limits. It does not cover the host trial (`docs/host-trial-runbook.md`) or the scored submission contract.
Source of truth: `notebooks/kaggle_remote_run.ipynb`, `data/raw/HARNESS_README.md`, `data/raw/wheelhouse/`, `scripts/host-trial/run_host_trial.py`, `docs/host-trial-runbook.md` (read 2026-10-26)
Limits: The notebook has not been executed on Kaggle yet; its first run is the verification. Kaggle session limits and accelerator availability are platform facts, not repository facts.
---

# Kaggle remote run

`notebooks/kaggle_remote_run.ipynb` is the first **remote** execution path for the
harness we tune locally. It clones this repository, runs the shipped `submission/`
tree through `swegemma eval`, serves the competition checkpoint with vLLM on the
notebook's GPUs, and archives the artifacts with the same `runs/<UTC>/report.json`
+ `STATUS` handoff the host trial produces.

It exists because every run so far executed on a local host (WSL2 + Docker) with a
substitute cloud model. The remote path exercises the Linux, Docker-less,
GPU-serving environment the submission is actually scored in.

## Why the `subprocess` sandbox

A Kaggle notebook has no Docker daemon, so the notebook passes
`--sandbox subprocess` (`data/raw/HARNESS_README.md` §4.1). That backend creates an
isolated temporary directory with `workspace/`, `tmp/`, `wheels/` and a per-task
`venv/`, rewrites `/workspace`, `/tmp`, `/wheels` and `/usr/local/bin` to the sandbox
paths, and kills the whole process group on timeout.

It is not the scored container: there is no 4 GiB memory cap and no 2 vCPU quota.
File isolation and process-group cleanup are equivalent; resource isolation is not.

## Inputs

Attach three inputs (Add Input):

| Input | Why | Where it lands |
|-------|-----|----------------|
| Competition data `gemma-4-developer-agent` | `tasks.jsonl`, `snapshots/`, `wheels/`, `graphs/`, `embeddings/`, `sandbox/setup.py` | `/kaggle/input/<slug>/` |
| Dataset `metric/gemma-4-developer-agent-wheelhouse` | `swegemma`, `adk-submission`, `adk-eval-core`, vLLM and their pinned dependencies | `/kaggle/input/<slug>/` |
| Model `google/gemma-4/transformers/gemma-4-31b-it-qat-w4a16-ct` version `1` | the competition checkpoint | `/kaggle/input/models/google/gemma-4/transformers/gemma-4-31b-it-qat-w4a16-ct/1/` |

The full competition data is 20.9 GiB. If that is too large for the session, publish
a small dataset with `tasks.jsonl`, `wheels/`, `sandbox/`, `graphs/`, `embeddings/`
and only the `snapshots/<instance_id>.tgz` files you intend to run; the notebook
validates the selected tasks and names any missing snapshot.

The notebook auto-detects the data root (any `/kaggle/input` directory holding
`tasks.jsonl` next to `snapshots/` or `wheels/`), the wheelhouse (a directory with
`swegemma-*.whl`, or the published `*wheelhouse*.zip`, which it unpacks) and the
model path. `DATA_ROOT`, `WHEELHOUSE` and `MODEL_PATH` override the detection.

## Session settings

- **Accelerator:** `GPU L4 x4`. This mirrors the scored environment
  (`tensor_parallel_size=4`, `gpu_memory_utilization=0.80`, `max_model_len=32768`).
  `GPU T4 x2` is not representative and the W4A16 checkpoint may not load on Turing;
  the notebook uses every visible GPU unless `TENSOR_PARALLEL_SIZE` says otherwise.
- **Internet:** `On`. The notebook clones the repository and installs the harness.
- **Secrets:** only for `MODEL_BACKEND = "api"`; add `OPENAI_API_KEY`. The default
  `local` backend needs no secret.

## Model serving parity

The notebook starts vLLM through `adk_submission.server.spawn_vllm_server`, which is
the same lifecycle manager the scoring harness uses, with the scoring flags
(`data/raw/HARNESS_README.md` §3.1): `tool_call_parser=gemma4`,
`reasoning_parser=gemma4`, `default_chat_template_kwargs={"enable_thinking": true}`,
`max_model_len=32768`, `gpu_memory_utilization=0.80`, LoRA enabled with
`max_loras=8` / `max_lora_rank=128`. It adds `--served-model-name` so the declared
alias resolves to one stable model id.

The notebook writes a `models.yaml` mapping the model declared in
`submission/agent.yaml` to that served id, and passes it with `--models-yaml`; the
alias is read from `agent.yaml`, never hard-coded.

`MODEL_BACKEND = "api"` is the fallback when no GPU or model input is available. It
reuses `HeaderInjectingProxy` and `smoke_test_backend` from
`scripts/host-trial/run_host_trial.py`, so the opencode `x-opencode-session` header
and the tool-aware probe behave exactly as in a host trial. An API run is a plumbing
check, not a model result.

## Budgets and selection

`SUBSET` reads `experiments/subsets/<id>.json`; the default `dev-v1` plus
`MAX_TASKS = 2` keeps the first run short. `TASK_IDS` overrides the subset. The
per-task budgets default to the competition caps (100 tool calls, 500 turns, 300 s
per command) except `MAX_TIME_MINUTES = 30`, which deliberately halves the 60-minute
session so two tasks fit a notebook session with room for model load.

## What it produces

```text
/kaggle/working/kaggle-remote-run/
├── models.yaml
├── results/<RUN_LABEL>/           # swegemma --results-dir
│   ├── summary.json
│   ├── task_results.jsonl
│   ├── patches/ test_outputs/ traces/ logs/
└── artifacts/runs/<UTC>/          # harness_runs archive
    ├── report.json
    ├── STATUS
    └── <instance_id>/...
```

The last cell writes `/kaggle/working/<RUN_LABEL>.zip` with both trees plus
`run_meta.json` (repo commit, backend, served model, task ids, budgets, exit code).
Bring that zip back into the host's `runs/` workflow; do not paste logs into chat
(`docs/run-reports.md`).

## Running it

Upload `notebooks/kaggle_remote_run.ipynb` through **Create → Notebook → File →
Import Notebook**, set the accelerator and internet switches, attach the three
inputs, then **Run all**.

To push it from the command line instead, create a `kernel-metadata.json` beside a
copy of the notebook with the real slugs:

```json
{
  "id": "<kaggle-user>/kaggle-remote-run",
  "title": "kaggle-remote-run",
  "code_file": "kaggle_remote_run.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": true,
  "enable_internet": true,
  "dataset_sources": [
    "metric/gemma-4-developer-agent-wheelhouse"
  ],
  "competition_sources": [
    "gemma-4-developer-agent"
  ],
  "model_sources": [
    "google/gemma-4/transformers/gemma-4-31b-it-qat-w4a16-ct/1"
  ]
}
```

```sh
kaggle kernels push -p <directory-holding-notebook-and-metadata>
```

## Known limits

- The `subprocess` sandbox is not the 4 GiB / 2 vCPU Docker container.
- JUnit XML stays inside the sandbox and is lost on teardown, so the verdict comes
  from `task_results.jsonl`, exactly as in a host trial.
- The notebook image's Python and preinstalled wheels may differ from the scored
  image; a wheel missing here is not necessarily missing at scoring time. The
  competition wheel set ships both `cp312` and `cp313` builds for its compiled
  packages, and the subprocess sandbox inherits the notebook's site-packages.
- Installing `vllm==0.19.1` may replace `torch` inside the session when the image's
  build does not satisfy vLLM's pin. That is session-local and does not touch the
  submission.
- The notebook needs **Python 3.11 or newer** on the image: it imports
  `scripts/host-trial/run_host_trial.py` and runs
  `kaggle_gemma_agent.harness_runs`. `tests/test_python_compat.py` pins every module
  under `src/` and `scripts/` to 3.11 syntax, so a 3.14-only construct cannot
  silently break the remote path again.
- A two-task run on `dev-v1` is evidence about those tasks, never an estimate of the
  hidden test set.
