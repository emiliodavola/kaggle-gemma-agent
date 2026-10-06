---
Date: 2026-10-06
Genre: run analysis
Status: current
Scope: Descriptive failure analysis by system-prompt version (v2/v3a/v3) across run_03; it is not a formal A/B test.
Source of truth: runs/20261006T103737Z/report.json, task_results.jsonl and rich_*/trace.json, results/run_03/task_results.jsonl, submission prompts/configs; read 2026-10-06.
Limits: prompt version, time and task difficulty are confounded; no randomisation and no task repeated across versions.
---

# Run_03 — Failures by system-prompt version (descriptive analytics)

Analysis document. **It does not modify the submission.** The comparison
between versions is **descriptive** and the analysis suggests it: it is basic
statistics, not a formal test or an A/B. Emilio **did not ask for and does not
require an A/B**, and it is not a technique applicable with rigour here
(confounded phases, small n, no randomisation, no same task repeated across
versions).

- **Run:** `20261006T103737Z` (= `results/run_03`), backend `gemma-4-31b-it-qat`,
  `STATUS DONE`, 48 tasks, all `Textualize/rich`.
- **Sources:** `runs/20261006T103737Z/report.json`, `task_results.jsonl`,
  `rich_*/trace.json` (ATIF-v1.7), `results/run_03/task_results.jsonl`,
  `submission/prompts/system.{v2,v3}.md`, `submission/configs/sampling.yaml`.
- **Version method:** the `system_instruction` of the first step
  (`source=system`, `event_type=system_instruction`) of each `trace.json` is
  extracted and compared byte by byte against the materialised prompts. `v3a` is
  the content of `submission/prompts/system.v3.md` at commit `d2ce207` (v3
  **without** mention of the `code_analyzer` sub-agent). The `timestamp` of the
  same step gives the UTC window.
- **Reproducibility:** `python3 /var/tmp/opencode/audit_per_version.py` (script
  used for all the figures in this document; dumps in `rows.json`).

## 0. Summary

1. The run **is not a prompt comparison**: the shared checkout materialised
   three versions as commits landed, and each version ran over a **different**
   subset of tasks (no task repeats). Version, temporal order and task difficulty
   are **perfectly confounded**.
2. Raw count: **v2 15/21 = 0.714 → v3a 7/11 = 0.636 → v3 7/16 = 0.438**.
   Without random sampling no inference is possible: they are three different
   batches of tasks, none repeats, so the drop may be batch difficulty and not a
   prompt effect. **It does not improve; if anything, it worsens in count, with
   no attribution.** Adjusted for "resolved without source": 0.619 / 0.636 /
   0.375.
3. Phase v3 concentrates **7/9 process failures** of the run (4 of the 6
   timeouts, the 2 call exhaustions and the only loop without submit). It is
   consistent with v3 having **lost** v2's anti-loop rules (~40-call cap, "do not
   stop at analysis / end every turn with a tool call", `git status` cleanup),
   but also with v3's tasks being the hardest (late timeline).
4. Phase v3 **did not change a single lever**: it changed prompt **+** skill
   compaction **+** `code_analyzer` guidance, all together. Not separable with
   this run.
5. The set is **100 % `rich`**: any reading is intra-repo and must not be
   generalised to the official mixed set (fastapi/requests/rich/httpx).

## 1. UTC windows and components that changed during the run

Commit order (timestamp in UTC) vs. task windows:

| Moment | Commit / event | Effect |
|---|---|---|
| 10-05 00:29 | `248f980` system.v2 | — |
| 10-05 13:20 → 21:14 | tasks idx 1–21 | **v2** |
| 10-05 20:53 | `d2ce207` system.v3 | prompt v3 materialised ~21:24 |
| 10-05 21:24 → 10-06 01:31 | tasks idx 22–32 | **v3a** (v3 without `code_analyzer`) |
| 10-06 01:13 | `3389078` compacts the 12 skills (469→322 lines) | materialises near the B/C limit |
| 10-06 01:49 | `c5f6331` `code_analyzer` localization-only | prompt v3 materialised ~02:31 |
| 10-06 02:31 → 10:28 | tasks idx 33–48 | **v3** + compacted skills + `code_analyzer` guidance |

Windows derived from the `timestamp` of the `system_instruction`:

| Version | Indices | UTC window (start) | n |
|---|---|---|---|
| v2 | 1–21 | 10-05 13:20 → 21:14 | 21 |
| v3a | 22–32 | 10-05 21:24 → 10-06 01:31 | 11 |
| v3 | 33–48 | 10-06 02:31 → 10:28 | 16 |

Components:

- **Compacted skills** — commit at 01:13 UTC. The `trace.json` **do not** contain
  the body of the skills (verified: the new `Trigger:` description does not appear
  in any trace), so the exact v3a→v3 boundary cannot be read from the trace. By
  time, the compaction is **collinear with phase v3** (it falls between idx 31 and
  idx 33); it remains **indistinguishable** from the prompt change.
