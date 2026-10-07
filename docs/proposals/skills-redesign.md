---
Date: 2026-10-06
Genre: proposal
Status: open
Scope: Proposal to redesign the 12 shipped submission skills so they are hypercompact and non-overlapping; it does not touch dev or OpenCode skills.
Source of truth: docs/skill-stack-inventory.md, docs/proposals/skill-stack-evaluation.md and submission/skills/; read 2026-10-06.
Limits: proposal only, not implemented; based on measured line counts at the time of writing.
---

# Proposal: hypercompact submission skills

Decision document. Not implemented. Written to be reviewed and then decided.

## 1. Objective

Redesign the **12 submission skills** (`submission/skills/<name>/SKILL.md`)
so they are **hypercompact and at the same time super descriptive**, without
breaking rule b (exactly 12) or rule e (forbidden tokens).

## 2. What the skills are here (and which ones we do NOT touch)

There are three classes of "skill" in the repo. This proposal is only about the first one:

1. **Submission skills** (`submission/skills/`, 12) → loaded by the agent in
   the evaluation, **every turn**, as read-only context. **This is the one
   we redesign.**
2. Development skills (`.agents/skills/`, 28 probabl) → ML tooling, not
   shipped. Out of scope.
3. OpenCode skills (`~/.config/opencode/skills/`) → development agent
   workflow. Out of scope.

## 3. Current state (measured)

| | Value |
|---|---|
| Skills | 12, each with a **single** `SKILL.md` (no scripts, no references) |
| Total | **469 lines / ~19.5 KB ≈ 5.6k tokens** |
| Effective window | ~14.3k tokens (playbook §10.1) → the skills are **~40% of the working context** |
| Caps from `docs/proposals/skill-stack-evaluation.md` | ≤60 per skill (ceiling 80), total ≤650 |
| Reality | all ≤54 lines; the total is 72% of the cap → **the problem is not length, it is overlap** |

### Concrete overlaps (rules repeated in 2+ skills)

| Duplicated rule | Skills |
|---|---|
| "do not touch tests/`conftest.py`/`pytest.ini`" | systematic-debugging, python-testing-patterns, patch-hygiene, verification-before-submit |
| "scratch in `/tmp`, never in the repo" | TDD, python-testing-patterns, patch-hygiene, verification-before-submit |
| "`submit_patch`/`get_status` are free" | budget-aware-tool-use, issue-localization |
| "run `run_command` and verify" | TDD, python-testing-patterns, systematic-debugging, implementation-planning, differential-diagnosis |
| "review the diff / scope" | patch-hygiene, verification-before-submit |
| "reproduce once" | systematic-debugging, differential-diagnosis |
| symbol search | code-search, code-graph-navigation, repo-mapping, issue-localization |

### Other findings

- **`skill-stack/` is a stale mirror.** `pack.py` only packages
  `submission/skills/`. `verification-before-submit` has already diverged (v1.0
  in `skill-stack/` vs v1.1 in `submission/`). The README (`:67`) claims they are
  copied, and that is not the case.
- **Rule e clean** in all 12 (zero forbidden tokens).
- **No scripts** in any of them: compacting is pure text (and avoids the
  `run_skill_script` bug, playbook §10.2).

## 4. Design principles (hypercompact + descriptive)

1. **One owner per rule.** Each rule lives in **one** skill; the others
   reference it by name, they do not repeat it.
2. **Single, actionable trigger** on the `description:` line (format
   `Trigger: <when>`), ≤20 words.
3. **Target ≤40 lines** per skill (ceiling 60). Target total **≤350 lines**
   (today 469) → saving ~1.4k tokens/turn.
4. **Tool-mapped**: each step names only the 9 tools; no MCP, no network,
   no processes.
5. **At most one differentiating table**, only if it is not in another skill
   (DD scoring, graph decision table, pytest patterns).
6. **No scripts** and no extra files: only `SKILL.md`.
7. **Descriptive = executable steps**, not prose. Short, imperative sentences.

## 5. Proposal: the 12 skills (same name, sharpened scope)

