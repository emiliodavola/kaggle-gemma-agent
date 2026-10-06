---
Date: 2026-10-06
Genre: proposal
Status: implemented in PR #74
Scope: Concrete, copy-paste prompt and skill hardening proposals for the submission across the 129 tasks; it does not modify the harness or any submission file.
Source of truth: docs/tasks/20261006-strategies-*.md, docs/runs/20261006T103737Z/04-harness-messages.md, the run_03 audits and the current submission prompts/skills; read 2026-10-06.
Limits: proposals only; every number is a count from a cited source and unverifiable values are flagged.
---

# Final synthesis of prompt and skill proposals

- **Date:** 2026-10-06
- **Scope:** cross-reference the **129 task summaries** (`docs/tasks/20261006-strategies-*.md`),
  the **harness message catalogue** (`docs/runs/20261006T103737Z/04-harness-messages.md`)
  and the run_03 audits/syntheses, against the submission's **current prompts and
  skills** (`submission/prompts/*.md`, `submission/skills/*/SKILL.md`,
  `submission/sub_agents/code_analyzer.yaml`, `submission/configs/sampling.yaml`).
- **Goal:** produce **concrete, copy-paste** proposals (literal diff) to
  raise the Resolution Rate across the 4 repos, without touching the harness and
  without breaking the compliance gate.
- **Tree state when writing:** `submission/prompts/system.md` ==
  `submission/prompts/system.v3.md` (byte-identical, verified with `diff`),
  selector `variant: v3`, and `pack --check` at **6/6**. **Read-only** document:
  no submission file was modified.

> Reading rule: every number that appears here comes from a cited source document.
> Anything I could not verify is marked **`not verified`**. There is no statistical
> inference: with no randomisation and no repeated tasks, only **counts** are read.

---

## 1. What is fixed and what is ours

The `swegemma` harness is a black box: its nudges, its receipts, its path
rejection and its task-prompt envelope **are not touched**. Everything that can
change lives under `submission/`.

| Aspect | Fixed (harness, not modifiable) | Ours (`submission/`) | Citation |
|---|---|---|---|
| Continuation nudges (2 strings, `max_nudges = 3`) | ✅ 3 fixed strings, chosen by condition | — | `HARNESS_README.md` §5.3 (nudge table) |
| Tool receipts (`status ok/error`, `error_type`, `budget_warning`) | ✅ format and threshold (`calls>=20` and `remaining<=10`) | — | `HARNESS_README.md` §6 (header) |
| Path resolution for `read/edit/write_file` (relative to `/workspace`, rejects `/tmp`) | ✅ | — | `HARNESS_README.md` §6.2 |
| Task-prompt envelope (7 sections) | ✅ | — | `HARNESS_README.md` §5.2 |
| Default budgets (100 calls / 60 min / 500 turns) | ✅ default; can be **declared** within limits | `eval_config.yaml` | `HARNESS_README.md` §7.1 |
| System prompt / sub-agent instructions | — | ✅ `prompts/*.md` | `HARNESS_README.md` §2.2 (`instruction`) |
| Sampling (temperature, top_p, max_output_tokens, thinking) | ✅ allowed fields, range 0–32768 | ✅ `configs/sampling.yaml` | `HARNESS_README.md` §2.4 |
| Skills (`SKILL.md`) | — | ✅ `skills/<dir>/SKILL.md` (12) | `HARNESS_README.md` §2.2 and §2.4 |
| Single base model | ✅ validates `gemma-4-31b-it-qat-w4a16-ct` | ✅ `agent.yaml` | `HARNESS_README.md` §3.2 |
| LoRA adapters (`<3 GiB`, `.safetensors`) | ✅ validates | ✅ `adapters/` | `HARNESS_README.md` §3.4 |
| Compliance gate (6 points a–f) | ✅ immutable | ✅ `src/kaggle_gemma_agent/pack.py` | `AGENTS.md` "Compliance gate" |

**Operational consequence:** the only available levers are the prompt text, the
text of the 12 skills, the sub-agent's `description`/`instruction`, and
`configs/*.yaml`. The prompts and skills load as context on **every turn** (see
`agent.yaml`: "skills/ … auto-loaded as read-only context"), so every new line
costs tokens across the 129 tasks: the proposals **replace** bad text and only
add where the return is measured.

---

## 2. Diagnosis — the gap between what the submission asks and what the 129 tasks + the harness demand

12 gaps, ordered by impact (frequency × cost in the rate). Each one cites a
task id, a harness message type and a count.

### G1 — 47 % of run_03 failures are process/budget, and the current prompt (v3) deleted v2's anti-loop rules
Evidence: the audit classifies **9/19 process failures** (6 timeouts of 60 min:
`rich_3043, 3278, 3454, 3470, 3472, 3942`; 2 exhaustions of 100 calls:
`rich_3064, 3469`; 1 without `submit_patch`: `rich_2943`). The failed ones have a
mean wall of **2421 s vs 1040 s** for the resolved ones and **75 vs 37** tool
calls; `tc≥89` in **12/19 failed vs 1/29 resolved** (`docs/runs/20261006T103737Z/06-segment-rich.md`). **96,5 % of the nudges (389/403)** fire "immediately after a `thinking` turn by the agent WITHOUT a tool call" (`docs/runs/20261006T103737Z/04-harness-messages.md` §1) — the model "talks without acting" and the harness only repeats `Please continue your work…` (T3a, 378×). v2 had `Point of no return: after about 40 tool calls` and `Do not stop at analysis. Until you submit, end every turn with a tool call.`; **v3 removed them** (`docs/runs/20261006T103737Z/03-failures-by-prompt-version.md` §3). The current prompt (v3) has no explicit cap and no turn-closing rule.

