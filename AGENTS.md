# AGENTS.md

Operating guide for anyone (human or AI) working in this repository.

## Goal

Compete in the Kaggle **gemma-4-developer-agent** competition (deadline
**2026-12-02**). We build a developer/coding agent that is packaged and
evaluated by the `swegemma` harness. The scored metric is **Resolution Rate**:
the fraction of tasks the agent resolves within the harness budget.

Base model: `gemma-4-31b-it-qat-w4a16-ct`.

## Language

Everything in this repository is written in **English**: documentation, issues,
pull requests, commit messages, code comments and identifiers. No Spanish or any
other language, in any file, including analysis documents. If a document is
written in another language, translate it before merging.

Single exception: `README_ES.md`, the Spanish translation of `README.md`, is kept
on purpose for outreach. Nothing else in the repository is exempt.

## Documentation

`docs/README.md` is the single entry point and the document index. It is
updated in the same PR that adds or moves any document.

Every document belongs to one of five genres:

- **living reference** — stable name, no date in the name, updated in place
  (`docs/`). Status `current`.
- **run analysis** — append-only, never rewritten; one directory per run id
  (`docs/runs/<run-id>/`). To revise one, add a new document and mark the old
  with `Status: superseded-by <path>`.
- **task digest** — regenerable from `data/raw/tasks.jsonl` (`docs/tasks/`);
  regenerate instead of hand-editing.
- **proposal** — dated, superseded but never deleted (`docs/proposals/`).
- **journal** — append-only change log; one human file per UTC day
  (`docs/journal/YYYYMMDD.md`) rendered from the machine file
  `docs/journal/events.jsonl`. See `## Change journal` below.

Every document starts with a six-field header block (`Date`, `Genre`, `Status`,
`Scope`, `Source of truth`, `Limits`); fill the values from the document itself.

The raw artifacts are the source of truth: `runs/`, `results/` and `data/raw/`.
A document that disagrees with a raw artifact is wrong: report the discrepancy
and fix the document, never silently rewrite the evidence. Never delete
evidence.

`engram` is agent recall, not documentation. Store one pointer per deliverable
(title, 2-3 lines, path, run, status, PR) and never the content, and never a
volatile number without an "as of <date>" stamp.

## Change journal

`docs/journal/` is the chronological, cross-cutting log of changes and
decisions. It is **not** the per-feature tracker (`odd/tasks/`), not the
documentation index (`docs/README.md`), not `engram` and not `git log`.

- Machine layer `docs/journal/events.jsonl` is append-only: one JSON object per
  line, UTF-8, LF terminated, and the source of truth.
- Human layer `docs/journal/YYYYMMDD.md` is rendered from `events.jsonl` for
  that UTC day; regenerate it, never hand-edit it.

The journal is **append-only**: an entry is never edited and never deleted. To
revise one, add a new entry that supersedes or reverts it and set the old
entry's status to `superseded` or `reverted`.

Evidence is counts and paths, never causality. Without randomisation a batch
comparison is written `"29/48 -> X/48 on a different batch"`, never
`"it improved"`.

Any PR that touches `submission/`, `docs/`, `scripts/host-trial/` or
`src/kaggle_gemma_agent/harness_runs.py` adds its journal entry in the same PR.
The CI job `journal` enforces this with `scripts/check_journal_entry.py`.

The token `[no-journal]` in the PR title or body is an escape hatch that must be
justified in the PR body. It is only legitimate for mechanical changes with no
decision and no new evidence: a plain revert, a typo or link fix, or a bot
commit. It is never legitimate for a change that alters agent behaviour,
submission content, prompts, skills or harness runs.

Format, schema and CLI: `docs/journal/README.md`.

## Layout

```
.
├── AGENTS.md                     # this file
├── README.md                     # public sketch / quickstart
├── docs/                         # documentation (index: docs/README.md)
│   ├── README.md                 # single entry point and document index
│   ├── runs/<run-id>/            # append-only run analyses
│   ├── tasks/                    # task digests (regenerable from tasks.jsonl)
│   ├── proposals/                # dated proposals (superseded, never deleted)
│   └── journal/                  # append-only change log (events.jsonl + day files)
├── data/                         # local data (raw is git-ignored)
├── src/
│   └── kaggle_gemma_4_developer_agent_competition/
│       └── __init__.py           # uv-init placeholder; dir reserved for helpers
├── .agents/skills/               # 28 project-only probabl skills (see below)
├── pyproject.toml
├── uv.lock
└── skills-lock.json
```

`src/` is currently only the `uv init` template. Keep the directory; it is
reserved for future helpers (harness runners, submission packers, local
evaluation scripts).

## Toolchain: uv only

- Environment management is **uv** exclusively (`pyproject.toml` + `uv.lock`).
- **Never** use pixi, poetry, pipenv, or bare `pip`.
- Common commands:
  - `uv sync` — create/refresh `.venv` from the lockfile.
  - `uv add <pkg>` — add a dependency (updates `pyproject.toml` + `uv.lock`).
  - `uv run <cmd>` — run inside the managed environment.
