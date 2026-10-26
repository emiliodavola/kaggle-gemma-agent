# Kaggle remote run: first remote execution of the tuned harness

Objective: run the shipped `submission/` tree through `swegemma eval` on a Kaggle
notebook (Linux, no Docker daemon, GPU-served competition checkpoint) and hand the
artifacts back in the same `runs/<UTC>/` shape the host trial produces.
Branch: `feat/kaggle-remote-run` (from `main`).
Delivery strategy: `ask-on-risk`; one work unit (notebook + doc + tracker).
Test runner: `uv run pytest -q`; notebook cells are syntax-checked with
`compile(source, "<cell>", "exec")` because the notebook is JSON, not a module.

## Specs

**S1 — One notebook, top to bottom.** `notebooks/kaggle_remote_run.ipynb` runs
unattended from a clean Kaggle session: configuration, environment probe, harness
install, repository clone, data/task resolution, model start, evaluation, archive,
package, stop. Only the configuration cell is edited for a normal run.

**S2 — The tuned tree, gated.** The notebook clones
`https://github.com/emiliodavola/kaggle-gemma-agent.git` at `REPO_REF` and runs
`python -m kaggle_gemma_agent.pack submission --check` before spending GPU time. A
failing gate stops the run. The model alias is read from `submission/agent.yaml`,
never hard-coded.

**S3 — Scoring-parity serving.** The local backend starts `VllmServer` with the
scoring flags (`tool_call_parser=gemma4`, `reasoning_parser=gemma4`,
`max_model_len=32768`, `gpu_memory_utilization=0.80`, `tensor_parallel_size` = 4/2/1
by visible GPUs, bfloat16 when supported) and registers the alias declared in
`agent.yaml` through `create_model_registry(..., model_prefix="openai/")`. The four
competition models are accepted; the 12B variant adds the official
`--hf-overrides` JSON. Adapters under `submission/adapters/` are discovered and
passed to both the server and the evaluator.

**S4 — Docker-less evaluation.** The notebook drives `Evaluator` (the official
entry point) with `EvalConfig(sandbox="subprocess")`, a bounded selection
(`SUBSET`/`TASK_IDS`, `MAX_TASKS = 2` by default), the context-cache and
compaction objects the official notebook uses, and budgets read from
`submission/eval_config.yaml` with optional notebook overrides
(`MAX_TIME_MINUTES = 30` is the only default override).

**S5 — Same handoff.** After the evaluation the notebook archives with
`python -m kaggle_gemma_agent.harness_runs archive --no-journal` and writes one
`<RUN_LABEL>.zip` holding `results/<RUN_LABEL>/`, `artifacts/runs/<UTC>/` and
`run_meta.json` (repo commit, backend, model id, task ids, budgets, resolved/total).

**S6 — API fallback.** `MODEL_BACKEND = "api"` reuses `HeaderInjectingProxy` and
`smoke_test_backend` from `scripts/host-trial/run_host_trial.py`, so the opencode
session header and the tool-aware probe behave exactly as in a host trial. It is a
plumbing check, not a model result.

**S7 — Fail loudly.** Missing data root, wheelhouse, model, snapshot or secret
raises with the exact input to attach (or the `kaggle competitions download`
command) instead of starting a run on an incomplete set.

**S8 — Notebook-Python compatibility.** Every module under `src/` and `scripts/`
parses as Python 3.11 syntax, so the notebook can import
`scripts/host-trial/run_host_trial.py` and run
`python -m kaggle_gemma_agent.harness_runs` on the Kaggle image. The four
PEP 758 `except A, B:` sites use parentheses; `tests/test_python_compat.py` pins
the contract.

**S9 — Official-reference alignment.** The notebook adopts the official Getting
Started notebook's exact data path
(`/kaggle/input/competitions/gemma-4-developer-agent`), wheelhouse install
(cutlass `.pth` cleanup, `+cu128` filename restore, `--no-deps --force-reinstall`
of every wheel), vLLM/Transformers/LiteLLM environment switches, allowed-model
list with the 12B `--hf-overrides`, budgets from `eval_config.yaml`, and the
`Evaluator` API with `ContextCacheConfig` / `EventsCompactionConfig`.

**S10 — Version-guarded optional fields.** The official notebook passes
`verification_timeout_seconds` to `EvalConfig` and `scheduler_reserve_full_isl` to
`VllmConfig`; the pinned `swegemma 0.2.7` wheelhouse has neither. The notebook
filters optional fields through the installed dataclass, prints the ignored names
and continues, so the same file works on 0.2.7 and on a newer wheelhouse.

## Tasks

- [x] T1 (S1, S7) — Notebook with configuration, probe, install, clone, data, model,
      eval, archive, package and stop cells. Evidence: 22 cells, 10 code cells,
      every cell compiles.
- [x] T2 (S2) — Clone by `git init` + `fetch --depth 1` + `checkout FETCH_HEAD`
      (works for a branch, tag or sha) and the submission gate. Evidence: gate
      printed `submission contract OK (6/6 points)`, `harness surface OK (3 checks)`,
      `answer leak OK (4 patterns)` against a real clone.
