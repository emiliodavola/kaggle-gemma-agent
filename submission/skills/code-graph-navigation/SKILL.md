---
name: code-graph-navigation
description: "Trigger: find callers, definitions, similar symbols, or dependencies. Pick the graph tool by need; SYMBOLS only."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load to find where a symbol is defined, used, or changed when lexical search is not enough. Use after `repo-mapping`.

## Hard Rules
- `search_similar_code` takes SYMBOLS or a short snippet, never prose.
- One tool per step; read the result before the next call.
- Cap at ~8 calls; if the graph is empty, fall back to `code-search`.

## Decision Gates
| Need | Tool |
|---|---|
| direct callers / callees of a symbol | `get_code_neighbors` |
| semantically similar symbols | `search_similar_code` (symbol query) |
| multi-hop dependency structure | `get_code_subgraph` |

## Execution Steps
1. Take the exact symbol from `issue-localization`.
2. `get_code_neighbors` to list callers and callees.
3. `search_similar_code` with the symbol or a one-line snippet to find parallel implementations.
4. `get_code_subgraph` to confirm module boundaries before a multi-file edit.
5. `read_file` only the nodes you will edit.

## Output Contract
Return the definition site, its callers, and the minimal node set to change. Hand off to `implementation-planning`.