### G2 — Time is the bottleneck, not calls: ~35–58 s per tool call and the prompt does not bound reasoning
Evidence: the 6 timeouts used **62–99 calls in 60 min ⇒ ≈ 35–58 s per tool
call**, "dominated by generation latency (thinking)" (audit §2). Mean `thinking`
steps: **38,5 (v2) → 52,2 (v3)** (failures-by-prompt §1). `sampling.yaml`
sets `thinking_budget: 4096` with `include_thoughts: true`. The harness already
has a nudge for the token cut-off (T3b, 25×, byte-identical to T3a — `messages` §1),
but **there is nothing in the prompt** that asks for short reasoning before each
tool call.

### G3 — `pass_to_pass` regressions from not running the target test before submit
Evidence: `verification-before-submit` says "run the nearest regression suite"
but the prompt/workflow only says "run the closest existing test file". Real
cases: `fastapi_15589` (run 2) breaks collection with **SyntaxError** in `utils.py`
because of its own patch (`docs/runs/20261006T103737Z/05-segment-fastapi.md`); `rich_3043`
fixes `_export_format.py` and **7 of `test_console.py` fail**; `rich_3130` and
`rich_4070` introduce regressions in markdown/syntax (`rich segment`). 100 % of the
observed regressions are `pass_to_pass` that a single `pytest <archivo>` would have
detected.

### G4 — Patch hygiene: 26/46 patches with scratch, 1 modifies a test, and 3 "resolved" ones do not touch source
Evidence: of the 46 patches submitted in run_03, **26 include scratch**
(`repro*.py`, `test_*.py`, `fix_*.py`); **1 modifies a test** (`rich_3454` includes
`tests/test_highlighter.py`); **7 do not touch source**, and of those **3 are marked
`resolved:true`** (`rich_3180, 3471, 3938`) ⇒ real rate with a source fix
**≤ 26/48 = 0.542** (audit §3.1–3.2). One patch even brings tool-call syntax
inside the content (`rich_4075`: a file named `repro.py}<tool_call|>...`).

### G5 — The agent does not react to `budget_warning`/`BudgetExceeded` or use `get_status`
Evidence: `get_status` was called **5 times in 48 tasks**, always already with
`tool_calls_remaining: 0` (messages §1 T7). The `BudgetExceeded` receipt
(`Tool call budget exhausted (100 calls)`) only appears explicitly in **2/19
failed** (`rich_3064`, `rich_3469`); the rest "die silently" (messages §3).
`rich_3064` reached 100 calls without submit; `rich_3469` spent 4 calls of
`code_analyzer` with the budget exhausted (messages §3). `budget_warning` exists in
every receipt when `calls>=20` and `remaining<=10` (README §6) and the prompt does
not mention it.

### G6 — Identical-error loops without reaction: `edit_file` accumulates 353 errors over 448 calls
Evidence: `edit_file` **353/448** are errors; **286** are
`old_string not found` (two forms: 286 `{"error":…}` + 67 `status:error`);
`rich_3454` has **72 failed `edit_file`** and `rich_3470` **65**, receiving
dozens of times **the same** error interleaved with **the same** nudge, "with no
escalation, no suggestion, no change of tone" (messages §1 and §3). The prompt
only says "one precise `edit_file` per hypothesis"; there is no protocol for when
the `old_string` does not match.

### G7 — Fixed contradiction: the prompt sends scratch to `/tmp` but `write_file` rejects `/tmp`
Evidence: `write_file` accumulates **79/292** errors; the most cited is
`FileWriteError: Path traversal detected: '/tmp/reproduce_issue.py' escapes
workspace root.` (43 `repro.py` alone + the rest up to 79), followed by cascades of
`No such file …repro*.py` (messages §1). The prompt says "a small script under
`/tmp`" and the fallback "if the tool layer rejects a path outside the repository,
create the file inside it" — which is exactly what produces the 26 patches with
scratch (G4). The tool that **can** write `/tmp` is `run_command`
(README gotcha §10.3 confirms it).

### G8 — Half-plumbed public API: `collection_error` dominates fastapi (78 %) and 4/7 are kwargs at the call site without the callee
Evidence: in the fastapi segment, **collection_error = 7/9 failures (78 %)**; "4/7:
`14978, 14262, 14301, 15588`-partial: new kwarg at the call site but not in the
callee. They do not even reach FAIL_TO_PASS" (`docs/runs/20261006T103737Z/05-segment-fastapi.md`). Cases:
`APIRouter(strict_content_type=…)` with no support in `APIRouter.__init__` (14978),
`Depends(scope=…)` with no constructor (14262), `Router(on_startup=…)` (14301),
`AlAPIRouter`/`Depends` without `scope` (14301). The agent touches the call site it
sees in the test and not the constructor.

### G9 — The tests are the spec: exact names, exact messages and alias vs `validation_alias`
Evidence from the 129 summaries: `fastapi_15588` fails on a **string**, not on
logic (`SSE 'event' must be a single line` vs the message the agent emits);
`fastapi_14258` requires the exact message `Cannot include the same APIRouter
instance into itself. …`; `fastapi_13786` has an **outdated statement** ("the
description is partially outdated — read the test, not the text"); the
`alias` vs `validation_alias` family crosses `14360/14371/15589`; and the
`test_openapi_schema` snapshots are literal (`14791` breaks 28 files if the schema
has one key too many/few) (`docs/tasks/20261006-strategies-fastapi-a.md`,
`-fastapi-b.md`). The prompt does not instruct reading the test that encodes the
behaviour before editing.

### G10 — Environment/baseline failures the patch cannot cause: requests 0/4 and fastapi inline_snapshot
Evidence: `requests` gives **0/4 with correct patches**; the 4 test_outputs are
bit-for-bit identical: 196/197 ERRORs from the **recursive `httpbin` fixture**
(`tests/conftest.py:34 def httpbin(httpbin)` shadows `pytest-httpbin`) and 4
`TestTimeout` from a **cut network** (`OSError Errno 101`) ⇒ "resolved=false
measures the harness, not the fix" (`docs/runs/20261006T103737Z/07-segment-requests-httpx.md`).
`fastapi`: 4/7 collection_error with `missing_modules:['inline_snapshot']`. `rich`:
4 tests of `test_console.py` fail **identically without the patch causing them**
(`rich_3105` sent only `repro.py` and they still fail) (audit §3.3). The agent
spends calls fighting the environment. **Do not confuse this with your own bug**:
the rule must be "record and continue", never "ignore the tests".

### G11 — `run_command` abuse: 231/1099 errors and it is the dominant tool in the failed ones
Evidence: `run_command` 868 ok / **231 error** / 1099 total (messages §1);
"in the 19 failures, `run_command` is the dominant tool (up to 57 in
`rich_4070`); many are reads (`grep`, `cat`) that should be
`read_file`/graph" (audit §4, §2.3). The prompt lists it as "targeted commands
only" but does not forbid `cat`/`grep` of the tree.

