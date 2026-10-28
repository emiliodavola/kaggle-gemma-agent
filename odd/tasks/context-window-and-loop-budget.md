# Context window and turn-budget hardening

Objective: remove the two failure modes the remote runs exposed: the 32k context
window (prompt plus requested output) and the 500-turn loops.
Branch: `fix/harness-context-and-loops` (from `main`).
Delivery strategy: `ask-on-risk`; one work unit (submission sampling/prompt plus docs).
Test runner: `uv run pytest -q`; the model behaviour is measured by a remote run,
so the local gate is `pack submission --check` plus the prompt-variant/pack tests.

## Specs

**S1 — Output budget.** `submission/configs/sampling.yaml` sets
`max_output_tokens: 12288` (within the harness range 1–32768), so a 16,385-token
prompt plus the output cap stays under the 32,768-token ceiling.

**S2 — Turn checkpoints.** `submission/prompts/system.md` and
`submission/skills/budget-aware-tool-use/SKILL.md` state: at 300 turns stop
exploring and call `submit_patch` with the best relevant patch; at 450 turns
submit unconditionally; never reach 500. After two failed edits, stop editing and
submit the best patch. The always-on prompt stays under `MAX_ALWAYS_ON_CHARS`.

**S3 — Environment gaps.** `docs/kaggle-remote-run.md` records `inline_snapshot`
and `scripts.prepare_release` as scoring-image gaps. Staging `inline_snapshot`
locally is explicitly not a fix: the host-trial runbook records it as a gap of
the notebook image too, so adding it would make the trial less faithful.

## Tasks

- [x] T1 (S1) — `max_output_tokens` 16384 -> 12288. Evidence: pack gate
      `6/6 points`, `3 checks`, `4 patterns`.
- [x] T2 (S2) — 300/450 turn checkpoints and the two-failed-edits stop. Evidence:
      prompt 5,869 chars (limit 24,000); skill updated.
- [x] T3 (S3) — environment-gap section with the shard-0 evidence.
- [ ] T4 — remote verification on a new shard/run when Kaggle quota allows.

## Log

**L1 — User request (verbatim):** "bien modificá todo lo que proponés, hacelo en
rama aparte, no subas nada a kaggle todavía"

**L2 — Evidence.** Run `20261027T140509Z` (11 tasks, 5/11, three
`ContextWindowExceededError`) and run `20261028T031307Z` (shard 0, 4/11, three
`collection_error`, one context window, two 500-turn loops).

**L3 — Decision.** Lower the output cap to 12,288 instead of compacting the
prompt: the initial prompt is already ~16.4k, so the cap alone removes the
overflow, and the 300/450 checkpoints are the turn-loop stop. `inline_snapshot`
stays a documented scoring-image gap because the host-trial runbook says the
notebook image lacks it too.
