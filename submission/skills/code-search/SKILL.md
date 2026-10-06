---
name: code-search
description: "Trigger: find definitions, call sites, or config keys. Scoped exact-symbol ripgrep inside /workspace, offline."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load before editing to find existing definitions, call sites, or config keys. Use after `repo-mapping`, before `implementation-planning`.

## Hard Rules
- Search inside `/workspace` only; exact identifiers, not descriptions.
- One concern per call; never repeat the same broad query twice.
- Never `find /` or dump huge output.

## Execution Steps
1. `run_command rg -n "exact_symbol" <src dir>` for definitions.
2. `rg -n "symbol\\("` for call sites; `rg -n "config\\.key"` for config keys.
3. `read_file` the top hits; separate the definition from usages.
4. Search tests for expected behaviour and the failing precondition.

## Output Contract
Return definition `file:line`, call sites, and the test encoding expected behaviour. Hand off to `implementation-planning`.
