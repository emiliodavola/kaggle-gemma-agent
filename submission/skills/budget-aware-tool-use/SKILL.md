---
name: budget-aware-tool-use
description: "Trigger: task start or an unproductive loop. Protect the 100-call and 60-minute budget; batch, stop after two failures, always submit."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load at task start and whenever a loop seems unproductive. Governs call and context spend against the 100-call / 60-minute / 32k bounds.

## Hard Rules
- Reserve >=15 calls for verification and submission; do not exhaust the budget exploring.
- `submit_patch` and `get_status` are free: call `get_status` at the 40-call
  checkpoint and again before `submit_patch`.
- On `budget_warning` or `BudgetExceeded`, stop exploring at once and submit the
  best verified source fix; `submit_patch` still works after the call budget is
  spent.
- Batch reads; never re-read an unchanged file; prefer `search_similar_code` and `get_code_neighbors`.
- Stop a failing approach after two attempts.
- Always submit before exhausting calls.

## Execution Steps
1. Note the approximate call count and the done-condition.
2. Spend early calls on localization; keep `read_file` excerpts small.
3. Every ~10 calls, re-check: is there a failing test and a candidate edit?
4. Stop signals: <30 calls left with no repro -> reproduce or submit the best patch; a file read twice unchanged -> switch to graph or search tools; two failed fixes -> re-localize.
5. **Read loop:** if two read-only calls add no new info, stop searching; edit or submit.
6. **Edit loop:** one edit per hypothesis; if the repro is unchanged, revert and re-diagnose; never stack edits.
7. Near budget end, prefer a verified partial fix; always submit.

## Output Contract
Return the call budget, remaining plan, and the next single action. Never end without a `submit_patch`.
