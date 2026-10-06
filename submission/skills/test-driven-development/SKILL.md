---
name: test-driven-development
description: "Trigger: add or fix behaviour expressible as a test. Run the RED-GREEN-REFACTOR cycle, scoped to the call budget."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load when adding or fixing behaviour an executable test can express. Not for config-only or docs-only edits.

## Hard Rules
- RED before GREEN: no production code before a failing test exists.
- One behaviour per cycle; refactor only while green.
- Cap at <=3 red-green cycles (100-call budget).
- Never edit task tests or protected files; respect `patch-hygiene`.

## Execution Steps
1. RED: locate the encoding test with `code-search`; if none, write a scratch test under `/tmp` (see `patch-hygiene`).
2. `run_command python -m pytest <test>::<case> -q`; confirm it fails for the right reason.
3. GREEN: smallest production edit with `edit_file`; re-run the same test.
4. REFACTOR: with green, clean only the touched function.
5. Repeat up to the cycle cap, then run the nearest suite.

## Output Contract
Return test path and case, red output, green output, and files changed. Hand off to `verification-before-submit`.
