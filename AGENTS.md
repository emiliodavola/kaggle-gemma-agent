# AGENTS.md

Operating guide for anyone (human or AI) working in this repository.

## Goal

Compete in the Kaggle **gemma-4-developer-agent** competition (deadline
**2026-12-02**). We build a developer/coding agent that is packaged and
evaluated by the `swegemma` harness. The scored metric is **Resolution Rate**:
the fraction of tasks the agent resolves within the harness budget.

Base model: `gemma-4-31b-it-qat-w4a16-ct`.

## Layout

```
.
├── AGENTS.md                     # this file
├── README.md                     # public sketch / quickstart
├── docs/                         # competition notes and reference material
│   └── reporte-competencia.md    # competition analysis (Spanish)
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
