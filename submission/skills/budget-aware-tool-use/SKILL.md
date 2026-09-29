---
name: budget-aware-tool-use
description: "Trigger: task start or an unproductive loop. Manage the 100-call, 60-minute, 32k-context budget; submit_patch and get_status are free."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load at task start and whenever a loop seems unproductive. Governs call and
context spend against the 100-call / 60-minute / 32k bounds.

## Hard Rules

- Reserve >=15 calls for verification and submission; do not exhaust the budget
  exploring.
- `submit_patch` and `get_status` are free: call `get_status` whenever unsure.
- Batch reads; never re-read an unchanged file.
- Prefer `search_similar_code` and `get_code_neighbors` over re-reading files.
- Stop a failing approach after two attempts.

## Decision Gates

| Situation | Action |
|---|---|
| <30 calls left, no failing test reproduced | stop exploring; reproduce or submit the best patch |
| same file read twice with no change | stop; use graph or search tools |
| two fix attempts failed | re-localize; do not retry blindly |
| verification green | `submit_patch` now |

## Execution Steps

1. At start, note the approximate call count and the task's done-condition.
2. Spend early calls on localization; keep `read_file` excerpts small.
3. Every ~10 calls, re-check: is there a failing test and a candidate edit?
4. Near budget end, prefer a verified partial fix over an unverified rewrite.
5. Always submit before exhausting calls.

## Output Contract

Return current call budget, remaining plan, and the next single action. Never
end a task without a `submit_patch`.
