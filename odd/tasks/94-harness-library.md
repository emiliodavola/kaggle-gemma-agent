# Feature: 94-harness-library

Closes #94. Branch `feat/94-harness-library`, stacked on
`docs/93-harness-improvement-protocol` (PR #103) because both append to the
journal. Runner: `uv run pytest`. Delivery strategy: single PR.

## Specs

Source of truth: issue #94 body, sections 1-9 and the acceptance criteria. This
file names the rules so a task can be tied to one; it does not restate them.

- S1 - the sixth genre `experience library`, named in `AGENTS.md` `## Documentation`
  (one new bullet) and in the `docs/README.md` genre table (one new row).
- S2 - `docs/harness-library/INDEX.md` with the six-column header, one data row,
  and the rule that `Status` is the only cell an existing row may change.
- S3 - `docs/harness-library/module-path-disagrees-with-disk/EXPERIENCE.md` with
  the six-field header, exactly five `##` sections in order, and the seed's
  verbatim `## Cue`, `## Lesson`, `## Evidence` and `## Confidence` strings.
- S4 - the slug rule `^[a-z][a-z0-9-]{2,47}$`, immutable once chosen.
- S5 - `provenance_hashes` gains `skills` between `eval_config` and `repo_commit`,
  with `SKILLS_DIR = "submission/skills"` and the byte-exact tree stream
  (path, `\x00`, bytes, `\x00`, sorted by path byte value, `/` separators,
  `__pycache__`/`.pyc` skipped, `None` when the directory is absent).
- S6 - `tests/test_harness_runs.py`: the explicit key set at the manifest test,
  the full expected dict at the missing-files test, and the new
  `test_provenance_skills_hash_is_order_independent_and_byte_sensitive`.
  `tests/test_host_trial_runner.py` is not touched.
- S7 - `docs/run-reports.md`: one `skills` row in the `provenance` table plus a
  `### Skills hash` subsection.
- S8 - one `docs/README.md` index row for the library index, placed after the
  `harness-improvement-protocol.md` row.
- S9 - one journal event, re-rendered day file, and `journal validate` green.

## Non-goals

- Backfilling entries from the `odd/tasks/*.md` files or from earlier runs.
- Re-archiving any run to add `skills`, or editing anything under `runs/`.
- A semantic or embedding index; retrieval is browsing `INDEX.md`.
- Any change to `submission/**`, the skill count, or `pack.py`'s surface checks.
- Adding `change tracker` to the header `Genre:` enum (pre-existing omission).
- Linking this tracker from the `docs/README.md` "Change trackers" list: that
  list is already five entries stale and the issue fixes `docs/README.md` at two
  added lines plus one changed line.

## Tasks

- [x] T1 - Write the failing tests for the new `skills` key (S6). RED observed
      before the source change: 3 failed, 18 deselected.
- [x] T2 - Add `SKILLS_DIR`, `_sha256_tree_or_none` and the `skills` key to
      `harness_runs.py` (S5). GREEN: the new test and both updated assertions
      pass.
- [x] T3 - Add the library index and the seeded entry (S2-S4).
- [x] T4 - Add the sixth genre to `AGENTS.md` and `docs/README.md`, plus the
      index row (S1, S8).
- [x] T5 - Document the hash in `docs/run-reports.md` (S7).
- [x] T6 - Append the journal event, render the day file, validate (S9).
- [x] T7 - Run the full suite, ruff, format, mypy, pyright, coverage and the pack
      gate; paste the observed output in Evidence (S6-S9).

## Log

L1 (verbatim, user): "implementá todos los issues approved con una rama de git
propia, pushealos y creá el PR asignandomelo a mi"

L2 - Baseline on `main` at `74cd549` before any change: `uv run pytest tests/ -q`
-> `5 failed, 375 passed in 10.05s`, the five pre-existing Windows
path-separator/CRLF failures the issue documents; `ruff check` clean, pack gate
`6/6 + 3 + 4`, `journal OK (41 events)`.

L3 - Deviations from the issue text, recorded rather than absorbed silently:
(a) `AGENTS.md` L29 said "one of five genres" and now reads "one of six" - a
six-bullet list under a "five" sentence is the defect the sixth genre creates,
and the issue's own resolved ambiguity calls the new bullet the sixth;
(b) `INDEX.md` carries the six-field header block and a one-line intro above the
required table, because `AGENTS.md` requires every document to start with that
block and belong to a genre;
(c) the index `Cue` cell is a 114-character prefix of the seeded cue plus an
ellipsis, because the seed's cue is 130 characters and the `Cue` column is capped
at 120.

L4 - The five `src_only` tasks in `runs/20261009T122847Z` were recomputed from
`run_report.build_report` rather than quoted from memory; `requests_7315`'s
manifest task entry has no `agent_patch.diff`, which the seed entry states.

## Evidence

RED before the source change:

```text
$ uv run pytest tests/test_harness_runs.py -q -k "provenance or missing_files"
FAILED tests/test_harness_runs.py::test_archive_run_records_provenance_in_manifest
FAILED tests/test_harness_runs.py::test_provenance_skills_hash_is_order_independent_and_byte_sensitive
FAILED tests/test_harness_runs.py::test_emit_run_finished_uses_null_for_missing_files
3 failed, 18 deselected in 0.93s
```

GREEN after it:

```text
$ uv run pytest tests/test_harness_runs.py -q
1 failed, 20 passed in 3.46s
```

The one failure is the pre-existing
`test_emit_run_finished_records_hashes_counts_and_evidence` Windows CRLF
assertion, which fails identically on `main`.

```text
$ uv run python -c "from kaggle_gemma_agent import harness_runs; import json; print(json.dumps(harness_runs.provenance_hashes(), indent=2))"
{
  "prompt": "960ec773f9b1394f3238e8ad2827e86f05aed3e8c57dde392a0cf523129af8ee",
  "sampling": "60f7bfa4d4f0e5ab12320ba11c3d82355209bc97a54a2d96b1be06ff3750d005",
  "eval_config": "2f9e88d219a1109f93c8c7b5446e545c152612a11194e82e9a0e3c58d552adac",
  "skills": "bb2174ad17fd657c4ba9acdcb9fd229bcaeb8e31b0aa3dbfffabedf7d67ce6f0",
  "repo_commit": "6a3071799dee7832cf3e630419bed6b862157b2b-dirty"
}
```

```text
$ uv run pytest tests/ -q
5 failed, 376 passed in 8.70s   (same five node ids as main)

$ uv run ruff check src/ tests/ scripts/
All checks passed!

$ uv run ruff format --check src/ tests/
17 files already formatted

$ uv run mypy src/ scripts/
Success: no issues found in 10 source files

$ uv run pyright
0 errors, 0 warnings, 0 informations

$ uv run coverage report -m
TOTAL ... 97%; harness_runs.py ... 94%   (gate 90)

$ uv run python -m kaggle_gemma_agent.pack submission --check
submission contract OK (6/6 points)
harness surface OK (3 checks)
answer leak OK (4 patterns)

$ uv run python -m kaggle_gemma_agent.journal validate
journal OK (43 events)
```

- Issue: #94. PR: see the PR linked from the issue.
- Branch: `feat/94-harness-library`.

Risk: item 3 - `provenance_hashes` is consumed by the archiver, the runner's
`run_started` journal event and `docs/run-reports.md`; the new key is additive and
keeps the existing four in order, but every consumer of the key set sees one more
member.
