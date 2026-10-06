# Feature: code-analyzer-subagent

Closes #71.

## Goal

Implement playbook §2.4: make the `code_analyzer` sub-agent a **localization-only**
helper for large repositories, with a capped call budget and an output contract
that carries exact paths, line ranges, and the **verbatim symbol signature**.
Keep `skip_summarization: true`.

## Context and evidence

- Current `code_analyzer.yaml` describes a broad "analyze root causes" role.
- `prompts/analyzer.md` asks for a 15-line report without the symbol signature
  and without a call cap.
- The main prompt (`system.v3.md`) never mentions the sub-agent.
- The official sample (`data/raw/sample_submission/sub_agents/code_analyzer.yaml`)
  has no budget field: the cap must be a prompt instruction.

## Decisions taken with the user

1. Implement the four §2.4 bullets: localization-only delegation, keep
   `skip_summarization: true`, cap the budget, and demand exact paths + lines +
   signature.
2. The budget cap is a prompt rule (the schema has no field).
3. The delegation policy goes in the analyzer `description` (what the parent
   sees) and one line in the main prompt.

## Non-goals

- The `analyzer_lora` adapter (§4.5).
- Adding tools to the analyzer or the main agent.
- Any harness change.

## Tasks

- [x] T1 — Narrow the `code_analyzer.yaml` description.
- [x] T2 — Rewrite `prompts/analyzer.md` (localization-only, call cap, output contract).
- [x] T3 — Add the delegation line to `system.v3.md` and materialize `system.md`.
- [x] T4 — Guard test: `skip_summarization: true`, analyzer tools/model, prompt length + signature.
- [x] T5 — Gates: pytest, ruff, format, mypy, pyright, `pack --check` 6/6.
- [x] T6 — Issue #71, branch, work-unit commits, PR against `main`.

## Evidence

- Issue: #71. Branch: `feat/code-analyzer-subagent` (from `main`).
- `uv run pytest tests/ -q` -> `235 passed` (4 new guards in `tests/test_analyzer.py`).
- `uv run ruff check src/ tests/ scripts/` -> `All checks passed!`
- `uv run mypy src/ scripts/` -> `Success: no issues found in 8 source files`.
- `uv run pyright` -> `0 errors, 0 warnings, 0 informations`.
- `uv run coverage report -m` -> TOTAL 98%.
- `uv run python -m kaggle_gemma_agent.pack submission --check` ->
  `submission contract OK (6/6 points)`.
- `prompts/analyzer.md` -> 28 lines; output contract requires `file:line`,
  the verbatim signature line, the edit range, and a confidence.
- `skip_summarization: true` verified unchanged in `agent.yaml`.
- `system.md` materialized to v3 and in sync.
- Rule e: no forbidden token in `code_analyzer.yaml` or `analyzer.md`.
- PR: (filled when opened).

