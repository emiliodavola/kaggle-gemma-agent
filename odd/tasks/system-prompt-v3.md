# Feature: system-prompt-v3

Closes #66.

## Goal

Add a **v3** prompt variant that addresses the loop findings from
`odd/tasks/host-trial-trace-metrics.md` and the Kaggle #745774 exchange: a
progress-based read-loop rule (P2), an explicit always-submit rule (P3), and a
prioritized structure (P7). Keep `legacy` and `v2` selectable.

## Context and evidence

Baseline from `trace_metrics.py`:

- Every resolved task is shape `none`; the v2 prompt did **not** reduce looping
  (run_01 3/9 → run_02 9/13 looped).
- The rule "never repeat an identical command" does not bind (Hitarth's bundle
  already had a `py_compile` step and it was skipped too).
- One resolved task never called `submit_patch`.

## Decisions taken with the user

1. Add v3 as a new variant (do not overwrite v2); the selector default becomes
   v3.
2. Changes: progress-based read-loop rule, always-submit rule, critical rules
   moved to the top as a short "Non-negotiables" list.
3. No budget change here (P4 is a separate decision).
4. Do not add a per-edit compile/re-read ritual (P1 was rejected as an excess).

## Non-goals

- Measuring v3 vs v2 (no A/B resources).
- Changing `eval_config.yaml` budgets.
- The analyzer prompt.

## Tasks

- [x] T1 — `submission/prompts/system.v3.md`.
- [x] T2 — Register `v3` in `prompt_variant.py` and the selector.
- [x] T3 — Materialize `submission/prompts/system.md` to v3.
- [x] T4 — Tests for the v3 registration and repo consistency.
- [x] T5 — Gates: pytest, ruff, format, mypy, pyright, `pack --check` 6/6.
- [x] T6 — Issue #66, branch, work-unit commits, PR against `main`.

## Evidence

- Issue: #66. Branch: `feat/system-prompt-v3` (from `main`).
- `uv run pytest tests/ -q` -> `225 passed`.
- `uv run ruff check src/ tests/ scripts/` -> `All checks passed!`
- `uv run mypy src/ scripts/` -> `Success: no issues found in 8 source files`.
- `uv run pyright` -> `0 errors, 0 warnings, 0 informations`.
- `uv run coverage report -m` -> TOTAL 98%.
- `uv run python -m kaggle_gemma_agent.pack submission --check` ->
  `submission contract OK (6/6 points)`.
- `uv run python -m kaggle_gemma_agent.prompt_variant list` ->
  `legacy`, `v2`, `v3`.
- `uv run python -m kaggle_gemma_agent.prompt_variant show` ->
  `variant: v3 -> prompts/system.v3.md | prompts/system.md: in sync`.
- `diff submission/prompts/system.md submission/prompts/system.v3.md` ->
  identical.
- What v3 changes vs v2: a "Non-negotiables" block at the top with the five
  critical rules (repro-first, one edit per hypothesis, stop searching when the
  answer is known, compile + clean before submit, always submit).
- PR: (filled when opened).

