---
Date: 2026-10-06
Genre: run analysis
Status: current
Scope: The rich_* segment of run_03 (48 tasks, 29 resolved), tabulating failures and success-vs-failure patterns; it does not cover fastapi/requests/httpx.
Source of truth: runs/20261006T103737Z/ (= results/run_03); read 2026-10-06.
Limits: 100% rich_* census; counts and medians only, no inference.
---

# 2026-10-06 — rich_* segment (run_03 = runs/20261006T103737Z)

48 tasks, 29 resolved (0.604). 19 failures: test_failure=14, collection_error=2, unknown=3. Real rate with a source fix ≤26/48=0.542 (3 repro-only resolutions: 3180, 3471, 3938).

| id | kind | root cause | evidence |
|---|---|---|---|
| 2943 | unknown | No-submit: 8 calls, 191s, no patch or test_output; loop in style.py | error="Agent completed without submit_patch"; session.log 3x continue-or-submit after __hash__/__eq__/lru_cache |
| 3043 | test_failure (+timeout) | Irrelevant fix to _export_format.py, 7 test_console fail | 7 failed, 89 passed; assert (80,25)==(133,24) size_fall_back |
| 3064 | test_failure (+budget) | Insufficient markdown | 4 failed test_markdown; assert ' ...' == '┏━━Heading' |
| 3105 | test_failure | No fix: repro.py only | 4 failed, 92 passed (size_fallback, capture_and_record, input_password, no_nested_live); all=['repro.py'] |
| 3130 | test_failure | Insufficient markdown | 6 failed test_markdown (same Heading as 3064) |
| 3278 | test_failure (+timeout) | Zero fix: 16 repro/debug, none in rich/; 3 test_ansi | 3 failed, 20 passed; Left contains one more item <text ''> |
| 3296 | collection_error | Tests do not even import: 0 tests | ImportError cannot import 'Console' from 'rich.syntax'; 1 error in 0.09s |
| 3454 | test_failure (+timeout) | Off-by-one highlighter + touches tests/ | 1 failed, 83 passed; Span(1,25) vs (1,24) test_highlight_regex user@example.com |
| 3468 | test_failure | Insufficient console | 4 failed, 94 passed; assert (80,25)==(133,24) |
| 3469 | test_failure (+budget) | repro.py only; 6 failed markdown | 6 failed, 1 passed (same set as 3130) |
| 3470 | test_failure (+timeout) | Insufficient console | 3 failed, 95 passed (size_fallback, input_password, no_nested_live) |
| 3472 | test_failure (+timeout) | repro_console.py only; pretty fails | 1 failed, 50 passed; test_attrs_broken_310 |
| 3486 | unknown | Required node absent with a green suite | 20 passed, 1 skipped; Required node did not pass: test_traceback_finely_grained_missing |
| 3675 | test_failure | Orthogonal: input_password/no_nested_live fail, introduces TTY_COMPATIBLE | 2 failed, 97 passed; has no attribute 'getpass' + DID NOT RAISE LiveError |
| 3777 | test_failure | Same as 3675 | 1 failed, 98 passed test_input_password; same getpass |
| 3782 | collection_error | Identical to 3296 | diff only test_syntax.py:12→13; same ImportError Console |
| 3942 | unknown (timeout) | Total drift with no test_output or patch; 3622s/93 calls | error='exceeded session timeout'; session.log "too vague", "budget almost gone" |
| 4070 | test_failure | Wrong file: 6 failed test_syntax, touches console/logging | 6 failed, 118 passed test_python_render*; diff 730 chars |
| 4079 | test_failure | Insufficient minimum: 1 failed markdown | 1 failed, 7 passed test_inline_code_in_table_cells |

Resolved vs failed:
- mean wall 1040s pass vs 2421s fail (median 829 vs 2645); wall>3000s: 1/29 vs 9/19. mean calls 36.7 vs 75.2 (median 30 vs 92); tc==100: 1/29 vs 7/19; tc≥89: fail 12/19.
- No patch 0/29 vs 2/19 (2943, 3942). Zero rich/ 3/29 vs 4/19 (3105, 3278, 3469, 3472). With a rich/ fix: 26/29 vs 13/19.
- Top fail modules: console.py 5, markdown.py 3, syntax.py 2. Pass: cells.py 4, console.py 3, table/prompt/text/segment/traceback 2.
- Clusters: console size_fallback+input_password (3043,3105,3468,3470,3675,3777), markdown heading/tables (3064,3130,3469+4079), one-off syntax/ansi/highlighter/pretty (3278,3296/3782,3454,3472,4070,3486).

Top 3 patterns:
1. Budget exhaustion with an absent/sterile fix (8/19 timeout/budget, 12/19 tc≥89, 9/19 wall>3000 vs 1/29).
2. Fix does not touch what fails (6/19 without rich/, +4 orthogonal: 3043 _export_format vs console; 3675/3777 is_terminal vs getpass; 4070 console/logging vs syntax).
3. Repeated clusters: (80,25)==(133,24) in 3043/3105/3468/3470; Heading ┏━━ in 3064/3130/3469; ImportError Console in 3296/3782; missing node 3486.