| # | Skill | Trigger (one line) | Owner of | Tools | Lines today → target |
|---|---|---|---|---|---|
| 1 | `repo-mapping` | unknown repo or the fix crosses modules | initial orientation | run_command, read_file, get_code_subgraph | 33 → 28 |
| 2 | `code-search` | find definitions, call sites or config keys | exact textual search | run_command, read_file | 31 → 24 |
| 3 | `code-graph-navigation` | callers, definitions, similar symbols | graph search | get_code_neighbors, search_similar_code, get_code_subgraph, read_file | 40 → 32 |
| 4 | `issue-localization` | issue/traceback → suspects | what and where | run_command, search_similar_code, read_file, get_code_neighbors | 42 → 32 |
| 5 | `systematic-debugging` | failing test or exception | the debug loop | run_command, read_file, get_code_neighbors, edit_file | 37 → 30 |
| 6 | `differential-diagnosis` | >1 possible cause and short budget | candidate scoring | run_command | 37 → 26 |
| 7 | `test-driven-development` | add/fix behavior with a test | RED-GREEN-REFACTOR cycle | edit_file, run_command | 34 → 26 |
| 8 | `python-testing-patterns` | write/read pytest, mock | pattern table | read_file, run_command | 42 → 30 |
| 9 | `implementation-planning` | the change exceeds a small edit | inline plan ≤7 steps | run_command, read_file | 32 → 24 |
| 10 | `budget-aware-tool-use` | task start or unproductive loop | budget **+ loop rules** | submit_patch, get_status | 42 → 34 |
| 11 | `patch-hygiene` | before the first edit or scratch | paths + scratch | edit_file, write_file, run_command | 45 → 30 |
| 12 | `verification-before-submit` | before `submit_patch` | submit gate | run_command, submit_patch, get_status | 54 → 34 |
| | **Total** | | | | **469 → 350** |

## 6. Ownership map (who keeps what)

- **`patch-hygiene`** is the sole owner of: the forbidden-file list
  (`tests/`, `conftest.py`, `pytest.ini`), scratch in `/tmp`, `git add -N`,
  `git status`/`diff --stat`. The others **reference it**.
- **`verification-before-submit`** owns the **gate**: run the target test,
  `py_compile` the changed `.py`, reject junk, and only then `submit_patch`. It
  does not repeat the forbidden list (it references it).
- **`budget-aware-tool-use`** owns: reserve ≥15 calls, batch
  reads, stop after 2 failed attempts, always-submit, and
  **the loop rules** (new, see §7).
- **`systematic-debugging`** owns the reproduce→isolate→root-cause→fix loop;
  **`differential-diagnosis`** keeps only the
  likelihood×severity/cost scoring and "when there is >1 cause".
- **`test-driven-development`** owns the cycle; **`python-testing-patterns`**
  keeps only the offline pattern table.
- **`code-search` / `code-graph-navigation` / `repo-mapping`**: text vs graph
  vs orientation, with a single declared fallback (empty graph → code-search).

## 7. New content (what we learned)

Added, **inside `budget-aware-tool-use`** (whose trigger already says "unproductive
loop"), based on `odd/tasks/host-trial-trace-metrics.md` and thread
#745774:

- **Read loop**: if two consecutive read-only commands do not contribute new info,
  stop searching; edit or submit.
- **Edit loop**: one edit per hypothesis; if the repro does not change, revert and
  re-diagnose; never pile up edits.

No new skills are created: the budget of 12 is fixed and these rules fit
the natural owner.

## 8. How to measure the improvement

1. **Cost**: total lines and bytes before/after (`trace_metrics` no; a
   direct count). Target: ≤350 lines.
2. **Overlap**: count duplicated rules before/after (target: 0).
3. **Trigger**: each skill has an actionable and distinct `Trigger:`.
4. **Compliance**: `pack --check` 6/6 and zero forbidden tokens.
5. (Optional, no A/B) run `trace_metrics.py` on a run with the new set and
   compare loop shapes against the baseline.

## 9. Risks and non-goals

- **Rule b**: exactly 12 directories must remain. None are created or deleted.
- **Rule e**: all new text must avoid `http(s)://|socket|urllib|requests.|
  pip install|uv add|mcp|subprocess|curl|wget`.
- **`skill-stack/`**: decide whether it is re-synced or removed (today it is a stale
  mirror that misleads). Recommendation: **remove it** and leave `submission/skills/`
  as the only source, updating the README.
- **`run_skill_script`**: do not add scripts (known bug).
- **Non-goals**: do not change the prompt (v3 is already there), do not touch the
  harness, do not add new skills, do not measure A/B.

## 10. Implementation plan (if approved)

- **Phase 1 (dedupe)**: remove the duplicated rules and add cross-references.
  Without changing the meaning. → PR with count/rule-e tests.
- **Phase 2 (sharpen triggers)**: rewrite each `description:` to
  `Trigger: <when>` ≤20 words.
- **Phase 3 (loop rules)** in `budget-aware-tool-use`.
- **Phase 4 (cleanup)**: remove `skill-stack/` or re-sync + README.
- Each phase: `pack --check` 6/6, line count, and real evidence in the PR.

## 11. Pending decision

- Do we go with the full redesign (phases 1–4) or only dedupe + triggers (1–2)?
- Is `skill-stack/` removed or re-synced?
- Does this doc stay in `docs/` (versioned) or is it discarded after deciding?