### G12 — The `code_analyzer` consumes the main agent's budget and its trigger is loose
Evidence: in v3 it was used **10 calls in 4 tasks** (`rich_3469` 4, `rich_3105` 4,
`rich_3278` 1, `rich_3064` 1) and **all 4 ended in failure** (3 process)
(failures-by-prompt §1/§4). It shares the main agent's budget, so each
unnecessary delegation subtracts verification calls.

---

## 3. Actionable proposals

Each proposal brings: (a) exact file; (b) literal before → after diff; (c) gap
it closes + evidence; (d) cost in tokens and why it is worth paying; (e) how it is
verified (counts, no statistical inference); (f) risk and failure mode.

> **Token funding (do together with P1).** The 12 proposals add
> ≈ **+32 lines** of prompt/skill (≈ **+0,4 k tokens per turn** across the 129
> tasks). To offset, `system.v3.md` trims the `## Skills` section, which repeats
> what each `SKILL.md`'s `description:` already says (which loads anyway):
>
> ```diff
>  ## Skills
> -
> -Load and follow the matching skill in `skills/` at each stage:
> -
> -- `repo-mapping` and `code-search` — first orientation and symbol lookup.
> -- `code-graph-navigation` — `get_code_neighbors`, `get_code_subgraph`,
> -  `search_similar_code` (pass symbols, not prose).
> -- `issue-localization` and `implementation-planning` — locate and plan the fix.
> -- `systematic-debugging` and `differential-diagnosis` — root cause over guessing.
> -- `test-driven-development` and `python-testing-patterns` — targeted tests only.
> -- `patch-hygiene` — scratch under `/tmp`, never touch tests or runner config.
> -- `budget-aware-tool-use` — spend calls intentionally; reserve >=15 for
> -  verification and submission.
> -- `verification-before-submit` — claim must be backed by evidence before submit.
> +Load the matching skill in `skills/` at each stage; each `SKILL.md` states its
> +own trigger:
> +
> +- Orient and localize: `repo-mapping`, `code-search`, `code-graph-navigation`,
> +  `issue-localization`.
> +- Plan and fix: `implementation-planning`, `systematic-debugging`,
> +  `differential-diagnosis`, `test-driven-development`, `python-testing-patterns`.
> +- Guard rails: `patch-hygiene`, `budget-aware-tool-use`,
> +  `verification-before-submit`.
> ```
>
> Trim: **−6 lines**. Net of the package: **≈ +26 lines**. Verified against the
> gate regex (see §5).

---

### P1 — Process budget: 40-call cap and "do not end the turn without a tool call" (recover what v3 deleted)

**(a) File:** `submission/prompts/system.v3.md` (and re-materialise with
`uv run python -m kaggle_gemma_agent.prompt_variant apply --cwd submission`; the
packing does it on its own).

**(b) Literal diff** — `## Non-negotiables` section:

```diff
 ## Non-negotiables
 
 1. Reproduce before fixing: a small script under `/tmp` that fails now and passes
    after your edit.
 2. One hypothesis, one edit. If an edit does not change the reproduction, revert
    it and re-diagnose; never stack edits on a failing guess.
 3. Stop searching once you have the answer. If two read-only commands in a row
    add nothing new, edit or submit.
-4. Before `submit_patch`, byte-compile every changed `.py` file and leave only
-   intended source changes (no scratch files).
-5. Always submit. If you are near the call or time limit, submit the best
-   verified patch; never end a session without `submit_patch`.
+4. Checkpoint at 40 tool calls. Past 40, stop exploring: if the reproduction
+   passes, run the target test and submit; otherwise submit the best source fix.
+5. End every turn with a tool call. Never answer with reasoning alone; if you are
+   stuck, call `get_status` or `submit_patch`.
+6. Before `submit_patch`, byte-compile every changed `.py` file and leave only
+   intended source changes (no scratch files).
+7. Always submit. If you are near the call or time limit, submit the best
+   verified patch; never end a session without `submit_patch`.
```

**(c) Gap:** G1. It closes the hole v3 opened by deleting the "point of no return"
(≈40 calls) and "do not stop at analysis". Evidence: 47 % process failures,
`tc≥89` 12/19 failed vs 1/29 resolved, 96,5 % of nudges after thinking without a
tool call.

**(d) Cost:** **+4 lines** (≈ +52 tokens/turn). It is worth paying because it is
the only change that directly attacks almost half of the measured failures; and
the 2 rules are the ones the telemetry itself identifies as removed.

