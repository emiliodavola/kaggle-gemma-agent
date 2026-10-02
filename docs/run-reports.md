# File-based run reports (`runs/`) — host ↔ Hermes handoff

The `swegemma` harness writes raw artifacts into a `--results-dir` that is
git-ignored and keyed by run name. Running on the host means results must reach
Hermes (and any future reviewer) **through the shared folder**, not by pasting
log text into chat.

This document defines that handoff contract: the `runs/<UTC>/` layout, the
`report.json` schema, the `STATUS` polling signal, `runs/index.jsonl`, the
scale caps, and exactly how Hermes picks a run up. The code lives in
`src/kaggle_gemma_agent/harness_runs.py` (archiver + CLI) and
`src/kaggle_gemma_agent/run_report.py` (report engine). `runs/` is git-ignored;
**never commit results**.

- Schema version: **`1.0`** (`run_report.SCHEMA_VERSION`)
- Producer: `python -m kaggle_gemma_agent.harness_runs ...`
- Consumer: `python -m kaggle_gemma_agent.harness_runs report runs/<id>`

## 1. Layout

```
runs/
├── index.jsonl                       # append-only, one line per finished run
├── index-archive/                    # compacted index lines (history, never lost)
│   └── <first-run-id>__<last-run-id>.jsonl
└── <UTC stamp>/                      # e.g. 20260930T120000Z
    ├── STATUS                        # DONE|BLOCKED|PARTIAL + 5-line summary
    ├── report.json                   # report 1.0 (metadata + first task chunk)
    ├── report.part0002.json          # only when tasks > REPORT_MAX_TASKS
    ├── manifest.json                 # archiver: source paths, per-task artifact sizes
    ├── summary.json                  # copied verbatim from --results-dir (if present)
    ├── task_results.jsonl            # copied verbatim from --results-dir (if present)
    └── <instance_id>/
        ├── trace.json                # ATIF trajectory
        ├── session.log               # Phase 1 transcript
        ├── agent_patch.diff          # extracted patch
        ├── test_output.log           # Phase 2 pytest output
        ├── junit.xml                 # copied out of Container B (optional)
        └── metadata.json             # per-task artifact sizes
```

`STATUS` is written **after** `report.json`, so a poller that waits for
`STATUS` always finds a complete report. The UTC stamp is
`datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")` unless `--timestamp` overrides it.

## 2. `report.json` (schema `1.0`)

Top-level keys:

| Key | Type | Meaning |
| :--- | :--- | :--- |
| `schema_version` | `str` | Always `"1.0"` for this contract. |
| `run_id` | `str` | The UTC stamp (directory name). |
| `generated_at` | `str` | ISO-8601 UTC timestamp. |
| `status` | `str` | `DONE` / `BLOCKED` / `PARTIAL` (see §3). |
| `status_reasons` | `list[str]` | Why `PARTIAL`/`BLOCKED` was chosen (empty for `DONE`). |
| `environment_blocked` | `bool` | `true` when the **same** missing module appears in `>= 2` failing tasks (a uniform environment gap, not agent performance). |
| `missing_modules` | `list[str]` | Sorted union of every `No module named '...'` module across failing tasks. |
| `env` | `object` | Host/backend names — **never credential values** (see §7). |
| `budgets` | `object` | Per-task budgets: `tool_calls` 100, `time_minutes` 60, `turns` 500. |
| `totals` | `object` | `tasks`, `resolved`, `unresolved`, `unknown`, `resolution_rate`, `wall_seconds`, `tool_calls`, `turns`. |
| `summary` | `object` | Echo of `summary.json` (`resolution_rate`, `resolved`, `total`) or `null`s. |
| `notes` | `list[str]` | Non-fatal parse notes (e.g. `task_results.jsonl:3 invalid JSON`). |
| `tasks` | `list[object]` | Task records (first chunk when split; see §6). |
| `parts` | `int` | `1` = single file; `>1` = task chunks live in `part_files`. |
| `part_files` | `list[str]` | Sidecar filenames (`report.part0002.json`, …). |
| `report_path`, `index_path` | `str` | Paths echoed into `STATUS` for the host. |

### Per-task record

