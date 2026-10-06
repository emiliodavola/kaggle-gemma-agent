---
name: differential-diagnosis
description: "Trigger: more than one plausible cause and a limited budget. Score candidates and run the cheapest discriminating check."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load when 2-4 plausible causes compete and the budget is limited. Use after reproduction (see `systematic-debugging`), before committing to a fix.

## Hard Rules
- Enumerate 2-4 candidates before touching code.
- Score each on likelihood, severity, and fix cost; no ties by intuition.
- Test the cheapest discriminating check first; eliminate losers, never stack half-fixes.

## Decision Gates
| Candidate (file:symbol) | Likelihood | Severity | Fix cost | Discriminating check |
|---|---|---|---|---|

## Execution Steps
1. List 2-4 candidate causes, each with `file:symbol`.
2. Fill the table; order by likelihood x severity / cost.
3. Run the cheapest check that separates the top two; eliminate the loser.
4. If none survive, return to `issue-localization`.
5. Apply one fix for the survivor and verify with `run_command`.

## Output Contract
Return the scored table, the discriminating check and result, and the surviving cause. Hand off to `verification-before-submit`.
