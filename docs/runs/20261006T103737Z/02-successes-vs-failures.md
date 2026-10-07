---
Date: 2026-10-06
Genre: run analysis
Status: current
Scope: Per-task successes-vs-failures census of the 48 rich_* tasks, plus proposals N1-N6; it does not repeat P1-P11, which are already shipped.
Source of truth: runs/20261006T103737Z/* and data/raw/tasks.jsonl; read 2026-10-06.
Limits: census of 48 tasks, not a random sample; counts, means and ranges only, no inference.
---

# run_03 — successes vs failures: audit of the 48 tasks and additional proposals

- **Run:** `runs/20261006T103737Z` (mirror `results/run_03`), backend `gemma-4-31b-it-qat`, `STATUS DONE`.
- **Universe:** 48 tasks, all `Textualize/rich`. This document is a **census of 48**, not a sample;
  the prompt phases (`v2` idx 1-21, `v3a` idx 22-32, `v3` idx 33-48) are temporal cuts, not randomization.
- **Rule:** every number comes from `runs/20261006T103737Z/*` or `data/raw/tasks.jsonl`; anything unverifiable is marked **unverified**.
  There is no statistical inference: only counts, means, medians and ranges.
- **Relation to previous work:** proposals P1-P11 are already applied in `submission/` (PR #74) and are **not repeated**;
  this document adds differences/similarities and proposals N1-N6.

---

## 1. Coverage

**48/48 tasks covered.** Every task appears in this table, in its card in §2 and in all the aggregates of §3-§6.

| # | task | verdict | failure_kind (report) | phase |
|---:|---|---|---|---|
| 1 | rich_4070 | failed | test_failure | v2 |
| 2 | rich_4077 | resolved | — | v2 |
| 3 | rich_4079 | failed | test_failure | v2 |
| 4 | rich_4076 | resolved | — | v2 |
| 5 | rich_4075 | resolved | — | v2 |
| 6 | rich_4006 | resolved | — | v2 |
| 7 | rich_3718 | resolved | — | v2 |
| 8 | rich_3934 | resolved | — | v2 |
| 9 | rich_3953 | resolved | — | v2 |
| 10 | rich_3944 | resolved | — | v2 |
| 11 | rich_3942 | failed | unknown (null in report.json) | v2 |
| 12 | rich_3938 | resolved | — | v2 |
| 13 | rich_3882 | resolved | — | v2 |
| 14 | rich_3894 | resolved | — | v2 |
| 15 | rich_3935 | resolved | — | v2 |
| 16 | rich_3905 | resolved | — | v2 |
| 17 | rich_3930 | resolved | — | v2 |
| 18 | rich_3180 | resolved | — | v2 |
| 19 | rich_3486 | failed | unknown | v2 |
| 20 | rich_3777 | failed | test_failure | v2 |
| 21 | rich_3468 | failed | test_failure | v2 |
| 22 | rich_3782 | failed | collection_error | v3a |
| 23 | rich_3772 | resolved | — | v3a |
| 24 | rich_3296 | failed | collection_error | v3a |
| 25 | rich_3675 | failed | test_failure | v3a |
| 26 | rich_3676 | resolved | — | v3a |
| 27 | rich_3518 | resolved | — | v3a |
| 28 | rich_3535 | resolved | — | v3a |
| 29 | rich_3521 | resolved | — | v3a |
| 30 | rich_3506 | resolved | — | v3a |
| 31 | rich_3480 | resolved | — | v3a |
| 32 | rich_3472 | failed | test_failure | v3a |
| 33 | rich_3454 | failed | test_failure | v3 |
| 34 | rich_3471 | resolved | — | v3 |
| 35 | rich_3470 | failed | test_failure | v3 |
| 36 | rich_3469 | failed | test_failure | v3 |
| 37 | rich_3052 | resolved | — | v3 |
| 38 | rich_3278 | failed | test_failure | v3 |
| 39 | rich_2943 | failed | unknown (null in report.json) | v3 |
| 40 | rich_2725 | resolved | — | v3 |
| 41 | rich_3105 | failed | test_failure | v3 |
| 42 | rich_3130 | failed | test_failure | v3 |
| 43 | rich_3043 | failed | test_failure | v3 |
| 44 | rich_3067 | resolved | — | v3 |
| 45 | rich_3006 | resolved | — | v3 |
| 46 | rich_3064 | failed | test_failure | v3 |
| 47 | rich_3063 | resolved | — | v3 |
| 48 | rich_3061 | resolved | — | v3 |

### 1.1 Count reconciliation across sources

| Count | Value | Exact source |
|---|---|---|
| Lines of `task_results.jsonl` | 48 | `runs/20261006T103737Z/task_results.jsonl` (48 lines; `wc -l`) |
| Mirror copy `task_results.jsonl` | identical | `results/run_03/task_results.jsonl` (same size 11 174 B; `diff` → *Files are identical*) |
| Task directories | 48 | `runs/20261006T103737Z/rich_*/` |
| `trace.json` (file) | 48 | `manifest.json` `tasks[].artifacts`; 48 with the `trace.json` key |
| `trace.json` (mirror) | 48, byte-identical | `results/run_03/traces/trace_rich_*.json`, 48/48 with the same SHA-256 as the file |
| `agent_patch.diff` | 46 | `rich_2943` (no-submit) and `rich_3942` (timeout) are missing |
| `test_output.log` | 46 | the same two tasks without a file |
| `session.log` | 48 | `manifest.json` |
| `report.json` tasks | 48 | `report.json` → `tasks` (48) |
| `summary.json` | 48/29/0.6042 | `summary.json` `total_tasks/resolved/resolution_rate` |
| Tool calls (report) | 2 493 | sum of `report.json` `tasks[].tool_calls` |
| Tool calls (traces) | 2 841 | `tool_calls[]` objects in the 48 `trace.json` |
| Total steps (traces) | 3 828 | `len(steps)` of the 48 traces |
| `thinking` steps (traces) | 2 062 | `steps[].extra.event_type == 'thinking'` (1 980 main + 82 sub-agent) |
| Total wall | 76 151.89 s = 1 269.2 min | sum of `report.json` `tasks[].wall_seconds` (= `task_results.jsonl duration_seconds`) |

### 1.2 Tool-call reconciliation (report vs trace)

The report does **not** count `submit_patch` (free), `get_status` (free), `code_analyzer_agent` (sub-agent)
or the `edit_file` calls that the harness rejects before executing due to missing parameters (`{"error": ...}`).
The rule that reconciles the 48 cases, verified one by one, is:

```
tool_calls(report) = min(100, tool_calls(trace) - submit_patch - get_status - code_analyzer_agent - ParamError)
```

- `submit_patch`: 35 calls; `get_status`: 5; `code_analyzer_agent`: 11; `ParamError` (edit_file): 286.
- 2 841 − 35 − 5 − 11 − 286 = 2 504; the `min(100, ...)` cap trims 8 tasks that saturated the budget (4070, 4075, 3486, 3296, 3469, 3278, 3105, 3064) and yields 2 493.

### 1.3 Receipt reconciliation (observations)

Total `observation` in the traces: **2 841** = **2 160 ok** + **670 error** + **11 raw `code_analyzer` receipts** (without `status`).
Receipts per tool (ok / error / total):

| Tool | ok | error | total | error/total |
|---|---:|---:|---:|---:|
| `run_command` | 868 | 231 | 1099 | 21.0% |
| `read_file` | 882 | 6 | 888 | 0.7% |
| `edit_file` | 95 | 353 | 448 | 78.8% |
| `write_file` | 213 | 79 | 292 | 27.1% |
| `search_similar_code` | 57 | 1 | 58 | 1.7% |
| `submit_patch` | 35 | 0 | 35 | 0.0% |
| `code_analyzer_agent` | — † | — † | 11 | — |
| `get_status` | 5 | 0 | 5 | 0.0% |
| `get_code_neighbors` | 5 | 0 | 5 | 0.0% |

Errors by `error_type`: ParamError 286, CommandError 225, FileWriteError 79, FileEditError 63,
BudgetExceeded 11, FileReadError 3, TimeoutExceeded 2, ValueError 1. The sum 670 matches the `error` receipts.
† The 11 `code_analyzer_agent` receipts are raw text (`{"raw": ...}`), with no ok/error `status`.

### 1.4 Discrepancies found between the raw files and the previous docs

| # | Previous source | Says | Raw file | Reported |
|---|---|---|---|---|
| D1 | `STATUS` line 5 | `unknown=3` | `report.json` `failure_kind`: `null` in 2 failures (2943, 3942) + `unknown` in 1 (3486) | `STATUS` groups the `null` as `unknown`; both criteria are reported (raw: 14 test_failure + 2 collection_error + 1 unknown + 2 null) |
| D2 | `docs/runs/20261006T103737Z/04-harness-messages.md` §1 | T4 ok 2160, T5 error 681 | parse of observations | 2 160 ok + **670** error + 11 raw `code_analyzer` receipts. The 681 adds the 11 raw ones to the error count; the per-tool table in the doc itself sums to 2 841 (2160+681+11+5=2857 ≠ 2841) |
| D3 | `docs/runs/20261006T103737Z/01-audit.md` §2 | timeouts at "≈ 35–58 s per tool call" | `wall_seconds / tool_calls` of the 6 timeouts | real range **36.3–58.5 s/call** (minimum 3278/3472 = 36.3–36.6; maximum 3470 = 58.5) |
| D4 | `docs/runs/20261006T103737Z/03-failures-by-prompt-version.md` §6 | `rich_3454` with `scr=4` | `agent_patch.diff` | source 1 (`rich/highlighter.py`), scratch 3, **tests 1** (`tests/test_highlighter.py`). The doc counted the modified test as scratch |
| D5 | `docs/runs/20261006T103737Z/03-failures-by-prompt-version.md` §6 | per-task table (`calls`, `wall`, `sub`, `ana`, `src`, `scr`) | traces/patches | the only difference: D4; the rest of the 48 rows match the raw data |

### 1.5 Independent verification of the aggregates (2026-10-06, Robotina)

The aggregates in this document were recomputed from scratch with a dedicated script over `runs/20261006T103737Z/*/trace.json`,
`results/run_03/task_results.jsonl` and the `agent_patch.diff` files, without reusing the document's tables. They match:
48/48 tasks in both origins (`task_results.jsonl` from `runs/` and from `results/` are byte-identical);
`tool_calls` and `wall` per group (36.7/30.0 vs 75.2/92.0 and 1039.5/829.4 vs 2421.3/2645.3); `edit_file` 448 calls / 353
errors; `run_command` 1099/231; `write_file` 292/79; `read_file` 888/6; `submit_patch` 35 calls in 35 tasks;
`get_status` 5; `code_analyzer_agent` 11; scratch in 26/46 patches; `tests/` touched in 1/46 (`rich_3454`); resolutions without a
source hunk: 3 (`rich_3180`, `rich_3471`, `rich_3938`); rate with a source fix 26/48 = 0.5417.

Two figures from the draft did not reproduce and were corrected in §6 and N1 (denominator and explicit definition):
"3/42 with `pytest` before the first edit" → **3/46** (and 1/46 with the loose definition) and "17/42 edited without running
`pytest`" → **21/46**. The direction of the finding does not change.

---

## 2. Per-task card (48, in execution order)

`kind` is `failure_kind` from `report.json`; `null` is shown as such (see D1). `calls` = `report.json`;
`trace` = `tool_calls` objects from `trace.json`. `thinking` = steps with `event_type=thinking`.

### 1. rich_4070 — failed — test_failure — phase v2
- **Calls:** 100 (report) / 103 (trace) · **Wall:** 2404.1 s · **Steps:** 132 · **Thinking steps:** 74 · **LLM calls:** 117
- **Tool-call distribution:** run_command:57, read_file:34, edit_file:9, write_file:2, submit_patch:1
- **Error receipts per tool:** run_command:19, edit_file:1, write_file:1
- **Errors by error_type:** CommandError:17, BudgetExceeded:2, FileEditError:1, FileWriteError:1
- **Patch:** 7259 B, 3 file(s), 9 hunk(s); source: rich/console.py, rich/logging.py; scratch: fix_imports.py; tests: none; submit: yes (1)
- **Test:** 118 passed, 6 failed
- **Cause (1 line):** edits rich/console.py+logging.py but the 6 failing nodes are in tests/test_syntax.py (render); never touches the target file.

### 2. rich_4077 — resolved — — — phase v2
- **Calls:** 60 (report) / 83 (trace) · **Wall:** 1519.8 s · **Steps:** 110 · **Thinking steps:** 57 · **LLM calls:** 94
- **Tool-call distribution:** run_command:28, edit_file:24, read_file:23, write_file:7, submit_patch:1
- **Error receipts per tool:** edit_file:22, run_command:10, write_file:1
- **Errors by error_type:** ParamError:22, CommandError:10, FileWriteError:1
- **Patch:** 4158 B, 5 file(s), 5 hunk(s); source: rich/console.py; scratch: repro.py, repro_buffer.py, repro_buffer_only.py, repro_file_proxy.py; tests: none; submit: yes (1)
- **Test:** 4 passed
- **Cause (1 line):** resolved; source rich/console.py (5 hunk(s)); target tests green (4 passed).

### 3. rich_4079 — failed — test_failure — phase v2
- **Calls:** 92 (report) / 93 (trace) · **Wall:** 2525.0 s · **Steps:** 107 · **Thinking steps:** 55 · **LLM calls:** 99
- **Tool-call distribution:** read_file:39, run_command:38, write_file:12, edit_file:3, submit_patch:1
- **Error receipts per tool:** run_command:9, write_file:2
- **Errors by error_type:** CommandError:9, FileWriteError:2
- **Patch:** 577 B, 1 file(s), 1 hunk(s); source: rich/markdown.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 7 passed, 1 failed
- **Cause (1 line):** 1-line fix in rich/markdown.py; test_inline_code_in_table_cells still fails (1 failed/7 passed): insufficient fix.

### 4. rich_4076 — resolved — — — phase v2
- **Calls:** 32 (report) / 33 (trace) · **Wall:** 498.1 s · **Steps:** 52 · **Thinking steps:** 21 · **LLM calls:** 42
- **Tool-call distribution:** run_command:20, read_file:6, write_file:5, edit_file:1, submit_patch:1
- **Error receipts per tool:** run_command:2, write_file:1
- **Errors by error_type:** CommandError:2, FileWriteError:1
- **Patch:** 393 B, 1 file(s), 1 hunk(s); source: rich/pretty.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 24 passed
- **Cause (1 line):** resolved; source rich/pretty.py (1 hunk(s)); target tests green (24 passed).

### 5. rich_4075 — resolved — — — phase v2
- **Calls:** 100 (report) / 103 (trace) · **Wall:** 2550.3 s · **Steps:** 137 · **Thinking steps:** 84 · **LLM calls:** 119
- **Tool-call distribution:** run_command:41, read_file:40, write_file:12, search_similar_code:5, edit_file:3, code_analyzer_agent:1, submit_patch:1
- **Error receipts per tool:** run_command:12, write_file:3, edit_file:2
- **Errors by error_type:** CommandError:11, FileWriteError:3, FileEditError:2, BudgetExceeded:1
- **Patch:** 5479 B, 2 file(s), 7 hunk(s); source: rich/console.py; scratch: repro.py`}<tool_call|><|tool_call>call:run_command{command:; tests: none; submit: yes (1)
- **Test:** 100 passed
- **Cause (1 line):** resolved; source rich/console.py (7 hunk(s)); target tests green (100 passed).

### 6. rich_4006 — resolved — — — phase v2
- **Calls:** 27 (report) / 28 (trace) · **Wall:** 573.8 s · **Steps:** 42 · **Thinking steps:** 19 · **LLM calls:** 34
- **Tool-call distribution:** run_command:10, read_file:8, edit_file:5, write_file:4, submit_patch:1
- **Error receipts per tool:** edit_file:3, write_file:1
- **Errors by error_type:** FileEditError:3, FileWriteError:1
- **Patch:** 1237 B, 1 file(s), 2 hunk(s); source: rich/cells.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 67 passed
- **Cause (1 line):** resolved; source rich/cells.py (2 hunk(s)); target tests green (67 passed).

### 7. rich_3718 — resolved — — — phase v2
- **Calls:** 15 (report) / 16 (trace) · **Wall:** 213.5 s · **Steps:** 21 · **Thinking steps:** 9 · **LLM calls:** 18
- **Tool-call distribution:** run_command:7, read_file:3, edit_file:3, write_file:2, submit_patch:1
- **Error receipts per tool:** write_file:1, run_command:1
- **Errors by error_type:** FileWriteError:1, CommandError:1
- **Patch:** 767 B, 1 file(s), 2 hunk(s); source: rich/panel.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 13 passed
- **Cause (1 line):** resolved; source rich/panel.py (2 hunk(s)); target tests green (13 passed).

### 8. rich_3934 — resolved — — — phase v2
- **Calls:** 28 (report) / 29 (trace) · **Wall:** 564.5 s · **Steps:** 42 · **Thinking steps:** 19 · **LLM calls:** 35
- **Tool-call distribution:** run_command:12, write_file:10, read_file:4, edit_file:2, submit_patch:1
- **Error receipts per tool:** write_file:1, run_command:1, edit_file:1
- **Errors by error_type:** FileWriteError:1, CommandError:1, FileEditError:1
- **Patch:** 484 B, 1 file(s), 1 hunk(s); source: rich/live_render.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 11 passed
- **Cause (1 line):** resolved; source rich/live_render.py (1 hunk(s)); target tests green (11 passed).

### 9. rich_3953 — resolved — — — phase v2
- **Calls:** 45 (report) / 46 (trace) · **Wall:** 1778.2 s · **Steps:** 62 · **Thinking steps:** 27 · **LLM calls:** 53
- **Tool-call distribution:** run_command:20, write_file:10, read_file:9, edit_file:6, submit_patch:1
- **Error receipts per tool:** write_file:3, edit_file:3, run_command:2
- **Errors by error_type:** FileWriteError:3, FileEditError:3, TimeoutExceeded:1, CommandError:1
- **Patch:** 4108 B, 3 file(s), 5 hunk(s); source: rich/cells.py; scratch: repro_zwj.py, repro_zwj_split.py; tests: none; submit: yes (1)
- **Test:** 56 passed
- **Cause (1 line):** resolved; source rich/cells.py (5 hunk(s)); target tests green (56 passed).

### 10. rich_3944 — resolved — — — phase v2
- **Calls:** 46 (report) / 47 (trace) · **Wall:** 948.0 s · **Steps:** 62 · **Thinking steps:** 32 · **LLM calls:** 54
- **Tool-call distribution:** run_command:20, edit_file:11, read_file:10, write_file:5, submit_patch:1
- **Error receipts per tool:** edit_file:9, run_command:6, write_file:1
- **Errors by error_type:** FileEditError:9, CommandError:6, FileWriteError:1
- **Patch:** 2700 B, 2 file(s), 6 hunk(s); source: rich/_export_format.py, rich/console.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 54 passed
- **Cause (1 line):** resolved; source rich/_export_format.py, rich/console.py (6 hunk(s)); target tests green (54 passed).

### 11. rich_3942 — failed — unknown (null in report.json) — phase v2
- **Calls:** 93 (report) / 93 (trace) · **Wall:** 3622.5 s · **Steps:** 121 · **Thinking steps:** 72 · **LLM calls:** 105
- **Tool-call distribution:** run_command:48, read_file:45
- **Error receipts per tool:** run_command:11, read_file:2
- **Errors by error_type:** CommandError:11, FileReadError:2
- **Patch:** no patch (not captured)
- **Test:** no test_output.log
- **Cause (1 line):** no patch and no test_output; 93 calls / 3622 s, exhausts the 60 min exploring (read_file 45, run_command 48).

### 12. rich_3938 — resolved — — — phase v2
- **Calls:** 36 (report) / 36 (trace) · **Wall:** 962.8 s · **Steps:** 65 · **Thinking steps:** 29 · **LLM calls:** 50
- **Tool-call distribution:** run_command:18, read_file:14, write_file:2, edit_file:2
- **Error receipts per tool:** run_command:2, write_file:1
- **Errors by error_type:** CommandError:2, FileWriteError:1
- **Patch:** 648 B, 1 file(s), 1 hunk(s); source: none; scratch: repro.py; tests: none; submit: no (0)
- **Test:** 174 passed
- **Cause (1 line):** resolved with a scratch-only patch (repro.py); no source hunk → pre-resolved or the verdict does not rely on the source.

### 13. rich_3882 — resolved — — — phase v2
- **Calls:** 15 (report) / 16 (trace) · **Wall:** 193.9 s · **Steps:** 19 · **Thinking steps:** 9 · **LLM calls:** 17
- **Tool-call distribution:** run_command:8, read_file:3, write_file:3, edit_file:1, submit_patch:1
- **Error receipts per tool:** write_file:1, run_command:1
- **Errors by error_type:** FileWriteError:1, CommandError:1
- **Patch:** 503 B, 1 file(s), 1 hunk(s); source: rich/prompt.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 8 passed
- **Cause (1 line):** resolved; source rich/prompt.py (1 hunk(s)); target tests green (8 passed).

### 14. rich_3894 — resolved — — — phase v2
- **Calls:** 14 (report) / 15 (trace) · **Wall:** 223.4 s · **Steps:** 18 · **Thinking steps:** 9 · **LLM calls:** 16
- **Tool-call distribution:** run_command:6, read_file:5, write_file:2, edit_file:1, submit_patch:1
- **Error receipts per tool:** write_file:1
- **Errors by error_type:** FileWriteError:1
- **Patch:** 719 B, 1 file(s), 1 hunk(s); source: rich/_inspect.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 42 passed, 4 skipped
- **Cause (1 line):** resolved; source rich/_inspect.py (1 hunk(s)); target tests green (42 passed, 4 skipped).

### 15. rich_3935 — resolved — — — phase v2
- **Calls:** 85 (report) / 86 (trace) · **Wall:** 2165.9 s · **Steps:** 109 · **Thinking steps:** 58 · **LLM calls:** 97
- **Tool-call distribution:** run_command:42, read_file:23, edit_file:12, write_file:8, submit_patch:1
- **Error receipts per tool:** run_command:11, write_file:3, edit_file:3, read_file:1
- **Errors by error_type:** CommandError:11, FileWriteError:3, FileEditError:3, ValueError:1
- **Patch:** 7139 B, 6 file(s), 8 hunk(s); source: rich/measure.py, rich/padding.py; scratch: repro.py, repro_v2.py, repro_v3.py, repro_v4.py; tests: none; submit: yes (1)
- **Test:** 22 passed
- **Cause (1 line):** resolved; source rich/measure.py, rich/padding.py (8 hunk(s)); target tests green (22 passed).

### 16. rich_3905 — resolved — — — phase v2
- **Calls:** 38 (report) / 98 (trace) · **Wall:** 1531.1 s · **Steps:** 103 · **Thinking steps:** 65 · **LLM calls:** 87
- **Tool-call distribution:** edit_file:59, read_file:18, run_command:16, write_file:4, submit_patch:1
- **Error receipts per tool:** edit_file:59, write_file:2, run_command:1
- **Errors by error_type:** ParamError:59, FileWriteError:2, CommandError:1
- **Patch:** 1771 B, 1 file(s), 2 hunk(s); source: rich/progress.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 39 passed
- **Cause (1 line):** resolved; source rich/progress.py (2 hunk(s)); target tests green (39 passed).

### 17. rich_3930 — resolved — — — phase v2
- **Calls:** 28 (report) / 29 (trace) · **Wall:** 829.4 s · **Steps:** 45 · **Thinking steps:** 22 · **LLM calls:** 36
- **Tool-call distribution:** run_command:16, edit_file:5, read_file:4, write_file:3, submit_patch:1
- **Error receipts per tool:** run_command:4, edit_file:3, write_file:1
- **Errors by error_type:** CommandError:4, FileEditError:3, FileWriteError:1
- **Patch:** 2660 B, 2 file(s), 4 hunk(s); source: rich/cells.py; scratch: repro.py; tests: none; submit: yes (1)
- **Test:** 189 passed
- **Cause (1 line):** resolved; source rich/cells.py (4 hunk(s)); target tests green (189 passed).

### 18. rich_3180 — resolved — — — phase v2
- **Calls:** 30 (report) / 30 (trace) · **Wall:** 1671.7 s · **Steps:** 50 · **Thinking steps:** 23 · **LLM calls:** 39
- **Tool-call distribution:** run_command:13, read_file:12, write_file:5
- **Error receipts per tool:** run_command:2, write_file:1
- **Errors by error_type:** CommandError:2, FileWriteError:1
- **Patch:** 2024 B, 2 file(s), 2 hunk(s); source: none; scratch: repro_wrap.py, test_len.py; tests: none; submit: no (0)
- **Test:** 114 passed
- **Cause (1 line):** resolved with a scratch-only patch (repro_wrap.py, test_len.py); no source hunk → pre-resolved or the verdict does not rely on the source.

### 19. rich_3486 — failed — unknown — phase v2
- **Calls:** 100 (report) / 104 (trace) · **Wall:** 3027.6 s · **Steps:** 136 · **Thinking steps:** 70 · **LLM calls:** 119
- **Tool-call distribution:** read_file:47, run_command:34, write_file:15, edit_file:5, get_status:2, submit_patch:1
- **Error receipts per tool:** run_command:5, write_file:2, edit_file:1
- **Errors by error_type:** CommandError:5, FileWriteError:2, BudgetExceeded:1
- **Patch:** 8871 B, 10 file(s), 14 hunk(s); source: rich/traceback.py; scratch: inspect_attrs.py, inspect_pep657.py, inspect_pep657_v2.py, repro.py, repro_pep657.py, test_format.py, test_order.py, test_te_explicit.py, test_te_init.py; tests: none; submit: yes (1)
- **Test:** 20 passed, 1 skipped
- **Cause (1 line):** submits a 10-file patch (traceback.py + 9 scratch); green suite (20 passed) but the required node test_traceback_finely_grained_missing does not pass → harness 'unknown'.

### 20. rich_3777 — failed — test_failure — phase v2
- **Calls:** 41 (report) / 42 (trace) · **Wall:** 478.4 s · **Steps:** 66 · **Thinking steps:** 31 · **LLM calls:** 53
- **Tool-call distribution:** run_command:23, read_file:13, write_file:3, edit_file:2, submit_patch:1
- **Error receipts per tool:** run_command:6, write_file:1
- **Errors by error_type:** CommandError:6, FileWriteError:1
- **Patch:** 976 B, 1 file(s), 1 hunk(s); source: rich/console.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 98 passed, 1 failed
- **Cause (1 line):** edits rich/console.py; test_input_password still fails (AttributeError getpass): console baseline node.

### 21. rich_3468 — failed — test_failure — phase v2
- **Calls:** 27 (report) / 28 (trace) · **Wall:** 569.4 s · **Steps:** 43 · **Thinking steps:** 23 · **LLM calls:** 35
- **Tool-call distribution:** read_file:13, run_command:10, write_file:2, edit_file:2, submit_patch:1
- **Error receipts per tool:** run_command:4, write_file:1, edit_file:1
- **Errors by error_type:** CommandError:4, FileWriteError:1, FileEditError:1
- **Patch:** 7327 B, 2 file(s), 2 hunk(s); source: rich/console.py; scratch: repro_broken_pipe.py; tests: none; submit: yes (1)
- **Test:** 94 passed, 4 failed
- **Cause (1 line):** edits rich/console.py; 4 console nodes fail identically to other tasks (size fallback, capture, input_password, no_nested_live).

### 22. rich_3782 — failed — collection_error — phase v3a
- **Calls:** 35 (report) / 36 (trace) · **Wall:** 972.9 s · **Steps:** 49 · **Thinking steps:** 25 · **LLM calls:** 42
- **Tool-call distribution:** read_file:16, run_command:12, write_file:4, edit_file:3, submit_patch:1
- **Error receipts per tool:** write_file:2, run_command:1
- **Errors by error_type:** FileWriteError:2, CommandError:1
- **Patch:** 1103 B, 1 file(s), 1 hunk(s); source: rich/syntax.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 1 error
- **Cause (1 line):** edits rich/syntax.py; collection_error: ImportError 'Console' from site-packages rich.syntax (import baseline).

### 23. rich_3772 — resolved — — — phase v3a
- **Calls:** 45 (report) / 46 (trace) · **Wall:** 1143.3 s · **Steps:** 56 · **Thinking steps:** 31 · **LLM calls:** 50
- **Tool-call distribution:** read_file:25, run_command:13, write_file:6, edit_file:1, submit_patch:1
- **Error receipts per tool:** write_file:3, run_command:3
- **Errors by error_type:** FileWriteError:3, CommandError:3
- **Patch:** 3084 B, 2 file(s), 2 hunk(s); source: rich/traceback.py; scratch: repro.py; tests: none; submit: yes (1)
- **Test:** 22 passed, 1 skipped
- **Cause (1 line):** resolved; source rich/traceback.py (2 hunk(s)); target tests green (22 passed, 1 skipped).

### 24. rich_3296 — failed — collection_error — phase v3a
- **Calls:** 100 (report) / 106 (trace) · **Wall:** 3295.7 s · **Steps:** 135 · **Thinking steps:** 66 · **LLM calls:** 119
- **Tool-call distribution:** read_file:50, run_command:32, write_file:13, edit_file:8, get_status:2, submit_patch:1
- **Error receipts per tool:** run_command:8, write_file:4, edit_file:3
- **Errors by error_type:** CommandError:8, FileWriteError:4, BudgetExceeded:2, ParamError:1
- **Patch:** 1957 B, 3 file(s), 3 hunk(s); source: rich/syntax.py; scratch: repro.py, repro_theme.py; tests: none; submit: yes (1)
- **Test:** 1 error
- **Cause (1 line):** edits rich/syntax.py + 2 scratch; same collection_error ImportError 'Console'.

### 25. rich_3675 — failed — test_failure — phase v3a
- **Calls:** 23 (report) / 24 (trace) · **Wall:** 289.6 s · **Steps:** 31 · **Thinking steps:** 17 · **LLM calls:** 27
- **Tool-call distribution:** run_command:16, read_file:4, write_file:2, edit_file:1, submit_patch:1
- **Error receipts per tool:** run_command:4, write_file:1
- **Errors by error_type:** CommandError:4, FileWriteError:1
- **Patch:** 723 B, 1 file(s), 1 hunk(s); source: rich/console.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 97 passed, 2 failed
- **Cause (1 line):** edits rich/console.py; test_input_password + test_no_nested_live still fail (baseline cluster).

### 26. rich_3676 — resolved — — — phase v3a
- **Calls:** 51 (report) / 52 (trace) · **Wall:** 1572.2 s · **Steps:** 68 · **Thinking steps:** 42 · **LLM calls:** 59
- **Tool-call distribution:** run_command:22, edit_file:14, read_file:8, write_file:7, submit_patch:1
- **Error receipts per tool:** run_command:5, edit_file:4, write_file:2
- **Errors by error_type:** CommandError:5, FileEditError:4, FileWriteError:2
- **Patch:** 4907 B, 1 file(s), 7 hunk(s); source: rich/traceback.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 21 passed, 1 skipped
- **Cause (1 line):** resolved; source rich/traceback.py (7 hunk(s)); target tests green (21 passed, 1 skipped).

### 27. rich_3518 — resolved — — — phase v3a
- **Calls:** 16 (report) / 37 (trace) · **Wall:** 392.2 s · **Steps:** 42 · **Thinking steps:** 24 · **LLM calls:** 39
- **Tool-call distribution:** edit_file:20, run_command:10, read_file:4, write_file:2, submit_patch:1
- **Error receipts per tool:** edit_file:20, write_file:1
- **Errors by error_type:** ParamError:20, FileWriteError:1
- **Patch:** 529 B, 1 file(s), 1 hunk(s); source: rich/table.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 20 passed
- **Cause (1 line):** resolved; source rich/table.py (1 hunk(s)); target tests green (20 passed).

### 28. rich_3535 — resolved — — — phase v3a
- **Calls:** 59 (report) / 60 (trace) · **Wall:** 1270.7 s · **Steps:** 101 · **Thinking steps:** 35 · **LLM calls:** 80
- **Tool-call distribution:** run_command:35, edit_file:13, read_file:8, write_file:3, submit_patch:1
- **Error receipts per tool:** edit_file:13, run_command:6, read_file:1, write_file:1
- **Errors by error_type:** FileEditError:13, CommandError:6, FileReadError:1, FileWriteError:1
- **Patch:** 465 B, 1 file(s), 1 hunk(s); source: rich/cells.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 8 passed
- **Cause (1 line):** resolved; source rich/cells.py (1 hunk(s)); target tests green (8 passed).

### 29. rich_3521 — resolved — — — phase v3a
- **Calls:** 33 (report) / 41 (trace) · **Wall:** 1356.8 s · **Steps:** 53 · **Thinking steps:** 27 · **LLM calls:** 46
- **Tool-call distribution:** run_command:14, read_file:12, edit_file:9, write_file:5, submit_patch:1
- **Error receipts per tool:** edit_file:7, write_file:1, run_command:1
- **Errors by error_type:** ParamError:7, FileWriteError:1, CommandError:1
- **Patch:** 4663 B, 4 file(s), 5 hunk(s); source: rich/segment.py; scratch: repro.py, repro_dw.py, repro_zw.py; tests: none; submit: yes (1)
- **Test:** 59 passed
- **Cause (1 line):** resolved; source rich/segment.py (5 hunk(s)); target tests green (59 passed).

### 30. rich_3506 — resolved — — — phase v3a
- **Calls:** 72 (report) / 72 (trace) · **Wall:** 3628.5 s · **Steps:** 111 · **Thinking steps:** 52 · **LLM calls:** 89
- **Tool-call distribution:** run_command:29, read_file:27, write_file:13, edit_file:3
- **Error receipts per tool:** write_file:3, edit_file:1
- **Errors by error_type:** FileWriteError:3, FileEditError:1
- **Patch:** 6565 B, 7 file(s), 8 hunk(s); source: rich/segment.py; scratch: repro.py, repro_bug.py, repro_control.py, repro_debug.py, repro_final.py, repro_inspect.py; tests: none; submit: no (0)
- **Test:** 52 passed
- **Cause (1 line):** resolved; source rich/segment.py (8 hunk(s)); target tests green (52 passed).

### 31. rich_3480 — resolved — — — phase v3a
- **Calls:** 20 (report) / 21 (trace) · **Wall:** 772.6 s · **Steps:** 30 · **Thinking steps:** 15 · **LLM calls:** 25
- **Tool-call distribution:** run_command:8, read_file:7, write_file:4, edit_file:1, submit_patch:1
- **Error receipts per tool:** write_file:1, run_command:1
- **Errors by error_type:** FileWriteError:1, TimeoutExceeded:1
- **Patch:** 875 B, 1 file(s), 2 hunk(s); source: rich/text.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 109 passed
- **Cause (1 line):** resolved; source rich/text.py (2 hunk(s)); target tests green (109 passed).

### 32. rich_3472 — failed — test_failure — phase v3a
- **Calls:** 100 (report) / 100 (trace) · **Wall:** 3629.0 s · **Steps:** 146 · **Thinking steps:** 84 · **LLM calls:** 121
- **Tool-call distribution:** read_file:57, run_command:41, write_file:2
- **Error receipts per tool:** run_command:3, write_file:1
- **Errors by error_type:** CommandError:3, FileWriteError:1
- **Patch:** 455 B, 1 file(s), 1 hunk(s); source: none; scratch: repro_console.py; tests: none; submit: no (0)
- **Test:** 50 passed, 1 failed, 1 skipped
- **Cause (1 line):** timeout; scratch-only patch (repro_console.py); test_attrs_broken_310 (pretty) still fails.

### 33. rich_3454 — failed — test_failure — phase v3
- **Calls:** 68 (report) / 138 (trace) · **Wall:** 3627.8 s · **Steps:** 166 · **Thinking steps:** 108 · **LLM calls:** 152
- **Tool-call distribution:** edit_file:74, read_file:31, run_command:20, write_file:13
- **Error receipts per tool:** edit_file:72, write_file:4, run_command:2
- **Errors by error_type:** ParamError:70, FileWriteError:4, CommandError:2, FileEditError:2
- **Patch:** 3591 B, 5 file(s), 5 hunk(s); source: rich/highlighter.py; scratch: check_span.py, repro_bug.py, reproduce_issue.py; tests: tests/test_highlighter.py; submit: no (0)
- **Test:** 83 passed, 1 failed
- **Cause (1 line):** timeout after 108 thinking steps; edits highlighter.py and also tests/test_highlighter.py; off-by-one Span(1,25) vs Span(1,24).

### 34. rich_3471 — resolved — — — phase v3
- **Calls:** 26 (report) / 26 (trace) · **Wall:** 698.1 s · **Steps:** 47 · **Thinking steps:** 24 · **LLM calls:** 36
- **Tool-call distribution:** read_file:12, run_command:11, write_file:3
- **Error receipts per tool:** write_file:1, run_command:1
- **Errors by error_type:** FileWriteError:1, CommandError:1
- **Patch:** 1806 B, 1 file(s), 1 hunk(s); source: none; scratch: repro_append_tokens.py; tests: none; submit: no (0)
- **Test:** 108 passed
- **Cause (1 line):** resolved with a scratch-only patch (repro_append_tokens.py); no source hunk → pre-resolved or the verdict does not rely on the source.

### 35. rich_3470 — failed — test_failure — phase v3
- **Calls:** 62 (report) / 127 (trace) · **Wall:** 3627.5 s · **Steps:** 149 · **Thinking steps:** 101 · **LLM calls:** 137
- **Tool-call distribution:** edit_file:67, read_file:33, run_command:23, write_file:4
- **Error receipts per tool:** edit_file:65, run_command:4, write_file:2
- **Errors by error_type:** ParamError:65, CommandError:4, FileWriteError:2
- **Patch:** 1463 B, 2 file(s), 2 hunk(s); source: rich/console.py; scratch: repro.py; tests: none; submit: no (0)
- **Test:** 95 passed, 3 failed
- **Cause (1 line):** timeout; 67 edit_file (65 ParamError); edits console.py; 3 console baseline nodes still fail.

### 36. rich_3469 — failed — test_failure — phase v3
- **Calls:** 100 (report) / 105 (trace) · **Wall:** 1996.8 s · **Steps:** 125 · **Thinking steps:** 86 · **LLM calls:** 112
- **Tool-call distribution:** read_file:40, run_command:35, search_similar_code:19, code_analyzer_agent:4, get_code_neighbors:4, write_file:3
- **Error receipts per tool:** run_command:4, write_file:2, search_similar_code:1
- **Errors by error_type:** CommandError:4, FileWriteError:2, BudgetExceeded:1
- **Patch:** 736 B, 1 file(s), 1 hunk(s); source: none; scratch: repro.py; tests: none; submit: no (0)
- **Test:** 1 passed, 6 failed
- **Cause (1 line):** exhausts 100 calls; scratch-only patch (repro.py); 6 test_markdown nodes fail.

### 37. rich_3052 — resolved — — — phase v3
- **Calls:** 24 (report) / 25 (trace) · **Wall:** 487.2 s · **Steps:** 37 · **Thinking steps:** 18 · **LLM calls:** 30
- **Tool-call distribution:** read_file:8, run_command:7, edit_file:7, write_file:2, submit_patch:1
- **Error receipts per tool:** write_file:1
- **Errors by error_type:** FileWriteError:1
- **Patch:** 3391 B, 1 file(s), 9 hunk(s); source: rich/prompt.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 7 passed
- **Cause (1 line):** resolved; source rich/prompt.py (9 hunk(s)); target tests green (7 passed).

### 38. rich_3278 — failed — test_failure — phase v3
- **Calls:** 99 (report) / 100 (trace) · **Wall:** 3626.9 s · **Steps:** 188 · **Thinking steps:** 81 · **LLM calls:** 140
- **Tool-call distribution:** run_command:42, write_file:21, read_file:19, edit_file:12, search_similar_code:5, code_analyzer_agent:1
- **Error receipts per tool:** edit_file:12, run_command:9, write_file:3
- **Errors by error_type:** FileEditError:12, CommandError:9, FileWriteError:3
- **Patch:** 6060 B, 16 file(s), 16 hunk(s); source: none; scratch: fix_ansi.py, repro.py, test_debug.py, test_debug2.py, test_debug3.py, test_debug4.py, test_debug5.py, test_debug6.py, test_debug7.py, test_esc.py, test_esc2.py, test_esc3.py, test_esc4.py, test_final.py, test_regex.py, test_simple.py; tests: none; submit: no (0)
- **Test:** 20 passed, 3 failed
- **Cause (1 line):** timeout; scratch-only patch (16 scratch, 14 of them test_*.py); 3 test_ansi decode nodes fail.

### 39. rich_2943 — failed — unknown (null in report.json) — phase v3
- **Calls:** 8 (report) / 8 (trace) · **Wall:** 190.8 s · **Steps:** 17 · **Thinking steps:** 8 · **LLM calls:** 12
- **Tool-call distribution:** read_file:5, run_command:3
- **Error receipts per tool:** none
- **Errors by error_type:** none
- **Patch:** no patch (not captured)
- **Test:** no test_output.log
- **Cause (1 line):** never calls submit_patch; 8 calls / 191 s; closes in 'final' after read/run without editing.

### 40. rich_2725 — resolved — — — phase v3
- **Calls:** 13 (report) / 14 (trace) · **Wall:** 187.3 s · **Steps:** 18 · **Thinking steps:** 9 · **LLM calls:** 15
- **Tool-call distribution:** run_command:7, read_file:3, write_file:2, edit_file:1, submit_patch:1
- **Error receipts per tool:** write_file:1, run_command:1
- **Errors by error_type:** FileWriteError:1, CommandError:1
- **Patch:** 1099 B, 1 file(s), 1 hunk(s); source: rich/table.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 19 passed
- **Cause (1 line):** resolved; source rich/table.py (1 hunk(s)); target tests green (19 passed).

### 41. rich_3105 — failed — test_failure — phase v3
- **Calls:** 100 (report) / 107 (trace) · **Wall:** 2261.3 s · **Steps:** 155 · **Thinking steps:** 93 · **LLM calls:** 127
- **Tool-call distribution:** run_command:53, search_similar_code:24, read_file:21, code_analyzer_agent:4, write_file:2, get_code_neighbors:1, edit_file:1, submit_patch:1
- **Error receipts per tool:** run_command:11, write_file:1, edit_file:1
- **Errors by error_type:** CommandError:10, BudgetExceeded:2, FileWriteError:1
- **Patch:** 538 B, 1 file(s), 1 hunk(s); source: none; scratch: repro.py; tests: none; submit: yes (1)
- **Test:** 92 passed, 4 failed
- **Cause (1 line):** submits a scratch-only patch (repro.py) with 100 calls; 4 console baseline nodes fail; no source change.

### 42. rich_3130 — failed — test_failure — phase v3
- **Calls:** 89 (report) / 117 (trace) · **Wall:** 3587.0 s · **Steps:** 157 · **Thinking steps:** 81 · **LLM calls:** 135
- **Tool-call distribution:** read_file:37, run_command:36, edit_file:28, write_file:15, submit_patch:1
- **Error receipts per tool:** edit_file:27, run_command:6, write_file:5
- **Errors by error_type:** ParamError:27, CommandError:6, FileWriteError:5
- **Patch:** 4511 B, 4 file(s), 5 hunk(s); source: rich/markdown.py; scratch: fix_markdown.py, repro.py, reproduce_issue.py; tests: none; submit: yes (1)
- **Test:** 6 failed
- **Cause (1 line):** edits rich/markdown.py; 6 test_markdown nodes fail (same cluster as 3064/3469).

### 43. rich_3043 — failed — test_failure — phase v3
- **Calls:** 92 (report) / 92 (trace) · **Wall:** 3627.7 s · **Steps:** 124 · **Thinking steps:** 67 · **LLM calls:** 107
- **Tool-call distribution:** run_command:41, read_file:34, write_file:11, edit_file:6
- **Error receipts per tool:** run_command:14, edit_file:5, write_file:3
- **Errors by error_type:** CommandError:14, FileEditError:5, FileWriteError:3
- **Patch:** 2620 B, 5 file(s), 6 hunk(s); source: rich/_export_format.py; scratch: output.txt, repro.py, repro_check.py, reproduce_issue.py; tests: none; submit: no (0)
- **Test:** 89 passed, 7 failed
- **Cause (1 line):** timeout; edits rich/_export_format.py; 7 failures incl. console baseline + export_html nodes.

### 44. rich_3067 — resolved — — — phase v3
- **Calls:** 24 (report) / 40 (trace) · **Wall:** 723.6 s · **Steps:** 46 · **Thinking steps:** 27 · **LLM calls:** 42
- **Tool-call distribution:** edit_file:15, run_command:14, write_file:6, read_file:4, submit_patch:1
- **Error receipts per tool:** edit_file:15, run_command:4, write_file:1
- **Errors by error_type:** ParamError:15, CommandError:4, FileWriteError:1
- **Patch:** 655 B, 1 file(s), 1 hunk(s); source: rich/highlighter.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 82 passed
- **Cause (1 line):** resolved; source rich/highlighter.py (1 hunk(s)); target tests green (82 passed).

### 45. rich_3006 — resolved — — — phase v3
- **Calls:** 16 (report) / 17 (trace) · **Wall:** 268.8 s · **Steps:** 29 · **Thinking steps:** 15 · **LLM calls:** 22
- **Tool-call distribution:** run_command:12, write_file:2, read_file:1, edit_file:1, submit_patch:1
- **Error receipts per tool:** run_command:3, write_file:1
- **Errors by error_type:** CommandError:3, FileWriteError:1
- **Patch:** 558 B, 1 file(s), 1 hunk(s); source: rich/repr.py; scratch: none; tests: none; submit: yes (1)
- **Test:** 8 passed
- **Cause (1 line):** resolved; source rich/repr.py (1 hunk(s)); target tests green (8 passed).

### 46. rich_3064 — failed — test_failure — phase v3
- **Calls:** 100 (report) / 104 (trace) · **Wall:** 2645.3 s · **Steps:** 116 · **Thinking steps:** 61 · **LLM calls:** 107
- **Tool-call distribution:** run_command:42, read_file:38, write_file:13, search_similar_code:5, edit_file:4, code_analyzer_agent:1, get_status:1
- **Error receipts per tool:** run_command:15, write_file:3, read_file:2
- **Errors by error_type:** CommandError:15, FileWriteError:3, BudgetExceeded:2
- **Patch:** 8139 B, 4 file(s), 6 hunk(s); source: rich/markdown.py; scratch: repro_issue.py, repro_markdown_table.py, repro_table.py; tests: none; submit: no (0)
- **Test:** 4 failed
- **Cause (1 line):** exhausts 100 calls; edits rich/markdown.py; 4 test_markdown nodes fail.

### 47. rich_3063 — resolved — — — phase v3
- **Calls:** 28 (report) / 29 (trace) · **Wall:** 866.5 s · **Steps:** 46 · **Thinking steps:** 20 · **LLM calls:** 37
- **Tool-call distribution:** run_command:11, write_file:9, read_file:6, edit_file:2, submit_patch:1
- **Error receipts per tool:** run_command:2, write_file:1
- **Errors by error_type:** CommandError:2, FileWriteError:1
- **Patch:** 1482 B, 2 file(s), 2 hunk(s); source: rich/markup.py; scratch: repro.py; tests: none; submit: yes (1)
- **Test:** 21 passed
- **Cause (1 line):** resolved; source rich/markup.py (2 hunk(s)); target tests green (21 passed).

### 48. rich_3061 — resolved — — — phase v3
- **Calls:** 38 (report) / 39 (trace) · **Wall:** 554.6 s · **Steps:** 44 · **Thinking steps:** 37 · **LLM calls:** 41
- **Tool-call distribution:** run_command:23, write_file:9, read_file:5, edit_file:1, submit_patch:1
- **Error receipts per tool:** run_command:14, write_file:1
- **Errors by error_type:** CommandError:14, FileWriteError:1
- **Patch:** 4239 B, 2 file(s), 3 hunk(s); source: rich/text.py; scratch: repro_tabs.py; tests: none; submit: yes (1)
- **Test:** 112 passed
- **Cause (1 line):** resolved; source rich/text.py (3 hunk(s)); target tests green (112 passed).

---

## 3. Aggregate comparison table

Cell format: **mean / median / min–max**. `resolved` (29) vs `failed` (19), and `source fix`
(26 = resolutions that touch `rich/*.py`) vs `other` (22). Error ratios = errors of that tool / calls to that tool, per task.

| Metric | resolved (29) | failed (19) | source fix (26) | other (22) |
|---|---|---|---|---|
| tool_calls (report) | 36.7 / 30.0 / 13-100 | 75.2 / 92.0 / 8-100 | 37.4 / 30.0 / 13-100 | 69.1 / 90.5 / 8-100 |
| wall_seconds | 1039.5 / 829.4 / 187.3-3628.5 | 2421.3 / 2645.3 / 190.8-3629.0 | 1031.3 / 801.0 / 187.3-3628.5 | 2242.6 / 2464.6 / 190.8-3629.0 |
| thinking steps | 29.6 / 24.0 / 9-84 | 63.3 / 70.0 / 8-108 | 30.1 / 25.5 / 9-84 | 58.1 / 66.5 / 8-108 |
| run_command count | 17.0 / 14.0 / 6-42 | 31.9 / 35.0 / 3-57 | 17.3 / 14.0 / 6-42 | 29.5 / 33.0 / 3-57 |
| run_command error ratio | 0.2 / 0.1 / 0-0.6 | 0.2 / 0.2 / 0-0.4 | 0.2 / 0.1 / 0-0.6 | 0.2 / 0.2 / 0-0.4 |
| edit_file count | 7.7 / 3.0 / 0-59 | 11.8 / 3.0 / 0-74 | 8.5 / 4.0 / 1-59 | 10.3 / 2.5 / 0-74 |
| edit_file error ratio | 0.4 / 0.3 / 0-1 | 0.5 / 0.4 / 0-1 | 0.4 / 0.3 / 0-1 | 0.4 / 0.3 / 0-1 |
| write_file errors | 1.4 / 1.0 / 1-3 | 2.0 / 2.0 / 0-5 | 1.5 / 1.0 / 1-3 | 1.9 / 1.5 / 0-5 |
| read_file count | 10.8 / 8.0 / 1-40 | 30.3 / 34.0 / 4-57 | 10.5 / 7.5 / 1-40 | 27.9 / 32.0 / 4-57 |
| submit_patch calls | 0.9 / 1.0 / 0-1 | 0.5 / 1.0 / 0-1 | 1.0 / 1.0 / 0-1 | 0.5 / 0.0 / 0-1 |
| patch size (B) | 2383.0 / 1771.0 / 393-7139 | 3347.4 / 1957.0 / 455-8871 | 2485.8 / 1626.5 / 393-7139 | 3069.2 / 1881.5 / 455-8871 |
| files changed | 1.9 / 1.0 / 1-7 | 3.6 / 2.0 / 1-16 | 2.0 / 1.0 / 1-7 | 3.2 / 2.0 / 1-16 |
| hunks | 3.2 / 2.0 / 1-9 | 4.4 / 2.0 / 1-16 | 3.4 / 2.0 / 1-9 | 4.0 / 2.0 / 1-16 |
| scratch files in the patch | 1.0 / 0.0 / 0-6 | 2.7 / 1.0 / 0-16 | 0.9 / 0.0 / 0-6 | 2.5 / 1.0 / 0-16 |
| tests modified (task count) | 0 | 1 | 0 | 1 |

Raw totals: `run_command` 868 ok / 231 error / 1 099; `edit_file` 95 / 353 / 448;
`write_file` 213 / 79 / 292; `read_file` 882 / 6 / 888; `search_similar_code` 57 / 1 / 58.

Resolution rates (census, no inference):

- Raw harness rate: **29/48 = 0.6042** (`summary.json`).
- With at least one hunk in `rich/*.py`: **26/48 = 0.5417** (26 resolutions + 13 failures touch source).
- Resolutions with a scratch-only patch (no source): **3/48** (`rich_3180`, `rich_3471`, `rich_3938`).
- Any patch with a source hunk, resolved or not: **39/48 = 0.8125**.
- Patches with scratch: **26/46 = 0.5652**; patches that touch `tests/`: **1/46** (`rich_3454`).

---

## 4. Similarities between successes and failures

- **Same tool repertoire.** Both classes use `run_command`, `read_file`, `write_file`,
  `edit_file` and `submit_patch`. `get_status` appears only in failures (3064, 3296, 3486) and `code_analyzer_agent`
  in 1 resolution (4075) and 4 failures (3469, 3278, 3105, 3064).
- **Same opening.** First action `run_command` in **44/48** (26 resolutions, 18 failures);
  the opening pair `run_command > read_file` is the most common in both (16/29 resolutions and 14/19 failures).
- **Same error types present in both classes:** `CommandError`, `FileWriteError`, `ParamError`,
  `FileEditError`, `FileReadError` and `BudgetExceeded`. No `error_type` is exclusive to one class.
- **Same harness envelope.** The 48 tasks receive 1 `system_instruction` + 1 `task_prompt` and the same
  `continuation_nudge` cycle; the nudges are 2 fixed strings. The receipts are a closed catalogue.
- **Same patch structure.** In both classes the typical patch touches 1 source file; 37/48 tasks
  have a single file in the gold patch and the median agent patch touches 1 file.

---

## 5. Differences between successes and failures

All per-task figures are in §3. The largest contrasts:

- **Budget/time:** median calls 30 vs 92; median wall 829 s vs 2 645 s; median thinking steps 24 vs 70;
  median `read_file` 8 vs 34. The failure is a ~2× longer session.
- **Process vs capability (per `error`):** 9/19 failures are **process** (6 timeouts: 3043, 3278, 3454, 3470, 3472, 3942;
  2 exhaustion of 100 calls: 3064, 3469; 1 without `submit_patch`: 2943) and 10/19 are **capability** (they submit a patch and it does not pass).
- **Hygiene:** scratch in the patch: 26/46; the median number of scratch files per patch is 0 in resolutions and 1 in failures;
  the only patch that modifies a test is a failure (`rich_3454`).

### 5.1 By failure_kind

| kind | n | ids | tool_calls (m/m/ra) | wall s (m/m/ra) | touches source |
|---|---:|---|---|---|---:|
| test_failure | 14 | rich_4070, rich_4079, rich_3777, rich_3468, rich_3675, rich_3472, rich_3454, rich_3470, rich_3469, rich_3278, rich_3105, rich_3130, rich_3043, rich_3064 | 78.1 / 92.0 / 23-100 | 2492.6 / 2585.2 / 289.6-3629.0 | 10/14 |
| collection_error | 2 | rich_3782, rich_3296 | 67.5 / 67.5 / 35-100 | 2134.3 / 2134.3 / 972.9-3295.7 | 2/2 |
| unknown | 1 | rich_3486 | 100.0 / 100.0 / 100-100 | 3027.6 / 3027.6 / 3027.6-3027.6 | 1/1 |
| null/unknown-in-STATUS | 2 | rich_3942, rich_2943 | 50.5 / 50.5 / 8-93 | 1906.6 / 1906.6 / 190.8-3622.5 | 0/2 |

### 5.2 By task family (primary file of the gold patch)

| family (gold) | resolved/total | failures |
|---|---:|---|
| console | 2/6 | rich_3777, rich_3468, rich_3675, rich_3470 |
| markdown | 0/4 | rich_4079, rich_3469, rich_3130, rich_3064 |
| cells | 4/4 | — |
| default_styles | 1/3 | rich_3942, rich_3486 |
| table | 3/3 | — |
| text | 3/3 | — |
| ansi | 1/2 | rich_3278 |
| prompt | 2/2 | — |
| syntax | 0/2 | rich_3782, rich_3296 |
| segment | 2/2 | — |
| highlighter | 1/2 | rich_3454 |
| _export_format | 0/2 | rich_3105, rich_3043 |
| _emoji_replace | 0/1 | rich_4070 |
| file_proxy | 1/1 | — |
| panel | 1/1 | — |
| live | 1/1 | — |
| _inspect | 1/1 | — |
| progress | 1/1 | — |
| __main__ | 1/1 | — |
| _wrap | 1/1 | — |
| traceback | 1/1 | — |
| pretty | 0/1 | rich_3472 |
| style | 0/1 | rich_2943 |
| repr | 1/1 | — |
| markup | 1/1 | — |

### 5.3 By prompt phase

| phase | n | resolved | rate | tool_calls (m/m) | wall s (m/m/ra) | thinking (m/m/ra) | failure kinds |
|---|---:|---:|---:|---|---|---|---|
| v2 | 21 | 15 | 0.714 | 50.1 / 38.0 | 1373.9 / 962.8 / 193.9-3622.5 | 38.5 / 29.0 / 9-84 | test_failure=4, unknown(null)=1, unknown=1 |
| v3a | 11 | 7 | 0.636 | 50.4 / 45.0 | 1665.8 / 1270.7 / 289.6-3629.0 | 38.0 / 31.0 / 15-84 | collection_error=2, test_failure=2 |
| v3 | 16 | 7 | 0.438 | 55.4 / 50.0 | 1811.1 / 1431.6 / 187.3-3627.8 | 52.2 / 49.0 / 8-108 | test_failure=8, unknown(null)=1 |

### 5.4 By estimated complexity (gold patch size)

Proxy: `len(patch)` in `data/raw/tasks.jsonl` (gold). Counts only; it does not imply intrinsic difficulty.

| gold bytes | n | resolved | failure ids |
|---|---:|---:|---|
| < 1 000 | 23 | 12 | rich_4079, rich_3296, rich_3472, rich_3454, rich_3470, rich_3469, rich_3278, rich_2943, rich_3105, rich_3043, rich_3064 |
| 1 000–4 999 | 19 | 13 | rich_3942, rich_3777, rich_3468, rich_3782, rich_3675, rich_3130 |
| >= 5 000 | 6 | 4 | rich_4070, rich_3486 |

### 5.5 Cause vs consequence (what this run cannot separate)

- **Consequences of failing** (the failure lengthens the session and makes it messy): high calls, high wall, high thinking,
  accumulated scratch, `BudgetExceeded`, extra `read_file`. In the 6 timeouts, wall ≈ 3 625–3 629 s with 62–99 calls.
- **Cause candidates** (they appear before the verdict): patch that does not touch the failing file
  (`rich_4070`, 3105, 3278, 3469, 3472), insufficient fix (`rich_4079`, 3130, 3064, 3469), baseline node
  unrelated to the patch (`rich_3468`, 3105, 3470; collection_error 3296/3782), and no-submit (`rich_2943`).
- **Not separable with these data:** (a) effect of the prompt phase vs difficulty of the later tasks
  (version ⇔ temporal order, without repetition); (b) effect of skill compaction and the sub-agent, collinear with v3;
  (c) how much of the `test_failure` is broken baseline and how much is a real fix; (d) causality of any difference, due to lack of randomization.

---

## 6. Fine cross-checks: trajectories

First 5 and last 5 actions (tool names):

| task | first 5 | last 5 |
|---|---|---|
| rich_4070 (fail) | run_command > read_file > read_file > read_file > read_file | write_file > write_file > run_command > run_command > submit_patch |
| rich_4079 (fail) | run_command > read_file > run_command > run_command > run_command | write_file > run_command > run_command > run_command > submit_patch |
| rich_3942 (fail) | run_command > read_file > run_command > read_file > read_file | read_file > run_command > run_command > run_command > run_command |
| rich_3486 (fail) | run_command > read_file > run_command > read_file > run_command | read_file > edit_file > get_status > get_status > submit_patch |
| rich_3777 (fail) | run_command > read_file > run_command > read_file > run_command | run_command > run_command > run_command > run_command > submit_patch |
| rich_3468 (fail) | run_command > read_file > run_command > run_command > run_command | run_command > run_command > read_file > run_command > submit_patch |
| rich_3782 (fail) | run_command > run_command > read_file > read_file > read_file | edit_file > run_command > run_command > run_command > submit_patch |
| rich_3296 (fail) | run_command > read_file > run_command > read_file > read_file | edit_file > edit_file > get_status > get_status > submit_patch |
| rich_3675 (fail) | run_command > read_file > run_command > run_command > read_file | run_command > run_command > run_command > run_command > submit_patch |
| rich_3472 (fail) | run_command > run_command > read_file > read_file > run_command | run_command > read_file > read_file > read_file > read_file |
| rich_3454 (fail) | run_command > read_file > write_file > write_file > run_command | run_command > read_file > read_file > write_file > run_command |
| rich_3470 (fail) | run_command > read_file > run_command > run_command > run_command | edit_file > edit_file > edit_file > edit_file > edit_file |
| rich_3469 (fail) | code_analyzer_agent > search_similar_code > search_similar_code > get_code_neighbors > get_code_neighbors | code_analyzer_agent > read_file > read_file > search_similar_code > search_similar_code |
| rich_3278 (fail) | run_command > code_analyzer_agent > search_similar_code > search_similar_code > search_similar_code | read_file > run_command > run_command > run_command > run_command |
| rich_2943 (fail) | run_command > read_file > run_command > read_file > run_command | read_file > run_command > read_file > read_file > read_file |
| rich_3105 (fail) | run_command > run_command > run_command > run_command > run_command | run_command > read_file > run_command > edit_file > submit_patch |
| rich_3130 (fail) | run_command > read_file > run_command > read_file > write_file | run_command > read_file > edit_file > run_command > submit_patch |
| rich_3043 (fail) | run_command > read_file > run_command > read_file > read_file | read_file > run_command > read_file > run_command > read_file |
| rich_3064 (fail) | run_command > read_file > run_command > read_file > write_file | run_command > run_command > get_status > read_file > read_file |
| rich_4077 (res) | run_command > read_file > read_file > read_file > read_file | run_command > run_command > submit_patch > run_command > run_command |
| rich_2725 (res) | write_file > write_file > run_command > run_command > read_file | run_command > run_command > run_command > run_command > submit_patch |
| rich_3052 (res) | run_command > read_file > read_file > read_file > write_file | read_file > read_file > run_command > run_command > submit_patch |
| rich_3676 (res) | run_command > read_file > read_file > read_file > read_file | run_command > run_command > run_command > run_command > submit_patch |
| rich_3006 (res) | run_command > run_command > run_command > run_command > run_command | run_command > run_command > run_command > run_command > submit_patch |

**Divergence point.** The opening is almost identical: `run_command > read_file...`. The divergence is not
in the first actions but in the closing and in the repetition of edits:

- Position of the first write (`write_file`): median 8 (res) vs 12 (fail).
- Position of the first `edit_file`: median 15 (res) vs 16 (fail) — **almost equal**.
- Position of `submit_patch`: median **37** (res) vs **98** (fail). Success closes ~60 actions earlier.
- `rich_3905` (resolved) makes 59 `edit_file` and `rich_3454`/`3470` (failures) 73/67: the difference is not editing more,
  but **when it closes** and whether the target test is run.

- Tasks that ran `pytest` at least once: **26/48** (res 16, fail 10).
- Tasks that ran the gold test file: **25/48**.
- Tasks with an edit that ran `pytest` before the **first edit of a file from the gold patch**: **3/46**
  (`rich_3521`, `rich_3935`, `rich_4077`; all 3 resolved, 0 failures). With the looser definition —`pytest`
  before **any** edit— it is **1/46** (`rich_3521`). *(Corrected on 2026-10-06 after independent verification:
  the draft said 3/42 without fixing the definition and with a miscounted denominator.)*
- Tasks that edited and **never** ran `pytest`: **21/46** (13 resolved, 8 failures).
- Tasks that called `submit_patch`: 35/48; of those, ran `pytest` before submit: **21/35**.

First edit directed at a file from the gold patch: 19/27 resolutions and 12/15 failures. There is no marked
difference in *localization*; there is in *closing*.

---

## 7. Additional improvement proposals (N1-N6)

None repeats P1-P11 (`docs/proposals/20261006-prompt-hardening.md` §3). All change only text in `submission/`.
The `swegemma` harness is immutable; no line matches the gate's `FORBIDDEN_PATTERNS`
(`src/kaggle_gemma_agent/pack.py`, `re.IGNORECASE`),
adds or removes no skills (still 12) and touches neither budgets nor the base model. Texts verified against that regex.

### N1 — Run the target test BEFORE the first edit (baseline capture)

**(a) Evidence:** The agent localizes and edits without having run the test that defines the target; it edits the module suggested by the issue prose instead of the one named by the traceback. Only **3/46** tasks with an edit ran `pytest` before the first edit of a file from the gold patch (`rich_3521`, `rich_3935`, `rich_4077`; all 3 resolved) and **0 failures** did so; **21/46** edited without ever running `pytest`. `rich_4070` edited console/logging while the 6 failing nodes are in tests/test_syntax.py; `rich_4079`, `rich_3130`, `rich_3064` edited markdown without reproducing the assertion.

**(b) File:** `submission/skills/issue-localization/SKILL.md, Execution Steps (new step before the current 5)`

**(c) Literal text:**

```
5. Before editing, `run_command` the target test file (or `pytest <file>::<node>`)
   once; capture its pass/fail counts and the first failing assertion, and edit the
   module named by that traceback, not the module suggested by the issue prose.
```
(renumber the current step 5 to 6)

**(d) Token cost:** +3 lines (~39 tokens/turn)

**(e) Risk:** It consumes 1 call before editing and the target test may have a different name (a new test from `test_patch`); mitigated by "or `pytest <file>::<node>`" and by the skill's own `bounded`.

### N2 — Baseline control: do not edit code for a node in a file you did not touch

**(a) Evidence:** 4 nodes of `tests/test_console.py` fail identically in `rich_3043`, `3105`, `3468`, `3470` (`test_size_can_fall_back_to_std_descriptors`, `test_input_password`, `test_no_nested_live`, `test_capture_and_record`) and 2 of them also in `3675`/`3777`. Decisive proof: `rich_3105` submitted only `repro.py` (0 source changes) and the nodes still fail. P9 lists plugin/module/endpoint/TTY, but not this case.

**(b) File:** `submission/skills/systematic-debugging/SKILL.md, Hard Rules (final bullet)`

**(c) Literal text:**

```
- Baseline control: if a failing node lives in a file you have not edited and
  fails identically before and after your change, it is pre-existing. Record the
  node, spend at most one call on it, keep your source fix, and submit.
```

**(d) Token cost:** +3 lines (~39 tokens/turn)

**(e) Risk:** It may declare a real failure to be baseline; mitigated by "in a file you have not edited" + "identically before and after". It complements (does not replace) P9.

### N3 — Forbid scratch named `test_*.py` or `conftest.py`

**(a) Evidence:** 19 scratch files named `test_*.py` across 3 tasks: `rich_3278` (14: `test_debug*.py`, `test_esc*.py`, `test_final.py`, `test_regex.py`, `test_simple.py`), `rich_3486` (4) and `rich_3180` (1). Pytest collects them in root-level runs and they pollute the result; none was the target test.

**(b) File:** `submission/skills/patch-hygiene/SKILL.md, Hard Rules (new bullet)`

**(c) Literal text:**

```
- Never name a scratch file `test_*.py` or `conftest.py`: pytest collects them and
  they pollute later runs. Name scratch `repro_*.py` under `/tmp`.
```

**(d) Token cost:** +2 lines (~26 tokens/turn)

**(e) Risk:** Low. A different name does not change the content; it only avoids accidental collection.

### N4 — Multi-line edits via read+write_file; `edit_file` only for short anchors

**(a) Evidence:** `edit_file` is the run's worst tool: 353/448 error receipts (78.8%), of which 286 are `ParamError` (the `new_string` value contains `,old_string:` and the parameter is missing) and 63 `FileEditError`. `rich_3454` made 73 edits to the same file (70 ParamError), `rich_3470` 67 (65) and `rich_3905` 59. The `write_file` error rate is 79/292 = 27.1%. P5 covers recovery after the failure; this proposal avoids the format that produces it.

**(b) File:** `submission/prompts/system.v3.md, Hard rules (new bullet before the current `edit_file` one)`

**(c) Literal text:**

```
- For a replacement spanning several lines or containing quotes/escapes, `read_file`
  the file, apply the change, and `write_file` it back; reserve `edit_file` for a
  short unique anchor. `edit_file` arguments are exactly `filepath`, `old_string`,
  `new_string`; never put `,old_string:` inside the `new_string` value.
```

**(d) Token cost:** +4 lines (~52 tokens/turn)

**(e) Risk:** `write_file` overwrites the whole file: one mistake discards code; mitigated by "read_file the file" first and by leaving `edit_file` for short anchors.

### N5 — A single scratch file, reused

**(a) Evidence:** 26/46 patches include scratch; the count per patch reaches 16 (`rich_3278`), 9 (`rich_3486`), 6 (`rich_3506`), 4 (`rich_3935`). Each new scratch is a `write_file` that fattens the patch and the noise (P6/P3 already cover *where* to create it and *how to clean it up*; not *how many*).

**(b) File:** `submission/skills/patch-hygiene/SKILL.md, Hard Rules (new bullet)`

**(c) Literal text:**

```
- Keep exactly one scratch file (for example `/tmp/repro.py`) and overwrite it;
  do not create a new `repro_*`/`test_*` file per hypothesis.
```

**(d) Token cost:** +2 lines (~26 tokens/turn)

**(e) Risk:** A single scratch may become stale; the agent can overwrite it. It does not affect the patch because it lives outside `/workspace`.

### N6 — Cap `max_output_tokens` in sampling (low-confidence proposal)

**(a) Evidence:** 3 268 LLM calls generated 1 004 741 completion tokens (~307/call); failures consume 26 228 completion tokens/task vs 17 463 for resolutions, and `rich_3454` reached 108 thinking steps. The `max_output_tokens` field (currently 16 384) is a lever distinct from `thinking_budget` (P2, already at 2 048) and is within the allowed range.

**(b) File:** `submission/configs/sampling.yaml`

**(c) Literal text:**

```diff
-max_output_tokens: 16384
+max_output_tokens: 8192
```

**(d) Token cost:** 0 lines (value change); risk of more T3b nudges (token cutoff, currently 25 in 14 tasks)

**(e) Risk:** The harness already nudges token cutoffs; lowering the cap may truncate legitimate turns and trigger retries. **Weak evidence**: there is no task with a single runaway; recommend only as a batch trial.

### Ideas evaluated and discarded for overlap or illegality

- **A/B or statistical validation** — does not apply: confounded phases, no randomization or repetition (not proposed).
- **Touching harness nudges/receipts/envelope** — illegal: the harness is immutable.
- **Adding/removing skills or changing budgets/model** — forbidden by the gate (12 skills; 100/60/500; single model).
- **Editing `submission/` with network/install commands in the text** — illegal (gate regex). Not proposed.
- **Rules duplicated from P1-P11** (40-call cap, `get_status`, scratch in `/tmp`, sub-agent trigger, tests-as-spec) — already implemented; not repeated.

---

## 8. Limits of the analysis

What **cannot** be answered with these data (counts only, no inference):

- Whether the rate drop v2→v3a→v3 is an effect of the prompt or of harder tasks: version ⇔ temporal order, without repetition.
- Whether `thinking_budget`/skills/`code_analyzer` caused anything: collinear with the v3 phase and with no control arm.
- What fraction of `test_failure` is broken baseline: there is no patch-free control in run_03.
- How many tasks were winnable: there is no winnability or pre-resolved label in the files.
- Causality of any success/failure difference: there is no randomization; the differences are descriptive.

What would have to be instrumented in the runner (not the harness, does not score) to be able to answer it:

- **Per-batch patch-free control** (`--skip-agent-patch`) to separate broken baseline nodes.
- **`fail_to_pass`/`pass_to_pass` per node** and `verdict_source` at node level (today `junit`/`fail_to_pass` are `null` in `report.json`).
- **Hash of the materialized prompt** per task in `manifest.json` (run_03 mixed v2/v3a/v3).
- **Per-task hygiene metrics** in the file: scratch-in-patch, test-file-in-patch, hunks per file.
- **Warning** when a "resolved" task has no source hunk at all.
- **Exact install and pytest command**, and whether the package is rebuilt from the snapshot or imported from `site-packages` (case 3296/3782).

---

## Appendix — sources read

- `runs/20261006T103737Z/{STATUS,summary.json,report.json,manifest.json,task_results.jsonl}` and the 48 `rich_*/{agent_patch.diff,metadata.json,session.log,test_output.log,trace.json}` directories.
- `results/run_03/{summary.json,task_results.jsonl,patches/,test_outputs/,traces/,logs/,models-trial.generated.yaml}`.
- `data/raw/tasks.jsonl` (gold `patch`/`test_patch` of the 48 rich).
- `docs/runs/20261006T103737Z/{01-audit,06-segment-rich,05-segment-fastapi,07-segment-requests-httpx,08-cross-segment-synthesis,03-failures-by-prompt-version}.md`, `docs/runs/20261006T103737Z/04-harness-messages.md`, `docs/proposals/20261006-prompt-hardening.md`.

