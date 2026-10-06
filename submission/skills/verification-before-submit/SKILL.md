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
- `submit_patch` and `get_status` are free (see `budget-aware-tool-use`).
- If evidence is missing or red, do not submit; loop back to the owning skill.

## Execution Steps
1. Name the target test file from the issue or the nearest test for the changed
   symbol; `run_command` it verbatim and capture the pass/fail counts.
2. `run_command python -m py_compile <changed .py files>`; a syntax error is a hard stop.
3. `run_command git status --short`; delete every untracked scratch file, then
   `git diff --name-only` and revert scratch, junk, or protected paths.
4. Confirm the diff has at least one hunk inside the repository package; a
   scratch-only diff is not a fix, re-localize instead.
5. Read the full diff; self-review against the issue and the target test.
6. Only when the target test passes and the diff is source-only, call `submit_patch`.

## Output Contract
Return the checklist (target test, regressions, syntax, diff scope) with real outputs, then `submit_patch`.
