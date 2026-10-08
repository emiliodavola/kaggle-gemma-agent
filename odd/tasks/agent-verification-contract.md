# Feature: agent-verification-contract

## Objective

Align the shipped evaluation timeout and agent instructions so local/Kaggle budget expectations agree, valid retesting can happen after source changes, and patch submission is a truthful terminal action.

## Problem and why

The shipped configuration grants a full 60-minute command timeout, the system prompt forbids exact reruns even when a source change makes the same reproduction meaningful, and the submission skill conflicts with the prompt about when `submit_patch` must be called. These contradictions can waste the task budget or prevent a useful final patch.

## Scope

- `submission/eval_config.yaml`: set the single-command timeout to 300 seconds while preserving 100 calls, 60 minutes, and 500 turns.
- `submission/prompts/system.v3.md` and its materialized `submission/prompts/system.md`: allow the exact reproduction/target test after a relevant source change; prohibit only unchanged exploratory repetition; resume using conversation/workspace evidence under standing harness context. Keep the selected variant and materialized prompt byte-identical.
- `submission/skills/verification-before-submit/SKILL.md`: unify verification and terminal submission policy, including hard budget stops and truthful evidence reporting.
- Append one journal event and render `docs/journal/20261008.md`.
- Follow-up for PR #87 CI: keep the verification skill within its 40-line limit and pass the prompt-variant synchronization test.

## Non-goals

- No host-trial or task-comparison changes; editing during execution is not a separate defect.
- No local performance trials or Kaggle trials; this follow-up runs CI checks needed to repair PR #87. No dependency changes.
- No changes to other shipped prompts, skills, or repository behavior.

## Decisions

1. `timeout_seconds` is 300; the other three evaluation budgets remain unchanged.
2. Exact reproduction or target-test reruns are allowed after relevant source changes. Repeating exploratory commands without new evidence or a changed hypothesis remains prohibited.
3. Spend the available budget on bounded fixes and verification. Submit once as the terminal action when finished or at a hard budget stop; at a hard stop with verification still red or missing, submit the best reasoned relevant patch and state the evidence status truthfully. Call 40 is a checkpoint, not an automatic stop.
4. Scope is limited to shipped `submission/` prompts, skills, and config; do not alter comparison logic.

## Tasks

- [x] T1 — Set the shipped single-command timeout to 300 seconds and preserve all other budgets.
- [x] T2 — Clarify prompt rerun and standing-context recovery rules; a parent spot-check also removed two remaining early-submit cues from rules 3 and 6.
- [x] T3 — Resolve verification/submission timing and hard-stop wording in the shipped skill.
- [x] T4 — Append the journal event and render the 20261008 journal day; docs index does not catalog individual journal days.
- [x] T5 — `git diff --check` passed with no output. `uv run --no-sync python -m kaggle_gemma_agent.pack submission --check` -> `submission contract OK (6/6 points)`.
- [x] T6 — Behavior work-unit commit `e5b9623` (`fix(submission): align agent verification contract`) is recorded here; its native review completed with `review-reliability` returning no findings and exact acknowledgement `review-d500368c7c2b099c` burned for the candidate.
- [x] T7 — Move the continuation guidance into `system.v3.md`, regenerate `system.md`; selector reports `variant: v3 -> prompts\system.v3.md | prompts\system.md: in sync`, and the focused selector test passed.
- [x] T8 — Compress the verification skill to 27 lines while retaining rerun, budget, hard-stop, truthful-reporting, syntax, cleanup, and terminal-submit rules. The line-budget test passed.
- [ ] T9 — Journal event J-20261008-02 was appended and journal validation passed. Required focused tests and submission checks passed, but full coverage pytest had 239 setup errors and one failure, and `coverage report -m` could not find the source path; therefore full verification, PR evidence, and issue #86 closure remain pending.

## Acceptance criteria and checks

- `timeout_seconds` is 300, with `max_tool_calls: 100`, `max_time_minutes: 60`, and `max_turns: 500` unchanged.
- Prompt and skill express compatible rerun, continuation, verification, terminal submission, and hard-stop policies concisely.
- The selected prompt source and materialized `system.md` are byte-identical; the verification skill is at most 40 lines.
- Journal machine and rendered layers validate; docs index is changed only if its index contract requires it.
- The failing CI tests pass, the submission pack check returns `submission contract OK (6/6 points)`, and `git diff --check` passes. No performance trial is required or claimed.
- No dependencies or trial infrastructure are used. Remote issue/PR actions are limited to the user's authorized repository and requested issue closures.

## Evidence and next steps

- Initial route: delegated direct on existing branch `fix/agent-verification-contract`; behavior work-unit commit: `e5b9623`; native review: approved and acknowledged (`review-reliability`, no findings).
- PR #87 is open against `main`, assigned to `emiliodavola`, and closes issue #86. CI run `37718826160` failed two pytest checks: the active prompt differs from selected `system.v3.md`, and the verification skill is 47 lines against a 40-line cap.
- Issues #82 and #83 were completed by merged PRs #84 and #85 and are now closed. Issue #70 remains open: its owner-phrase regression test is not present, so it is not implemented by this change.
- PR #87 and issue #86 remain open; no GitHub operation was performed. T7–T8 are complete. Full-suite verification is partial: focused tests `2 passed in 0.05s`; full suite `1 failed, 103 passed, 239 errors in 46.39s`; coverage report failed with `No source for code: C:\workspace\kaggle-gemma-agent\src\kaggle_gemma_agent\__init__.py`. Ruff passed (`All checks passed!`); pack passed (`submission contract OK (6/6 points)`); journal passed (`journal OK (31 events)`); `git diff --check` passed with no output.
