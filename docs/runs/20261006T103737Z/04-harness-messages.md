---
Date: 2026-10-06
Genre: run analysis
Status: current
Scope: Catalogue, frequencies and fail-vs-pass comparison of the messages the harness delivers to the agent in run_03; it excludes model responses and thinking.
Source of truth: runs/20261006T103737Z/ (48 rich_* ATIF-v1.7 traces) and results/run_03/; read 2026-10-06.
Limits: message counts only; no causal attribution to the resolution outcome.
---

# Harness → agent messages in run_03: catalogue, frequencies and fail-vs-pass

Run: `runs/20261006T103737Z` (48 dirs `rich_*`, ATIF-v1.7 trace) + `results/run_03` (29 pass / 19 fail).
Unit of analysis: **only what the harness delivers to the agent** — steps with `author=harness`
(`system_instruction`, `task_prompt`, `continuation_nudge`) and tool receipts
(`observation` inside `agent` steps, plus `code_analyzer` observation-only `system` steps).
Model responses/thinking (`author=kaggle_gemma_agent` / `code_analyzer_agent`) are excluded.

## 1. Type catalogue

| # | Type | Fixed / adapted | N total |
|---|------|-----------------|---------|
| T1 | `system_instruction` (system/harness) | **Fixed**: 3 variants byte-identical within variant (3176×11 without code_analyzer, 3364×16 with code_analyzer, 3728×21 Objective/DoD format) | 48 |
| T2 | `task_prompt` (user/harness) | **Fixed envelope + adapted content**: identical header, problem statement and issue-body specific to each task | 48 |
| T3a | standard `continuation_nudge` (system/harness) | **Fixed**, 1 string in the 378 cases | 378 |
| T3b | token-limit `continuation_nudge` (system/harness) | **Fixed**, 1 string in the 25 cases; chosen by condition (previous response cut), not by content | 25 |
| T4 | `observation` receipt ok | **Adapted in payload, fixed template per tool**: `{"status":"ok",...}` with the real stdout/content | 2160 |
| T5 | `observation` error receipt | **Adapted in payload, closed catalogue of `error_type` + fixed strings** (see table) | 681 |
| T6 | `code_analyzer` receipt (observation-only system step, `{"raw":...}`) | **Adapted**: free text from the sub-agent | 11 |
| T7 | `get_status` receipt | **Adapted**: real budget/time numbers for that task | 5 |

Total harness→agent messages: **3340** = 48 + 48 + 403 + 2841 (obs T4+T5+T6+T7).

### Triggering of T3 (verified across the 403)
- 389/403 (96,5%) fall **immediately after an agent `thinking` turn WITHOUT a tool call** (the agent "talks without acting" and the harness pushes it).
- 10/403 after a `code_analyzer` receipt (observation-only system step).
- 2/403 nudges back-to-back, 2/403 after thinking WITH a tool call (edge cases).
- Typical spacing: 1 nudge every 2–9 steps in long sessions (e.g. rich_3278: 40 nudges, median gap 3; rich_3506: 17 nudges, median 4). Short, clean sessions barely see them (rich_2725, rich_3882, rich_3894: 0).

### Real textual examples
- **T1** (the 3 variants share Non-negotiables/Skills; they differ only in this):
  `Use only these tools; there are no others.` (3176, 3728) vs
  `Use only these tools and the \`code_analyzer\` sub-agent; there are no others.` + paragraph
  `` \`code_analyzer\` sub-agent — localizes code in a large repository when the edit site is unclear; it shares your call budget, so delegate at most once. `` (3364).
  Variant 3728 replaces `## Non-negotiables` with `## Objective` + `## Definition of done` (`The task is done only when…`) and closes with `Do not stop at analysis. Until you submit, end every turn with a tool call.`