**(e) Verification (counts):** in the next batch, count (i) tasks with
`exceeded session timeout` and (ii) tasks with 100 calls without `submit_patch`,
and (iii) number of T3a nudges per task (proxy for "thinking without a tool
call"). Compare against run_03's 6 timeouts / 2 exhausted / 9 process. **With no
randomisation and different batches there is no attribution**: it is a before/after
count, not an A/B.

**(f) Risk:** a poorly calibrated cap (40 too early) can make it submit
incomplete patches on 4–11-file tasks (the 15 `Alta` from fastapi-a/b). Failure
mode: `test_failure` rises due to an incomplete patch. Mitigation: the rule only
fires "past 40"; it still allows editing up to the limit if needed.

---

### P2 — Latency: lower `thinking_budget` and ask for short reasoning

**(a) File:** `submission/configs/sampling.yaml` + `submission/prompts/system.v3.md`.

**(b) Literal diff** — `sampling.yaml`:

```diff
 thinking_config:
-  thinking_budget: 4096
+  thinking_budget: 2048
   include_thoughts: true
```

`system.v3.md`, `## Hard rules` section (a bullet is added; anchored on the
no-repeat bullet):

```diff
 - Never repeat an identical command or search; change the identifier, the case,
   or the tool instead.
+- Keep reasoning under a few sentences before each tool call; long thinking
+  burns the wall-clock budget.
 - Keep one action per turn and stay under 500 turns.
```

**(c) Gap:** G2. Evidence: 47 % of failures from time, ≈ 35–58 s/tool call, thinking
steps 38→52. `include_thoughts` is **not touched** because playbook §10.1 flags it
as an open risk (it could disable reasoning); `thinking_budget` is
within the allowed range 0–32768 (README §2.4).

**(d) Cost:** `sampling.yaml` **0 lines** (value change); prompt **+2 lines**
(≈ +26 tokens). It is worth paying because the binding constraint of the measured run is time.

**(e) Verification:** measure **seconds per tool call** in the timeouts and the
count of tasks that expire on time (today 6/48). Compare mean wall of the failed
ones (2421 s) and median (2645 s). **Do not infer** quality improvement from a single batch.

**(f) Risk:** less thinking can lower quality on the 10 capability tasks
(53 %). Failure mode: `test_failure` rises and `timeout` falls. Mitigation: if the
batch shows a drop in resolved, revert to 4096 and try 3072 as a middle point.
It is the easiest change to revert (one line).

---

### P3 — Pre-submit verification: run the target test, compile, clean up and reject diffs without source

**(a) File:** `submission/skills/verification-before-submit/SKILL.md` +
`submission/prompts/system.v3.md`.

**(b) Literal diff** — `verification-before-submit/SKILL.md`, `## Execution Steps`:

```diff
 ## Execution Steps
-1. `run_command` the exact target test verbatim; capture green output.
-2. `run_command` the nearest regression suite; if red, return to `systematic-debugging`.
-3. `run_command git diff --name-only`; revert any scratch, junk, or protected path.
-4. `run_command python -m py_compile <changed .py files>`; any syntax error is a hard stop.
-5. Read the full diff; self-review against the issue.
-6. Only when all checks are green, call `submit_patch`.
+1. Name the target test file from the issue or the nearest test for the changed
+   symbol; `run_command` it verbatim and capture the pass/fail counts.
+2. `run_command python -m py_compile <changed .py files>`; a syntax error is a hard stop.
+3. `run_command git status --short`; delete every untracked scratch file, then
+   `git diff --name-only` and revert scratch, junk, or protected paths.
+4. Confirm the diff has at least one hunk inside the repository package; a
+   scratch-only diff is not a fix, re-localize instead.
+5. Read the full diff; self-review against the issue and the target test.
+6. Only when the target test passes and the diff is source-only, call `submit_patch`.
```

`system.v3.md`, `## Workflow`, step 4:

```diff
-4. Verify: re-run the reproduction, then run the closest existing test file.
+4. Verify: re-run the reproduction, then run the test file named in the issue or
+   the nearest test for the changed symbol; read its pass/fail counts. If an
+   existing test regresses, revert that edit before continuing.
```

**(c) Gap:** G3 + G4. Evidence: `pass_to_pass` regressions (`fastapi_15589`
SyntaxError, `rich_3043`, `rich_3130`, `rich_4070`); 26/46 patches with scratch; 3
"resolved" without touching source (`rich_3180, 3471, 3938`).

**(d) Cost:** skill **+6 lines**, prompt **+1 line** (≈ +91 tokens). It is worth
paying because the "run the target test" step is exactly what is missing in the
measured regressions, and the "source-only" check catches the scratch-only patches
that inflate the rate today.

**(e) Verification:** count (i) resolved tasks with **≥1 source hunk** (must
exceed 26/48), (ii) patches with scratch (today 26/46), (iii) patches that touch
`tests/` (today 1), (iv) `pass_to_pass` broken per node. The archiver (`harness_runs.py`)
already reads `FAIL_TO_PASS`/`PASS_TO_PASS` from the JUnit; expose the count per node.
**Do not attribute** the difference to P3 alone if the batch changed.

**(f) Risk:** mandatory verification consumes calls (today we reserve ≥15). If
the target is not clear, it can induce a loop of "run the test, it fails,
edit again" and expire on time (the fail mode we already saw). Mitigation:
the phrase "only when the target test passes … call submit_patch", with P1's rule
(40 cap) as a safety net.

---

### P4 — Reactive budget: use `get_status` and react to `budget_warning`/`BudgetExceeded`

**(a) File:** `submission/skills/budget-aware-tool-use/SKILL.md` +
`submission/prompts/system.v3.md`.

**(b) Literal diff** — `budget-aware-tool-use/SKILL.md`, `## Hard Rules`:

```diff
 ## Hard Rules
 - Reserve >=15 calls for verification and submission; do not exhaust the budget exploring.
-- `submit_patch` and `get_status` are free: call `get_status` whenever unsure.
+- `submit_patch` and `get_status` are free: call `get_status` at the 40-call
+  checkpoint and again before `submit_patch`.
+- On `budget_warning` or `BudgetExceeded`, stop exploring at once and submit the
+  best verified source fix; `submit_patch` still works after the call budget is
+  spent.
 - Batch reads; never re-read an unchanged file; prefer `search_similar_code` and `get_code_neighbors`.
```

`system.v3.md`, `## Hard rules` (new bullet, anchored before "Keep one action"):

```diff
 - Never repeat an identical command or search; change the identifier, the case,
   or the tool instead.
+- If a tool response contains `budget_warning`, or `get_status` shows at most 15
+  calls or 10 minutes left, stop exploring and submit the best verified fix.
 - Keep one action per turn and stay under 500 turns.
```

**(c) Gap:** G5. Evidence: `get_status` 5/48 tasks, always with
`remaining:0`; textual `BudgetExceeded` only in 2/19 failed; `rich_3064` at 100
calls without submit. The threshold coincides with the harness's (README §6:
`calls>=20` and `remaining<=10`).

