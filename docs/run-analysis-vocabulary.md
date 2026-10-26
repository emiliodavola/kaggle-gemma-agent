---
Date: 2026-10-26
Genre: living reference
Status: current
Scope: The four verdicts used by every run analysis and proposal when a claim attributes an outcome to a change; does not cover failure classification, scoring or the journal schema.
Source of truth: AGENTS.md § Change journal; google-research/harness2 harness2/core/prompts.py experience() at 1cfe254e8d25b15f37048c3730134686abe60335; runs/20261009T122847Z/ and runs/20261008T025904Z/ (read 2026-10-26)
Limits: A vocabulary and a record format, not an inferential method: no randomisation, no confidence intervals, no causal estimation.
---

# Run-analysis vocabulary

Every attribution in a run analysis or proposal carries exactly one of four
verdicts. The verdict states what the evidence supports, not what the author
believes. This document is the single definition; `AGENTS.md` and
`docs/README.md` reference it without restating it.

## The four verdicts

| Verdict | Use when | Requires |
| --- | --- | --- |
| `helped` | The declared change moved the measured outcome in the intended direction. | A valid execution contrast (R3). |
| `hurt` | The declared change moved the measured outcome against the intended direction. | A valid execution contrast (R3). |
| `no observed effect` | Both executions produce the same measured outcome: identical `resolved` per task and identical `failure_kind` per task. | A valid execution contrast (R3). |
| `confounded` | The comparison cannot isolate the declared change, or no contrast exists at all. | State the confound in `Observed`. |

## Rules

**R1 - Attributions only.** A claim is an **attribution** when it says a change
to the shipped harness or its inputs (prompt, skill, config, submission helper
code) caused, changed or explains a task/run outcome. Only an attribution
carries a verdict. An **observation** reports what an artifact contains: counts,
statuses, `failure_kind`, a missing `submit_patch`, a patch hunk, a failing test
name. It carries no verdict. A **prediction** ("this edit should help") is not an
attribution: keep it in a separate `## Expected effect` section, never in the
attribution table, and never cite it as evidence.

**R2 - Four strings only.** The verdict is exactly one of `helped`, `hurt`,
`no observed effect`, `confounded`. No synonyms, no abbreviations, no "no
effect", no "improved".

**R3 - Execution contrast.** A valid contrast is two archived executions of the
same task, or the same task set, where:

1. one declared change is named in the proposal;
2. every other component is held identical, and the record can show it (a
   missing hash means it cannot: see issue #94);
3. both run ids are cited, and the outcome difference is read from
   `report.json` / `STATUS` for those runs;
4. the intended direction (for `helped` / `hurt`) was stated in the proposal's
   `## Expected effect` before the executions. A direction chosen after reading
   the result makes the verdict `confounded`.

A repeated run with no declared change, or two runs whose recorded provenance is
identical, is **variance, not a contrast for an edit**.

**R4 - `confounded` is the default.** If any requirement of R3 cannot be met,
the verdict is `confounded`. One execution, several components changed at once,
a different batch, a different environment, an unrecorded component, or no
execution at all all produce `confounded`.

**R5 - Adoption is not evidence.** Merging, shipping, or a proposal being
accepted never establishes `helped`, `hurt` or `no observed effect`. Adoption
selects a deliverable; it does not isolate an edit.

**R6 - No retroactive edits.** Existing `docs/runs/20261006T103737Z/*` and
`docs/proposals/*` are not rewritten. A correction is a new document with
`Status: superseded-by <path>`; the old one is marked, never edited (the
`09-corrections.md` precedent).

**R7 - Scope of application.** Run analyses (`docs/runs/<run-id>/*.md`) and
proposals (`docs/proposals/*.md`). Not journal entries
(`docs/journal/events.jsonl`), not `odd/tasks/*.md`, not PR bodies.

**R8 - `delivery` is not a verdict.** The `delivery` record from issue #88
(`patch_scope`, `submitted`, `ran_pytest`, `ran_target_test`) is descriptive
context. It may support `Observed`; it never establishes `helped`, `hurt` or
`no observed effect`.

**R9 - Comparisons across runs.** Use the existing style exactly:
`A -> B on a different batch`. Never a verb such as "improved", "regressed",
"recovered" or "caused".

## Claim record

Every attribution is one row in a Markdown table with exactly these columns:

```markdown
| Task | Artifact | Verdict | Observed |
| --- | --- | --- | --- |
| `requests_7205` | `runs/20261009T122847Z/requests_7205/agent_patch.diff` | `confounded` | ... |
```

- **`Task`** - the instance id, or `run` for a claim about a whole batch. Never a
  repository name or a guessed id.
- **`Artifact`** - one or more repo-relative paths, separated by `; `. Raw
  artifacts (`runs/...`) are preferred over prose. A claim with no artifact is
  dropped, not hedged.
- **`Verdict`** - one of the four exact strings, in code spans.
- **`Observed`** - what the artifact shows and where: the field, line, or test
  name; for `helped` / `hurt` / `no observed effect`, both run ids and the
  direction; for `confounded`, the specific confound (several components, batch
  change, single execution, missing hash).
- Rows are ordered by `Task` (instance ids lexicographically first, then `run`).

Prose may summarize, but it must not assert an attribution that has no row. A
sentence that makes a causal claim points to its row.
