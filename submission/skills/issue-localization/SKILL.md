---
name: issue-localization
description: "Trigger: bug report, traceback, failing test, or feature request. Turn issue text into ranked suspect files and symbols before editing."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load for any issue-shaped task: bug report, traceback, failing test name, or feature request. Skip when the task already names the exact file and line.

## Hard Rules
- Never edit before the target is localized to a file and symbol.
- Bounded, not exhaustive: at most 3 ranked hypotheses.
- Extract entities from the issue only; never invent files, symbols, or APIs.
- The tests are the spec: before editing, read the test that asserts the new
  behaviour and use its exact symbol names, message strings, status codes, and
  aliases verbatim; when issue text and test disagree, the test wins.
- Cap this phase at ~10 calls; `submit_patch` and `get_status` are free (see `budget-aware-tool-use`).

## Execution Steps
1. Parse entities: identifiers, error text, stack frames, paths, test names, expected vs actual.
2. `run_command` grep the exact identifiers and error substrings; `search_similar_code` with those SYMBOLS (never prose).
3. `read_file` the hits; `get_code_neighbors` to widen definitions and callers.
4. Record `file:line`, defining symbol, and callers; name the function that must change.
5. Rank hypotheses by evidence, not intuition: `#`, suspect `file:symbol`, evidence, falsifying test.
6. Return the ranked list plus the single most likely edit site, then stop.

## Output Contract
Return entities, <=3 ranked hypotheses each with a falsifying test, and the top suspect as `file:line` + symbol. Hand off to `implementation-planning` or `test-driven-development`.
