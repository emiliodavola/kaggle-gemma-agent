---
name: repo-mapping
description: "Trigger: unfamiliar repo or a fix spanning modules. Orient with one ls, manifests, README, test config, and get_code_subgraph."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load at task start in an unfamiliar repo, or when the fix spans modules. Read-only; never edit while mapping.

## Hard Rules
- One `ls` at `/workspace`, then targeted `read_file`; never dump the whole tree.
- Read the smallest entry surface first: README, package manifest, test config.
- Cap at ~8 calls; stop once the edit site is known.
- No network, no installs, or long-running commands.

## Execution Steps
1. `run_command ls -la` at `/workspace`; list the main source and test dirs.
2. `read_file` the package manifest and README for entry points.
3. `read_file` the test config (`pyproject.toml`, `pytest.ini`) to see how tasks are verified.
4. `get_code_subgraph` on the issue's module to reveal import structure.
5. Build module -> responsibility -> key symbols -> imports; name the 1-2 modules the task likely touches.

## Output Contract
Return a compact module map (path, role, key symbols) and the likely edit scope. Hand off to `issue-localization` or `code-search`.
