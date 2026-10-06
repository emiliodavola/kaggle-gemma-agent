---
name: systematic-debugging
description: "Trigger: failing test, exception, or wrong behaviour. Reproduce, isolate, root-cause, then apply the smallest fix."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load when a test fails, an exception occurs, or behaviour differs from the issue. Not for a pure feature add with no failing signal.

## Hard Rules
- Never patch before reproducing; no speculative edits.
- Four phases in order: reproduce -> isolate -> root-cause -> fix.
- State the cause in one sentence before editing.
- Smallest fix that removes the cause; no drive-by refactors.
- After two failed fixes, stop and re-diagnose (see `budget-aware-tool-use`).
- Do not edit tests or protected files; respect `patch-hygiene`.
- Separate your bug from the environment: if the target test fails for a missing
  plugin or module, an unreachable endpoint, or a TTY, that failure is not yours.
  Record it, spend at most two calls on it, keep your source fix, and submit.

## Execution Steps
1. **Reproduce:** `run_command` the failing test or command; capture exact output; `read_file` the failing test.
2. **Isolate:** trace the failing value to its origin with `read_file` and `get_code_neighbors`; use `code-search` for the symbol.
3. **Root-cause:** write one causal sentence; distinguish symptom from cause.
4. **Fix:** `edit_file` only the causing code.
5. Re-run the exact failing command, then the nearest passing suite.

## Output Contract
Return repro command, root-cause sentence, diff summary, and the passing verification command. Hand off to `verification-before-submit`.
