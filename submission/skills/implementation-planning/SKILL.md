---
name: implementation-planning
description: "Trigger: change spans more than a small edit. Keep a short inline plan of one-edit steps and verify after each; no subagents or ledger files."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load after localization and before the first edit, when the change spans more
than one small edit.

## Hard Rules

- Plan is short: <=7 steps, each one edit or one command.
- No subagents, no external ledger files, no PR flow.
- Keep the plan inline in the turn; do not create repo files for it.
- Re-plan only when a step fails, not on every turn.

## Execution Steps

1. State the goal in one sentence and the done-condition: the test that must
   pass.
2. List ordered steps; each names one file and one change.
3. Mark the first step and execute only that step.
4. After each step, verify with `run_command` or `read_file`; update the plan.
5. If a step invalidates the plan, stop and re-localize.

## Output Contract

Return the goal, done-condition, ordered step list, and current step status.
Hand off to `test-driven-development`.
