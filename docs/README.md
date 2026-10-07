# Documentation index

This directory holds every research, analysis and decision document for the
gemma-4-developer-agent competition, in English. Start here: it is the single
entry point that tells you what exists, in which genre, with what status and
from which raw artifact it was derived.

## Genres and their lifecycles

| Genre | Directory | Lifecycle |
|-------|-----------|-----------|
| living reference | `docs/` (root) | Stable name, no date in the name, updated in place. Status is `current`. |
| run analysis | `docs/runs/<run-id>/` | Append-only, never rewritten. One directory per run id. Status is `current`, `superseded-by <path>` or `archived`. |
| task digest | `docs/tasks/` | Regenerable from `data/raw/tasks.jsonl`; regenerate rather than hand-edit. |
| proposal | `docs/proposals/` | Dated, superseded but never deleted. Status is `open`, `accepted`, `superseded-by <path>` or `implemented in PR #N`. |
| journal | `docs/journal/` | Append-only change log: one human file per UTC day, rendered from the machine file `events.jsonl`; never rewritten. Revise by adding a superseding or reverting entry. |
| change tracker | `odd/tasks/` | Per-feature tracker; goal, decisions, checkboxed tasks and evidence. Never deleted. |

## Header rule

Every document starts with a six-field header block. Fill the values from the
document itself; do not invent them.

```text
---
Date: <YYYY-MM-DD>
Genre: run analysis | task digest | proposal | living reference | journal
Status: current | superseded-by <path> | archived
Scope: <one line: what it covers and what it does not>
Source of truth: <the raw paths it was derived from, plus the read date>
Limits: <e.g. "census, not a random sample: counts only, no inference">
---
```

## Source of truth

The raw artifacts are the source of truth: `runs/`, `results/` and
`data/raw/`. A document that disagrees with a raw artifact is wrong. When you
find a discrepancy, report it and correct the document; never silently rewrite
the evidence. Run analyses are append-only: to revise one, add a new document
(same run directory) that supersedes it, and mark the old one with
`Status: superseded-by <path>`. Never delete evidence.

## Index

`Run` is the run id for run analyses, or `—` when not tied to a single run.
`Updated` is the last date the document's content was revised.

