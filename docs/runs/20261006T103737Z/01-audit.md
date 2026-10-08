---
Date: 2026-10-06
Genre: run analysis
Status: superseded-by docs/runs/20261006T103737Z/09-corrections.md
Scope: Full audit of run_03 (48 rich_* tasks): resolution, failure kinds, prompt provenance, patch hygiene and recommendations; it does not cover the fastapi/requests/httpx segments.
Source of truth: runs/20261006T103737Z/ and results/run_03/; read 2026-10-06.
Limits: single-repo census (100% rich_*); descriptive counts, no statistical inference.
---

# Host trial audit `20261006T103737Z` (run_03)

Analysis document. Source: `runs/20261006T103737Z/` (host archive) and
`results/run_03/` (same run, unarchived). It does not modify the submission.

- **Analysis date:** 2026-10-06.
- **Run:** `20261006T103737Z`, backend `gemma-4-31b-it-qat`, `STATUS DONE`.
- **Tasks:** 48, all `Textualize/rich`. Resolved 29, rate **0.604**.
- **Failures:** 19 (`collection_error=2`, `test_failure=14`, `unknown=3`).
- **Cost:** wall 76 151.89 s (1 269.2 min), 2 493 tool calls, `unknown 0`,
  `environment_blocked false`, `missing_modules []`.

## 0. TL;DR

1. **The run is NOT a clean comparison (and it was not an A/B).** Between run_02 and
   run_03 "the prompt did not change to v2": run_02 already ran with **v2**. Moreover, within
   run_03 the prompt changed **two more times** (v2 → v3a → v3) as commits
   landed. The run has three mixed phases and does not allow attributing
   the rate to one prompt. Emilio did not request and does not require an A/B; the descriptive
   comparison between phases that appears in this document is a **suggestion of the
   analysis**, not a requirement, and it is not a statistically rigorous test (see
   `docs/runs/20261006T103737Z/03-failures-by-prompt-version.md`).
2. **47 % of failures are process/budget**, not capability: 6
   timeouts of 60 min, 2 exhaustions of 100 calls and 1 session without `submit_patch`.
3. **There are "resolved" tasks with no code change** (3/29): the patch
   contains only `repro*` files. The real rate with a source fix is ≤ 26/48 =
   **0.542**.
4. **Patch hygiene violated in 26/46 submitted patches**: they include scratch
   files; 1 even came to **modify a test** (`rich_3454`).
5. **Repeated baseline failures unrelated to the patch**: 4 tests of
   `tests/test_console.py` fail identically in ≥ 4 tasks and keep
   failing in `rich_3105`, whose patch does not touch source. There are probably
   non-viable tasks in this environment; a no-patch control is missing.
