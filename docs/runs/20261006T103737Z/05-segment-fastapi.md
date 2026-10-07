---
Date: 2026-10-06
Genre: run analysis
Status: current
Scope: The fastapi_* segment across runs 20261004, 20261005 and 20261006T103737Z (7 distinct tasks / 10 executions; run_03 contributes no fastapi executions); it does not cover rich, requests or httpx.
Source of truth: runs/20261004T225306Z/, runs/20261005T050122Z/ and runs/20261006T103737Z/, plus results/; read 2026-10-06.
Limits: census of 10 executions classified from logs; no re-run.
---

# 2026-10-06 — fastapi_* segment (runs 20261004 + 20261005)

Actual universe: 7 distinct tasks, 10 observations. Resolved: 1/10 (10%), 1/7 distinct (14,3%). The only one: fastapi_15589 in run 20261004 (7 passed). In run 20261005 it drops to 0/7.

Kinds (9 failures): collection_error=7 (78%), test_failure=2 (22%), unknown=0. Of the 7 collection_error, 4 with infra_error:true + missing_modules:['inline_snapshot'].

| task | run | resolved | kind | cause (1 line) | evidence |
|---|---|---|---|---|---|
| 14978 | 20261004 | false | collection_error (infra) | Adds strict_content_type only in Body, never in APIRouter.__init__; the new tests use it and collection blows up + inline_snapshot missing | runs/20261004T225306Z/fastapi_14978/test_output.log: TypeError APIRouter.__init__() got an unexpected keyword argument 'strict_content_type' + ModuleNotFoundError inline_snapshot |
| 15588 | 20261004 | false | test_failure | Only checks \n, lets \r through; the message does not match the regex | test_output.log: DID NOT RAISE on [first\rsecond-*] + Regex did not match, actual "SSE field must not contain newline characters" |
| 15589 | 20261004 | true | — | 7 passed | test_output.log: 7 passed in 0.72s |
| 14246 | 20261005 | false | collection_error (infra) | Pure environment: inline_snapshot missing | test_output.log: ModuleNotFoundError inline_snapshot x2; missing_modules inline_snapshot, infra_error:true |
| 14262 | 20261005 | false | collection_error (infra) | scope as a class attribute in Depends without a constructor + budget exhausted + inline_snapshot | test_output.log: Depends() got an unexpected keyword argument 'scope'; session.log: BudgetExceeded 100 calls |
| 14266 | 20261005 | false | collection_error (infra) | Pure environment inline_snapshot | test_output.log: ModuleNotFoundError inline_snapshot in test_top_level_security_scheme_in_openapi.py:7 |
| 14301 | 20261005 | false | collection_error | Non-existent depends.scope reference; the real earlier failure: Router.__init__ on_startup | test_output.log: Router.__init__() got an unexpected keyword argument 'on_startup'; whole patch scope=depends.scope |
| 14978 | 20261005 | false | collection_error (infra) | Identical to run1: APIRouter strict_content_type unsupported + inline_snapshot | Same log (2x strict_content_type + 1x inline_snapshot) |
| 15588 | 20261005 | false | test_failure | Now it checks \r but the message still does not match | 6 failed, 18 passed; Expected "SSE 'event' must be a single line" |
| 15589 | 20261005 | false | collection_error | Its own patch breaks collection: SyntaxError + junk | utils.py line 832 SyntaxError unexpected character after line continuation (\"_\"); adds repro.py, repro_model.py |

Intra patterns:
1. Half-wired feature (4/7: 14978, 14262, 14301, 15588-partial): new kwarg at the call-site but not in the callee. They do not even reach FAIL_TO_PASS.
2. inline_snapshot block (4/7, 5/9 failures). environment_blocked:true in run 20261005. In 14246/14266 it is 100% environment.
3. Message different from the one the test matches (15588 x2): it fails on the string, not on the logic.
4. Patches that dirty the repo and produce SyntaxError (15589-run2, 15588-run1, 14978-run1): repro.py, compradores: empty, \"_\" escaped.
5. Reproducibility 0% new: repeated 14978/15588/15589 — 2 repeat the failure, 1 worsens pass→fail.

Distinguishes it from the rest: worst rate (0/7 run2 vs rich 1/4, run3 rich 29/48). 78% collection_error vs rich/requests test_failure/unknown. The only one with infra_error:true. Failures due to new-API plumbing, non-existent in rich/requests.
