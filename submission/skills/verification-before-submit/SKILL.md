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
1. `run_command` the exact target test verbatim; capture green output.
2. `run_command` the nearest regression suite; if red, return to `systematic-debugging`.
3. `run_command git diff --name-only`; revert any scratch, junk, or protected path.
4. `run_command python -m py_compile <changed .py files>`; any syntax error is a hard stop.
5. Read the full diff; self-review against the issue.
6. Only when all checks are green, call `submit_patch`.

## Output Contract
Return the checklist (target test, regressions, syntax, diff scope) with real outputs, then `submit_patch`.
