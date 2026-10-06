---
name: implementation-planning
description: "Trigger: change spans more than one small edit. Keep an inline plan of <=7 one-edit steps and verify after each."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load after localization and before the first edit, when the change spans more than one small edit.

## Hard Rules
- Plan is short: <=7 steps, each one edit or one command.
- Keep the plan inline in the turn; no repo files, no ledger, no subagents.
- Re-plan only when a step fails.

## Execution Steps
1. State the goal in one sentence and the done-condition: the test that must pass.
2. List ordered steps; each names one file and one change.
3. Execute only the first step, then verify with `run_command` or `read_file`.
4. Update the plan after each step; if a step invalidates it, stop and re-localize.

## Output Contract
Return the goal, done-condition, ordered steps, and current step status. Hand off to `test-driven-development`.
