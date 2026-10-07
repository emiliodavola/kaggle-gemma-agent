# kaggle-gemma-agent

Developer/coding agent for the Kaggle **gemma-4-developer-agent** competition
(deadline **2026-12-02**). The agent is packaged and evaluated by the
`swegemma` harness; the scored metric is **Resolution Rate** on a per-task
budget of **60 minutes** and **100 tool calls**.

Base model: `gemma-4-31b-it-qat-w4a16-ct`.

## Quickstart

```bash
# 1. Create the environment from the lockfile (uv only).
uv sync

# 2. Install the git hooks once per checkout.
uv run pre-commit install

# 3. Install/verify the Kaggle CLI.
uv run kaggle --version

# 4. Configure Kaggle credentials outside the repo.
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

Kaggle API docs: <https://www.kaggle.com/docs/api>. Never commit the token.

## Layout

```plaintext
.
├── AGENTS.md               # operating guide (uv, git, submission, budgets)
├── README.md               # this file
├── README_ES.md            # Spanish translation of this file
├── docs/                   # documentation (index: docs/README.md)
├── odd/tasks/              # per-feature tracker (goal, tasks, evidence)
├── scripts/host-trial/     # cross-platform host trial runner
├── src/kaggle_gemma_agent/ # submission packer, harness runs, run reports
├── submission/             # agent manifest, configs, prompts, shipped skills
├── tests/                  # pytest suite
├── .github/                # CI, PR template, issue form
├── pyproject.toml
├── uv.lock
└── skills-lock.json
```

Local-only paths (`data/`, `runs/`, `tmp/`, `.agents/`) are git-ignored.

## What's implemented

- **Submission packer** (`src/kaggle_gemma_agent/pack.py`) — builds
  `submission.zip` from `submission/` (declarative `agent.yaml`, configs,
  prompts, sub-agents, shipped skills). Stdlib-only and offline.
- **Compliance gate** — checks the six contract points on every PR.
- **System prompt variant** (`submission/configs/prompt_variant.yaml`) — selects
  `legacy`, `v2`, or `v3`; `uv run python -m kaggle_gemma_agent.prompt_variant
  apply` materializes it into `submission/prompts/system.md`, and packing applies
  the selection automatically.
- **Harness runs and reports** (`harness_runs.py`, `run_report.py`) — archive a
  `swegemma` run and render it; see `docs/harness-logging-contract.md` and
  `docs/run-reports.md`.
- **Host trial** (`scripts/host-trial/run_host_trial.py`) — the eight-phase host
  trial; see `docs/host-trial-runbook.md`.
- **Skills** — 12 skills under `submission/skills/` (one `SKILL.md` each).
- **Change journal** (`src/kaggle_gemma_agent/journal.py`) — the chronological,
  cross-cutting log of changes and decisions: `uv run python -m
  kaggle_gemma_agent.journal add|render|list|validate`; a PR touching
  `submission/`, `docs/`, `scripts/host-trial/`, `harness_runs.py` or
  `run_report.py` must carry an entry. See `docs/journal/README.md`.

## Compliance gate

A submission that fails any contract point scores **zero**, so the gate is
mandatory and runs on every PR:

```sh
uv run python -m kaggle_gemma_agent.pack submission --check
```

It enforces: declarative-only `agent.yaml` (**a**); 12 skills, each with a
`skills/<dir>/SKILL.md` (**b**); a single base model id (**c**); budgets within
limits in `eval_config.yaml` (**d**, 100 calls / 60 min / 500 turns); no
network / pip / MCP / subprocess strings under `submission/` (**e**); and an
archive below **3 GiB** (**f**).

## Submission overview

`submission.zip` contains:

- `agent.yaml` — required agent manifest.
- Optional LoRA adapters — at most one model, total size **< 3 GiB**.

Keep the archive minimal and self-contained; the `swegemma` harness runs it
under the task budgets above.

## Contributing

Read [AGENTS.md](AGENTS.md) for the full rules: uv-only toolchain, Kaggle auth
handling, submission contract, harness budgets, skills usage, and git workflow
(feature branches, PRs with real command outputs, Emilio merges).

CI (`.github/workflows/ci.yml`) runs `uv run ruff check src/ tests/`, the pytest
coverage gate (`fail_under = 90`), and the pack compliance check.
