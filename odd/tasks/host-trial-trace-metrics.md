# Feature: host-trial-trace-metrics

Closes #64.

## Goal

Measure, per task, **what shape a loop took** in an archived run, so we can tell
whether a prompt change reduced edits or whether a task looped by reading or by
editing. This is the baseline measurement before touching the system prompt.

## Context and evidence

Kaggle topic #745774 (Hitarth Jain) distinguishes:

- **read loop** — the same command repeated (e.g. `python3 -c` 69x, `grep` 46x),
  0-2 edits, no test runs; cause: the agent does not notice it already has the
  answer.
- **edit loop** — many `edit_file` calls on one file; cause: the agent does not
  verify the edit landed.

`report.json` gives `tool_calls` but not the shape. The archived `trace.json`
(ATIF v1.7) has every tool call and argument, so the shape is derivable.

## Decisions taken with the user

1. Ship as a versioned dev tool under `scripts/host-trial/` (stdlib-only), with
   tests, not as a throwaway in `tmp/`.
2. Metrics are descriptive; the loop classifier is a documented heuristic.
3. No automatic remediation and no submission change in this feature.

## Non-goals

- Changing the prompt or the submission (that is the P2/P3/P7 feature).
- Fixing loops.
- Reading JUnit or re-running tests.

## Tasks

- [x] T1 — `trace_metrics.py`: parse ATIF traces, compute per-task metrics.
- [x] T2 — Coarse classifier (read loop / edit loop / mixed / none).
- [x] T3 — CLI: table by default, `--json` for scripting; tolerate missing artifacts.
- [x] T4 — Tests with synthetic traces.
- [x] T5 — Run it on run_01/run_02 and record the baseline in this doc.
- [x] T6 — Gates: pytest, ruff, ruff format, mypy, pyright.
- [x] T7 — Issue #64, branch, work-unit commits, PR against `main`.

## Evidence

- Issue: #64. Branch: `feat/host-trial-trace-metrics` (from `main`).
- PR: #65 (base `main`, assignee `emiliodavola`, `Closes #64`).
- `uv run pytest tests/ -q` -> `224 passed`.
- `uv run ruff check src/ tests/ scripts/` -> `All checks passed!`
- `uv run ruff format --check src/ tests/ scripts/` -> `15 files already formatted`.
- `uv run mypy src/ scripts/` -> `Success: no issues found in 8 source files`.
- `uv run pyright` -> `0 errors, 0 warnings, 0 informations`.
- `uv run coverage report -m` -> TOTAL 98%.

### Baseline (real output)

run_01 = `runs/20261004T225306Z` (9 tasks, legacy prompt, 3 resolved):

```
task             res calls read edit cmd  rep  maxEd 1stEd sub  nudge shape
fastapi_14978    n      54   15   18   18    3    17    21   54     7 edit_loop
fastapi_15588    n      46   14   13   12    1    13     6   46     1 edit_loop
fastapi_15589    Y      31   13    1   12    1     1    27   31     4 none
requests_7502    n      62   22   10   20   10    10    26   62    16 mixed
requests_7505    n      35    8    8   15    3     4    17   35     5 none
rich_3006        Y      20    4    1   10    2     1    18   20     4 none
rich_3061        n      31   10    2   14    2     1    17   31     1 none
rich_3063        Y      28    7    3    8    2     3    20    -     9 none
rich_3064        n      23   10    2    9    3     2     9   23     3 none
```

run_02 = `runs/20261005T050122Z` (13 tasks, v2 prompt, 1 resolved):

```
task             res calls read edit cmd  rep  maxEd 1stEd sub  nudge shape
fastapi_14246    n      26    9    3    8    1     3    19   26     7 none
fastapi_14262    n     102   53   11   35   10     6    24  102    13 mixed
fastapi_14266    n     102   58    4   28    6     2    42  102    10 read_loop
fastapi_14301    n      29    5    1   18    1     1    21   25     3 none
fastapi_14978    n      53   14   13   23    6     9    14   53     5 mixed
fastapi_15588    n      21    4    5    9    1     5     9   21     3 edit_loop
fastapi_15589    n      20    8    1    8    1     1    19    -     6 none
requests_7502    n      66   11   13   37   13    13    12   66    14 mixed
requests_7505    n      43   10    9   19    3     5    18   43     3 edit_loop
rich_3006        Y      24    6    1   14    1     1    16   24     2 none
rich_3061    n      43   10    5   24    8     5    17   43    11 mixed
rich_3063        n     115   18   21   52   10    21    50  115    22 mixed
rich_3064    n      96   50    7   26   11     5    18   96    10 mixed
```

### What the baseline says

- **Every resolved task is shape `none`.** No resolved task looped.
- **The v2 prompt did not reduce looping.** run_01: 3/9 looped (2 edit, 1 mixed).
  run_02: 9/13 looped (6 mixed, 2 edit, 1 read). Even excluding the 4 tasks new
  to run_02, the ratio did not improve.
- **Edit loop dominates** (`max_edits_same_file` up to 21 on `rich_3063`).
- The 4 tasks new to run_02 (`fastapi_14246/14262/14266/14301`) are all
  environment/base-blocked; `fastapi_14266` is a clean read loop (58 reads, 6
  repeats, 102 calls).

Implication for the next feature (P2/P3/P7): the loop rules must be validated
against this baseline, and the edit loop is the first target.

