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

# 2. Install/verify the Kaggle CLI.
uv run kaggle --version

# 3. Configure Kaggle credentials outside the repo.
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

Kaggle API docs: <https://www.kaggle.com/docs/api>. Never commit the token.

## Layout

```plaintext
.
├── AGENTS.md          # operating guide (uv, git, submission, budgets)
├── README.md          # this file
├── docs/              # competition notes
├── data/              # local data (raw is git-ignored)
├── src/
│   └── kaggle_gemma_4_developer_agent_competition/  # reserved for helpers
├── pyproject.toml
└── uv.lock
```

`src/` is a placeholder; harness runners, the submission packer, and local
evaluation scripts will live here.

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
