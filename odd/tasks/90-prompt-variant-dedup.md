# Feature: 90-prompt-variant-dedup

Closes #90. Branch `fix/90-prompt-variant-dedup` (from `main`). Runner: `uv run pytest`.
Delivery strategy: single PR (two work units: behaviour, then documentation).

The issue body is the specification. This file ties each task to one of its
rules and records the evidence; it does not restate them.

## Specs

- **S1** — `prompt_variant.py`: `VARIANTS["v3"] is ACTIVE_PROMPT` (issue D1), a
  resolution- and case-aware `_same_file`/`_path_key` pair, `apply_variant`
  returning early for the alias and raising
  `PromptVariantError("prompts/system.md: active prompt not found")` when the
  alias target is missing, and `is_active` returning `active.is_file()` for the
  alias so `show` and `apply` cannot disagree. `duplicate_variants(source_dir)`
  returns the name pairs whose prompt bytes are identical. Stdlib only.
- **S2** — CLI (issue D2): `show` prints
  `variant: v3 -> … | …: active (no copy needed)` and never `OUT OF SYNC` for the
  alias; `apply` prints `variant 'v3' is already the active prompt (…)` and is
  idempotent; `list` prints `v3` mapped to `prompts/system.md`. For copy-backed
  variants the existing `in sync` / `OUT OF SYNC (run 'apply')` / `applied
  variant '…' to …` strings stay byte-identical.
- **S3** — `submission/prompts/system.v3.md` is deleted; the selector comment
  describes `v3` as the active prompt and states the no-duplicate rule;
  `variant: v3` stays the default.
- **S4** — `tests/test_prompt_variant.py`: the test that pinned the deleted path
  is replaced by the alias mapping; new tests cover the alias apply (twice), the
  alias apply on a missing active prompt, alias `is_active`, alias `show`, a
  missing alias target, the alias `apply` message, `list`, and a pack build
  under a `v3` selector. All new tests are separator-agnostic.
- **S5** — the duplicate guard: `duplicate_variants(SUBMISSION_DIR) == []` in the
  repository, plus a positive (two file-backed variants with equal bytes) and a
  positive "file copies the active prompt" case.
- **S6** — documentation (issue D6): this tracker, a superseded note in
  `odd/tasks/system-prompt-v3.md`, a superseded note in
  `odd/tasks/agent-verification-contract.md`, and the stale-reference list below.
  `docs/proposals/20261006-prompt-hardening.md` is not edited.
- **S7** — one `change` journal event, then one `observation` event linking the
  PR, matching the append-only practice of J-20261025-01/02.
- **S8** — gates: `uv run pytest tests/ -q` keeps exactly the five Windows-only
  baseline failures (issue "Constraints"), `ruff check`, `mypy src/`, `pyright`,
  `pack submission --check` at 6/6, and the built archive holds no
  `prompts/system.v3.md`.

## Decision

Option A (issue "Expected behavior"). Option B was rejected because the `v3`
file was byte-identical to the active prompt from the commit that introduced it
(`d2ce207`), so it has no content delta to restore; making the bytes differ
would mean inventing prompt wording, which is out of scope.

## Stale references to the deleted file

Recorded here instead of rewriting history, so future work is not sent to a
missing path:

- `odd/tasks/cheap-improvement-wins.md` L39, L52 — instruct editing `system.v3.md`.
- `odd/tasks/agent-verification-contract.md` L14, L40 — instruct editing
  `system.v3.md` and keeping it byte-identical (note appended; body left as
  written).
- `odd/tasks/code-analyzer-subagent.md` L17, L40 — instruct editing `system.v3.md`.
- `docs/proposals/20261006-prompt-hardening.md` L21-23, L185, L221, L275, L286,
  L319, L342, L377, L393, L425, L461 — dated proposal; superseded, never edited.

The canonical edit target is now `submission/prompts/system.md`.

## Tasks

- [x] T1 — `prompt_variant.py` alias mapping, helpers, `apply_variant`,
  `is_active`, `duplicate_variants` (S1). Commit `feat` unit.
