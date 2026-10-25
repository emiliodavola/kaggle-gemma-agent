# Feature: 88-delivery-record

Closes #88. Branch `feat/88-delivery-record` (from `main`). Runner: `uv run pytest`.
Delivery strategy: single PR (one work unit; the issue states the full spec).

## Specs

Source of truth for every rule below: issue #88 body, sections 1-13 and the
acceptance criteria. This file does not restate the rules; it names them so a
task can be tied to one.

- S1 — `run_report.py` gains `PATCH_SCOPES`, `_CONFIG_FILES`, `_PYTEST_RE` and
  the helpers `_patch_text`, `_patch_paths`, `_patch_scope`, `_is_test_path`,
  `_is_config_path`, `_is_src_path`, `_trace_facts`, `_target_paths`,
  `_delivery_record`, `_delivery_totals`, with the semantics of issue §2-§8 and
  §11. Stdlib only, no new imports.
- S2 — `_build_task` adds `"delivery": _delivery_record(task_dir, meta)`
  immediately after `"patch_path"` and before `"artifacts"`; the record has
  exactly five keys in the order `patch_files`, `patch_scope`, `submitted`,
  `ran_pytest`, `ran_target_test` (issue §8).
- S3 — `build_report` adds `totals.delivery` **last**, after `"turns"`, computed
  from the already-built records with `_delivery_totals(tasks)`; integer counts
  only, all six `patch_scope` keys present in `PATCH_SCOPES` order (issue §8).
- S4 — `render_summary` emits exactly one extra line between `failures ...` and
  `schema ...`, only when `totals.delivery` is a `Mapping`, in the exact format
  of issue §9; the docstrings change from "five-line" to "six-line". Every other
  line stays byte-identical.
- S5 — `tests/test_run_report.py` gains
  `test_build_report_delivery_record_and_totals` (7-task `tmp_path` fixture, exact
  expected records/totals/render from the acceptance criteria) and
  `test_render_summary_omits_delivery_for_old_reports`; the edge-case matrix rows
  1, 3, 4, 5, 9, 10, 14, 15, 19, 25, 26, 27, 28 are asserted by direct helper
  calls inside those two tests. `test_render_summary_lines` and
  `test_build_report_surfaces_sandbox_deps_mode` move from 6 to 7 lines.
- S6 — `docs/run-reports.md` documents `totals.delivery`, the five per-task
  fields, the `patch_scope` enum with precedence, the `bool | null` semantics of
  `ran_target_test` and its `tasks.jsonl` dependency, the `_PYTEST_RE`
  mention-detector caveat, and the new seven-line `STATUS`.
- S7 — one journal event is appended (`--type change --issue 88`), its day file
  regenerated, and the journal validates.
- S8 — nothing else changes: `resolved`, `resolution_rate`, `unresolved`,
  `measured`, `failure_kind`, `verdict_source`, `patch_path`, `patch_sha256`,
  `index_entry`, `SCHEMA_VERSION` and `runs/` evidence stay untouched (issue §13).

Cannot-do clauses from the issue that must be honoured: do not run the
`harness_runs report` CLI against `runs/`; do not fix the five pre-existing
Windows failures; do not resolve/open patch paths.

## Non-goals

- Any scoring, rate, filter or denominator change (issue §Scope, "Out of scope").
- Writing `delivery` into `runs/index.jsonl` or `index_entry`.
- Re-scoring or editing any archived `runs/` or `docs/runs/` artifact.
- Touching `submission/`.

## Tasks

- [x] T1 — Add constants, path predicates, patch parsing, trace facts, target
      paths, record and totals to `run_report.py` (S1).
- [x] T2 — Wire `_build_task`, `build_report` and `render_summary` (S2-S4).
- [x] T3 — Add the two tests, fold the edge-case assertions in, update the
      STATUS line-count assertions (S5).
- [x] T4 — Document the contract in `docs/run-reports.md` (S6).
- [x] T5 — Append the journal event, render the day file, validate (S7).
- [x] T6 — Run `pytest tests/`, `ruff check src/ tests/ scripts/`, mypy and
      pyright; paste the observed output in Evidence (S5-S8).

## Log

L1 (verbatim, user): "comenzá a implementar, en una rama de git para versionar
aparte, el issue #88"

L2 — Pre-existing uncommitted changes on `main`
(`docs/journal/events.jsonl`, `docs/journal/20261008.md`, untracked
`docs/journal/20261009.md`, the runner's entries for run `20261009T122847Z`) were
stashed with `git stash push -u -m "pre-existing run journal entries for
20261009 (issue 88 session)"` before branching, so this branch's journal diff
holds only its own entry. Restore them on `main` with `git stash pop`.

L3 — Baseline observed on this checkout before any change:
`uv run pytest tests/ -q` -> `5 failed, 338 passed in 9.54s`, the five
path-separator/CRLF failures the issue documents.

L4 — Implementation follows the issue §11 sketch in behavior. Two deviations
from the acceptance text, both recorded rather than silently absorbed:
`journal check` does not exist (`journal.py` exposes `validate`), so the check
uses `validate`; and four existing tests asserted a six-line `STATUS`, not two,
so `test_build_report_flags_environment_blocked_for_a_shared_missing_module`
and `test_build_report_reports_measured_totals_and_reason` were updated from
`== 6` to `== 7` alongside the two the issue named.

## Evidence

- `uv run pytest tests/test_run_report.py -q` ->
  `1 failed, 47 passed in 0.60s`; the failure is the pre-existing
  `test_build_report_done` Windows path-separator assertion.
- `uv run pytest tests/ -q` -> `5 failed, 340 passed`, the same five
  pre-existing Windows failures and no new one.
- `uv run ruff check src/ tests/ scripts/` -> `All checks passed!`.
- `uv run ruff format --check src/ tests/` -> `17 files already formatted`.
- `uv run mypy src/` -> `Success: no issues found in 6 source files`.
- `uv run pyright` -> `0 errors, 0 warnings, 0 informations`.
- `uv run coverage run -m pytest tests/ -q` + `uv run coverage report -m` ->
  `TOTAL ... 97%`, `run_report.py ... 98%` (gate is 90%).
- `uv run python -m kaggle_gemma_agent.journal add ... --issue 88` ->
  `J-20261025-01`; `uv run python -m kaggle_gemma_agent.journal validate` ->
  `journal OK (32 events)`.
- Golden check on `runs/20261009T122847Z/` with
  `run_report.load_task_metadata(Path("data/raw/tasks.jsonl"))` through a
  throwaway read-only script (never the `report` CLI) reproduces issue §12 row
  by row:
  `TOTALS {'submitted': 11, 'ran_pytest': 5, 'ran_target_test': 3,
  'ran_target_test_unknown': 0, 'patch_scope': {'src_only': 5, 'edits_tests': 2,
  'config_only': 1, 'scratch': 3, 'none': 1, 'corrupted': 1}}` and
  `delivery submitted 11/13 | scope src_only=5 edits_tests=2 config_only=1
  scratch=3 none=1 corrupted=1 | pytest 5 | target 3`, with `STATUS` at seven
  lines.
- Issue: #88. PR: #96 (`feat/88-delivery-record`).

Risk: none — additive report fields and one extra STATUS line; no stored data,
credentials, concurrency, dependency or release surface changes, and no
existing key's value moves.
