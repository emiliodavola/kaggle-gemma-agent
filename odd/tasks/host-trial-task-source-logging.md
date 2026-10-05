# Feature: host-trial-task-source-logging

Closes #62.

## Goal

Make the host-trial task resolution self-explaining: log whether
`HARNESS_TRIAL_TASKS` came from the process environment, `.env`, or the default,
with the `.env` path, and warn loudly when the process environment shadows a
different `.env` value. This is the root-cause fix for the "runner did not read
the `.env`" symptom (13 ids in `.env`, run kept the 9 old ones).

## Context and evidence

- Precedence lives at `run_host_trial.py:392`:
  `raw = environ.get(TASKS_ENV) or env_file_values.get(TASKS_ENV) or ""`.
- Running the runner's own resolver against the current `.env` returns 13 ids,
  so the file is correct; the run used 9 because the process environment won.
- The 4 new ids (`fastapi_14301`, `fastapi_14262`, `fastapi_14266`,
  `fastapi_14246`) exist in `data/raw/tasks.jsonl`, carry `test_patch`, and have
  snapshots, so the miss is not a data gap.

## Decisions taken with the user

1. Keep the precedence unchanged (process env keeps winning); make it visible.
2. Log the source and the `.env` path once, early in `run()` before phase 3
   downloads snapshots.
3. Warn (not fail) when the process env overrides a different `.env` value,
   printing both values and the `unset` hint.
4. No `--task-ids` flag and no dry-run mode in this change.

## Non-goals

- Changing task resolution precedence or the resolved ids.
- Validating every id against `tasks.jsonl` (snapshot download already fails
  loudly on an unknown id).
- The system-prompt work from PR #61.

## Tasks

- [x] T1 — `TaskResolution` dataclass + `describe_task_resolution` helper, with
      `resolve_trial_tasks` delegating to it (behavior parity).
- [x] T2 — `note_task_resolution` logging the source/path and the shadow warning.
- [x] T3 — Call it in `run()` before `fetch_data`.
- [x] T4 — Tests: source detection, shadow detection, parity, log output.
- [x] T5 — `.env.example` documents the precedence and the warning.
- [x] T6 — Gates: pytest, ruff, ruff format, mypy, pyright, coverage.
- [x] T7 — Issue #62, branch, work-unit commits, PR against `main`.

## Evidence

- Issue: #62. Branch: `feat/host-trial-task-source-logging` (from `main`).
- Commit: `6f196fd` (code + tests + `.env.example` + tracker).
- `uv run pytest tests/ -q` -> `215 passed`.
- `uv run ruff check src/ tests/ scripts/` -> `All checks passed!`
- `uv run mypy src/ scripts/` -> `Success: no issues found in 7 source files`.
- `uv run pyright` -> `0 errors, 0 warnings, 0 informations`.
- `uv run coverage report -m` -> TOTAL 98% (gate 90%).
- `uv run python -m kaggle_gemma_agent.pack submission --check` ->
  `submission contract OK (6/6 points)`.
- Behavior on the real `.env` (no process override):
  `trial tasks source: .env (.env)` + 13 ids.
- Simulated exported `HARNESS_TRIAL_TASKS` (old 9) now warns:
  `WARNING: the process environment overrides HARNESS_TRIAL_TASKS from .env; unset HARNESS_TRIAL_TASKS to use the file`, with both lists printed.
- PR: #63 (base `main`, assignee `emiliodavola`, `Closes #62`).
