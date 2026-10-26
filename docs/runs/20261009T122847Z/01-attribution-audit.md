---
Date: 2026-10-26
Genre: run analysis
Status: current
Scope: Observations and attributions for run 20261009T122847Z and its comparison with run 20261008T025904Z; does not re-audit other runs or classify every failure.
Source of truth: runs/20261009T122847Z/, runs/20261008T025904Z/, data/raw/tasks.jsonl, docs/journal/events.jsonl (read 2026-10-26)
Limits: counts and paths only; no randomisation, no causal estimation.
---

# Attribution audit - run 20261009T122847Z

This analysis applies `docs/run-analysis-vocabulary.md`. Observations report
what the artifacts contain; attributions carry one of the four verdicts.

## Observations

- `20261009T122847Z`: 13 tasks, `resolved 1`, `resolution_rate 0.0769`
  (`report.json` totals; `STATUS`: `rate 0.077`), `unknown 0`.
- `requests_7205`: `agent_patch.diff` hunk headers and bodies equal the `patch`
  of `data/raw/tasks.jsonl` (`hunk_headers_equal: True`,
  `hunk_bodies_equal: True`). `test_output.log` shows 4 failures in
  `tests/test_utils.py::test__parse_content_type_header[...no_equals...]`.
- `requests_7315`: `report.json` records 22 tool calls and the error
  `Agent completed execution without calling submit_patch.`; status `pass` in
  `20261008T025904Z`, `fail` in `20261009T122847Z`.
- Both runs: the 13 instance ids are identical; 12 of 13 statuses are identical;
  only `requests_7315` changed.

## Attributions

| Task | Artifact | Verdict | Observed |
| --- | --- | --- | --- |
| `requests_7205` | `runs/20261009T122847Z/requests_7205/agent_patch.diff`; `runs/20261009T122847Z/requests_7205/test_output.log` | `confounded` | The patch equals the gold hunk, yet 4 `tests/test_utils.py::test__parse_content_type_header[...no_equals...]` parameters fail in the same file against the installed distribution; the failure is not isolated from the environment. |
| `run` | `runs/20261008T025904Z/STATUS`; `runs/20261009T122847Z/STATUS` | `confounded` | `2/13 -> 1/13 on a different batch`; the only status change is `requests_7315` (`pass` -> `fail`) and its `report.json` has no `submit_patch` call; the recorded `prompt`, `sampling`, `eval_config` and `repo_commit` hashes are identical, and no `skills` hash exists (#94), so no recorded edit is identified. |

No row carries `helped`, `hurt` or `no observed effect`, because no archived pair
of executions isolates one harness change.

## Cross-run comparison

`2/13 -> 1/13 on a different batch`

Both batches hold the same 13 instance ids, and 12 of the 13 per-task statuses
are identical; the only change is `requests_7315` from `pass` to `fail`.

## What this does not establish

- No harness edit is identified as the cause of any outcome in these runs.
- The `skills` bytes may have changed between the runs without a recorded hash
  (see issue #94), so the record cannot rule that out.
- The resolution rate is not attributable to any edit: two runs, no
  randomisation, identical recorded provenance for the named components.