- **`code_analyzer`** — available from the skeleton (`64b10a4`); `c5f6331` only
  makes it localization-only and prompt v3 says "delegate at most once".
  Observed use: **v2 1 call** (`rich_4075`), **v3a 0**, **v3 10 calls in 4 tasks**
  (`rich_3469` 4, `rich_3105` 4, `rich_3278` 1, `rich_3064` 1). That is 1–4 calls
  per task that uses it, and it only rises strongly in v3.
- **`thinking_budget` / `include_thoughts`** — `submission/configs/sampling.yaml`
  did not change throughout the run (`thinking_budget: 4096`, `include_thoughts:
  true`, `temperature: 0.2`). **It is not a confounder**: it is constant. What did
  change is the *behaviour* (mean `thinking` steps: v2 38.5, v3a 38.0, v3 52.2),
  which is a **consequence** of the phase, not a config adjustment.
- **100 % rich set** — run_01/02 were mixed; run_03 is pure rich. It blocks any
  inter-repo generalisation.
- **Task order as a confounder** — the version is assigned by **time**, and time
  fixes **which task** runs. There is no randomisation or repetition. It is the
  dominant confounder and cannot be broken post-hoc with this run.

## 2. Table by version

n, resolved and rates (raw and adjusted for "resolved without source"). Counts
only, no intervals: there is no random sampling and no task repeats across
phases.

| Metric | v2 | v3a | v3 |
|---|---|---|---|
| n | 21 | 11 | 16 |
| Resolved (raw) | 15 | 7 | 7 |
| **Raw rate** | **0.714** (15/21) | **0.636** (7/11) | **0.438** (7/16) |
| Resolved **without source** (pre-resolved) | 2 | 0 | 1 |
| **Adjusted rate** (with source fix) | **0.619** (13/21) | **0.636** (7/11) | **0.375** (6/16) |

Failure kinds (the `null` values of `failure_kind` are counted as `unknown`,
which is how `STATUS` counts them):

| Kind | v2 | v3a | v3 |
|---|---|---|---|
| `collection_error` | 0 | 2 | 0 |
| `test_failure` | 4 | 2 | 8 |
| `unknown` (incl. `null`) | 2 | 0 | 1 |
| **Total failures** | **6** | **4** | **9** |

Process/budget failures:

| Category | v2 | v3a | v3 |
|---|---|---|---|
| Timed out (~60 min) | 1 (`3942`) | 1 (`3472`) | 4 (`3043, 3278, 3454, 3470`) |
| Exhausted 100 calls without submit (without timing out) | 0 | 0 | 2 (`3064, 3469`) |
| No `submit_patch` due to loop | 0 | 0 | 1 (`2943`) |
| **Total process** | **1** | **1** | **7** |

Note: `rich_3472` (v3a) saturated **both** caps (100 calls and 60 min) without
submit; it is counted once, as a timeout, as in the general audit.

Latency and budget:

| Metric | v2 | v3a | v3 |
|---|---|---|---|
| wall (min) mean / median | 22.9 / 16.0 | 27.8 / 21.2 | 30.2 / 23.9 |
| tool-calls mean / median | 50.1 / 38 | 50.4 / 45 | 55.4 / 50 |
| mean `thinking` steps | 38.5 | 38.0 | 52.2 |

Patch hygiene (over patches captured in `agent_patch.diff`):

| Metric | v2 | v3a | v3 |
|---|---|---|---|
| Patches with files | 20 | 11 | 15 |
| With scratch files | 10 (50 %) | 5 (45 %) | 11 (73 %) |
| Modifies `tests/` | 0 | 0 | 1 (`3454`) |
| Does not touch source (`rich/*.py`) | 2 (`3180, 3938`) | 1 (`3472`) | 4 (`3105, 3278, 3469, 3471`) |

Note: the 3 "resolved without source" (`rich_3180`, `rich_3938` in v2;
`rich_3471` in v3) **did not call `submit_patch`**; the harness captured the diff
anyway. The raw rate is inflated by those pre-resolved ones, especially in v2.

## 3. What changed between versions

**v2 → v3a** (prompt text only; `d2ce207`):

- Removed `Do not stop at analysis. Until you submit, end every turn with a tool
  call.`
- Removed `Point of no return: after about 40 tool calls.`
- Removed the explicit pre-submit check `git diff --name-only` + `git status
  --short` and the untracked cleanup.
- Rewrote the section as `Non-negotiables`; **keeps** "Always submit …
  never end a session without `submit_patch`".

**v3a → v3** (`c5f6331` + `3389078`):

- Adds the mention of the `code_analyzer` sub-agent and "it shares your call
  budget, so delegate at most once".
