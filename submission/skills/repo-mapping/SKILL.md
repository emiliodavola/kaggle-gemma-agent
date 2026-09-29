---
name: repo-mapping
description: "Trigger: unfamiliar repository, new task, fix spans modules. Map modules and dependencies with read-only tools before editing."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load at the start of a task in an unfamiliar repository, or when a fix appears
to span modules. Read-only: never edit during mapping.

## Hard Rules

- Never dump the whole tree. One directory listing, then targeted reads.
- Read the smallest entry surface first: README, package manifest, test config.
- Cap mapping at ~8 tool calls; stop as soon as the edit site is known.
- No network, no installs, no build servers, no long-running commands.

## Execution Steps

1. `run_command ls -la` at `/workspace`, then `ls` the main source and test dirs.
2. `read_file` the package manifest and README to learn entry points.
3. `read_file` the test config (`pyproject.toml`, `pytest.ini`) to see how tasks
   are verified.
4. `get_code_subgraph` on the module the issue names to reveal import structure.
5. Build the map: module -> responsibility -> key symbols -> imports.
6. Return the map and the 1-2 modules the task likely touches.

## Output Contract

Return a compact module map (path, role, key symbols) and the likely edit scope.
Hand off to `issue-localization` or `code-search`.
