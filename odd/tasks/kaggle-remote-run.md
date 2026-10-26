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

**S3 — Scoring-parity serving.** The local backend starts vLLM through
`adk_submission.server.spawn_vllm_server` with the scoring flags
(`tool_call_parser=gemma4`, `reasoning_parser=gemma4`,
`default_chat_template_kwargs={"enable_thinking": True}`, `max_model_len=32768`,
`gpu_memory_utilization=0.80`, `tensor_parallel_size` = visible GPUs) plus
`--served-model-name`, and writes a `models.yaml` that maps the declared alias to
that served id.

**S4 — Docker-less evaluation.** The notebook runs `python -m swegemma eval` with
`--sandbox subprocess`, a bounded selection (`SUBSET`/`TASK_IDS`, `MAX_TASKS = 2` by
default), the competition caps (100 tool calls, 500 turns, 300 s per command) and a
configurable `--max-time-minutes` (default 30).

**S5 — Same handoff.** After the evaluation the notebook archives with
`python -m kaggle_gemma_agent.harness_runs archive --no-journal` and writes one
`<RUN_LABEL>.zip` holding `results/<RUN_LABEL>/`, `artifacts/runs/<UTC>/` and
`run_meta.json` (repo commit, backend, served model, task ids, budgets, exit code).

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
`python -m kaggle_gemma_agent.harness_runs` on the Kaggle image. The three
PEP 758 `except A, B:` sites use parentheses; `tests/test_python_compat.py` pins
the contract.

## Tasks

- [x] T1 (S1, S7) — Notebook with configuration, probe, install, clone, data, model,
      eval, archive, package and stop cells. Evidence: 22 cells, 10 code cells,
      every cell compiles.
- [x] T2 (S2) — Clone by `git init` + `fetch --depth 1` + `checkout FETCH_HEAD`
      (works for a branch, tag or sha) and the submission gate. Evidence: gate
      printed `submission contract OK (6/6 points)`, `harness surface OK (3 checks)`,
      `answer leak OK (4 patterns)` against a real clone.
- [x] T3 (S3) — vLLM start through `adk_submission.server` and the generated
      `models.yaml`. Evidence: flags read from `adk_submission/server.py` and
      `data/raw/HARNESS_README.md` §3.1.
- [x] T4 (S4, S5) — `swegemma eval --sandbox subprocess` and the archive/package
      cells. Evidence: arguments cross-checked against `swegemma/cli.py` and
      `harness_runs.py` from the shipped wheels.
- [x] T5 (S6) — API fallback reusing the host-trial proxy and smoke probe.
      Evidence: imports resolved from `scripts/host-trial/run_host_trial.py`.
- [x] T6 — Documentation: `docs/kaggle-remote-run.md`, indexed in `docs/README.md`.
- [x] T7 (S8) — Python 3.11 portability for the modules the notebook imports.
      Evidence: `ast.parse(..., feature_version=(3, 11))` reported
      `run_report.py`, `run_host_trial.py` and `trace_metrics.py` (four PEP 758
      sites) before the fix and `incompatible files: 0` after it;
      `uv run pytest tests/test_python_compat.py -q` → `13 passed`.
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
