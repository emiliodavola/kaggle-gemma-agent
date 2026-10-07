---
Date: 2026-10-07
Genre: run analysis
Status: current
Scope: Corrects specific claims in 01-audit.md, 03-failures-by-prompt-version.md and 04-harness-messages.md that disagree with the raw run artifacts; does not re-audit run_03.
Source of truth: runs/20261006T103737Z/, runs/20261004T225306Z/, runs/20261005T050122Z/, results/run_03/, results/run_01/, results/run_02/ (read 2026-10-07)
Limits: corrections only; counts and paths, no inference.
---

# run_03 — corrections to the audit documents

This document corrects four claims in `01-audit.md`,
`03-failures-by-prompt-version.md` and `04-harness-messages.md` that disagree with
the raw run artifacts. Those three documents remain otherwise valid: only the
claims below are corrected, and no other figure was re-checked here.

C2, C3 and C4 are also recorded as D3, D2 and D4 in
`02-successes-vs-failures.md` §1.4. C1 is new and was not in that section.

| # | Affected document | Claim as written | Raw evidence | Corrected value |
|---|---|---|---|---|
| C1 | `docs/runs/20261006T103737Z/01-audit.md` §0.1 | run_02 missed `inline_snapshot`; run_01 missed `typing_inspection` | `runs/20261004T225306Z/report.json` lines 7-18 and `runs/20261004T225306Z/STATUS` line 5 list only `inline_snapshot` for run_01; `runs/20261005T050122Z/STATUS` line 5 reads `env missing: inline_snapshot` for run_02 | RUN_01 AND RUN_02 BOTH missed `inline_snapshot`; `typing_inspection` never appears as a missing module in either run (it only appears inside a `fastapi/dependencies/utils.py` source body in a trace) |
| C2 | `docs/runs/20261006T103737Z/01-audit.md` §2 | the 6 timeouts were at "≈ 35–58 s per tool call" | `runs/20261006T103737Z/report.json` `wall_seconds / tool_calls` of the 6 timeouts (3043, 3278, 3454, 3470, 3472, 3942) | 36.3–58.5 s/call |
| C3 | `docs/runs/20261006T103737Z/04-harness-messages.md` §1 (line 27) | the T5 `observation` error-receipt count is 681 | parse of `runs/20261006T103737Z/rich_*/trace.json` observations: 670 error receipts (the doc's own per-tool table sums to 2 841); the 681 added the 11 raw `code_analyzer` receipts | 670 |
| C4 | `docs/runs/20261006T103737Z/03-failures-by-prompt-version.md` §6 (line 258) | `rich_3454` with `scr=4` | `runs/20261006T103737Z/rich_3454/agent_patch.diff`: source 1 (`rich/highlighter.py`), scratch 3 (`check_span.py`, `repro_bug.py`, `reproduce_issue.py`), tests 1 (`tests/test_highlighter.py`) | source 1, scratch 3, tests 1 |

Correction references: C2 = `02-successes-vs-failures.md` §1.4 D3; C3 = §1.4 D2;
C4 = §1.4 D4.