| Doc | Genre | Status | Scope | Run | Source of truth | Updated |
|-----|-------|--------|-------|-----|-----------------|---------|
| [runs/20261006T103737Z/00-tracker.md](runs/20261006T103737Z/00-tracker.md) | run analysis | archived | Coordination tracker for the run_03 audit; indexes the analyses but does not contain them. | 20261006T103737Z | runs/20261006T103737Z/, results/run_03/ (read 2026-10-06) | 2026-10-06 |
| [runs/20261006T103737Z/01-audit.md](runs/20261006T103737Z/01-audit.md) | run analysis | superseded-by docs/runs/20261006T103737Z/09-corrections.md | Full audit of run_03 (48 rich_* tasks): resolution, failure kinds, prompt provenance, patch hygiene and recommendations. | 20261006T103737Z | runs/20261006T103737Z/, results/run_03/ (read 2026-10-06) | 2026-10-07 |
| [runs/20261006T103737Z/02-successes-vs-failures.md](runs/20261006T103737Z/02-successes-vs-failures.md) | run analysis | current | Per-task successes-vs-failures census of the 48 rich_* tasks plus proposals N1-N6. | 20261006T103737Z | runs/20261006T103737Z/*, data/raw/tasks.jsonl (read 2026-10-06) | 2026-10-06 |
| [runs/20261006T103737Z/03-failures-by-prompt-version.md](runs/20261006T103737Z/03-failures-by-prompt-version.md) | run analysis | superseded-by docs/runs/20261006T103737Z/09-corrections.md | Descriptive failure analysis by system-prompt version (v2/v3a/v3); not a formal A/B. | 20261006T103737Z | runs/20261006T103737Z/, results/run_03/, submission prompts/configs (read 2026-10-06) | 2026-10-07 |
| [runs/20261006T103737Z/04-harness-messages.md](runs/20261006T103737Z/04-harness-messages.md) | run analysis | superseded-by docs/runs/20261006T103737Z/09-corrections.md | Catalogue, frequencies and fail-vs-pass comparison of harness-to-agent messages; excludes model thinking. | 20261006T103737Z | runs/20261006T103737Z/ (48 ATIF-v1.7 traces), results/run_03/ (read 2026-10-06) | 2026-10-07 |
| [runs/20261006T103737Z/05-segment-fastapi.md](runs/20261006T103737Z/05-segment-fastapi.md) | run analysis | current | The fastapi_* segment (7 tasks / 10 executions); does not cover rich, requests or httpx. | 20261004, 20261005, 20261006T103737Z | runs/ (20261004T225306Z, 20261005T050122Z, 20261006T103737Z) (read 2026-10-06) | 2026-10-06 |
| [runs/20261006T103737Z/06-segment-rich.md](runs/20261006T103737Z/06-segment-rich.md) | run analysis | current | The rich_* segment of run_03 (48 tasks, 29 resolved), tabulating failures and pass-vs-fail patterns. | 20261006T103737Z | runs/20261006T103737Z/ (= results/run_03) (read 2026-10-06) | 2026-10-06 |
| [runs/20261006T103737Z/07-segment-requests-httpx.md](runs/20261006T103737Z/07-segment-requests-httpx.md) | run analysis | current | The requests_*/httpx_*/other segments (70 executions; httpx and other have zero). | 20261004, 20261005, 20261006T103737Z | runs/ (20261004T225306Z, 20261005T050122Z, 20261006T103737Z) (read 2026-10-06) | 2026-10-06 |
| [runs/20261006T103737Z/08-cross-segment-synthesis.md](runs/20261006T103737Z/08-cross-segment-synthesis.md) | run analysis | current | Intra/inter-segment synthesis over 70 executions plus a generalised anti-overfit proposal; not a formal A/B. | 20261004, 20261005, 20261006T103737Z | runs/ (3 run ids) and the segment reports (read 2026-10-06) | 2026-10-06 |
| [runs/20261006T103737Z/09-corrections.md](runs/20261006T103737Z/09-corrections.md) | run analysis | current | Corrects specific claims in 01-audit.md, 03-failures-by-prompt-version.md and 04-harness-messages.md that disagree with the raw run artifacts; does not re-audit run_03. | 20261006T103737Z | runs/20261006T103737Z/, runs/20261004T225306Z/, runs/20261005T050122Z/, results/run_03/, results/run_01/, results/run_02/ (read 2026-10-07) | 2026-10-07 |
| [tasks/20261006-inventory-129.md](tasks/20261006-inventory-129.md) | task digest | current | One-line problem-statement title per task for all 129 dev tasks, grouped by segment. | — | data/raw/tasks.jsonl (read 2026-10-06) | 2026-10-06 |
| [tasks/20261006-strategies-fastapi-a.md](tasks/20261006-strategies-fastapi-a.md) | task digest | current | Strategy and complexity for fastapi_11194 to fastapi_14372 (25 tasks). | — | data/raw/tasks.jsonl (read 2026-10-06) | 2026-10-06 |
| [tasks/20261006-strategies-fastapi-b.md](tasks/20261006-strategies-fastapi-b.md) | task digest | current | Strategy and complexity for fastapi_14371 to fastapi_9753 (44 tasks). | — | data/raw/tasks.jsonl (read 2026-10-06) | 2026-10-06 |
| [tasks/20261006-strategies-requests.md](tasks/20261006-strategies-requests.md) | task digest | current | Strategy and complexity for the 13 requests_* tasks. | — | data/raw/tasks.jsonl (read 2026-10-06) | 2026-10-06 |
| [tasks/20261006-strategies-rich-httpx.md](tasks/20261006-strategies-rich-httpx.md) | task digest | current | Strategy and complexity for the rich_* tasks plus httpx_3672 (49 tasks). | — | data/raw/tasks.jsonl (read 2026-10-06) | 2026-10-06 |
| [proposals/20261006-prompt-hardening.md](proposals/20261006-prompt-hardening.md) | proposal | implemented in PR #74 | Copy-paste prompt and skill hardening proposals across the 129 tasks; does not modify the harness or submission files. | — | the task digests, run analyses and current submission prompts/skills (read 2026-10-06) | 2026-10-06 |
| [proposals/skills-redesign.md](proposals/skills-redesign.md) | proposal | open | Redesign of the 12 shipped submission skills to be hypercompact and non-overlapping. | — | docs/skill-stack-inventory.md, docs/proposals/skill-stack-evaluation.md, submission/skills/ (read 2026-10-06) | 2026-10-05 |
| [proposals/skill-stack-evaluation.md](proposals/skill-stack-evaluation.md) | proposal | open | Selection decision over all 86 inventory items (which skills to ship and why). | — | docs/skill-stack-inventory.md, AGENTS.md (read 2026-10-06) | 2026-09-29 |
| [competition-research.md](competition-research.md) | living reference | current | Competition research: goal, submission format, metric, harness/hardware budgets and LoRA guidance. | — | Kaggle competition listing/rules pages (read 2026-10-06) | 2026-09-28 |
| [competition-data.md](competition-data.md) | living reference | current | Inventoried snapshot of the public dataset, timeline and task/model facts, with provenance. | — | Kaggle competition pages and `kaggle` CLI output (read 2026-10-06) | 2026-09-29 |
| [competitive-options-playbook.md](competitive-options-playbook.md) | living reference | current | Working playbook of levers to raise Resolution Rate, conditioned by the sandbox constraints. | — | submission/, scripts/host-trial/, docs/, odd/tasks/ (read 2026-10-06) | 2026-10-06 |
| [harness-logging-contract.md](harness-logging-contract.md) | living reference | current | What the swegemma harness logs per task and what is required to run a local trial. | — | data/raw/HARNESS_README.md, data/raw/tasks.jsonl, data/raw/docker/ (read 2026-10-06) | 2026-09-30 |
| [host-trial-runbook.md](host-trial-runbook.md) | living reference | current | Operator runbook to run a real swegemma trial on Windows/Docker or Linux/WSL2. | — | scripts/host-trial/run_host_trial.py and the harness contract (read 2026-10-06) | 2026-10-04 |
| [run-reports.md](run-reports.md) | living reference | current | Handoff contract for file-based run reports: runs/ layout, report.json schema, STATUS polling, manifest provenance. | — | src/kaggle_gemma_agent/harness_runs.py, run_report.py (read 2026-10-07) | 2026-10-07 |
| [skill-stack-inventory.md](skill-stack-inventory.md) | living reference | current | Inventory of candidate skills (86 items, 8 gaps) with compatibility, dependencies and licenses. | — | upstream SKILL.md files and repo metadata (read 2026-10-06) | 2026-09-28 |
| [journal/README.md](journal/README.md) | journal | current | Genre spec for the change journal: two layers, entry schema, human file format, CLI and CI guard. | — | docs/journal/events.jsonl, src/kaggle_gemma_agent/journal.py (read 2026-10-07) | 2026-10-07 |
| [journal/events.jsonl](journal/events.jsonl) | journal | current | Machine layer of the change journal: append-only JSON Lines, the source of truth for the human day files. | — | docs/journal/events.jsonl (read 2026-10-07) | 2026-10-07 |

