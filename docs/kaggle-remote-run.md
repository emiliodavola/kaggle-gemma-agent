---
Date: 2026-10-26
Genre: living reference
Status: current
Scope: The Kaggle notebook that runs the tuned `submission/` tree remotely: inputs, accelerator, wheelhouse install, vLLM serving, evaluation, artifacts and known limits. It does not cover the host trial (`docs/host-trial-runbook.md`) or the scored submission contract.
Source of truth: `notebooks/kaggle_run.ipynb`, the official Kaggle **Getting Started: Gemma 4 Developer Agent** notebook (local copy, not committed), `data/raw/HARNESS_README.md`, `data/raw/wheelhouse/`, `scripts/host-trial/run_host_trial.py` (read 2026-10-26)
Limits: The notebook has not been executed on Kaggle yet; its first run is the verification. Kaggle session limits, accelerator availability and the exact model mount are platform facts, not repository facts.
---

# Kaggle remote run

`notebooks/kaggle_run.ipynb` is the first **remote** execution path for the
harness we tune locally. It follows the official **Getting Started: Gemma 4
Developer Agent** notebook: installs the competition wheelhouse, loads the
competition data from `/kaggle/input/competitions/gemma-4-developer-agent`, serves
the checkpoint with vLLM through `adk_submission`, and runs `swegemma`'s
`Evaluator` with the Docker-less `subprocess` sandbox. It then archives the
artifacts with the same `runs/<UTC>/report.json` + `STATUS` handoff the host trial
produces.

It exists because every run so far executed on a local host (WSL2 + Docker) with a
substitute cloud model. The remote path exercises the Linux, Docker-less,
GPU-serving environment the submission is actually scored in.

## Why the `Evaluator` API instead of the CLI

The official notebook drives `Evaluator` directly, and that is the only entry point
that accepts the context-management objects a 32k-token agent needs:

- `ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10)`
- `EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336, event_retention_size=5)`

It also accepts the adapter manifest, explicit `graph_dir` / `embeddings_dir` /
`wheels_dir`, and a `verification_timeout_seconds` when the installed harness
version exposes it. `Evaluator.run()` still writes `summary.json`,
`task_results.jsonl`, `patches/`, `test_outputs/`, `traces/` and `logs/`, so the
`harness_runs archive` step is unchanged.

## Inputs

Attach three inputs (Add Input):

| Input | Why | Mount |
|-------|-----|-------|
| Competition data `gemma-4-developer-agent` | `tasks.jsonl`, `snapshots/`, `wheels/`, `graphs/`, `embeddings/`, `sandbox/setup.py` | `/kaggle/input/competitions/gemma-4-developer-agent/` |
| Dataset `metric/gemma-4-developer-agent-wheelhouse` | `swegemma`, `adk-submission`, `adk-eval-core`, vLLM and their pinned dependencies | `/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse/` |
| Model `google/gemma-4/...` | the competition checkpoint | `/kaggle/input/models/google/gemma-4/Other/<model>/<version>/` |
| Dataset `bistiarj/kaggle-gemma-agent-code` | `submission/`, `src/`, `experiments/` and `COMMIT` for offline runs | `/kaggle/input/kaggle-gemma-agent-code/` |

The notebook auto-detects the data root (the explicit competition path first, then
any `/kaggle/input` directory holding `tasks.jsonl` next to `snapshots/` or
`wheels/`), the wheelhouse (a directory with `swegemma-*.whl`, or a published
`*wheelhouse*.zip`, which it unpacks) and the model path (the `other/`,
`Other/`, `transformers/` and `Transformers/` families, highest version first).
`DATA_ROOT`, `WHEELHOUSE` and `MODEL_PATH` override the detection.

The full competition data is 20.9 GiB. If that is too large for the session, publish
a small dataset with `tasks.jsonl`, `wheels/`, `sandbox/`, `graphs/`, `embeddings/`
and only the `snapshots/<instance_id>.tgz` files you intend to run; the notebook
validates the selected tasks and names any missing snapshot.

## Offline on L4 (required)

The competition's **Upgraded Accelerators** page states: *"No Internet - All L4
sessions must have internet disabled."* The notebook probes GitHub once:

- **Online** (CPU/T4 or a local host): it clones `REPO_URL` at `REPO_REF`.
- **Offline** (L4): it looks for an attached dataset holding `submission/` and
  `src/` (for example `bistiarj/kaggle-gemma-agent-code`) and uses it as the
  repository root; the dataset's `COMMIT` file records the commit.

The wheelhouse install, the evaluation and the archive are all offline. The only
online-only fallback is the PyPI fill for a genuinely missing runtime dependency;
offline it prints a warning instead.

## Session settings

- **Accelerator:** `GPU L4 x4`. The notebook uses every visible GPU
  (`tensor_parallel_size` 4 / 2 / 1) and mirrors the scoring flags:
  `tool_call_parser=gemma4`, `reasoning_parser=gemma4`, `max_model_len=32768`,
  `gpu_memory_utilization=0.80`. The official getting-started notebook uses `0.90`;
  `0.80` is the value `data/raw/HARNESS_README.md` documents for scoring.
  `GPU T4 x2` is not representative and the W4A16 checkpoint may not load on Turing.
- **Internet:** `On`. The notebook clones the repository and installs the
  wheelhouse.