- Rewrites `analyzer.md` to localization-only with an 8-call cap.
- **Collinear:** compacted skills (469→322 lines) at the same boundary.

That is why the clean comparison **does not exist** in either direction: v2→v3a
changes several rules at once, and v3a→v3 changes prompt + skills + sub-agent.

## 4. Does it improve, worsen, or nothing?

Honest reading, without a formal test:

- **There is no sign of improvement.** The point estimate falls from v2 to v3 in
  the raw rate (0.714 → 0.438) and in the adjusted rate (0.619 → 0.375). v3a sits
  in the middle and, in the adjusted rate (0.636), slightly above v2 (0.619), but
  with n=11 and a huge interval.
- **The CIs overlap**: v2–v3a, v2–v3 and v3a–v3 are all compatible with "no
  difference". One cannot claim worsening, only that **one cannot claim
  improvement**.
- **Confounders that prevent attribution**: (a) version ⇔ temporal order; (b)
  each version runs different tasks (no paired control); (c) v3 mixes prompt,
  skills and `code_analyzer`; (d) the set is 100 % rich; (e) n = 21/11/16.
- The process drop in v3 (7 of the 9 process failures of the run) and the jump in
  `thinking` steps (38→52) are **consistent** with the removed anti-loop rules
  mattering, but **also** with the late tasks being harder. The run cannot
  separate the two explanations.
- On `code_analyzer`: in v2 it was used 1 time and in v3a 0; in v3 it rises to 10
  calls in 4 tasks and **all 4 ended in failure** (3 process: `3469` and `3064` by
  budget, `3278` by timeout; and `3105` by `test_failure`). With n=4 it is an
  anecdote, not evidence, but it reinforces the risk already noted in playbook
  §2.4: the sub-agent **consumes budget** from the main agent.

## 5. Methodological recommendation (descriptive, not required)

For a prompt comparison to be interpretable, without the need for a formal A/B
or a statistical test:

1. **Fixed prompt per batch** (a single `system_instruction` for all tasks) and
   hash of the materialised prompt in the run file.
2. **Same tasks** in both arms (paired control) and, if possible, randomise the
   order; do not confound version with time.
3. **No-patch control** per batch to detect broken baseline nodes.
4. **Mixed set** (4 fastapi + 4 requests + 4 rich + 4 httpx), not 100 % rich.
5. Report **raw and adjusted without-source rate** separately, plus n and the
   known confounders; without p-values.

## 6. Evidence per task

`idx` = execution order (`task_index` in `results/run_03/task_results.jsonl`).
`src`/`scr` = source files `rich/*.py` / the rest in the patch. `ana` = calls to
`code_analyzer_agent`. `sub` = called `submit_patch`.

