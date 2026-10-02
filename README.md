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
├── docs/                   # competition notes, contracts, runbook, reports
├── odd/tasks/              # per-feature tracker (goal, tasks, evidence)
├── scripts/host-trial/     # cross-platform host trial runner
├── skill-stack/            # 12 agent skills (one SKILL.md each)
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
- **Harness runs and reports** (`harness_runs.py`, `run_report.py`) — archive a
  `swegemma` run and render it; see `docs/harness-logging-contract.md` and
  `docs/run-reports.md`.
- **Host trial** (`scripts/host-trial/run_host_trial.py`) — the eight-phase host
  trial; see `docs/host-trial-runbook.md`.
- **Skills** — 12 skills under `skill-stack/`, copied into `submission/skills/`.

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