| Field | Type | Notes |
| :--- | :--- | :--- |
| `instance_id` | `str` | e.g. `fastapi_15661`. |
| `backend` | `str` | From the result line (`model`/`backend`) or the run backend. |
| `repo` | `str \| null` | Populated only when `--tasks tasks.jsonl` is supplied. |
| `wall_seconds` | `float \| null` | `agent_elapsed_seconds` / `elapsed_seconds` / … |
| `tool_calls` / `tool_calls_budget` | `int \| null` / `int` | vs the 100-call budget. |
| `turns` / `turns_budget` | `int \| null` / `int` | vs the 500-turn budget. |
| `resolved` | `bool \| null` | From the result line; else inferred from JUnit. |
| `status` | `str` | `pass` / `fail` / `unknown`. |
| `junit` | `object \| null` | Counts + capped `testcases` when `junit.xml` exists. |
| `fail_to_pass` | `object \| null` | Expected/observed/passed/failed/missing nodes (JUnit only). |
| `pass_to_pass` | `object \| null` | Same shape for the passing set. |
| `error` | `str \| null` | Harness error text when present. |
| `patch_sha256` | `str \| null` | `sha256` of `agent_patch.diff`. |
| `patch_path` | `str \| null` | Run-relative path to the patch. |
| `artifacts` | `object` | `run-relative path → {size, sha256}` for **every** task file. |
| `failure_tail` | `object \| null` | `{source, chars, truncated, text}` for non-passing tasks. |
| `failure_kind` | `str \| null` | Coarse cause from `test_output.log`: `collection_error` / `test_failure` / `timeout` / `unknown`; `null` when the task passed or has no test log. |
| `missing_modules` | `list[str]` | Sorted unique `No module named '...'` modules from the `test_output.log` tail; empty for a passing task or one without a test log. |

`fail_to_pass` / `pass_to_pass` are always present when `junit.xml` exists.
Expected nodes come from (in order): the result line's `FAIL_TO_PASS` /
`PASS_TO_PASS`, the `--tasks` metadata, added `test_*` functions in
`test_patch`, then the JUnit outcome set itself. The harness's
`task_results.jsonl` schema is unpublished, so the reader matches keys
case-insensitively through documented aliases and records (never raises on)
unmapped input.

## 3. `STATUS` — the polling signal

`STATUS` is a six-line text file: the status token, then a fixed five-line
human summary. Hermes and the host print the **same** text via the `report`
subcommand.

```
DONE
run 20260930T120000Z | backend muse-spark | docker 27.3.1 | os Linux ...
tasks 1 | resolved 1 | rate 1.000 | unknown 0
tool_calls 37/100 | wall 13.5/60 min | turns 14/500
failures 0 | top: none
schema 1.0 | report runs/20260930T120000Z/report.json | index runs/index.jsonl
```

When at least one task failed, the `failures` line also carries the coarse
causes, e.g. `failures 2 | kinds collection_error=2 | top: fastapi_15588, ...`.
That distinguishes an environment/collection failure from an assertion failure
without opening `failure_tail`; the per-task value is `failure_kind` above.

When the same missing module appears in `>= 2` failing tasks, `environment_blocked`
is set and the `failures` line additionally carries `| env missing: <names>`,
e.g. `failures 5 | kinds collection_error=5 | env missing: typing_inspection | top: ...`.
The matching `status_reasons` entry reads
`environment failure: missing module(s) typing_inspection (5/5 tasks)`, so a
uniform dependency gap (the competition wheel set is incomplete, see
`docs/host-trial-runbook.md` §6.2) is not mistaken for agent performance. A single
task or two tasks with *different* modules does not set the flag.

Status selection:

| Token | When |
| :--- | :--- |
| `BLOCKED` | No task records at all (the harness produced nothing). |
| `PARTIAL` | Tasks exist but `summary.json` is missing, the harness reported errors, or one or more tasks have no verdict. |
| `DONE` | Every task has a verdict and the summary is present. |

`resolved < tasks` is **not** `PARTIAL` — an unresolved task is a normal,
complete result. `PARTIAL` means *incomplete/corrupt*, not *low score*.

