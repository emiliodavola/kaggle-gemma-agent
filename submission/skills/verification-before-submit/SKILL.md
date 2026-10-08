---
name: verification-before-submit
description: "Trigger: about to submit_patch or after a fix. Run the exact target test, byte-compile changed .py, reject junk paths."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load immediately before `submit_patch`, and after any fix, to prove the claim.

## Hard Rules
- No claim without command output; "should work" is not evidence.
- Byte-compile every changed `.py`; a syntax error is a hard stop.
- Reject scratch or junk paths in the diff (`fix_*.py`, `reproduce_*.py`, `test_*_val.py`, temp files); revert first.
- Respect `patch-hygiene` for the protected-files list and scope checks.
- `submit_patch` captures the current diff and ends the agent loop. Use the
  available budget to fix and verify first, then call it once as the terminal
  action when finished or at a hard budget stop.
- At a hard budget stop, submit the best reasoned relevant patch even if
  verification is red or missing. Report the evidence status truthfully; never
  claim a failing or unrun check passed. Do not submit a speculative no-op.
- Call 40 is a progress checkpoint, not an automatic stop. Continue when a
  bounded useful action remains and reserve final budget for verification and
  submission.
- `get_status` is free (see `budget-aware-tool-use`).
- Rerun the exact reproduction or target test after a relevant source change.
  Repeat exploratory commands only when new evidence or a changed hypothesis
  makes them useful.

## Execution Steps
1. Name the target test file from the issue or the nearest test for the changed
   symbol; `run_command` it and capture the pass/fail counts. After a relevant
   source change, rerunning that exact test or reproduction is allowed.
2. `run_command python -m py_compile <changed .py files>`; a syntax error is a hard stop.
3. `run_command git status --short`; delete every untracked scratch file, then
   `git diff --name-only` and revert scratch, junk, or protected paths.
4. Confirm the diff has at least one hunk inside the repository package; a
   scratch-only diff is not a fix, re-localize instead.
5. Read the full diff; self-review against the issue and the target test.
6. When finished, call `submit_patch` once as the terminal action. If a hard
   budget stop arrives first and verification is red or missing, submit the best
   reasoned relevant patch and report that evidence accurately.

## Output Contract
Return the checklist (target test, regressions, syntax, diff scope) with real
outputs, then call `submit_patch` once as the terminal action. At a hard budget
stop, include every failed, missing, or unrun check and do not claim a pass.