6. **v3 deleted the strongest rules of v2** (cap of 40 calls, "do not stop at
   analysis", `git status` cleanup), precisely the ones that failed the most in this run.
   Recommendation: do not adopt v3 as is; redesign based on v2.
7. Validating only against `rich_*` is **overfitting**: the improvements proposed below
   are defined over the full set (fastapi/requests/rich/httpx) and validated
   with mixed tasks.

## 0.1 Scope and segments

run_03 is 100 % `Textualize/rich`; therefore this document provides direct evidence
**only for the rich segment**. The inter-segment comparison
(`fastapi_*`, `requests_*`+`httpx_*`) is covered with subagents in parallel
(coordination in `docs/runs/20261006T103737Z/00-tracker.md`). What is transversal and
can be asserted today:

- **The dependency failures were resolved**: run_03 has no
  `ModuleNotFoundError` (run_02 had `inline_snapshot`; run_01,
  `typing_inspection`). The wheelhouse repair worked and is not a current improvement
  axis.
- **The transversal bottleneck is process/latency** (47 % of failures here), not
  model knowledge. It is the first thing to attack in the 4 repos.
- **Patch hygiene and non-regression verification** are transversal and
  apply equally to fastapi/requests/httpx.

## 1. Prompt provenance: the run is contaminated

Method: the `system_instruction` was extracted (first step of each `trace.json`,
ATIF-v1.7) and compared byte by byte against the materialized files.

| Phase | Tasks | UTC window (start) | Identical file | Resolved |
|---|---|---|---|---|
| A | idx 1–21 | 10-05 13:20 → 21:14 | `prompts/system.v2.md` | 15/21 = **0.714** |
| B | idx 22–32 | 10-05 21:24 → 10-06 01:31 | v3 without `code_analyzer` (v3a) | 7/11 = **0.636** |
| C | idx 33–48 | 10-06 02:31 → 10:28 | `prompts/system.v3.md` | 7/16 = **0.438** |

Evidence of the intra-run rotation:

- v3 is committed `d2ce207` on 2026-10-05 17:53 -0300 (20:53 UTC); phase B
  starts 21:24 UTC.
- `code_analyzer` is committed `c5f6331` on 2026-10-05 22:49 -0300 (01:49 UTC
  of 10-06); phase C starts 02:31 UTC.
- The shared checkout materializes the prompt per task; as the tree was edited
  during the run, each task took the version in force at that moment.

Precedents (same methodology):

| Run | Prompt | Tasks |
|---|---|---|
| `20261004T225306Z` (run_01) | `system.legacy.md` | 9 |
| `20261005T050122Z` (run_02) | `system.v2.md` | 13 |
| `20261006T103737Z` (run_03) | v2 (21) + v3a (11) + v3 (16) | 48 |

Also the task set changed: run_01/02 were mixed (fastapi/requests/rich),
run_03 is 100 % rich. Rich overlap between run_02 and run_03: 4 tasks
(`3006` T→T, `3061` F→T, `3063` F→T, `3064` F→F). With n=4 there is no signal.

**Conclusion:** the rate 0.604 is not comparable with 0.333 (run_01) or 0.077
(run_02), and the prompt difference v2→v3 cannot be isolated from the domain
difference or the task order. The per-phase rates (0.714 / 0.636 / 0.438)
suggest that v3 did not help, but they are confounded by order.

## 2. Triage of the 19 failures

Classification by origin. "Process" = the agent did not reach a valid patch due to
budget or loop; "capability" = it submitted a patch and it does not pass.

| Task | Phase | calls | min | submit | kind | Origin |
|---|---|---|---|---|---|---|
| rich_2943 | v3 | 8 | 3.2 | no | — | process: thinking loop without a tool call (8 "continuation_nudge" nudges) |
| rich_3043 | v3 | 92 | 60.5 | no | test_failure | process: timeout 60 min |
| rich_3064 | v3 | 100 | 44.1 | no | test_failure | process: 100 calls |
| rich_3105 | v3 | 100 | 37.7 | yes | test_failure | capability (patch without source) + baseline |
| rich_3130 | v3 | 89 | 59.8 | yes | test_failure | capability: markdown regression |
| rich_3278 | v3 | 99 | 60.4 | no | test_failure | process: timeout 60 min |
| rich_3296 | v3a | 100 | 54.9 | yes | collection_error | infra/environment: import to site-packages |
| rich_3454 | v3 | 68 | 60.5 | no | test_failure | process: timeout (and it modified the test) |
| rich_3468 | v2 | 27 | 9.5 | yes | test_failure | capability: broad patch breaks console |
| rich_3469 | v3 | 100 | 33.3 | no | test_failure | process: 100 calls (patch without source) |
| rich_3470 | v3 | 62 | 60.5 | no | test_failure | process: timeout 60 min |
| rich_3472 | v3a | 100 | 60.5 | no | test_failure | process: timeout (patch without source) |
| rich_3486 | v2 | 100 | 50.5 | yes | unknown | harness: required node did not pass with exit 0 |
| rich_3675 | v3a | 23 | 4.8 | yes | test_failure | capability: partial fix |
| rich_3777 | v2 | 41 | 8.0 | yes | test_failure | capability + getpass baseline |
| rich_3782 | v3a | 35 | 16.2 | yes | collection_error | infra/environment: import to site-packages |
| rich_3942 | v2 | 93 | 60.4 | no | — | process: timeout 60 min |
| rich_4070 | v2 | 100 | 40.1 | yes | test_failure | capability: syntax regression |
| rich_4079 | v2 | 92 | 42.1 | yes | test_failure | capability: partial fix |

Aggregates:

- **Process/budget: 9/19 (47 %).** 6 timeouts (`3043, 3278, 3454, 3470,
  3472, 3942`), 2 call exhaustions (`3064, 3469`), 1 without `submit_patch`
  (`2943`). None of those 9 exhausted calls and time at the same time: the
  timeouts used 62–99 calls in 60 min ⇒ **≈ 35–58 s per tool call**, dominated by
  generation latency (thinking).
- **Capability: 10/19 (53 %).** They submitted a patch and it does not pass. A good
  part of these 10 is also contaminated by baseline failures (§3).
- **There are no dependency failures**: 0 `ModuleNotFoundError` in the 48
  `test_outputs`. The wheelhouse repair (starting from run_02) **did
  work**; the `environment_blocked` of previous runs was resolved.

## 3. Patterns that the aggregate report hides

### 3.1 "Resolved" without a code change (data validity)

Three tasks are marked `resolved: true` with patches that **only add scratch
files**, without touching `rich/*.py`:

| Task | Phase | Patch content |
|---|---|---|
| rich_3180 | v2 | `repro_wrap.py`, `test_len.py` |
| rich_3471 | v3 | `repro_append_tokens.py` |
| rich_3938 | v2 | `repro.py` |

Either the target node already passed in `base_commit` (pre-resolved / mislabeled
task), or the `record` verdict is not reading the correct nodes.
Impact: **real rate with a source fix ≤ 26/48 = 0.542**, not 0.604.

### 3.2 Patch hygiene

Over the 46 submitted patches:

- **26 include scratch files** (`repro*.py`, `test_*.py`, `fix_*.py` at the
  repo root). 13 of those 26 are in resolved tasks: the harness does not
  punish it, but it is noise, it costs tokens and it contradicts the prompt.
- **1 modifies a test**: `rich_3454` includes `tests/test_highlighter.py`
  (explicit hard rule). The harness probably ignores it when re-applying the
  `test_patch`, but it is a direct violation.
- **7 patches do not touch source**: `3105, 3180, 3278, 3469, 3471, 3472, 3938`.
- **Parsing artifact**: the patch of `rich_4075` includes a file with a
  garbage name `repro.py`}<tool_call|><|tool_call>call:run_command{command:...`
  ⇒ the model emitted tool-call syntax inside the content. It is worth
  inspecting the `write_file`/parser path.

### 3.3 Repeated baseline failures (unrelated to the patch)

The same group of 4 tests in `tests/test_console.py` fails identically in
`3043, 3105, 3468, 3470`:

| Test | Error |
|---|---|
| `test_input_password` | `AttributeError: <module 'rich.console' ...> has no attribute 'getpass'` (×6 in total) |
| `test_no_nested_live` | `Failed: DID NOT RAISE LiveError` (×4) |
| `test_size_can_fall_back_to_std_descriptors[True-...]` | `assert (80, 25) == (133, 24)` (×4) |
| `test_capture_and_record` | `assert 'ABC\n' == 'ABC\nHello\n'` (×4) |

The decisive test: `rich_3105` submitted **only `repro.py`** (0 source changes)
and even so those 4 tests fail. That is, **they fail without the patch being
able to cause them** ⇒ baseline/environment. At least a fraction of the
`test_failure` is not attributable to the agent.

Mechanism hypothesis (to be confirmed with a control): the `collection_error` of
`3296` and `3782` import from
`/usr/local/lib/python3.13/site-packages/rich/syntax.py`, not from
`/workspace/rich/syntax.py`. If the installed package is not rebuilt from the
snapshot, there are tests that fail or pass due to the installed version, not the
`base_commit`. It requires verifying how the harness installs/runs.

### 3.4 Thinking loop without action

`rich_2943`: 8 calls, 12 LLM calls, 3 consecutive `continuation_nudge` from the
harness ("Please continue… or call submit_patch"), ended in
`Agent completed execution without calling submit_patch.` The model repeats
analysis (1 700–2 300 chars) without emitting a tool call. Mitigable with prompt
("if there is no tool call, end in submit") and with `thinking_budget`.

## 4. Playbook rectification (`docs/competitive-options-playbook.md`)

Each section is checked against the run_03 evidence. A §11 section is added to
the playbook with the summary; detail below.

### Confirmed

- **§1 "measure before changing"**: correct and now mandatory. This run
  shows that without prompt provenance, without a no-patch control and without separating
  process from capability, the measurement is not interpretable. The `report.json`
  distinguishes `environment_blocked`/`failure_kind` but does **not** distinguish
  `pass_to_pass` regression, a patch without source, or a broken baseline.
- **§1.3 "filter winnable tasks"**: confirmed. There are repeated baseline failures
  (console) and "pre-resolved" tasks; measuring the raw rate mixes in noise. Those
  tasks still need to be marked winnable/non-winnable.
- **§2.3 "`run_command` abuse"**: confirmed. In the 19 failures,
  `run_command` is the dominant tool (up to 57 in `rich_4070`); many
  are reads (`grep`, `cat`) that should be `read_file`/graph.
- **§2.5 "context and truncation / latency"**: confirmed and aggravated. 6/19 failures
  are timeout with <100 calls; the bottleneck is the time per turn, not the calls.
- **§10.4 "broken public tasks"**: confirmed with new evidence (the 4
  console tests; imports to site-packages).
- **§10.2 "evaluator bugs"**: the `rich_3486` case (required node does not pass
  with `exit 0`) is an inconsistent verdict to document.
- **§2.10 / compliance gate**: the gate is at 6/6; keep it.

### Refuted / corrected

- **Premise "only the prompt changed to v2"**: **false**. run_02 was already v2; run_03
  mixed v2/v3a/v3 and changed the domain to pure rich. There is no clean comparison
  (nor an A/B, which was not requested).
- **§2.1 "the prompt is the cheapest lever"**: nuance. In this run, the phase with
  v3 (supposedly improved) performed **worse** (0.438) than v2 (0.714), although
  confounded by order. v3 also **deleted** v2 rules: "Point of no return:
  after about 40 tool calls", "Do not stop at analysis… end every turn with a
  tool call", and the `git diff --name-only`/`git status --short` check. Do not
  adopt v3; redesign from v2.
- **§2.4 analyzer sub-agent**: `code_analyzer` was used little and badly
  (`3105`: 4 calls; `3064`/`3278`: 1) and it **consumes budget** from the main one.
  The risk is confirmed; its `skip_summarization: true` cannot be audited from
  the trace (its reports do not appear).
- **§2.6 `include_thoughts`**: the warning of §10.1 (it could disable
  reasoning) is still unresolved; in `2943` the model "thinks" without acting.
  Treat it as an open risk, not as a safe adjustment.

### Change

- Add to the runner: hash of the materialized prompt in `manifest.json`; install
  and pytest command; `fail_to_pass`/`pass_to_pass` per task;
  node-level `verdict_source`; a warning if a "resolved" task has no source
  hunks; patch hygiene metrics (scratch/tests).
- Add a **no-patch control** task per batch to detect broken baseline
  nodes.
- Reconcile budgets: §0 says "12 h total" and the playbook §2.9 warns
  that 60 min × N does not fit. run_03 needed 1 269 min for 48 tasks; the
  full set (129) does not fit in 12 h with 60 min per task. Lower the per-task
  cap or prioritize latency.

## 5. Proposed improvements (generalized, not only rich)

Goal: raise `resolution_rate` over the whole set of 129 (fastapi/requests/rich/
httpx). Each proposal indicates how it is validated without overfitting to rich.

### 5.1 System prompt (base v2, not v3)

- **Keep v2 and re-add what v3 removed**: explicit exploration cap
  (~40 calls), "do not end a turn without a tool call", `git diff --name-only`
  + `git status --short` cleanup before `submit_patch`.
- **Mandatory verification rule**: before `submit_patch`, run **once**
  the closest test file and paste the result; if a pre-existing test
  breaks, do not submit. It attacks 100 % of the observed `pass_to_pass`
  regressions (console/markdown/syntax).
- **Explicit and verifiable prohibition** of new files outside the package and
  of touching `tests/` (it is already there, but it is not obeyed: add a self-check).
- **Anti-loop**: "if two consecutive tool calls do not change the state, move
  to `edit_file` or `submit_patch`" and "if a search returns nothing, change
  tool".
- **Suggested validation** (suggestion of the analysis, not a user request; without
  statistical rigor): descriptive comparison with fixed prompt, minimum 12–16
  mixed tasks (4 fastapi + 4 requests + 4 rich + 4 httpx) and **a no-patch
  control**.

### 5.2 Skills

- Keep the compaction already done (12 skills, ≤ ~33 lines).
- Add to `verification-before-submit` the step "run the target test file and
  compare `git diff`"; to `patch-hygiene`, the cleanup command.
- Review overlaps and that each step uses only the 9 tools.
- **Suggested validation** (descriptive, not a required A/B): measure skill
  tokens per turn and compare the same batch.

### 5.3 agent.yaml / sub-agents

- Reinforce the `code_analyzer` trigger (only large repos and when the edit site
  cannot be located; require paths+lines+symbol) so as not to spend calls.
- Confirm and document that the sub-agent's calls **are deducted** from the
  main agent's budget.
- **Validation:** count sub-agent calls per task and correlate with
  resolution; target 0–1 uses per task outside large repos.

### 5.4 Pipeline / runner (the highest-return lever today)

- **No-patch control** per batch: detect broken baseline nodes (console,
  imports to site-packages) and exclude them from the rate, or report them separately.
- Record in the archive: hash of the materialized prompt, installed package
  version, install and pytest command, and per-node result
  (`fail_to_pass`, `pass_to_pass`).
- Mark and exclude **pre-resolved** tasks (0 source hunks) from the metric.
- Hygiene metrics: scratch-in-patch, test-file-in-patch, % of patches without
  source.
- **Budget/latency:** lower `thinking_budget` or review `include_thoughts`;
  100 % of the timeouts were due to time, not calls.
- **Validation:** repeat exactly the same batch with the instrumented runner
  and compare the "genuine" rate (with a source fix) against 0.542.

### 5.5 Sampling / latency

- Try a lower `thinking_budget` and measure time per tool call; today 35–58 s/call
  in the tasks that expire.
- Document the effect of `include_thoughts` (§10.1) before trusting it.

## 6. Methodological warnings

- **Do not validate only against `rich_*`**: they are 48 tasks very similar to each other
  (same repo, same test files). Optimizing against them is overfitting;
  the official set is mixed. Any later descriptive comparison
  (suggested by the analysis, not required) should use tasks from the 4 repos.
- **Do not confuse order with effect**: the run phases change prompt
  *and* task; the order is not randomized. An interpretable comparison
  requires a fixed prompt, fixed tasks and a no-patch control; even then it would be
  descriptive, with no formal statistical test.
- **Do not read `resolved` as "the agent fixed it"**: 3/29 did not touch source.

## 7. Commands run (verification)

```sh
# provenance del prompt por trace (ATIF-v1.7, step source=system)
python3 /var/tmp/opencode/audit_promptmap.py
# triage profundo por tarea
python3 /var/tmp/opencode/audit_deep.py
# resumen de fallos por nodo de test
python3 - <<'PY'  # (script inline; ver §3)
...
PY
# gate de cumplimiento
uv run python -m kaggle_gemma_agent.pack submission --check
# -> submission contract OK (6/6 points)
```

Evidence paths:

- `runs/20261006T103737Z/STATUS`, `report.json`, `summary.json`,
  `manifest.json`, `task_results.jsonl` (archive).
- `runs/20261006T103737Z/rich_*/trace.json`, `session.log` (per task).
- `results/run_03/{summary.json,task_results.jsonl,patches/,test_outputs/,traces/,logs/}`
  (unarchived copy).
- `submission/prompts/system.{legacy,v2,v3}.md`,
  `submission/configs/prompt_variant.yaml` (`variant: v3`).