- **Git hooks**: run `uv run pre-commit install` once per checkout, after the
  first `uv sync`. The hook lives in `.git/hooks/` and is **not versioned**, so
  a fresh clone or a moved/renamed directory must reinstall it, otherwise
  commits fail with `` `pre-commit` not found ``. Never bypass the hook with
  `--no-verify`; fix the environment instead.

## Kaggle authentication

- The Kaggle API token lives in `~/.kaggle/` **outside this repository**.
- Never commit, echo, or paste credentials. `.gitignore` already excludes
  secret files; keep it that way.

## Submission contract

`submission.zip` must contain:

- `agent.yaml` — required agent manifest.
- Optional LoRA adapters — at most one model, total adapter size **< 3 GiB**.

The archive is evaluated by the `swegemma` harness; keep the package minimal
and self-contained.

## Compliance gate

No exceptions: a submission that fails any contract point scores **zero**, so
the gate is mandatory and runs on EVERY PR.

```sh
uv run python -m kaggle_gemma_agent.pack submission --check
```

It enforces the 6 points from PR #9 (`check_submission` in
`src/kaggle_gemma_agent/pack.py`), each violation naming the file and rule:

- **a** — declarative-only `agent.yaml`; no `agent.py`, no dynamic imports.
- **b** — 12 skills, each shipping `skills/<dir>/SKILL.md`.
- **c** — a single base model id (`gemma-4-31b-it-qat-w4a16-ct`).
- **d** — budgets in `eval_config.yaml` within limits (100 calls / 60 min / 500 turns).
- **e** — no network / pip / MCP / subprocess strings under `submission/`.
- **f** — packed archive stays **< 3 GiB**.

CI runs it in `.github/workflows/ci.yml`; fix the reported file before pushing.

## Harness budgets

Per task the agent gets:

- **60 minutes** wall-clock.
- **100 tool calls**.

Design and test against these limits.

## Offline sandbox constraint

The scored environment is two air-gapped Docker containers per task: **no
internet, no pip installs, no MCP, no background processes**. This applies to
the competition sandbox and to every artifact shipped in the submission,
including `skills/` — which load as read-only context and cost tokens each turn.

- Forbidden inside the agent and its skills: network calls, `pip`/`uv add`,
  MCP servers, long-running or background processes, and any download.
- Skills must stay short, procedural, and mapped to the 9 sandbox tools.
- Development, training, and data download run **off-Kaggle**, with network.

See `docs/skill-stack-inventory.md` section A for the full constraint list.

## Skills usage

`.agents/skills/` holds 28 project-only **probabl** skills. They are general ML
workflow tooling, not agent-training tooling.

- Useful here: `triage-ml-task`, `frame-ml-problem`, `manage-ml-backlog`.
- **Not applicable** to this competition: `build-ml-pipeline`,
  `evaluate-ml-pipeline`, `smoke-test-ml-pipeline` (they assume classic
  tabular/sklearn modeling, not agent harness work).

Load a skill only when the task genuinely matches its trigger.

## Git rules

- Never commit directly to `main`. Work on feature branches.
- Branch naming: `docs/...`, `feat/...`, `fix/...`, `chore/...`.
- Open PRs against the integration branch (`dev` when it exists, otherwise
  `main`).
- PR descriptions must include **real command outputs** for verification, not
  claims.
- PR bodies must follow `.github/PULL_REQUEST_TEMPLATE.md` (Summary, Changes,
  Verification with pasted output, Files changed, Design artifacts,
  Checklist) — no free-form bodies.
- **Emilio merges.** Do not merge your own PR.
- Never push to `main`.
- Do not add AI attribution / `Co-Authored-By` trailers; use conventional
  commit messages.

## Issue and PR templates (mandatory)

Every issue and every PR **must** use the repository templates. No free-form
bodies, no partial/missing sections.

- **Issues** — open them through `.github/ISSUE_TEMPLATE/task.yml` (the
  "Task / bug report" form) and complete every required field. When editing an
  existing issue, keep the same section structure: Kind, Area / component,
  Summary, Problem / current behavior, Expected behavior, Reproduction /
  evidence, Acceptance criteria, Scope, Constraints, References, Checklist.
- **PRs** — every PR body must follow `.github/PULL_REQUEST_TEMPLATE.md`
  (Summary, Changes, Verification with pasted real output, Files changed,
  Design artifacts, Checklist) and link its issue with `Closes #N`.
- Verification sections must contain **real pasted command output**, never a
  summary or a claim that a command passed.
- Do not rename, reorder, or delete template sections to work around the
  requirement; extend them when a change needs more detail.

## Tracker

- `odd/tasks/*.md` is the per-feature tracker (one file per feature/finding).
- Every feature branch that changes behavior must add or update its task file:
  goal, decisions taken with the user, non-goals, checkboxed tasks, evidence
  (commands, PR links, measured outputs — never claims).
- Findings that affect future work (bad tasks, infra gaps, open debt) go in a
  `*-collect-and-open-items.md` file instead of living only in chat.

## CI

`.github/workflows/ci.yml` runs on every push to `main` and every PR targeting
`main`. It is uv-based and runs `uv sync --locked`, `uv run ruff check src/
tests/`, and `uv run pytest -q`.
