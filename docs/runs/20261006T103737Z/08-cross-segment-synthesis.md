---
Date: 2026-10-06
Genre: run analysis
Status: current
Scope: Intra- and inter-segment synthesis over 70 executions plus a generalised, anti-overfit improvement proposal for the 129 tasks; it is not a formal A/B.
Source of truth: runs/20261004T225306Z/, runs/20261005T050122Z/, runs/20261006T103737Z/ and the segment reports; read 2026-10-06.
Limits: synthesis of existing censuses; recommendations are unvalidated by a controlled run.
---

# 2026-10-06 — Inter-segment synthesis + generalised proposal (not only rich)

70 executions: fastapi 10 (1 resolved, 10%), requests 4 (0, 0%), rich 56 (32, ~57%; run_03 29/48=0.604, real ≤0.542). httpx 0, others 0.

## Intra (common within each one)
- fastapi: half-wired feature (kwarg at the call-site without a callee, 4/7) + inline_snapshot blocks 4/7 + regex message 15588 + scratch/SyntaxError + 0% new on repeat.
- rich: budget (8/19 timeout/budget, 12/19 tc≥89) + fix does not touch the failure (6/19 without rich/, +4 orthogonal) + console/markdown/syntax clusters.
- requests: bit-for-bit determinism; recursive httpbin fixture (196/197 errors) + network down (4 TestTimeout); correct patches, the harness fails them.

## Inter (differences between segments)
- Dominant kind: fastapi collection_error 78% (they do not collect) vs rich test_failure (they fight the tests) vs requests fixture+network ERROR (not even the patch).
- Misleading rate: rich 57% vs fastapi 10% vs requests 0% — but requests 0% is 100% environmental; fastapi mixes environment + plumbing; rich is real capability/latency.
- Distinctive fastapi: the only ones with infra_error:true and constructor TypeError (APIRouter/Depends/Router).
- Distinctive requests: the only ones with a green suite where it matters (138 passed) and a fully orthogonal fail.
- Distinctive rich: the only ones with repeated logic clusters (terminal fallback, headings) and time overhead (wall fail 2.3x pass).
- Cross-cutting (all 3): scratch in the patch (fastapi repro.py/compradores:, rich 26/46 + 1 touches tests/, requests 3/4 with scripts), no-submit/timeout (rich 2943/3942, fastapi 14262 budget), phantom "verified" signal (requests x4, rich 3486 green+missing node).

## Generalised proposal (valid for 129 tasks, not overfit to rich)
1. V2 as the base, not v3 (v3 0.438 < v2 0.714 and it removed the 40-call cap, do-not-stop-on-analysis, cleanup). Re-add: ~40-call cap, do not end the turn without a tool call, 2-reads→edit/submit anti-loop.
2. Mandatory verification: run the target test file 1x, do not submit if it breaks a pre-existing one (targets 100% of pass_to_pass regressions: fastapi 15589 SyntaxError, rich 3454 touches tests/, requests a separate drama). py_compile before submit.
3. Pre-submit hygiene: git status/diff, remove repro*/debug*/fix_*.py, resolved-without-source-hunks warning (rich 3105/3469/3472, the real rate).
4. code_analyzer: reinforced trigger (used 1-4 calls and it deducts); localisation only.
5. Runner (highest return): per-batch control without a patch, materialised prompt hash (run_03 contaminated v2+v3a+v3), install/pytest command, fail_to_pass/pass_to_pass per node, empty-source warning, scratch/test-file metrics. Without this the metric lies (rich ≤0.542, requests 0% environmental, fastapi inflated by inline_snapshot).
6. Latency: lower thinking_budget / include_thoughts; 47% die on time in rich, fastapi budget-exhausted, requests 7502 2x cost.
7. Winability filter (playbook §1.3): broken baseline (rich test_console x4 identical, 3296/3782 broken import, 3486 missing node; requests fixture+network; fastapi inline_snapshot) → do not measure a serious resolution rate there.
8. Descriptive comparison with mixed tasks + fixed prompt + control (explicit rich-only overfitting warning; no formal A/B: not required by Emilio nor applicable with statistical rigour here).

Playbook: they confirm §1, §1.3, §2.3, §2.5, §10.4; they refute §2.1 (v3) and §2.4 (subagent). OpenCode detail §10.9 + today's segment docs.