- [x] T3 (S3) — vLLM start through `VllmServer` and the alias registry. Evidence:
      flags cross-checked against `adk_submission/server.py` and the official
      getting-started notebook; `scheduler_reserve_full_isl` filtered because 0.2.11
      has no such field.
- [x] T4 (S4, S5) — `Evaluator` + `EvalConfig(sandbox="subprocess")` and the
      archive/package cells. Evidence: fields cross-checked against
      `swegemma/config.py`, `swegemma/evaluate.py` and `harness_runs.py` from the
      shipped wheels; `verification_timeout_seconds` filtered because 0.2.11 has no
      such field.
- [x] T5 (S6) — API fallback reusing the host-trial proxy and smoke probe.
      Evidence: imports resolved from `scripts/host-trial/run_host_trial.py`.
- [x] T6 — Documentation: `docs/kaggle-remote-run.md`, indexed in `docs/README.md`.
- [x] T7 (S8) — Python 3.11 portability for the modules the notebook imports.
      Evidence: `ast.parse(..., feature_version=(3, 11))` reported
      `run_report.py`, `run_host_trial.py` and `trace_metrics.py` (four PEP 758
      sites) before the fix and `incompatible files: 0` after it;
      `uv run pytest tests/test_python_compat.py -q` → `13 passed`.
- [x] T9 (S9, S10) — Alignment with the official getting-started notebook after
      the user supplied it for comparison. Evidence: exact data/model paths, the
      wheelhouse install block, the environment switches, the four-model list with
      the 12B overrides, budgets read from `eval_config.yaml`, the `Evaluator` API
      with context cache/compaction, and the guarded optional fields.
- [ ] T8 — First remote run on Kaggle (L4 x4, internet on, three inputs attached).
      Evidence to record: the notebook's `STATUS` block, the zip path, and the
      per-task `error` values. This task stays open until the run exists.

## Log

**L1 — User request (verbatim):** "partiendo de lo implementado, podrás crear una
jupyter notebook para subirla a kaggle y hacer la primera corrida remota? incorporá
todas los cambios que fuimos haciendo para tunear el harness"

**L2 — User request (verbatim):** "guardá los cambios en una rama de git aparte"

**L3 — Decisions.** The remote path uses the `subprocess` sandbox because a Kaggle
notebook has no Docker daemon (`data/raw/HARNESS_README.md` §4.1). The default
backend is the real checkpoint on the notebook's GPUs because every previous run
used a substitute cloud model; the API backend remains as a plumbing fallback. The
task selection defaults to `dev-v1` capped at two tasks so the first run fits one
session. The notebook does not ship a `kernel-metadata.json` with invented slugs;
`docs/kaggle-remote-run.md` documents the shape instead.

**L4 — Verification.** `compile()` over all 10 code cells passed. `bounded_glob`,
`find_wheelhouse` (zip branch), `find_data_root`, task resolution and the snapshot
check were executed against the local `data/raw` tree with `/kaggle/input` mapped to
it: it unpacked 41 wheels, selected `fastapi_15588` and `fastapi_15589` from
`dev-v1`, and found both snapshots. The submission gate passed on a fresh clone.
The notebook itself has not run on Kaggle yet; T8 is the verification.

**L5 — Portability fix found while wiring the notebook.** The repository targets
Python 3.14, and four `except A, B:` sites (PEP 758) made `run_report.py`,
`run_host_trial.py` and `trace_metrics.py` unparseable on the older Python of a
Kaggle notebook image. The notebook imports the runner for the header proxy and the
smoke probe, and runs the archiver, so those modules had to parse on 3.11. The four
sites now use parentheses (same behavior) and `tests/test_python_compat.py` pins the
contract. This is a portability fix, not a behavior change.

**L6 — Comparison with the two reference notebooks.** The official Getting Started
notebook showed six gaps in the first proposal: the data mount is
`/kaggle/input/competitions/gemma-4-developer-agent`; the model lives under
`.../google/gemma-4/other/<model>/<version>`; the wheelhouse is installed with
`--no-deps --force-reinstall` after cutlass cleanup and `+cu128` restore; the
image needs the vLLM/Transformers/LiteLLM/OTEL switches; four models are allowed and
the 12B needs `--hf-overrides`; and the official entry point is `Evaluator` with
context cache/compaction, not the CLI. The notebook now follows that path, with the
two fields the pinned 0.2.11 wheelhouse lacks (`verification_timeout_seconds`,
`scheduler_reserve_full_isl`) filtered at runtime. The small-model leaderboard
notebook confirmed the 12B/E4B/E2B track and the same data layout.

`ruff format notebooks/` accidentally reformatted both reference notebooks while the
new notebook was being formatted. They are Kaggle inputs, not repository artifacts:
they were restored from the captured original sources (cell counts match), their
leaderboard outputs were preserved, and `.gitignore` now keeps both out of commits.