## 4. `runs/index.jsonl` — cross-run comparison

One JSON object per line, appended when a run is finalized:

```json
{"run_id": "20260930T120000Z", "timestamp": "20260930T120000Z", "status": "DONE", "backend": "muse-spark", "tasks": 1, "resolved": 1, "rate": 1.0, "report": "runs/20260930T120000Z/report.json"}
```

Read the last `N` lines to compare runs without opening every report.

## 5. CLI

```bash
# archive a --results-dir into runs/<UTC>/ and write the handoff
python -m kaggle_gemma_agent.harness_runs archive results/run_01 \
    --junit-dir junit --tasks tasks.jsonl --backend muse-spark

# backward-compatible bare form (same as `archive`)
python -m kaggle_gemma_agent.harness_runs results/run_01 --junit-dir junit

# print the STATUS text (host AND Hermes)
python -m kaggle_gemma_agent.harness_runs report runs/20260930T120000Z

# regenerate report.json/STATUS/index.jsonl from archived artifacts
python -m kaggle_gemma_agent.harness_runs report runs/20260930T120000Z --rebuild

# archive artifacts only, no report/STATUS/index
python -m kaggle_gemma_agent.harness_runs archive results/run_01 --no-report
```

## 6. Scale caps

| Cap | Constant | Value | Behavior |
| :--- | :--- | :--- | :--- |
| Failure tail | `FAILURE_TAIL_CHARS` | `4000` chars | Tail is truncated; `failure_tail.truncated` is set. |
| JUnit rows | `JUNIT_MAX_CASES` | `2000` rows | `junit.testcases` is capped; `cases_truncated` is set; counts stay complete. |
| Tasks per report | `REPORT_MAX_TASKS` | `400` | Extra tasks move to `report.part0002.json`, …; `parts`/`part_files` list them. `load_report` reassembles transparently. |
| Index length | `INDEX_MAX_LINES` / `INDEX_KEEP_LINES` | `1000` / `500` | On overflow, the oldest lines move to `index-archive/<first>__<last>.jsonl`; the newest 500 stay in `index.jsonl`. |

Read a split report with `run_report.load_report(run_dir)` rather than opening
`report.json` directly.

## 7. Redaction guarantee

`report.json.env` records **names only**:

- `backend` from `ROBOTINA_HERMES_MODEL` (a model name),
- `backend_base_host` = the hostname of `ROBOTINA_HERMES_MODEL_BASE_URL`
  (never the path, query, or key),
- `safe_env_names` = which of those two variables were set,
- `credential_vars_present` = names of variables whose name contains
  `KEY`/`TOKEN`/`SECRET`/`PASSWORD`/`CREDENTIAL`, e.g. `OPENCODE_GO_API_KEY`.

No secret **value** is ever read or stored; tests assert a sentinel key never
appears anywhere in the serialized environment.

## 8. How Hermes picks up a run

1. Poll `runs/*/STATUS` (newest by modification time). Absence means the run is
   still in progress — `STATUS` is written last.
2. Read all six lines. The first token is the verdict: `DONE`, `BLOCKED`, or
   `PARTIAL`.
3. For per-task detail, read `runs/<id>/report.json` and reassemble chunks:
   `python -c "import json,sys; from pathlib import Path; from kaggle_gemma_agent import run_report; print(json.dumps(run_report.load_report(Path(sys.argv[1])), indent=2))" runs/<id>`.
4. For cross-run comparison, tail `runs/index.jsonl`.
5. To reprint the summary identically to the host:
   `python -m kaggle_gemma_agent.harness_runs report runs/<id>`.

Because everything is a file in the shared folder, Hermes needs no chat paste
and no network: detection is `runs/` + a `STATUS` read.

## 9. Host workflow

The host trial runbook (`docs/host-trial-runbook.md`, §9) ends with the
archive + report step:

```powershell
uv run python -m kaggle_gemma_agent.harness_runs archive results\run_01 `
    --junit-dir junit --tasks data\raw\tasks.jsonl --backend <model-name>
uv run python -m kaggle_gemma_agent.harness_runs report runs\<UTC>
```

Then stop: Hermes reads `runs/` directly.
