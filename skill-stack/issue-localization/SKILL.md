---
name: issue-localization
description: "Trigger: bug report, issue, traceback, failing test, feature request. Turn issue text into ranked suspect files and symbols before any edit."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load for any task that arrives as an issue: a bug report, traceback, failing
test name, or feature request. Load before editing. Do not load when the task
already names the exact file and line.

## Hard Rules

- Never edit before the target is localized to a file and symbol.
- Bounded, not exhaustive: at most 3 ranked hypotheses.
- Extract entities from the issue text only; never invent files, symbols, or APIs.
- `submit_patch` and `get_status` are free; localization calls are not. Cap this
  phase at ~10 tool calls.

## Execution Steps

1. Parse the issue into entities: identifiers, error text, stack frames, file
   paths, test names, expected vs actual.
2. `run_command` grep for the exact identifiers and error substrings you found;
   `search_similar_code` with those SYMBOLS (never prose).
3. `read_file` the hits; `get_code_neighbors` to widen definitions and callers.
4. For each entity record `file:line`, defining symbol, and callers. Name the
   function that must change.
5. Rank hypotheses by evidence within this table, not intuition:

   | # | Suspect (file:symbol) | Evidence | Falsifying test |
   |---|---|---|---|

6. Return the ranked list plus the single most likely edit site, then stop.

## Output Contract

Return: entity list, ranked hypotheses (<=3) each with a falsifying test, and the
top suspect as `file:line` + symbol. Hand off to `implementation-planning` or
`test-driven-development`.