- **Secrets:** only for `MODEL_BACKEND = "api"`; add `OPENAI_API_KEY`. The default
  `local` backend needs no secret.

## Model support

The submission's `agent.yaml` decides the model; the notebook never hard-codes it.
The four competition models are accepted: `gemma-4-31b-it-qat-w4a16-ct`,
`gemma-4-12b-it-qat-w4a16-ct`, `gemma-4-e4b-it-qat-w4a16-ct` and
`gemma-4-e2b-it-qat-w4a16-ct`. The 12B variant needs
`--hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'`,
which the notebook adds automatically.

LoRA adapters under `submission/adapters/` are discovered and passed to the vLLM
server and the evaluator. The shipped tree has none today; an adapter run also needs
the alias registered in the model registry, which the `Evaluator` API path supports.

## Wheelhouse install and environment

The notebook follows the official install instead of resolving dependencies:

1. remove broken cutlass `.pth` hooks from the image;
2. restore the PEP 440 `+cu128` local version that Kaggle dataset uploads strip;
3. `pip install --no-deps --force-reinstall` every wheelhouse wheel;
4. fill a genuinely missing runtime dependency (`litellm`, `docker`, `pyyaml`, ...)
   from PyPI only when the import fails.

It also sets the switches the official notebook sets: `TRANSFORMERS_OFFLINE`,
`VLLM_WORKER_MULTIPROC_METHOD=spawn`, `VLLM_ENGINE_READY_TIMEOUT_S=1200`,
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, the LiteLLM quiet flags and
`OTEL_SDK_DISABLED`.

The wheelhouse is built for CPython 3.12, which matches the scored notebook image.
The notebook checks every wheel against the running interpreter's tags and stops
with a clear message when the session uses another Python (for example 3.13):
switch the notebook image to the Python 3.12 image and restart.

## Budgets and selection

The notebook reads `submission/eval_config.yaml` — the tuned tree wins. The
configuration cell can override `MAX_TOOL_CALLS`, `MAX_TIME_MINUTES`,
`MAX_TURNS` and `COMMAND_TIMEOUT_SECONDS`. All default to `None`, which reads the
tuned `submission/eval_config.yaml` (100 calls, 60 min, 500 turns); set a value
only for a deliberately shorter run.

`SUBSET` reads `experiments/subsets/<id>.json`; the default `dev-v1` runs all
11 tasks (`MAX_TASKS = None`). Set `MAX_TASKS` to cap it, or `TASK_IDS` to pick
explicit ids. The whole 129-task corpus needs sharded runs, not one session.

## What it produces

```text
/kaggle/working/kaggle-remote-run/
├── results/<RUN_LABEL>/           # Evaluator --results-dir
│   ├── summary.json
│   ├── task_results.jsonl
│   ├── patches/ test_outputs/ traces/ logs/
└── artifacts/runs/<UTC>/          # harness_runs archive
    ├── report.json
    ├── STATUS
    └── <instance_id>/...
```

The last cell writes `/kaggle/working/<RUN_LABEL>.zip` with both trees plus
`run_meta.json` (repo commit, backend, model id, task ids, budgets, resolved/total).
Bring that zip back into the host's `runs/` workflow; do not paste logs into chat
(`docs/run-reports.md`).

## Version-guarded fields

The official notebook targets a newer harness than the pinned `swegemma 0.2.7`
wheelhouse: it passes `verification_timeout_seconds` to `EvalConfig` and
`scheduler_reserve_full_isl` to `VllmConfig`, and neither exists in 0.2.11. The
notebook filters every optional field through the installed dataclass, so the same
file works on both: on 0.2.11 it prints the ignored names and continues; on a newer
wheelhouse it passes them through.

## Running it

Upload `notebooks/kaggle_run.ipynb` through **Create → Notebook → File →
Import Notebook**, set the accelerator and internet switches, attach the three
inputs, then **Run all**.

To push it from the command line, create a `kernel-metadata.json` beside a copy of
the notebook and copy the exact source slugs from the Add Input dialog:

```json
{
  "id": "<kaggle-user>/kaggle-remote-run",
  "title": "kaggle-remote-run",
  "code_file": "kaggle_run.ipynb",
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
    "google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/<version>"
  ]
}
```

```sh
kaggle kernels push -p <directory-holding-notebook-and-metadata>
```

## Known limits

- The `subprocess` sandbox is not the 4 GiB / 2 vCPU Docker container; it isolates
  files and the process group, not memory or CPU.
- JUnit XML stays inside the sandbox and is lost on teardown, so the verdict comes
  from `task_results.jsonl`, exactly as in a host trial.
- The notebook image's Python and preinstalled wheels may differ from the scored
  image; a wheel missing here is not necessarily missing at scoring time.
- Installing the wheelhouse with `--force-reinstall` can replace packages the image
  shipped; that is session-local and does not touch the submission.
- A two-task run on `dev-v1` is evidence about those tasks, never an estimate of the
  hidden test set.
- The two reference notebooks the comparison used
  (`getting-started-gemma-4-developer-agent.ipynb` and
  `gemma-4-developer-agent-small-model-leaderboard.ipynb`) are Kaggle inputs, not
  repository artifacts; `.gitignore` keeps them out of commits.
