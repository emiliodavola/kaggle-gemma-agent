# Feature: cheap-improvement-wins

## Goal

Land four cheap, independent improvements surfaced by the run_03/run_04
artifacts:

1. Surface per-task import/collection resolution errors in the run report
   (`run_report.py`), without reclassifying them as infrastructure failures.
2. Record submission provenance in the archived manifest (`harness_runs.py`),
   the same hashes the journal already captures at run start.
3. Document both in `docs/run-reports.md`.
4. Add two short prompt/skill guards for the failure modes seen in run_03:
   N4 (multi-line `edit_file` replaced via `read_file` + `write_file`) in
   `submission/prompts/system.md`, and N1 (capture a failing-test baseline
   before the first edit) in `submission/skills/issue-localization/SKILL.md`.

## Decisions taken with the user

1. `import_errors` is an additive, surfaced signal. It never changes the meaning
   of `infra_error` or `environment_blocked`, because an import/attribute error
   can be agent-caused; it needs triage, not an automatic verdict.
2. The manifest `provenance` block carries the same keys as
   `harness_runs.provenance_hashes` (`prompt`, `sampling`, `eval_config`,
   `repo_commit`) and inherits the re-archive caveat already documented for the
   journal: an archived re-report hashes the current submission, not the one the
   run used.
3. The prompt/skill additions stay to one or two lines each, match the existing
   voice, and introduce no forbidden token (rule e).

## Non-goals

- Reclassifying import errors as infrastructure failures.
- Changing the `archive` CLI surface; only an optional `repo_root` parameter was
  added to `archive_run` (defaulting to the existing default), so the CLI is
  byte-compatible.
- Re-running any trial, or rewriting any run analysis document.
- Editing the other prompt variants; `prompts/system.md` is materialized from the
  selected `prompts/system.v3.md`, so the same line was added there and
  re-applied.

## Tasks

- [x] T1 — `run_report.py`: `cannot import name 'X' from 'Y'` and
      `AttributeError: module 'Y' has no attribute 'X'` regexes, an
      `_import_errors(task_dir, status)` helper, and the `import_errors` field on
      the per-task record.
- [x] T2 — `harness_runs.py`: `provenance` block in `manifest.json` via
      `provenance_hashes(repo_root)`.
- [x] T3 — `docs/run-reports.md`: document `import_errors` and the manifest
      `provenance` block plus its re-archive caveat.
- [x] T4 — prompt/skill guards N4 (`system.v3.md`, materialized into
      `system.md`) and N1 (`issue-localization/SKILL.md`).
- [x] T5 — tests added; `pytest -q`, `ruff check src/ tests/`,
      `pack submission --check` and `journal validate` all green.

## Evidence

- `uv run pytest -q` -> `343 passed`.
- `uv run ruff check src/ tests/` -> `[]` (no findings).
- `uv run python -m kaggle_gemma_agent.pack submission --check` ->
  `submission contract OK (6/6 points)`.
- `uv run python -m kaggle_gemma_agent.journal validate` -> `journal OK (25 events)`.
  Journal entry `J-20261007-09` records this change.
- Unit test with the exact run_04 httpx text
  (`tests/test_run_report.py::test_build_report_surfaces_httpx_attribute_error`)
  asserts `import_errors == ["module 'httpx' has no attribute 'Stream'"]` and
  `infra_error is False`.
- `tests/test_harness_runs.py::test_archive_run_records_provenance_in_manifest`
  asserts the manifest `provenance` key set.
- Raw source of the failures: `runs/20261007T165050Z/httpx_3672/test_output.log`
  and `runs/20261007T165050Z/manifest.json` (read 2026-10-07).