**(d) Cost:** skill **+3 lines**, prompt **+2 lines** (≈ +65 tokens). It is worth
paying because the hole "I reached 100 calls without submit" is 100 % avoidable with a free
probe that is barely used today.

**(e) Verification:** count calls to `get_status` per task (today ~0,1/task) and
silent `BudgetExceeded` receipts (tasks that reach 100 calls without submit,
today 2/48). **Do not infer** a causal relationship with the rate from small n.

**(f) Risk:** `get_status` is free but **takes a turn**; combined with P1's
cap it could push it to submit before having a fix. Failure mode:
`test_failure` due to an incomplete patch if the agent uses "remaining≤15" as an excuse
not to verify. Mitigation: the phrase requires "best verified fix", not "any fix".

---

### P5 — Failed `edit_file` loop: protocol after two identical failures

**(a) File:** `submission/prompts/system.v3.md`.

**(b) Literal diff** — `## Hard rules` (new bullet, anchored on the first one):

```diff
 ## Hard rules
 
 - Never modify tests, `conftest.py`, `pytest.ini`, or runner config.
+- `edit_file` needs the exact current text. If `old_string not found` or a missing
+  parameter error repeats twice, stop guessing: `read_file` the exact region, copy
+  the verbatim lines into `old_string`, or `write_file` the whole file. Never send
+  the same `old_string` a third time.
 - Keep scratch files out of the patch. Prefer `/tmp`; if the tool layer rejects a
```

**(c) Gap:** G6. Evidence: `edit_file` 353/448 errors, 286 `old_string not
found`; `rich_3454` 72 failed and `rich_3470` 65, with the harness repeating the
same error + the same nudge. The harness **never** escalates; the only way out is for
the agent to change strategy.

**(d) Cost:** **+4 lines** (≈ +52 tokens). It is worth paying because it is the #1 error of the run
(353 of 448 `edit_file`) concentrated in 2 tasks that burned 60 min.

**(e) Verification:** count `edit_file`/`old_string not found` errors per task and
the maximum per task (today 72). Compare against 286 total and the peak of 72.
**Do not attribute** from a single task.

**(f) Risk:** `write_file` overwrites the whole file; a hasty `write_file`
can lose code. Failure mode: `pass_to_pass` broken by a truncated file.
Mitigation: the protocol prioritises `read_file` + copying verbatim, and
`write_file` remains a last resort.

---

### P6 — Scratch: create it with `run_command` in `/tmp`, never with the file tools

**(a) File:** `submission/prompts/system.v3.md` +
`submission/skills/patch-hygiene/SKILL.md`.

**(b) Literal diff** — `system.v3.md`, `## Workflow`, step 2:

```diff
-2. Reproduce: write a minimal script under `/tmp` and run it with `python3`
-   against the edited tree.
+2. Reproduce: create the scratch script with `run_command` shell redirection
+   under `/tmp` (for example `run_command` with `python3 - <<'PY'`), then run it
+   with `python3` against the edited tree. `write_file`, `edit_file`, and
+   `read_file` resolve paths inside `/workspace` only and reject `/tmp`.
```

`patch-hygiene/SKILL.md`, `## Hard Rules`, first bullet:

```diff
-- Scratch files and logs go in `/tmp`, never in `/workspace`.
+- Scratch files and logs go in `/tmp`, never in `/workspace`. Create them with `run_command` shell redirection; the file tools resolve paths inside `/workspace` only and reject `/tmp`.
```

**(c) Gap:** G7 (+ reinforces G4). Evidence: `write_file` 79/292 errors; the
`Path traversal detected: '/tmp/…'` is 43+ identical clashes; cascades of
`No such file`. The README (gotcha §10.3) confirms that the correct path for `/tmp`
is `run_command`. The file tools, moreover, must be used only on `/workspace`.

**(d) Cost:** prompt **+2 lines**; skill **+0 lines** (replacement, same line
made longer) (≈ +26 tokens). It is worth paying because it removes the cause of dozens of identical
errors and of the `No such file` cascades.

**(e) Verification:** count `FileWriteError`/`Path traversal` errors
(today 79 `write_file`) and `No such file` receipts from `repro*`. Expected: strong drop.
**Do not infer** quality from one batch.

**(f) Risk:** `run_command` with a heredoc can fail on special characters;
robust alternative: `printf '%s\n' '…' > /tmp/x.py`. Failure mode: the agent
goes back to `write_file` and repeats the error. Mitigation: the prompt names **both**
file tools that reject `/tmp`, so there is no ambiguity.

---

### P7 — Public API plumbing: add the kwarg/alias at the definition site and grep the call sites in the same step

**(a) File:** `submission/skills/implementation-planning/SKILL.md`.

**(b) Literal diff** — `## Hard Rules` (new bullet):

```diff
 ## Hard Rules
 - Plan is short: <=7 steps, each one edit or one command.
 - Keep the plan inline in the turn; no repo files, no ledger, no subagents.
+- Add or rename a public keyword, parameter, alias, or error message at the
+  definition site and grep every call site in the same step; a half-plumbed
+  keyword breaks test collection.
 - Re-plan only when a step fails.
```

**(c) Gap:** G8. Evidence: fastapi `collection_error` 78 %; 4/7 from a kwarg without
a callee (`14978` `strict_content_type`, `14262` `scope`, `14301` `on_startup`).
The agent edits the call site the test shows it and not the constructor.

**(d) Cost:** **+3 lines** (≈ +39 tokens). It is worth paying because it is the dominant cause
of the worst segment (fastapi 1/10) and turns a collection failure (0 tests
run) into a real fix.

