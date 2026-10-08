---
name: verification-before-submit
description: "Trigger: after a fix or before submit_patch; verify the exact change and report evidence."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation
Load after a fix and immediately before `submit_patch`.

## Rules
- Make no claim without command output; never call a failing or unrun check passed.
- After a relevant source change, rerun the exact reproduction or target test; repeat exploration only with new evidence or a changed hypothesis.
- Use the budget to fix and verify first. Call 40 is a checkpoint, not a stop; continue bounded work and reserve budget for verification and submission.
- At a hard budget stop, submit the best reasoned relevant patch even if checks are red or missing, and report that status truthfully. Do not submit a speculative no-op.
- Compile every changed `.py` file; a syntax error is a hard stop. `get_status` is free.
- Keep scratch/junk files out of the diff; respect `patch-hygiene` for protected paths and scope.

## Steps
1. Run the issue's target test or the nearest test for the changed symbol; capture pass/fail counts.
2. Run `python -m py_compile` on changed Python files and `git status --short`; remove scratch files.
3. Check `git diff --name-only` for scratch, junk, or protected paths; revert any such change.
4. Read the full diff, check it against the issue and test, and confirm a repository-package hunk exists.
5. When finished or at a hard stop, call `submit_patch` once as the terminal action; it captures the current diff.

## Output
Return target-test, regression, syntax, and diff-scope check results with real outputs. At a hard stop, include every failed, missing, or unrun check.
