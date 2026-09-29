---
name: code-graph-navigation
description: "Trigger: find callers, definitions, similar symbols, dependencies. Use get_code_neighbors, search_similar_code, and get_code_subgraph with symbol-first queries."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load when you need to find where a symbol is defined, used, or changed and
lexical grep is not enough. Use after `repo-mapping`.

## Hard Rules

- `search_similar_code` takes SYMBOLS or a short code snippet, never prose.
- One tool per step: read the result before the next call.
- Prefer graph tools over re-reading the same file.
- Cap at ~8 calls; if the graph is empty, fall back to `code-search`.

## Decision Gates

| Need | Tool |
|---|---|
| direct callers / callees of a symbol | `get_code_neighbors` |
| semantically similar symbols | `search_similar_code` (symbol query) |
| multi-hop dependency structure | `get_code_subgraph` |

## Execution Steps

1. Take the exact symbol name from `issue-localization`.
2. `get_code_neighbors` on the symbol to list callers and callees.
3. `search_similar_code` with the symbol, or a one-line snippet, to find parallel
   implementations that must change together.
4. `get_code_subgraph` to confirm module boundaries before a multi-file edit.
5. `read_file` only the nodes you will actually edit.

## Output Contract

Return the definition site, its callers, and the minimal node set to change.
Hand off to `implementation-planning`.
