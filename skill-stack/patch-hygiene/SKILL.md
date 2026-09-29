---
name: patch-hygiene
description: "Trigger: before the first edit or scratch file. Keep scratch in /tmp, never touch tests/conftest/pytest.ini, and keep the diff source-only."
license: MIT
metadata: {author: emiliodavola, version: "1.0"}
---

## Activation Contract

Load before the first edit and before any scratch file, log redirect, or diff
inspection.

## Hard Rules

- Scratch files and logs go in `/tmp`, never in `/workspace`.
- Never modify tests, `conftest.py`, `pytest.ini`, or harness runner config;
  the harness resets them and scoring ignores changes.
- Edit library source with `edit_file`; use `write_file` only for a genuinely
  new source file.
- No network, no installs, no background processes.
- Keep the diff minimal and focused on the issue.

## Decision Gates

| Path | Allowed? |
|---|---|
| `/workspace/<pkg>/*.py` | yes - edit |
| `/workspace/tests/**`, `conftest.py`, `pytest.ini` | no - never |
| `/tmp/**` | yes - scratch, repro, logs |
| new module under `/workspace/<pkg>/` | yes - `write_file` |

## Execution Steps

1. Confirm the target is a library file before editing.
2. Put scratch reproductions under `/tmp`.
3. Make the smallest edit with `edit_file`.
4. `run_command git status --short` and `git diff --stat` to review scope.
5. If any test or config path appears in the diff, revert it.
6. Submit only the intended source diff.

## Output Contract

Return the changed-file list (source only), confirmation that no test or config
file changed, then proceed to `verification-before-submit`.
