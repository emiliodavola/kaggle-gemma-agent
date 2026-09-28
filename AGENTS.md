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

## Harness budgets

Per task the agent gets:

- **60 minutes** wall-clock.
- **100 tool calls**.

Design and test against these limits.

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
- **Emilio merges.** Do not merge your own PR.
- Never push to `main`.
- Do not add AI attribution / `Co-Authored-By` trailers; use conventional
  commit messages.

## CI

There are no tests yet and the current deliverable is documentation, so no CI
config is added at this stage. A follow-up issue tracks introducing lightweight
uv-based checks once the first helper script or test suite lands.