**(e) Verification:** count `collection_error` failures in fastapi (today 78 % of its
failures) and `TypeError … unexpected keyword argument`. **Do not infer** from 7 tasks.

**(f) Risk:** adding the kwarg at the definition site without keeping compatibility can
break existing signatures (fastapi's gold does it with defaults). Failure mode:
new `collection_error` from signatures. Mitigation: the bullet asks for "definition site +
all call sites", which is the shape of the gold.

---

### P8 — The tests are the spec: exact names, strings and aliases

**(a) File:** `submission/skills/issue-localization/SKILL.md`.

**(b) Literal diff** — `## Hard Rules` (new bullet):

```diff
 ## Hard Rules
 - Never edit before the target is localized to a file and symbol.
 - Bounded, not exhaustive: at most 3 ranked hypotheses.
 - Extract entities from the issue only; never invent files, symbols, or APIs.
+- The tests are the spec: before editing, read the test that asserts the new
+  behaviour and use its exact symbol names, message strings, status codes, and
+  aliases verbatim; when issue text and test disagree, the test wins.
 - Cap this phase at ~10 calls; `submit_patch` and `get_status` are free (see `budget-aware-tool-use`).
```

**(c) Gap:** G9. Evidence: `fastapi_15588` (exact message `SSE 'event' must be a
single line`), `fastapi_14258` (exact message of the assert), `fastapi_13786`
(outdated statement: "read the test, not the text"), the
`alias`/`validation_alias` family (`14360/14371/15589`), literal snapshots
(`14791` breaks 28 files).

**(d) Cost:** **+3 lines** (≈ +39 tokens). It is worth paying because many fastapi/rich
failures are not about logic but about an exact string/name: without reading the test, the
agent gets the fix right and fails the assertion.

**(e) Verification:** count failures from "message mismatch"/string `assert`
(today: `15588` ×2, `14479`, `14258`) and snapshot regressions. **Do not infer**
from one batch.

**(f) Risk:** "read the test before editing" consumes localization calls; if
the test does not exist in the snapshot, the agent wastes time looking for it. Failure
mode: fewer calls to edit. Mitigation: the bullet says "the test that asserts
the new behaviour"; if there is none, the rule does not apply.

---

### P9 — Separate your own bug from the environment: do not chase environmental failures

**(a) File:** `submission/skills/systematic-debugging/SKILL.md`.

**(b) Literal diff** — `## Hard Rules` (new bullet, at the end):

```diff
 - After two failed fixes, stop and re-diagnose (see `budget-aware-tool-use`).
 - Do not edit tests or protected files; respect `patch-hygiene`.
+- Separate your bug from the environment: if the target test fails for a missing
+  plugin or module, an unreachable endpoint, or a TTY, that failure is not yours.
+  Record it, spend at most two calls on it, keep your source fix, and submit.
```

**(c) Gap:** G10. Evidence: `requests` 0/4 with **correct** patches (recursive
`httpbin` fixture + `Errno 101`); `fastapi` 4/7 with `inline_snapshot`;
`rich_3105` fails the 4 tests of `test_console.py` **without touching source** (broken
baseline). The agent spends calls against the environment. **The rule does NOT say ignore tests**:
it says distinguish the failure the patch cannot cause and continue.

**(d) Cost:** **+4 lines** (≈ +52 tokens). It is worth paying because environmental failures
represent 100 % of the requests segment and 4/7 of fastapi; each call spent there
is one less call to verify your own fix.

**(e) Verification:** count (i) tasks with `infra_error:true`/`missing_modules` and
(ii) their wall/calls (today requests 34–65 calls without being able to resolve). Compare against
the batch. **Do not conclude** a rate improvement on environmental tasks: they are
unsolvable by definition in the public environment.

**(f) Risk:** an agent that "does not chase the environment" can declare a
failure environmental that **was** its own and submit a broken patch. Failure mode: `test_failure`/regression
rises. Mitigation: require "spend at most two calls" and "keep your
source fix" — not an abandonment of verification; and the per-batch no-patch control
(§6) marks which nodes are broken at baseline.

---

### P10 — `run_command` discipline: `read_file` to inspect

**(a) File:** `submission/skills/code-search/SKILL.md`.

**(b) Literal diff** — `## Hard Rules` (new bullet):

```diff
 ## Hard Rules
 - Search inside `/workspace` only; exact identifiers, not descriptions.
 - One concern per call; never repeat the same broad query twice.
+- Use `read_file` to inspect source; `run_command` is for tests, byte-compile,
+  and one `rg -n "symbol"` per query. Never `cat` a file or `grep` the tree.
 - Never `find /` or dump huge output.
```

**(c) Gap:** G11. Evidence: `run_command` 231/1099 errors and the dominant tool
in the failed ones (up to 57 in `rich_4070`), many times `grep`/`cat` that should
be `read_file`.

**(d) Cost:** **+2 lines** (≈ +26 tokens). It is worth paying because `run_command` is the
tool with the most errors and the current prompt does not forbid `cat`/`grep` of the tree.

**(e) Verification:** count `run_command` per task and its error ratio per task
(today 231/1099 global). **Do not infer** from global counts without separating read-only
from test.

**(f) Risk:** forbidding `cat` too strongly can push toward a truncated
`read_file` (150 lines) on large files, losing context. Failure mode:
edits over badly read regions. Mitigation: `rg -n` is still allowed to
locate, and `read_file` accepts `start_line`/`end_line`.

---

### P11 — `code_analyzer` trigger: only after two failed searches of your own

**(a) File:** `submission/sub_agents/code_analyzer.yaml` +
`submission/prompts/system.v3.md`.

**(b) Literal diff** — `code_analyzer.yaml`:

```diff
-description: Localizes the exact code to change in a large repository when the edit site is unclear. Returns ranked file:line suspects and the verbatim symbol signature. Does not fix code.
+description: Localizes the exact code to change only when two of your own targeted searches failed to find the edit site in a large repository. Returns ranked file:line suspects and the verbatim symbol signature. Costs your call budget; call at most once.
```

`system.v3.md`, `## Tools`, sub-agent bullet:

```diff
-- `code_analyzer` sub-agent — localizes code in a large repository when the edit
-  site is unclear; it shares your call budget, so delegate at most once.
+- `code_analyzer` sub-agent — localizes code in a large repository only after two
+  targeted searches fail; it shares your call budget, so delegate at most once.
```

**(c) Gap:** G12. Evidence: in v3, 10 calls in 4 tasks and **all 4 failed**
(3 process) (failures-by-prompt §1/§4). It shares the main agent's budget.

**(d) Cost:** **0 net lines** (replacement of a description and a bullet; the
sub-agent's `description` is passed to the parent when delegating). It is worth paying because it avoids
burning verification calls.

**(e) Verification:** count calls to `code_analyzer_agent` per task (today 1–4 in
the ones that use it, 5 tasks) and their correlation with resolution. **Do not infer** from
n=4 (failures-by-prompt itself calls it "anecdote, not evidence").

**(f) Risk:** hardening the trigger can make large, unknown repos
(httpx `_parsers.py` with two implementations) not be delegated and the main agent
end up unable to localize the site. Failure mode: more exploration calls by the
main agent. Mitigation: the condition is "two targeted searches fail", not "never".

---

## 4. What NOT to do

- **Do not overfit to `rich_*`.** run_03 is 100 % rich, but the 129 span 4
  repos with different families: fastapi (2/3 surgical fixes in
  `dependencies/utils.py`/`_compat/v2.py`), requests (bit-for-bit determinism and
  the `hasattr` family), rich (console/markdown/syntax clusters), httpx (1 task,
  never run). Validating only with rich is overfitting (audit §6).
- **Do not go back to v3 as it is.** v3 scored 7/16 (0.438 raw) with no attribution, and
  **deleted** v2 rules. Do not adopt v3 as "the improvement"; redesign from v2 and
  re-measure descriptively (audit TL;DR #6, failures-by-prompt §3).
- **Do not touch the harness.** Nudges, error strings, `/tmp` rejection, envelope,
  gates and harness budgets are immutable. No proposal in this doc modifies them
  (see §1).
- **Do not write rules the gate forbids.** The regex
  `https?://|socket|urllib|requests\.|pip install|uv add|mcp|subprocess|\bcurl\b|\bwget\b`
  (`IGNORECASE`) matches in **any** file under `submission/`, prompts and
  skills included. **A prohibition also breaks the gate**: writing "do not use
  `http://`" or "do not run `pip install`" inside the prompt makes rule e fail.
  Every proposal in §3 was verified against the regex (see §5).
- **Do not block the broken-environment diagnosis.** No rules that obscure
  infrastructure failures (broken baseline, `inline_snapshot`, `httpbin` fixture,
  `Errno 101`): the agent must **be able to name them**. It is forbidden to propose
  "ignore the tests that fail weirdly" or "do not look at the environment"; P9 says the opposite
  (record and continue, without abandoning verification).
- **Do not ask for an A/B or p-values.** Emilio did not ask for it and it is not applicable: confounded
  phases, no randomisation, no repeated tasks. Counts per batch only.
- **Do not add skills or touch `agent.yaml`/`eval_config.yaml` by reflex.**
  The gate requires **exactly 12 skills** (rule b) and budgets ≤ 100/60/500 (rule d).
  No proposal adds or removes skills.

---

## 5. Compliance checklist

Each proposal × file × does it break the `FORBIDDEN_PATTERNS` regex? × does it respect the 12
skills? × is it within the budgets?. All the "after" blocks in §3 were
scanned with the gate's exact regex: **0 matches**.

| # | File(s) | Does it break the regex (rule e)? | Does it respect 12 skills (rule b) / single model (rule c)? | Is it within budgets (rule d / sampling)? |
|---|---|---|---|---|
| P1 | `prompts/system.v3.md` | **No** (verified) | Yes; adds no skills or models | Does not touch budgets |
| P2 | `configs/sampling.yaml`, `prompts/system.v3.md` | **No** (verified) | Yes | `thinking_budget: 2048` ∈ [0, 32768] (README §2.4) |
| P3 | `skills/verification-before-submit/SKILL.md`, `prompts/system.v3.md` | **No** (verified) | Yes (same skill, same dir) | Does not touch budgets |
| P4 | `skills/budget-aware-tool-use/SKILL.md`, `prompts/system.v3.md` | **No** (verified) | Yes | Does not touch budgets |
| P5 | `prompts/system.v3.md` | **No** (verified) | Yes | Does not touch budgets |
| P6 | `prompts/system.v3.md`, `skills/patch-hygiene/SKILL.md` | **No** (verified) | Yes | Does not touch budgets |
| P7 | `skills/implementation-planning/SKILL.md` | **No** (verified) | Yes | Does not touch budgets |
| P8 | `skills/issue-localization/SKILL.md` | **No** (verified) | Yes | Does not touch budgets |
| P9 | `skills/systematic-debugging/SKILL.md` | **No** (verified) | Yes | Does not touch budgets |
| P10 | `skills/code-search/SKILL.md` | **No** (verified) | Yes | Does not touch budgets |
| P11 | `sub_agents/code_analyzer.yaml`, `prompts/system.v3.md` | **No** (verified) | Yes; `model:` remains single (`gemma-4-31b-it-qat-w4a16-ct`) | Does not touch budgets |
| Funding. | `prompts/system.v3.md` (trim of `## Skills`) | **No** (verified) | Yes | Does not touch budgets |

**Final verification (mandatory, after applying):**

```sh
uv run python -m kaggle_gemma_agent.pack submission --check
# esperado: submission contract OK (6/6 points)
```

Also suggested, so that the next run does not mix variants again (run_03
ran v2+v3a+v3):

```sh
uv run python -m kaggle_gemma_agent.prompt_variant apply --cwd submission
uv run python -m kaggle_gemma_agent.prompt_variant show  --cwd submission
# esperado: variant: v3 -> prompts/system.v3.md | prompts/system.md: in sync
sha256sum submission/prompts/system.md
```

---

## 6. Validation plan

**Goal:** measure the package (P1–P11) with counts, without statistical attribution.

1. **Fixed prompt + hash.** A single `system.md` for the whole batch (applied with
   `prompt_variant apply`), and record `sha256sum submission/prompts/system.md`
   in `runs/<UTC>/manifest.json`. run_03 mixed v2/v3a/v3 because the shared
   checkout materialised the prompt while commits landed; the hash prevents
   repeating that.
2. **Mixed batch** (not 100 % rich): 4 fastapi + 4 requests + 4 rich (=12), with
   tasks that failed in run_03 and with representation of each family:
   `fastapi_15588, fastapi_14978, fastapi_14301, fastapi_14262`,
   `requests_7502, requests_7505, requests_6644, requests_7315`,
   `rich_3064, rich_3130, rich_3105, rich_3454`.
3. **No-patch control per batch.** Run **one** task of the batch with
   `--skip-agent-patch` (README §9.1) to detect broken baseline nodes: we already
   know that 4 tests of `test_console.py` and the imports into `site-packages`
   (`rich_3296/3782`) fail without the patch causing them, and that requests has the
   recursive `httpbin` fixture.
4. **Counts to compare** (against run_03):
   - resolved **with ≥1 source hunk** (run_03: 26/48 = 0.542; raw 29/48);
   - **process** failures (timeouts + budget + no-submit): run_03 = 9/19;
   - mean/median wall and mean/median tool calls of the failed (2421 s / 75) vs
     resolved (1040 s / 37);
   - patches with scratch (26/46) and that touch `tests/` (1/46);
   - `pass_to_pass` broken per node;
   - `write_file`/`Path traversal` errors (79) and `edit_file old_string not found`
     (286); peak of `edit_file` per task (72);
   - calls to `get_status` (5/48) and to `code_analyzer_agent`.
5. **What NOT to conclude.**
   - It is **not** an A/B: with no randomisation or repeated tasks there is no attribution; batch
     differences confound the effect (failures-by-prompt §0).
   - Do **not** generalise from the 12 to the 129 or from the public set to the hidden one (there is
     "domain shift", playbook §10.4).
   - Do **not** read `resolved` as "the agent fixed it" (3/29 without touching source).
   - **No** p-values or intervals: counts per batch and n only.
6. **Runner instrumentation (not the harness, does not score).** Add to the local
   archiver: node-level `verdict_source` (JUnit already exists), a warning if a
   "resolved" task has no source hunks, scratch/test-file metrics in the patch,
   and the prompt hash. This does not change the official score; it changes what can be
   read from the run.

---

## 7. Ratification / rectification of the playbook

`docs/competitive-options-playbook.md`.

### Ratified
- **§0 / §1 "measure before changing"** — confirmed and now mandatory: without
  prompt provenance, no-patch control and process/capability separation, the
  metric is not interpretable (audit §4).
- **§1.3 "filter winnable tasks"** — confirmed: broken baseline and unsolvable by
  environment (console, `inline_snapshot`, `httpbin`).
- **§2.2 "skills, remove overlaps"** — confirmed; the 469→322-line pruning
  and the §3 token trim are ratified.
- **§2.3 "`run_command` abuse"** — confirmed: 231/1099 errors and dominant in
  failed.
- **§2.5 "context and truncation / latency"** — confirmed and worsened: 47 % of failures
  from time.
- **§2.7 "pre-submit verification"** — confirmed; P3 extends it to "run the
  target test".
- **§2.10 "packaging and gate"** — ratified: gate at 6/6.
- **§10.1 "~14 k context"**, **§10.4 "broken public tasks"** — ratified with
  new evidence.
- **§10.9** — ratified in full (it is the run_03 rectification).

### Rectified
- **§2.1 "the prompt is the cheapest lever"** → nuance: in run_03 phase v3
  scored worse (0.438) than v2 (0.714), confounded by order. The prompt is still
  cheap, but **not** "v3 improved": redesign from v2 (audit §4, come-off).
- **§2.4 "analyzer sub-agent"** → rectified: the `code_analyzer` was used little and
  badly and **consumes budget**; in v3, 4 tasks used it and all 4 failed (P11).
- **§2.6 "sampling"** → partially rectified: `include_thoughts` is an open risk
  (§10.1), so only lowering `thinking_budget` is proposed, not touching it (P2).
- **§7 "roadmap"** → rectified: the lever with the highest measured return is
  **process/latency** and **runner** (audit §5.4), not training.

---

## Appendix — traceability of the proposals

| Proposal | Gap | Main evidence |
|---|---|---|
| P1 | G1 | audit §2 (9/19 process); messages §1 (389/403 nudges after thinking without a tool call); failures-by-prompt §3 (v3 removed rules) |
| P2 | G2 | audit §2 (35–58 s/call); failures-by-prompt §1 (thinking 38→52) |
| P3 | G3, G4 | audit §3.1–3.2; fastapi segment (`15589` SyntaxError); rich segment (`3043/3130/4070`) |
| P4 | G5 | messages §1/§2/§3 (get_status 5/48; BudgetExceeded 2/19) |
| P5 | G6 | messages §1/§3 (edit_file 353/448; 286 old_string; 72/65 per task) |
| P6 | G7 | messages §1 (write_file 79/292; `Path traversal '/tmp'`); README gotcha §10.3 |
| P7 | G8 | fastapi segment (collection_error 78 %; 4/7 kwarg without callee) |
| P8 | G9 | strategies fastapi-a/b (`15588`, `14258`, `13786`, `14371`, `14791`) |
| P9 | G10 | requests-httpx segment (0/4 environmental); audit §3.3 (console) |
| P10 | G11 | messages §1 (run_command 231/1099); audit §4/§2.3 |
| P11 | G12 | failures-by-prompt §1/§4 (10 calls in 4 tasks, 4 failures) |
