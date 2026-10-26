# Feature: 91-answer-leak

Closes #91. Branch `feat/91-answer-leak` (from `main`). Runner: `uv run pytest`.
Delivery strategy: chained PR, slice 1 of 2 (issue #92 is slice 2 on top of it).

The issue body is the specification. This file ties each task to its rules and
records the evidence; it does not restate them.

## Goal

Add `check_answer_leak`, a third independent layer of
`pack.py` `--check`, that fails when the shipped harness contains
grader-specific literals: task instance ids, test node ids,
`tests/test_*.py` paths, or `FAIL_TO_PASS` / `PASS_TO_PASS` markers.

## Decisions

- The issue's exact patterns, suffix set, emission order, messages and exit
  codes are implemented verbatim; no allowlist, suppression comment or
  per-file exemption was added.
- `build_submission` is untouched: the enforcement point stays CI running
  `pack submission --check`.
- The one current-tree violation, a YAML comment in
  `submission/configs/prompt_variant.yaml`, was fixed instead of exempted.

## Non-goals

- Preventing the runtime agent from editing tests.
- A semantic detector for paraphrased answers.
- A `skills` provenance hash or any run-report change (#94, #88).
- Wiring the scan into `build_submission` or `validate_source`.

## Tasks

- [x] **T1** - `ANSWER_LEAK_PATTERNS` and `_LEAK_SCAN_SUFFIXES` added with the
      exact values of issue decisions 2; stdlib only.
- [x] **T2** - `check_answer_leak(source_dir: Path) -> list[str]`: name scan
      first, suffix-gated content scan, relative POSIX paths, 1-based lines,
      duplicate suppression, `OSError` skipped, missing directory reported
      without an exception.
- [x] **T3** - `main --check` runs contract -> harness surface -> answer leak,
      prints `answer leak OK (4 patterns)` or `answer leak FAILED (n
      violation(s))`, and exits 1 when any layer fails.
- [x] **T4** - Module docstring and `--check` help text describe three layers.
- [x] **T5** - `submission/configs/prompt_variant.yaml` no longer carries a
      `tests/test_*.py` literal; no behaviour change.
- [x] **T6** - Twelve focused tests in `tests/test_pack.py`, including the
      shipped-tree regression pin.
- [x] **T7** - `AGENTS.md`, `README.md` and `README_ES.md` document the third
      layer with the exact strings.
- [x] **T8** - One `change` journal event for issue #91.

## Evidence

Focused suite:

```text
$ uv run pytest tests/test_pack.py -q
...............................................                          [100%]
47 passed in 1.51s
```

Clean shipped tree:

```text
$ uv run python -m kaggle_gemma_agent.pack submission --check
submission contract OK (6/6 points)
harness surface OK (3 checks)
answer leak OK (4 patterns)
exit=0
```

Full suite, lint and types are recorded in the pull request.

## Open items

- The answer-leak scan is a literal deny-list; a paraphrased answer is out of
  scope and would need its own issue.
