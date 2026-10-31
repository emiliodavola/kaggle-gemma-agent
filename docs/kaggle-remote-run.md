---
Date: 2026-10-28
Genre: living reference
Status: current
Scope: The Kaggle notebook that runs the tuned `submission/` tree remotely: inputs, accelerator, wheelhouse install, vLLM serving, evaluation, artifacts and known limits. It does not cover the host trial (`docs/host-trial-runbook.md`) or the scored submission contract.
Source of truth: `notebooks/kaggle_run.ipynb`, the official Kaggle **Getting Started: Gemma 4 Developer Agent** notebook (local copy, not committed), the competition's *Model Selection, Budget, and Harness Rules* and *Upgraded Accelerators* pages, `data/raw/HARNESS_README.md` (the 2026-10-13 competition copy), `data/raw/wheelhouse/`, `scripts/host-trial/run_host_trial.py`, `runs/20261027T140509Z/`, `runs/20261028T031307Z/` (read 2026-10-31)
Limits: The 31B notebook has been executed on Kaggle (runs 20261027T140509Z and 20261028T031307Z); the E4B baseline of 2026-10-31 is the first small-model run. The 129-task corpus is still sharded across sessions. Kaggle session limits, accelerator availability and the exact model mount are platform facts, not repository facts.
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
sessions must have internet disabled."* That is a rule, not a preference: the
same page says attempts to circumvent it may be enforced by Kaggle moderation,
including team and account bans. Every L4 run is therefore `enable_internet:
false`, and the repository arrives as the attached code dataset.

The notebook probes GitHub once anyway, so the same file still runs on a machine
that allows internet:

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
  `gpu_memory_utilization=0.90`, `scheduler_reserve_full_isl=False`. `0.90` is
  the value the 2026-10-13 `HARNESS_README.md` documents for scoring and the one
  the official getting-started notebook uses; the earlier `0.80` came from the
  stale 2026-10-01 copy.
  `GPU T4 x2` is not representative and the W4A16 checkpoint may not load on Turing.
- **Internet:** `Off`, required on L4 (see above). The repository comes from the
  attached code dataset and the wheelhouse installs offline.
- **Secrets:** only for `MODEL_BACKEND = "api"`; add `OPENAI_API_KEY`. The default
  `local` backend needs no secret.

## Model support

The submission's `agent.yaml` decides the model. The four competition models are
accepted: `gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`,
`gemma-4-e4b-it-qat-w4a16-ct` and `gemma-4-e2b-it-qat-w4a16-ct`. The 12B variant
needs `--hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type":
"gemma4"}'`, which the notebook adds automatically; the E4B needs no override.

The config cell also pins `EXPECTED_MODEL`. Before the server starts, the
notebook aborts when `agent.yaml` declares anything else, so a stale code dataset
cannot silently measure the wrong model and label the artifacts with the right
one. A 31B run therefore needs both the model source in the kernel metadata and
switched YAMLs in the dataset, or it stops in seconds instead of hours later.

## Model preflight

Starting vLLM is not proof that the run will work. After the server is up the
notebook runs three checks before the first task, because a broken parser costs
minutes here and the whole session later:

1. `/v1/models` answers. vLLM serves the **weights path** as the model id unless
   a served-model name is passed, so the preflight reads the id from the server
   instead of assuming the declared alias.
2. One short chat completion returns non-empty text.
3. One tool-call round trip returns a call whose `arguments` parse as JSON, with
   one retry. A parser that cannot emit a tool call fails every task, and the E4B
   tool-call parser has a reported hang on array arguments (discussion 753973).

Any of the three failing aborts the run with a named reason.

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
`MAX_TURNS` and `COMMAND_TIMEOUT_SECONDS`. `MAX_TOOL_CALLS`, `MAX_TURNS` and
`COMMAND_TIMEOUT_SECONDS` default to `None`, which reads the tuned
`submission/eval_config.yaml` (100 calls, 60 min, 500 turns). `MAX_TIME_MINUTES`
is `18.0` for the E4B baseline: the scored budget is 12 h for the whole corpus,
so a 60-minute per-task cap cannot be the run's cap.

The evaluation cell also refuses to start when the worst case
`tasks x max_time_minutes / concurrency` exceeds `MAX_WORST_CASE_HOURS` (10.5 h); at 129 tasks, 18 minutes and concurrency 4 the
worst case is 9.7 h, which leaves room for setup and the archive.
A 12 h session that dies mid-flight never reaches the archive cell, so the guard
trades a longer run for a complete one. Lower `MAX_TIME_MINUTES`, raise
`CONCURRENCY` or shard the corpus to fit.

`SUBSET = None` selects the whole 129-task corpus. Two run modes:

- **Single session** (`NUM_SHARDS = None`, `CONCURRENCY = 4`): about 5–9 h of
  contended wall time. The model and sandboxes are shared, so per-task latency
  grows and the 60-minute budget includes that contention. It is a quick dev
  estimate, not the scored condition.
- **Faithful** (`NUM_SHARDS = 12`, `CONCURRENCY = 1`): about 11 tasks per
  session at the per-task condition; the corpus takes 2–3 weeks of the weekly
  GPU quota (30 h, L4x4 at 2x).

The notebook prints an estimate from the observed 16.4 min/task and warns above
7.5 h. `SUBSET = "dev-v1"` keeps the 11-task contrast set; `MAX_TASKS` caps the
selection and `TASK_IDS` picks explicit ids.

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
the notebook. This is the metadata of the last working push
(`kaggle kernels pull <user>/<kernel> -m`), with the model source switched:

```json
{
  "id": "bistiarj/gemma-e4b-baseline",
  "title": "gemma-e4b-baseline",
  "code_file": "kaggle_run.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": true,
  "enable_internet": false,
  "dataset_sources": [
    "metric/gemma-4-developer-agent-wheelhouse",
    "bistiarj/kaggle-gemma-agent-code"
  ],
  "competition_sources": [
    "gemma-4-developer-agent"
  ],
  "model_sources": [
    "google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2"
  ],
  "machine_shape": "NvidiaL4",
  "docker_image": "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"
}
```

The `docker_image` pins the Python 3.12 image the wheelhouse is built for; without
it a later default image can be 3.13 and the wheel-tag check stops the run.
`machine_shape: NvidiaL4` is what makes the session a 4×L4 GPU session.

```sh
kaggle kernels push -p <directory-holding-notebook-and-metadata>
```

## Refreshing the attached code dataset

Offline runs read `submission/`, `src/`, `experiments/subsets/` and a `COMMIT`
file from `bistiarj/kaggle-gemma-agent-code`, so a branch that changes the
submission is invisible to Kaggle until the dataset is versioned:

```sh
# 1. stage exactly what the notebook reads
uv run python - <<'PY'
import pathlib, shutil
stage = pathlib.Path("./tmp/kaggle-code-dataset")
shutil.rmtree(stage, ignore_errors=True)
for name in ("submission", "src"):
    shutil.copytree(name, stage / name)
(stage / "experiments" / "subsets").mkdir(parents=True)
shutil.copy("experiments/subsets/dev-v1.json", stage / "experiments" / "subsets")
PY

# 2. record the commit the dataset was built from
git rev-parse HEAD > tmp/kaggle-code-dataset/COMMIT

# 3. publish a new version
kaggle datasets version -p tmp/kaggle-code-dataset -m "E4B baseline: <commit>"
```

Check the result with `kaggle datasets files bistiarj/kaggle-gemma-agent-code`:
`submission/agent.yaml` must declare the model the notebook expects.

## Known environment gaps

The shard-0 run (`runs/20261028T031307Z`) hit three `collection_error` tasks:
`inline_snapshot` is absent from the notebook image, and fastapi's
`scripts.prepare_release` is not importable from the snapshot. The host-trial
runbook already records `inline_snapshot` as a gap of the scoring image too;
staging it locally would make the trial less faithful, not more. They stay
documented gaps, not local fixes.

The same run hit one `ContextWindowExceededError` (a 16,385-token prompt plus a
16,384-token output cap) and two 500-turn loops. The tuning branch lowers
`max_output_tokens` to 12,288 and adds 300/450-turn checkpoints to the system
prompt and `budget-aware-tool-use`.

## Known limits

- The `subprocess` sandbox is not the 4 GiB / 2 vCPU Docker container; it isolates
  files and the process group, not memory or CPU.
- JUnit XML stays inside the sandbox and is lost on teardown, so the verdict comes
  from `task_results.jsonl`, exactly as in a host trial.
- The notebook image's Python and preinstalled wheels may differ from the scored
  image; a wheel missing here is not necessarily missing at scoring time.
- Installing the wheelhouse with `--force-reinstall` can replace packages the image
  shipped; that is session-local and does not touch the submission.
- The 129-task corpus at concurrency 1 is 22–36 h; a single session cannot
  finish it. Concurrency 4 fits 5.4–8.8 h but changes per-task latency.
- A run on `dev-v1` or a shard is evidence about those tasks, never an estimate
  of the hidden test set.
- The two reference notebooks the comparison used
  (`getting-started-gemma-4-developer-agent.ipynb` and
  `gemma-4-developer-agent-small-model-leaderboard.ipynb`) are Kaggle inputs, not
  repository artifacts; `.gitignore` keeps them out of commits.