| idx | task | ver | res | kind | calls | wall min | sub | ana | src | scr |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | rich_4070 | v2 | 0 | test_failure | 100 | 40.1 | 1 | 0 | 2 | 1 |
| 2 | rich_4077 | v2 | 1 | — | 60 | 25.3 | 1 | 0 | 1 | 4 |
| 3 | rich_4079 | v2 | 0 | test_failure | 92 | 42.1 | 1 | 0 | 1 | 0 |
| 4 | rich_4076 | v2 | 1 | — | 32 | 8.3 | 1 | 0 | 1 | 0 |
| 5 | rich_4075 | v2 | 1 | — | 100 | 42.5 | 1 | 1 | 1 | 1 |
| 6 | rich_4006 | v2 | 1 | — | 27 | 9.6 | 1 | 0 | 1 | 0 |
| 7 | rich_3718 | v2 | 1 | — | 15 | 3.6 | 1 | 0 | 1 | 0 |
| 8 | rich_3934 | v2 | 1 | — | 28 | 9.4 | 1 | 0 | 1 | 0 |
| 9 | rich_3953 | v2 | 1 | — | 45 | 29.6 | 1 | 0 | 1 | 2 |
| 10 | rich_3944 | v2 | 1 | — | 46 | 15.8 | 1 | 0 | 2 | 0 |
| 11 | rich_3942 | v2 | 0 | — (timeout) | 93 | 60.4 | 0 | 0 | 0 | 0 |
| 12 | rich_3938 | v2 | 1 | — | 36 | 16.0 | 0 | 0 | 0 | 1 |
| 13 | rich_3882 | v2 | 1 | — | 15 | 3.2 | 1 | 0 | 1 | 0 |
| 14 | rich_3894 | v2 | 1 | — | 14 | 3.7 | 1 | 0 | 1 | 0 |
| 15 | rich_3935 | v2 | 1 | — | 85 | 36.1 | 1 | 0 | 2 | 4 |
| 16 | rich_3905 | v2 | 1 | — | 38 | 25.5 | 1 | 0 | 1 | 0 |
| 17 | rich_3930 | v2 | 1 | — | 28 | 13.8 | 1 | 0 | 1 | 1 |
| 18 | rich_3180 | v2 | 1 | — | 30 | 27.9 | 0 | 0 | 0 | 2 |
| 19 | rich_3486 | v2 | 0 | unknown | 100 | 50.5 | 1 | 0 | 1 | 9 |
| 20 | rich_3777 | v2 | 0 | test_failure | 41 | 8.0 | 1 | 0 | 1 | 0 |
| 21 | rich_3468 | v2 | 0 | test_failure | 27 | 9.5 | 1 | 0 | 1 | 1 |
| 22 | rich_3782 | v3a | 0 | collection_error | 35 | 16.2 | 1 | 0 | 1 | 0 |
| 23 | rich_3772 | v3a | 1 | — | 45 | 19.1 | 1 | 0 | 1 | 1 |
| 24 | rich_3296 | v3a | 0 | collection_error | 100 | 54.9 | 1 | 0 | 1 | 2 |
| 25 | rich_3675 | v3a | 0 | test_failure | 23 | 4.8 | 1 | 0 | 1 | 0 |
| 26 | rich_3676 | v3a | 1 | — | 51 | 26.2 | 1 | 0 | 1 | 0 |
| 27 | rich_3518 | v3a | 1 | — | 16 | 6.5 | 1 | 0 | 1 | 0 |
| 28 | rich_3535 | v3a | 1 | — | 59 | 21.2 | 1 | 0 | 1 | 0 |
| 29 | rich_3521 | v3a | 1 | — | 33 | 22.6 | 1 | 0 | 1 | 3 |
| 30 | rich_3506 | v3a | 1 | — | 72 | 60.5 | 0 | 0 | 1 | 6 |
| 31 | rich_3480 | v3a | 1 | — | 20 | 12.9 | 1 | 0 | 1 | 0 |
| 32 | rich_3472 | v3a | 0 | test_failure | 100 | 60.5 | 0 | 0 | 0 | 1 |
| 33 | rich_3454 | v3 | 0 | test_failure | 68 | 60.5 | 0 | 0 | 1 | 4 |
| 34 | rich_3471 | v3 | 1 | — | 26 | 11.6 | 0 | 0 | 0 | 1 |
| 35 | rich_3470 | v3 | 0 | test_failure | 62 | 60.5 | 0 | 0 | 1 | 1 |
| 36 | rich_3469 | v3 | 0 | test_failure | 100 | 33.3 | 0 | 4 | 0 | 1 |
| 37 | rich_3052 | v3 | 1 | — | 24 | 8.1 | 1 | 0 | 1 | 0 |
| 38 | rich_3278 | v3 | 0 | test_failure | 99 | 60.4 | 0 | 1 | 0 | 16 |
| 39 | rich_2943 | v3 | 0 | — (bucle) | 8 | 3.2 | 0 | 0 | 0 | 0 |
| 40 | rich_2725 | v3 | 1 | — | 13 | 3.1 | 1 | 0 | 1 | 0 |
| 41 | rich_3105 | v3 | 0 | test_failure | 100 | 37.7 | 1 | 4 | 0 | 1 |
| 42 | rich_3130 | v3 | 0 | test_failure | 89 | 59.8 | 1 | 0 | 1 | 3 |
| 43 | rich_3043 | v3 | 0 | test_failure | 92 | 60.5 | 0 | 0 | 1 | 4 |
| 44 | rich_3067 | v3 | 1 | — | 24 | 12.1 | 1 | 0 | 1 | 0 |
| 45 | rich_3006 | v3 | 1 | — | 16 | 4.5 | 1 | 0 | 1 | 0 |
| 46 | rich_3064 | v3 | 0 | test_failure | 100 | 44.1 | 0 | 1 | 1 | 3 |
| 47 | rich_3063 | v3 | 1 | — | 28 | 14.4 | 1 | 0 | 1 | 1 |
| 48 | rich_3061 | v3 | 1 | — | 38 | 9.2 | 1 | 0 | 1 | 1 |

## 7. Scope and limits

- Everything is **intra-`rich`**; do not extrapolate to the official mixed set.
- Sampling check (2026-10-06): `tasks.jsonl` has 129 tasks (fastapi 67, requests 13, rich 48, httpx 1) and run_03 has all 48 rich — it is a census of the rich segment, not a random sample. Within the run, phases v2/v3a/v3 are temporal cuts (idx 1–21/22–32/33–48), with no randomisation and no repeated tasks. Without a random sample, inference is not appropriate; counts per batch only.
- The breakdown does not change the conclusions of
  `docs/runs/20261006T103737Z/01-audit.md`: they are confirmed (process
  dominates, pre-resolved, hygiene, broken baseline) and the cut by prompt
  version is added, which remains **not attributable**.
