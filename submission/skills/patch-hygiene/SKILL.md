---
name: patch-hygiene
description: "Trigger: before the first edit or scratch file. Keep scratch in /tmp; never touch tests, conftest.py, or pytest.ini."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load before the first edit and before any scratch file, log redirect, or diff inspection.

## Hard Rules
- Scratch files and logs go in `/tmp`, never in `/workspace`.
- Never modify `tests/`, `conftest.py`, `pytest.ini`, or harness runner config; the harness resets them and scoring ignores changes.
- Allowed: edit `/workspace/<pkg>/*.py`; use `write_file` only for a new module under `/workspace/<pkg>/`.
- No network, no installs, no background processes; keep the diff minimal.

## Execution Steps
1. Confirm the target is a library file before editing.
2. Put scratch reproductions under `/tmp`.
3. Smallest `edit_file`; for a new source file, `write_file` then `run_command git add -N <path>`.
4. `run_command git status --short` and `git diff --stat` to review scope.
5. Revert any test or config path that appears in the diff.

## Output Contract
Return the source-only changed-file list and confirmation that no test or config changed. Then proceed to `verification-before-submit`.
