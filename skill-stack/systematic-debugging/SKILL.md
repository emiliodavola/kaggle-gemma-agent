---
name: systematic-debugging
description: "Trigger: failing test, exception, wrong behaviour. Reproduce, isolate, root-cause, then apply the smallest fix; no speculative patches."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load when a test fails, an exception occurs, or behaviour differs from the
issue. Not for a pure feature add with no failing signal.

## Hard Rules

- Never patch before reproducing. No speculative edits.
- Four phases in order: reproduce -> isolate -> root-cause -> fix.
- State the cause in one sentence before editing.
- Smallest fix that removes the cause; no drive-by refactors.
- If two fix attempts fail, stop and re-run phases 1-3.

## Execution Steps

1. **Reproduce:** `run_command` the failing test or command; capture exact
   output. `read_file` the failing test.
2. **Isolate:** trace the failing value to its origin with `read_file` and
   `get_code_neighbors`; use `code-search` for the symbol.
3. **Root-cause:** write one causal sentence. Distinguish symptom from cause;
   prefer explaining over trying.
4. **Fix:** edit only the causing code with `edit_file`. Never edit tests,
   `conftest.py`, or `pytest.ini`.
5. Re-run the exact failing command, then the nearest passing suite.
6. If still red after two attempts, re-enter phase 1; do not stack guesses.

## Output Contract

Return: repro command, root-cause sentence, diff summary, and the passing
verification command. Hand off to `verification-before-submit`.
