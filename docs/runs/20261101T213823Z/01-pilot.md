---
Date: 2026-11-01
Genre: run analysis
Status: current
Scope: The five-task teacher pilot that measures trajectory-generation cost and mechanics before the 100-task batch. It does not estimate the teacher's resolution rate; the sample was chosen by hand.
Source of truth: runs/20261101T213823Z/report.json, results/pilot_01/, runs/20261101T021024Z/report.json (the E4B baseline on the same five tasks), docs/proposals/20261101-lora-sft.md
Limits: Five tasks, selected for spread rather than at random, on a Windows host with a repaired sandbox; not the scored condition. Two earlier attempts produced no data (run 20261101T211915Z failed on encoding, run 20261101T212455Z on a dependency mismatch) and are recorded below.
---

# Teacher pilot, 5 tasks

Purpose, per stage S1 of `docs/proposals/20261101-lora-sft.md`: before spending
a 100-task batch on the teacher, measure what a trajectory costs and prove the
pipeline produces trajectories the harness accepts. The task list was chosen for
spread, not sampled: two tasks the E4B already resolves, one it resolves with a
scratch-file patch, and two it fails.

Command:

```bash
PYTHONUTF8=1 HARNESS_TRIAL_BACKEND=opencode HARNESS_MODEL=deepseek-v4.1-flash \
  uv run python scripts/host-trial/run_host_trial.py pilot_01 --repair-sandbox-deps \
  --tasks rich_3006,fastapi_15589,fastapi_14463,rich_3777,requests_7315
```

## Two failures before the data

Neither is a competition fact; both are recorded because each one costs a full
attempt to discover.

**Encoding.** The first run died in 0.5-1.6 minutes per task with
`Sandbox execution error: 'charmap' codec can't encode character` and zero tool
calls. Windows locale encoding is cp1252 and `swegemma` pipes task text through
`subprocess(text=True)`, so the first character it cannot encode kills the
sandbox before the first call. `PYTHONUTF8=1` fixed it; the runner now sets it
itself (`evals_utf8_env`, runbook 6.4).

**Dependency.** The second run died on `cannot import name 'CacheableResult' from
'mcp.types'`: a global `uv tool install` of `swegemma` had `litellm` 1.106.6
against `mcp` 1.30.0. `mcp 2.3.0` fixed it. Phase 4 skips the install when
`swegemma` is already on `PATH`, so the repository's wheelhouse does not protect
against a stale tool environment.

## Result

```
tasks 5 | resolved 3 | rate 0.600 | wall 38.8 min | tool_calls 176
delivery submitted 5/5 | scope src_only=4 scratch=1
```

| Task | E4B baseline | Teacher | Teacher patch scope |
|------|--------------|---------|---------------------|
| `fastapi_15589` | resolved | resolved | src_only |
| `rich_3006` | resolved | resolved | src_only |
| `requests_7315` | not resolved | **resolved** | src_only |
| `fastapi_14463` | resolved | not resolved | — |
| `rich_3777` | not resolved | not resolved | scratch (rejected) |

Head to head on these five: 3 each. The teacher wins one the E4B loses and loses
one the E4B wins. On the cleaner measure — patches that pass the `src_only`
filter — it is 3 of 3 against 2 of 3, because `fastapi_14463` was resolved by
the E4B with a scratch-file patch, which the filter rejects.

That is a sample of five and it is chosen. **It is not an estimate of the
teacher's rate.**

## Cost

| Task | Prompt tokens | Completion tokens | Total |
|------|--------------:|------------------:|------:|
| `fastapi_14463` | 458,114 | 7,765 | 465,879 |
| `fastapi_15589` | 1,092,418 | 19,423 | 1,111,841 |
| `requests_7315` | 255,707 | 5,414 | 261,121 |
| `rich_3006` | 635,053 | 13,903 | 648,956 |
| `rich_3777` | 700,439 | 16,902 | 717,341 |
| **total** | **3,141,731** | **63,407** | **3,205,138** |

98% of the spend is prompt: every agent turn resends the whole conversation.
Per accepted trajectory that is ~1.07 M tokens, so a 100-task batch at 60%
acceptance is ~64 M tokens. The price of that depends on the provider's rate and
must be checked before the batch, not assumed here.

Wall clock: 38.8 minutes for five tasks at concurrency 1, or 7.8 minutes per
task. A 100-task pass at the same concurrency is ~13 hours; the batch needs
concurrency.

## What the pilot proves and what it does not

Proves:

- the teacher produces trajectories the harness accepts end to end, and the
  artifacts archive under `runs/` like any other run;
- the `src_only` filter behaves as designed: `rich_3777` was rejected for
  scratch files, which is exactly the filter's job;
- the cost per trajectory is measurable and dominated by prompt tokens.

Does not prove:

- the teacher's resolution rate, because the sample is stratified by hand;
- that the teacher is meaningfully better than the E4B. On these five it is not.

## Next step

A **random**, repository-stratified sample of 20 tasks from `ft-train` measures
the two numbers the pilot cannot: the teacher's acceptance rate and the cost per
accepted trajectory with less noise. The 100-task batch is decided from that, not
from this.

`runs/20261101T211915Z` and `runs/20261101T212455Z` are the failed attempts; they
carry a `STATUS` and no usable task results, and both are kept as evidence of the
two environment failures rather than deleted.
