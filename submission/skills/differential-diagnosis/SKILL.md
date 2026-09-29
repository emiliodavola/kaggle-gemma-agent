---
name: differential-diagnosis
description: "Trigger: several competing causes, limited budget. Score candidates by likelihood, severity, and cost, then run the cheapest discriminating check."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load when multiple plausible causes compete and the budget is limited. Use
after reproduction, before committing to a fix.

## Hard Rules

- Enumerate candidates before touching code; keep 2-4.
- Score each on likelihood, severity, and fix cost. No ties by intuition.
- Test the cheapest discriminating check first.
- Eliminate the losers; do not accumulate half-fixes.

## Decision Gates

| Candidate (file:symbol) | Likelihood | Severity | Fix cost | Discriminating check |
|---|---|---|---|---|

## Execution Steps

1. Reproduce once (see `systematic-debugging` phase 1).
2. List 2-4 candidate causes, each with `file:symbol`.
3. Fill the table; order by likelihood x severity / cost.
4. Run the cheapest check that separates the top two candidates.
5. Eliminate the loser. If none survive, return to `issue-localization`.
6. Apply one fix for the survivor; verify with `run_command`.

## Output Contract

Return the scored table, the discriminating check and its result, and the
surviving cause with its fix. Hand off to `verification-before-submit`.
