# Feature: skills-compaction

Closes #68.

## Goal

Cut the token cost of the 12 submission skills without changing behaviour:
remove duplicated rules (dedupe), rewrite each trigger, delete the stale
`skill-stack/` mirror, and version the redesign proposal in `docs/`.

## Context and evidence

`docs/skills-redesign-proposal.md` (versioned from this change) has the full
analysis. Summary:

- 12 `SKILL.md` = 469 lines / ~19.5 KB / ~5.6k tokens, loaded **every turn**
  against an effective ~14.3k window (~40% of the working context).
- All skills are under the per-skill caps; the cost is **duplicated rules**:
  protected files in 4 skills, `/tmp` scratch in 4, free calls in 2, verify in 5.
- `skill-stack/` is a stale mirror (v1.0 vs v1.1 for verification) and
  `pack.py` ships only `submission/skills/`.

## Decisions taken with the user

1. Scope: **dedupe + triggers + delete `skill-stack/` + version the doc**.
   The **loop rules are deferred** to a second iteration, after measuring
   whether v3 already moved the loop shapes (`trace_metrics.py`).
2. `skill-stack/` is deleted; `submission/skills/` is the single source.
3. The proposal lives at `docs/skills-redesign-proposal.md`.

## Non-goals

- Adding or removing skills (rule b: exactly 12).
- Changing behaviour, the prompt, the harness, or budgets.
- Skill scripts (`run_skill_script` bug).

## Tasks

- [x] T1 — Dedupe: one owner per rule; others reference by name.
- [x] T2 — Rewrite every `description:` as `Trigger: <when>` (<= 20 words).
- [x] T3 — Version the proposal at `docs/skills-redesign-proposal.md`.
- [x] T4 — Delete `skill-stack/`; fix the README/README_ES claim.
- [x] T5 — Test: 12 dirs, each SKILL.md, total lines <= budget, rule-e clean.
- [x] T6 — Gates: pytest, ruff, format, `pack --check` 6/6, line count.
- [x] T7 — Issue #68, branch, work-unit commits, PR against `main`.

## Evidence

- Issue: #68. Branch: `feat/skills-compaction` (from `main`).
- Line count: **469 -> 322** lines across the 12 `submission/skills/*/SKILL.md`
  (largest 33, cap 40; total cap 380).
- `uv run pytest tests/ -q` -> `231 passed` (6 new guards in `tests/test_skills.py`).
- `uv run ruff check src/ tests/ scripts/` -> `All checks passed!`
- `uv run mypy src/ scripts/` -> `Success: no issues found in 8 source files`.
- `uv run pyright` -> `0 errors, 0 warnings, 0 informations`.
- `uv run coverage report -m` -> TOTAL 98%.
- `uv run python -m kaggle_gemma_agent.pack submission --check` ->
  `submission contract OK (6/6 points)`.
- Rule e: zero forbidden tokens across the 12 skills.
- Differentiators kept: DD scoring table, graph-tool decision table
  (`search_similar_code` symbols-not-prose), pytest pattern table, `py_compile`
  hard stop + junk-path rejection.
- `skill-stack/` deleted (12 stale files); README/README_ES no longer claim a
  copy step (and the prompt-variant line now lists `legacy`, `v2`, `v3`).
- Deferred: the loop rules (second iteration, after measuring v3 with
  `trace_metrics.py`).
- PR: (filled when opened).