- [x] T2 — CLI strings and exit codes (S2).
- [x] T3 — delete `system.v3.md`, update the selector comment (S3).
- [x] T4 — tests (S4, S5).
- [x] T5 — tracker, two superseded notes, stale-reference list (S6).
- [x] T6 — journal `change` plus PR `observation` (S7).
- [x] T7 — gates (S8).

## Evidence

- PR: #98 (base `main`, `Closes #90`).

Focused suite after the change:

```text
$ uv run pytest tests/test_prompt_variant.py -q
2 failed, 26 passed in 0.62s
FAILED tests/test_prompt_variant.py::test_pack_build_materializes_selected_variant
FAILED tests/test_prompt_variant.py::test_pack_build_without_selector_keeps_prompt
```

Both are the pre-existing Windows path-separator failures listed in the issue.

Full suite, before and after:

```text
$ uv run pytest tests/ -q            # before (main @ f9c5b80)
5 failed, 340 passed in 9.34s

$ uv run pytest tests/ -q            # after
5 failed, 352 passed in 11.11s
```

The failure set is identical (same five named tests); the passed count grows by
the twelve added tests.

Static gates:

```text
$ uv run ruff check src/ tests/ scripts/
All checks passed!

$ uv run mypy src/
Success: no issues found in 6 source files

$ uv run pyright
0 errors, 0 warnings, 0 informations
```

Selector CLI:

```text
$ uv run python -m kaggle_gemma_agent.prompt_variant show --cwd submission
variant: v3 -> prompts\system.md | prompts\system.md: active (no copy needed)

$ uv run python -m kaggle_gemma_agent.prompt_variant list
legacy	prompts\system.legacy.md
v2	prompts\system.v2.md
v3	prompts\system.md

$ uv run python -m kaggle_gemma_agent.prompt_variant apply --cwd submission
variant 'v3' is already the active prompt (submission\prompts\system.md)
$ uv run python -m kaggle_gemma_agent.prompt_variant apply --cwd submission
variant 'v3' is already the active prompt (submission\prompts\system.md)
```

`git status --short` shows no modification of `submission/prompts/system.md`
after either `apply`.

Compliance gate and archive contents:

```text
$ uv run python -m kaggle_gemma_agent.pack submission --check
submission contract OK (6/6 points)

$ uv run python -m kaggle_gemma_agent.pack submission -o <tmp>/verify.zip
wrote .../verify.zip (19660 bytes)

zip entries under prompts/:
prompts/analyzer.md	1141
prompts/system.legacy.md	2371
prompts/system.md	5376
prompts/system.v2.md	3755
```

The duplicate is gone from the archive (22069 -> 19660 bytes) and
`prompts/system.v3.md` is no longer packed.

## Log

- **L1** (user request, verbatim): "implementalo".
- **L2**: the specification is issue #90, whose "Expected behavior" records
  Option A and the D1-D7 contract. Decisions taken with the user: implement
  Option A as written; no prompt wording change; no new issue for the
  archive-exclusion or provenance follow-ups.
- **L3** (requirement refinement, discovered during T4): the issue says the
  guard compares "the variant files that exist" after deduplicating aliases.
  Implemented as: copy-backed variants are always compared with each other, and
  the active prompt joins as `active` **only while the selector names an alias**.
  Reason: the active prompt mirrors whichever variant was materialized, so
  including it while the selector names a copy-backed variant would report a
  duplicate after every legitimate `apply` (selector `v2` makes
  `system.md == system.v2.md` by construction). The committed selector is `v3`,
  so the shipped state still compares the active prompt and would catch a new
  file copying it.
- **L4** (test detail): the new fixtures write with `newline="\n"`; without it
  Windows text translation produced CRLF and the byte comparison failed for the
  wrong reason.
- **L5** (out of scope, unchanged): excluding variant files from the packed
  archive and recording the variant name in `provenance` remain separate issues.
- **L6** (coverage detail): the first green run left `is_active`'s copy-backed
  fallback and the CLI `apply` error path untested; two tests were added in
  `4eefab4` and the passed count in the evidence above reflects them.