- **T2** (rich_2725): `You are evaluating a software engineering task for repository Textualize/rich.\n\nProblem Statement:\nfix table rendering order of box elements\n\n## Type of changes…` (rich_3130: `…Problem Statement:\nFix markdown table rendering issue with inline styles/links…`).
- **T3a** (verbatim, 378×): `Please continue your work using the available tools, or call submit_patch when you have completed and verified your changes.`
- **T3b** (verbatim, 25×, 14 tasks): `Your previous response reached the token limit while thinking before a tool call was completed. Do NOT repeat your analysis in thought—keep reasoning under a few sentences and emit your next tool call immediately, or call submit_patch when you have completed and verified your changes.`
- **T4-ok** `run_command` (rich_2725 s5): `{"status": "ok", "stdout": "┏━━━…1 Date  2 Title …` (real payload of the command).
- **T4-ok** `read_file` (rich_2725 s7): `{"status": "ok", "filepath": "rich/table.py", "content": "\n    def _measure_column(…`.
- **T4-ok** `submit_patch` (all identical in shape): `{"status": "ok", "patch_size": 1099, "files_changed": 1}` (rich_2725).
- **T4-ok** `get_status` (only 5 calls in the whole run: rich_3064, rich_3296×2, rich_3486×2): `{"status": "ok", "tool_calls_used": 100, "patch_submitted": false, "patch_size": 0, "tool_calls_remaining": 0, "max_tool_calls": 100, "time_seconds_remaining": 1143.26…, "max_time_minutes": 60.0, …}`.
- **T5** `write_file` (79×, e.g. rich_2725 s3): `{"status": "error", "error_type": "FileWriteError", "error_message": "Path traversal detected: '/tmp/reproduce_issue.py' escapes workspace root."}` — the message orders scratch in `/tmp` (T1) but the tool rejects `/tmp`; fixed harness contradiction, 79 identical clashes.
- **T5** `edit_file` (53×, e.g. rich_3043 s14): `{"status": "error", "error_type": "FileEditError", "error_message": "Failed to replace: old_string not found. Ensure you're not escaping content incorrectly and check whitespace, indentation, and context."}`. Second form (param validation failure, e.g. rich_3470 s55): `{"error": "Invoking \`edit_file()\` failed as the following mandatory input parameters are not present:\nold_string\nYou could retry calling this tool, but it is IMPORTANT for you to provide all the mandatory parameters."}`.
- **T5** `run_command` (231×; e.g. pytest rich_3130 s65): `{"status": "error", "error_type": "CommandError", "error_message": "============================= test session starts ==============================\nplatform linux -- Python 3.13.16, pytest-9.1.1 …` (the test stderr travels inside the receipt).
- **T5** budget (11×, e.g. rich_3064 s113): `{"status": "error", "error_type": "BudgetExceeded", "error_message": "Tool call budget exhausted (100 calls)"}`.
- **T5** command timeout (2×, both in PASS: rich_3480 s18, rich_3953 s46): `{"status": "error", "error_type": "TimeoutExceeded", "error_message": "Command timed out after 300 seconds"}`.
- **T6** delegation (rich_3469 s125, with budget exhausted): `{"raw": "I was unable to complete the localization due to a tool call budget exhaustion error. However, based on the issue description …` (the sub-agent does "talk" about the cause; the harness only forwards it).

### Receipts per tool (T4+T5+T6+T7 = 2841)
| Tool | ok | error | Total |
|---|---|---|---|
| run_command | 868 | 231 | 1099 |
| read_file | 882 | 6 | 888 |
| edit_file | 95 | 353 (286 form `{"error":…}` + 67 `status:error`) | 448 |
| write_file | 213 | 79 | 292 |
| search_similar_code | 57 | 1 | 58 |
| submit_patch | 35 | 0 | 35 |
| code_analyzer_agent (T6) | 11 (raw) | — | 11 |
| get_status | 5 | 0 | 5 |
| get_code_neighbors | 5 | 0 | 5 |

Dominant errors: `CommandError` from run_command with repro/test stdout inside (~87 with empty output + dozens with tracebacks), `FileEditError old_string not found` (53), `FileWriteError Path traversal /tmp` (43 only `repro.py` + the rest up to 79), `No such file…repro*.py` (cascades after the `/tmp` rejection).

## 2. Fail-vs-pass comparison (per-task averages)