## Change trackers (`odd/tasks/`)

Genre: change tracker. One file per feature/finding; goal, decisions,
checkboxed tasks and evidence. These live outside `docs/` but are reachable
from here.

- [cheap-improvement-wins.md](../odd/tasks/cheap-improvement-wins.md)
- [code-analyzer-subagent.md](../odd/tasks/code-analyzer-subagent.md)
- [configurable-system-prompt.md](../odd/tasks/configurable-system-prompt.md)
- [github-issue-template.md](../odd/tasks/github-issue-template.md)
- [host-trial-backend-selector.md](../odd/tasks/host-trial-backend-selector.md)
- [host-trial-deps-integrity.md](../odd/tasks/host-trial-deps-integrity.md)
- [host-trial-launcher-reads-env.md](../odd/tasks/host-trial-launcher-reads-env.md)
- [host-trial-linux-wsl.md](../odd/tasks/host-trial-linux-wsl.md)
- [host-trial-local-model-launcher.md](../odd/tasks/host-trial-local-model-launcher.md)
- [host-trial-repair-audit.md](../odd/tasks/host-trial-repair-audit.md)
- [host-trial-retry-output-hardening.md](../odd/tasks/host-trial-retry-output-hardening.md)
- [host-trial-sandbox-deps-repair.md](../odd/tasks/host-trial-sandbox-deps-repair.md)
- [host-trial-smoke-reasoning.md](../odd/tasks/host-trial-smoke-reasoning.md)
- [host-trial-task-source-logging.md](../odd/tasks/host-trial-task-source-logging.md)
- [host-trial-tasks-env.md](../odd/tasks/host-trial-tasks-env.md)
- [host-trial-trace-metrics.md](../odd/tasks/host-trial-trace-metrics.md)
- [host-trial-wheel-closure.md](../odd/tasks/host-trial-wheel-closure.md)
- [host-trial-wheels-backoff.md](../odd/tasks/host-trial-wheels-backoff.md)
- [host-trial-wheels-offline-resume.md](../odd/tasks/host-trial-wheels-offline-resume.md)
- [host-trial-wheels-staging.md](../odd/tasks/host-trial-wheels-staging.md)
- [pre-submit-guard-skill.md](../odd/tasks/pre-submit-guard-skill.md)
- [readme-es-alignment.md](../odd/tasks/readme-es-alignment.md)
- [run-report-verdicts.md](../odd/tasks/run-report-verdicts.md)
- [skills-compaction.md](../odd/tasks/skills-compaction.md)
- [system-prompt-v3.md](../odd/tasks/system-prompt-v3.md)
- [trial-collect-and-open-items.md](../odd/tasks/trial-collect-and-open-items.md)
