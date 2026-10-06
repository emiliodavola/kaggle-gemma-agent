---
Date: 2026-10-06
Genre: proposal
Status: open
Scope: Selection decision over all 86 inventory items (which skills to ship and why); it does not build skill-stack/.
Source of truth: docs/skill-stack-inventory.md and AGENTS.md; read 2026-10-06.
Limits: decision record only; no upstream re-fetch and no web.
---

# Skill Stack Evaluation — Selection Proposal (Stage 2)

Status: **PROPOSAL / decision record**. This document decides *what* to build and
*why*. It does **not** create `skill-stack/`; that is the next phase.

Scope and evidence: derived **only** from `docs/skill-stack-inventory.md`
(86 items, 8 gaps) and `AGENTS.md` (Offline sandbox constraint, Harness budgets).
No upstream re-fetch, no web. Numbers in parentheses are inventory IDs.

## A. Hard filters

Every candidate must pass all four before it can be IN:

1. **Offline-safe** — no network calls, no `pip`/`uv add`, no downloads.
2. **No MCP / no background process** — no servers, daemons, watchers, long-running loops.
3. **Tool-mappable** — expressible with the 9 sandbox tools:
   `run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`,
   `write_file`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`.
4. **Context-cheap** — short, procedural, fits the per-skill and total line caps (§D).

Anything that fails 1–3 is OUT of the shipped stack regardless of quality. Items that
are useful off-Kaggle (training / eval / Kaggle tooling) are OUT of `skills/` and, where
noted, preserved as future off-Kaggle docs — never shipped inside `submission.zip`.

## B. Selection table

All 86 inventory items are covered below. The inventory already dedupes some units
(TDD pair #2/#39, skill-creator pair #27/#28, the gh-fix-ci duplicate); those are
evaluated as single rows.

| Inventory item(s) | Verdict | Reason (hard filters) | Rework needed |
|---|---|---|---|
| **Debugging cluster** #1 systematic-debugging, #38 debugging-and-error-recovery, #42 swe.debug, #45 differential-diagnosis | **IN** | Core of Resolution Rate; all offline, tool-mappable; complementary (4-phase loop, root-cause vs guessing, causal-first smallest fix, hypothesis triage). | Merge overlaps into a lean debugging cluster; trim subagent refs; remap shell/test examples to `run_command` + `read_file`; cap each file. |
| #13 debugging-strategies | OUT | 527 lines → context-expensive for a reference already covered by the cluster. | Optional off-line reference only, never shipped. |
| #14 parallel-debugging | OUT | Requires parallel agents (fail filter 2/3). | — |
| #46 grace-fix | OUT | Depends on GRACE contract files that do not exist in the task repos. | — |
| **TDD pair** #2 + #39 | **IN** (one skill) | RED-GREEN-REFACTOR is the patch-generation spine; both offline + pytest-mappable; #39 is the shorter example-led variant. | Scope cycles to the 100-call budget; pytest via `run_command`; drop CI/toolchain refs; merge into one file. |
| #43 swe.unit-test-generation | OUT | Overlaps #20 and the TDD skill; harness resets test files, so generating tests for score is low-value. | Fold any useful template into TDD skill. |
| **Verification gate** #3 verification-before-completion | **IN** | Claim/evidence gate maps directly to `submit_patch`; short and offline. | Remap examples to `run_command`/`get_status`; cap length. |
| **Self-review** #8 requesting-code-review, #18 code-review-excellence, #40 code-review-and-quality | **IN** (one skill) | Pre-submit self-review raises resolve rate; pick the shortest checklist. | Drop reviewer dispatch; sequential self-review before `submit_patch`; condense 529-line #18 if chosen. |
| #17 multi-reviewer-patterns | OUT | Parallel reviewers (fail filter 2/3). | — |
| #32 security-best-practices | OUT | Static security checks do not move Resolution Rate on bugfix tasks; adds context cost. | Optional off-line checklist later. |
| #48 grace-reviewer | OUT | Contract-anchored; no contract files. | — |
| **Planning** #4 writing-plans, #5 executing-plans | **IN** (one light skill) | A short plan-before-edit habit helps budget discipline; offline. | Drop subagent framing, ledger path, PR flow; cap for context. |
| #6 subagent-driven-development, #7 dispatching-parallel-agents, #15 task-coordination-strategies, #16 parallel-feature-development | OUT | All assume subagent/parallel dispatch absent in the sandbox (fail filter 2/3). | — |
| #19 workflow-patterns (conductor) | OUT | Conductor scaffolding + external plan.md/git-notes; heavier than needed. | Optional reference only. |
| #25 notion-spec-to-implementation | OUT | Notion MCP blocked (fail filter 2). | — |
| #37 pr-design-doc | OUT | PR flow does not exist in the sandbox. | — |
| **Issue analysis** #9 brainstorming, #23 define-goal | **IN via Gap #1** | Intent→spec / goal-shaping prose folds into issue localization. | Bounded autonomous variant, no human Q&A; strip goal-tool refs. |
| #10 using-git-worktrees | OUT | Worktree availability in the sandbox is unverified; in-place + diff discipline is safer. | Fallback discipline goes into patch-hygiene. |
| #11 finishing-a-development-branch | OUT as standalone | PR/push flow N/A. | Fold verify+diff-review steps into patch-hygiene / verification gate. |
| **Meta / authoring** #12 writing-skills, #27 skill-creator (openai), #28 skill-creator (anthropics) | OUT of shipped stack | Build-time tooling; not loaded in the sandbox (fail context filter). | Use off-Kaggle while authoring `skill-stack/`; strip Codex/agents refs from #27 if used. |
| **Testing** #20 python-testing-patterns | **IN** | pytest/fixture/mock via `run_command`; directly usable. | Trim to offline patterns; no plugins that need install. |
| #21 e2e-testing-patterns, #29 webapp-testing, #36 e2e-testing | OUT | Browser/runner/Docker dependencies; layering idea already covered. | — |
| #26 playwright, #41 browser-testing-with-devtools, #50 agent-browser | OUT | Browser tooling absent offline (fail filter 1/2). | — |
| #33 jupyter-notebook | OUT | Notebooks are marginal for SWE tasks and add surface. | — |
| **Code search** #22 similarity-search-patterns | OUT | Teaches *building* retrieval; we need *using* the harness search tools. | Logic inverted into Gap #2/#4 skills. |
| **Code graph / planning** #47 grace-plan | OUT | Contract-driven planning; no contract files. | — |
| **Orchestration** #49 sssf | OUT | Deterministic agent/code split + SQLite log; conflicts with the closed harness. | — |
| **Repo nav / history** #44 code-forensics | OUT | Git/log/trace reconstruction is not central; adds context. | Optional fold into repo-mapping if needed. |
| **Frontend** #31 frontend-design, #34 composition-patterns, #35 react-best-practices | OUT | Frontend-only; no backend SWE transfer (fail filter 3). | — |
| #24 gh-fix-ci | OUT | Needs `gh` + Actions + internet (fail filter 1). | Offline diagnosis half is folded into the debugging cluster. |
| **Training / LoRA / RL** #51–#71 (GRPO/RLVR, LoRA, SFT, DPO, PEFT, Unsloth, Axolotl, LlamaFactory, OpenRLHF, NeMo-RL, Gemma Cookbook, smol-course) | OUT of shipped stack | Off-Kaggle training-side; not sandbox-runnable (fail filter 1/2). | Keep as off-Kaggle reference later: #53 method chooser, #54 curation, #60–#63 TRL, #69 PEFT artifact format, #70 Gemma Cookbook. #57 vision mismatch; #67/#68 cluster-only. |
| **Evaluation (off-Kaggle)** #74 lm-eval, #75 SWE-bench, #76 Inspect, #77 MLflow GenAI; #55 eval-harness-first, #58 llm-evaluation, #59 evaluation-methodology | OUT of shipped stack | Eval harnesses need Python/network/server; run off-Kaggle (fail filter 1). | #75 schema (FAIL_TO_PASS/PASS_TO_PASS) and #55 eval-first discipline inform local swegemma runs. |
| **Kaggle tooling** #72 kaggle (local), #73 Kaggle CLI | OUT | Off-Kaggle download/submission tooling; network + token (fail filter 1). | Keep off-Kaggle. |
| #78 nvidia-kaggle-skill, #79 kaggle (shepsci), #80 tabpfn-core, #83 kaggle-autopilot | OUT | Network / cloud API / Kaggle API (fail filter 1). | — |
| #81 kaggle-grandmaster-playbook, #82 tabular-competition | OUT | Tabular-competition methodology, not SWE-agent resolution. | Off-Kaggle methodology note only. |
| #84 adk-skill | OUT | Needs live ADK + API key (fail filter 1). | — |
| #85 a2ui-adk | OUT | UI focus, irrelevant to SWE agent. | — |
| #86 anthropics/skills negative record | OUT | No training skills; kept only to avoid re-sweeping. | — |
| **Gaps #1–#4, #7, #8** (no existing skill) | **IN as new drafts** | Must be built; see §C. | Author from scratch, mapped to the 9 tools. |
| **Gaps #5, #6** (trajectory filtering, QAT tuning) | OUT / deferred | Training-side, off-Kaggle; no verified source. | Defer to off-Kaggle training spike. |

## C. Gap plan (section E of the inventory)

| Gap | Plan | Draft title (stage 2) / defer reason |
|---|---|---|
| 1. Issue-localization procedure | **Close in stage 2** | `issue-localization` — issue → entities → files → functions → lines + ranked hypotheses. |
| 2. Code-graph navigation for harness graph tools | **Close in stage 2** | `code-graph-navigation` — `get_code_neighbors` / `search_similar_code` (symbol queries) / `get_code_subgraph`. |
| 3. Repository exploration / mapping | **Close in stage 2** | `repo-mapping` — first-`read_file` layout → module map → dependency overview. |
| 4. Lexical / symbol search procedure | **Close in stage 2** | `code-search` — grep/definition/call-site discipline before editing (offline). |
| 5. Trajectory filtering / dataset construction | **Defer** | Training-side and off-Kaggle (no network/sandbox); no verified source. |
| 6. QAT-w4a16 tuning guidance | **Defer** | Off-Kaggle training spike; Cookbook has no QAT recipe; separate experiment. |
| 7. Budget-aware tool-use discipline | **Close in stage 2** | `budget-aware-tool-use` — 100 calls / 60 min / 32k; free `submit_patch`/`get_status`. |
| 8. Patch-hygiene skill | **Close in stage 2** | `patch-hygiene` — scratch in `/tmp`, never touch tests/`pytest.ini`/`conftest.py`, `git add -N`. |

## D. Proposed stack (12 skills)

Stack order is a rough priority; each row must respect the line caps in §E.

| # | Skill (working title) | Source | Trim plan | Cap |
|---|---|---|---|---|
| 1 | `issue-localization` | Gap 1 (+#9, #23) | New draft; no human Q&A, bounded hypotheses. | ≤ 60 |
| 2 | `repo-mapping` | Gap 3 | New draft; read-only, no full-tree dump. | ≤ 50 |
| 3 | `code-graph-navigation` | Gap 2 (+ invert #22) | New draft; symbol-first queries, one tool per step. | ≤ 50 |
| 4 | `code-search` | Gap 4 | New draft; ripgrep/symbol discipline via `run_command`. | ≤ 45 |
| 5 | `systematic-debugging` | #1 (+#38, #42) | Trim subagent refs; remap examples; keep 4-phase loop. | ≤ 70 |
| 6 | `differential-diagnosis` | #45 (+#42) | Keep likelihood×severity×cost triage; drop generic prose. | ≤ 55 |
| 7 | `test-driven-development` | #2 + #39 | Merge to one; budget-scoped cycles; pytest via `run_command`. | ≤ 60 |
| 8 | `verification-before-submit` | #3 (+#8/#18/#40) | Merge gate + self-review; drop reviewer dispatch/PR. | ≤ 60 |
| 9 | `python-testing-patterns` | #20 | Trim to offline pytest/fixture/mock. | ≤ 55 |
| 10 | `implementation-planning` | #4 + #5 | One light skill; drop ledger/subagent/PR. | ≤ 45 |
| 11 | `budget-aware-tool-use` | Gap 7 | New draft; call/time/context budget heuristics. | ≤ 50 |
| 12 | `patch-hygiene` | Gap 8 (+#11) | New draft; scratch paths, protected files, diff discipline. | ≤ 50 |

Total target: **≤ 650 SKILL.md lines** across the 12 skills. This is inside the
8–15 cap and leaves headroom below.

## E. Context budget

Assumptions: `max_model_len = 32768`. Every shipped `SKILL.md` loads as read-only
context, so the whole stack competes with the harness prompt, the 9 tool schemas,
conversation, and file excerpts.

- **Per-skill SKILL.md target:** ≤ 60 lines; **hard ceiling 80**.
- **References:** at most one optional reference per skill, ≤ 30 lines; default is none.
- **Frontmatter description:** ≤ 40 words (it is always in context).
- **Total stack cap:** ≤ 650 lines (~7–8k tokens at ~12 tokens/line).
- **Reserved headroom:** ~12k tokens for harness + tools, ~10k for working
  conversation/file excerpts, leaving ≥ 2k slack after the stack.
- **Rule:** any skill that cannot be expressed within its cap is split into a
  referenced sub-file or dropped — never inflated in the always-loaded file.

## F. Non-goals (this phase)

- Do **not** create, move, or edit any `skill-stack/` files — the next phase builds them.
- Do **not** re-fetch or vendor upstream skills; no web.
- No harness runner, adapters, training scripts, `src/` changes, or CI.
- Do not close issue #5; this proposal only *refs* it.
- Do not merge; Emilio merges.
