---
name: code-search
description: "Trigger: find definitions, call sites, config keys. Run scoped ripgrep with exact symbols inside /workspace before editing, fully offline."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load before editing when you must find existing definitions, call sites, or
config keys. Use after `repo-mapping`, before `implementation-planning`.

## Hard Rules

- Search inside `/workspace` only; never search outside the task repo.
- Search exact identifiers and strings, not descriptions.
- One concern per call; read the result before the next query.
- Do not `find /` or dump huge output; scope every query to source dirs.

## Execution Steps

1. `run_command rg -n "exact_symbol" <src dir>` for definitions.
2. `rg -n "symbol\\("` for call sites; `rg -n "config\\.key"` for config keys.
3. `read_file` the top hits; separate the real definition from usages.
4. Search tests for the expected behaviour and the failing precondition.
5. Re-run a query only with a narrower pattern, never the same broad one twice.

## Output Contract

Return: definition `file:line`, call sites, and the test that encodes expected
behaviour. Hand off to `implementation-planning`.