| Metric | PASS (29) | FAIL (19) |
|---|---|---|
| Total observations | 41,9 (31,3 ok / 10,5 err) | 85,6 (65,8 ok / 19,8 err) |
| Standard T3a nudges | 5,6 | 11,4 |
| Token-limit T3b nudges | 0,4 (9 tasks) | 0,6 (8 tasks) |
| edit_file errors | 5,7 | 9,9 |
| run_command errors | 3,3 | 7,1 |
| BudgetExceeded receipts | ~0 (1 in total) | 0,5 (10 in total) |
| submit_patch receipts | 25/29 tasks | 10/19 tasks |

Types: **the same in both groups** — no message type is exclusive to fail or pass.
Quantity: fail receives **~2× messages** because the session is ~2× longer (more turns → more receipts + more nudges for thinking without a tool call).
Order: identical skeleton `[T1, T2] → loop [agent turn + receipt] with T3 inserted after idle thinking → close according to class` (see §3).
Real qualitative difference: only the **close**.

## 3. Last harness message before the end, by failure class

| Failure class | Tasks | Last harness→agent message |
|---|---|---|
| Submit + tests fail (patch submitted, exit≠0; incl. exit 2) | 3105, 3130, 3296, 3468, 3675, 3777, 3782, 4070, 4079, 3486* | **10/10: `submit_patch` receipt ok** `{"status": "ok", "patch_size": N, "files_changed": M}` — the harness confirms receipt; the evaluator dictates the failure afterwards, with no message to the agent |
| Session timeout 60 min | 3043, 3278, 3454, 3470, 3472, 3942 | **Ordinary work receipt, nothing distinctive**: read_file ok (3043, 3472), nudge_std (3278), run_command ok (3454, 3942), edit_file param error (3470). There is no timeout message inside the trace |
| Budget 100 calls exhausted | 3064, 3469 (+3105/3296/4070/3472 reach 100 tc) | 3064: `read_file` → `BudgetExceeded: Tool call budget exhausted (100 calls)`; 3469: T6 `I was unable to complete the localization due to a tool call budget exhaustion…`. Only 2 tasks see the explicit text; the rest die silently |
| No-submit (ends without calling submit) | 2943 (8 tool calls, 8 obs all ok) | **nudge_std** (s16): `Please continue your work…` — the agent closes with `final` anyway, without submit |
| Pass without submit in trace (note) | 3180, 3471, 3506, 3938 | They resolve with the worktree diff; there is no submit receipt. `agent_patch_size>0` ≠ `submit_patch` called (the reverse also holds: 3043 leaves patch 2620 without submit due to timeout) |

\* 3486: exit 0 but `Required test node did not pass: test_traceback_finely_grained_missing` — also closes with submit ok (patch of 8871, 11 files).

Cases that confirm the rigidity before error loops: rich_3454 (72 failed edit_file) and rich_3470 (65) receive dozens of times **the same** `old_string not found` / `mandatory parameters…` interspersed with **the same** `Please continue…`, without escalation, without a suggestion, without a change of tone. `get_status` (the only budget probe the harness offers) is used 5 times across 48 tasks, always with `tool_calls_remaining: 0` already consummated.

## 4. Verdict

**The harness always speaks the same way.** The full repertoire is 2 byte-identical nudge strings, 3 initial instruction variants (they differ only in the Tools/`code_analyzer` section and in Objective-vs-Non-negotiables) and a closed catalogue of receipts typified per tool. The only "adapted" thing is the **payload** the tool returns (stdout, file content, `get_status` counters) and the **binary choice** between the 2 nudges depending on whether the previous turn was cut by tokens — a switch by condition, not by understanding the situation. Verdict by question:

- Is `go on, continue` fixed or adapted? **Fixed**: T3a is always the same `Please continue your work using the available tools, or call submit_patch…`, whether it fires 1 time (rich_3718) or 39 (rich_3278). It never diagnoses, never suggests, never changes before 70+ identical errors in a row.
- What message precedes each failure class? **Submit+test-fail → `submit_patch: ok` receipt** (the harness "approves" the delivery that the tests will reject); **timeout → any ordinary work receipt or a nudge**, without warning (the cut leaves no message in the trace); **budget → `BudgetExceeded` or silence** (only 2/19 fails see the text); **no-submit → nudge_std ignored**. No failure class has its own distinctive harness preamble: fail and pass receive the same types, in the same order, and differ only in quantity (fail sessions ~2× longer) and in the closing line.
