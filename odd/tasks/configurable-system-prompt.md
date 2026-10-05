# Feature: configurable-system-prompt

Closes #60.

## Goal

Make the submission system prompt configurable between the current text
(`legacy`) and a new data-driven `v2`, selected by a YAML file, without editing
`agent.yaml` and without losing either prompt. v2 folds in the playbook §2.1
recommendations plus the failure/ success patterns measured in
`runs/20261004T225306Z` (9 tasks, 3 resolved, 33.3%).

## Context and evidence

`runs/20261004T225306Z` (backend `gemma-4-31b-it-qat`, 9 tasks, 3 resolved):

- Resolved: `fastapi_15589` (31 calls, 1 edit), `rich_3006` (20 calls, 1 edit),
  `rich_3063` (28 calls, 3 edits, never called `submit_patch`).
- Failed with heavy edit thrashing: `fastapi_14978` (54 calls, 18 edits),
  `fastapi_15588` (46 calls, 13 edits, shipped a patch with tool-call markup in
  file names), `requests_7502` (62 calls, 10 edits, 16 continuation nudges).
- Other concrete failures: `requests_7502` used a real network URL in its
  reproduction and ran the fix against the wrong import tree; `rich_3006` burned
  four `grep "Parameters"` calls before finding `param.default`; successful runs
  still shipped scratch `repro*.py` files inside the patch.

The signal that separates resolved from failed is **edit convergence and total
calls**, not exploration: resolved runs used 1–3 edits and ≤31 calls; failed runs
often used 8–18 edits and 46–62 calls.

## Decisions taken with the user

1. One new prompt (`v2`) is implemented and shipped by default; the legacy text
   is preserved verbatim so it can be restored by flipping the selector.
2. The selector is a small YAML (`configs/prompt_variant.yaml`, `variant:` line);
   the variant→file mapping lives in code, mirroring the host-trial backend
   selector pattern.
3. `agent.yaml` keeps its static `!include prompts/system.md`; the selector is
   materialized into that file. Packing applies the selection so the archive is
   always consistent; `apply` does it for a local trial.
4. No A/B run (no resources). The change is validated by the standard gates.
5. The 6-point compliance contract and its `6/6` message are unchanged.

## Non-goals

- The analyzer prompt (`prompts/analyzer.md`, `sub_agents/`).
- Adding or removing skills (rule b requires exactly 12).
- Any trial run or resolution-rate measurement.
- Changing `pack.py` validation rules or the `6/6` contract.

## Tasks

- [x] T1 — `submission/prompts/system.legacy.md` (current prompt verbatim) and
      `submission/prompts/system.v2.md` (new data-driven prompt).
- [x] T2 — `submission/configs/prompt_variant.yaml` selector, default `v2`.
- [x] T3 — `src/kaggle_gemma_agent/prompt_variant.py`: read/apply/status + CLI.
- [x] T4 — `pack.py` build path materializes the selection; no-op when the
      selector is absent (backward compatible).
- [x] T5 — `submission/prompts/system.md` materialized to the selected variant.
- [x] T6 — Tests: `tests/test_prompt_variant.py` + pack integration case.
- [x] T7 — Gates: pytest, ruff, ruff format, mypy, pyright, coverage, `pack
      submission --check` 6/6, forbidden-token scan of `submission/`.
- [x] T8 — Issue #60, branch, work-unit commits, PR against `main`.

## Evidence

- Issue: #60. Branch: `feat/configurable-system-prompt` (from `main`).
- Commits: `248f980` (prompts + selector), `f2be3e7` (module + pack wiring +
  tests).
- `uv run pytest tests/ -q` -> `207 passed`.
- `uv run ruff check src/ tests/ scripts/` -> `All checks passed!`
- `uv run mypy src/ scripts/` -> `Success: no issues found in 7 source files`.
- `uv run pyright` -> `0 errors, 0 warnings, 0 informations`.
- `uv run coverage report -m` -> TOTAL 98% (gate 90%).
- `uv run python -m kaggle_gemma_agent.pack submission --check` ->
  `submission contract OK (6/6 points)`.
- `uv run python -m kaggle_gemma_agent.prompt_variant show` ->
  `variant: v2 -> prompts/system.v2.md | prompts/system.md: in sync`.
- `git show HEAD:submission/prompts/system.md | diff - submission/prompts/system.legacy.md`
  -> `IDENTICAL` (legacy is the pre-change prompt verbatim).
- `diff submission/prompts/system.md submission/prompts/system.v2.md` ->
  identical (active prompt is the selected v2).
- PR: (filled when opened).
