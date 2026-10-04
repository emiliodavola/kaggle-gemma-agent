---
name: verification-before-submit
description: "Trigger: about to submit_patch, or after a fix. Prove the claim with real test and diff output, byte-compile the change, and self-review, before submitting."
license: MIT
metadata: {author: emiliodavola, version: "1.1"}
---

## Activation Contract

Load immediately before `submit_patch`, and after any fix, to prove the claim
before submitting.

## Hard Rules

- No claim without command output. "Should work" is not evidence.
- Re-run the exact failing test verbatim, not a paraphrase.
- Byte-compile every changed `.py` file before submitting; a syntax error is a
  hard stop.
- Never submit with a scratch or junk file in the diff (`fix_*.py`,
  `reproduce_*.py`, `test_*_val.py`, temp files); revert it first.
- Self-review the diff; never edit tests, `conftest.py`, or `pytest.ini`.
- `submit_patch` and `get_status` are free; use `get_status` freely.
- If evidence is missing or red, do not submit; loop back.

## Decision Gates

| Check | Evidence required | If fail |
|---|---|---|
| target test | green output of the exact test | return to TDD |
| regressions | nearest suite still green | return to debugging |
| syntax | every changed `.py` byte-compiles | fix the file |
| diff hygiene | no scratch/junk path in the changed-file list | revert the file |
| diff scope | only intended files, no tests | revert and re-edit |
| lint | repo lint command if present | fix before submit |

## Execution Steps

1. `run_command` the exact target test; capture output.
2. `run_command` the nearest regression suite.
3. `run_command` the repo lint or format check if configured.
4. `run_command git diff --name-only`; if any listed path is scratch, junk, or a
   test/config file, revert it before continuing.
5. `run_command python -m py_compile <changed .py files>`; treat any syntax error
   as a hard stop.
6. `run_command git diff --stat` and read the full diff; confirm no test or
   config file changed.
7. Self-review against the issue: does the change cause the expected behaviour?
   Any unrelated edit?
8. Only when every row is green, call `submit_patch`.

## Output Contract

Return a checklist (target test, regressions, syntax, diff scope) with real
outputs, then `submit_patch`. On any red, return to the owning skill.
