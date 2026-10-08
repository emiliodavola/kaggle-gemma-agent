# Feature: agent-verification-contract

## Objective

Align the shipped evaluation timeout and agent instructions so local/Kaggle budget expectations agree, valid retesting can happen after source changes, and patch submission is a truthful terminal action.

## Problem and why

The shipped configuration grants a full 60-minute command timeout, the system prompt forbids exact reruns even when a source change makes the same reproduction meaningful, and the submission skill conflicts with the prompt about when `submit_patch` must be called. These contradictions can waste the task budget or prevent a useful final patch.

## Scope

- `submission/eval_config.yaml`: set the single-command timeout to 300 seconds while preserving 100 calls, 60 minutes, and 500 turns.
- `submission/prompts/system.md`: allow the exact reproduction/target test after a relevant source change; prohibit only unchanged exploratory repetition; resume using conversation/workspace evidence under standing harness context.
- `submission/skills/verification-before-submit/SKILL.md`: unify verification and terminal submission policy, including hard budget stops and truthful evidence reporting.
- Append one journal event and render `docs/journal/20261008.md`.

## Non-goals

- No host-trial or task-comparison changes; editing during execution is not a separate defect.
- No trial runs, test suite, dependency changes, GitHub issue/PR activity, or credential/session use.
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

## Acceptance criteria and checks

- `timeout_seconds` is 300, with `max_tool_calls: 100`, `max_time_minutes: 60`, and `max_turns: 500` unchanged.
- Prompt and skill express compatible rerun, continuation, verification, terminal submission, and hard-stop policies concisely.
- Journal machine and rendered layers validate; docs index is changed only if its index contract requires it.
- `git diff --check` passed. `uv run --no-sync python -m kaggle_gemma_agent.pack submission --check` returned exactly `submission contract OK (6/6 points)`. No pytest suite or trial was run.
- No remote operations or dependencies are used.

## Evidence and next steps

- Route: delegated direct on existing branch `fix/agent-verification-contract`; writer task owns the authorized files listed in the task prompt.
- Engram mirror: pending; Engram tools are unavailable in this session.
- Remote issue/PR: pending explicit destination, operation, and credential-session authorization under repository instructions.
- A parent spot-check found two remaining early-submit cues in system-prompt rules 3 and 6; both now direct the agent to useful bounded work or `get_status` while work remains and reserve `submit_patch` for completion or a hard budget stop. Behavior work-unit commit: `e5b9623`; native review: approved and acknowledged (`review-reliability`, no findings). Engram mirror and remote issue/PR remain pending as noted above.
