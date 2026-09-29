---
name: test-driven-development
description: "Trigger: add or fix behaviour with an executable test. RED-GREEN-REFACTOR via run_command, scoped to the tool budget; never edit task tests."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load when adding or fixing behaviour that an executable test can express. Not
for config-only or docs-only edits.

## Hard Rules

- RED before GREEN: never write production code before a failing test exists.
- Never edit task-shipped tests, `conftest.py`, or `pytest.ini`; the harness
  resets them. If a test is the spec, make it pass by fixing library code.
- Scope to <=3 red-green cycles given the 100-call budget.
- One behaviour per cycle; refactor only while tests are green.

## Execution Steps

1. RED: locate the test that encodes expected behaviour with `code-search`. If
   none exists, write a scratch test under `/tmp`, never in the repo.
2. `run_command python -m pytest <test>::<case> -q`. Confirm it fails for the
   right reason.
3. GREEN: smallest production edit with `edit_file`; re-run the same test.
4. REFACTOR: with green, clean up only the touched function.
5. Repeat up to the cycle cap, then run the nearest suite.

## Output Contract

Return: test path and case, red output, green output, and files changed. Hand
off to `verification-before-submit`.
