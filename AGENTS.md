# AGENTS.md

Operating guide for anyone (human or AI) working in this repository.

## Integration rule: `main` changes only through a pull request

`main` is the delivered line: **nothing is ever pushed to it directly**, and
every change reaches it through a feature branch and a merged pull request — a
four-line documentation fix, a typo, a revert and a hotfix included. There is no
emergency path and no size exception; "it is only one line" is not a reason, and
a passing local run is not a substitute for the PR.

A commit that lands on `main` without a PR is a process defect, not a shortcut:
do not build on top of it. Open a branch, revert it there, and re-land the same
change on its own branch through a PR. The merge strategy is free — squash,
merge commit or rebase — because what this rule forbids is the push, never the
merge.

## Goal

Compete in the Kaggle **gemma-4-developer-agent** competition (deadline
**2026-12-02**). We build a developer/coding agent that is packaged and
evaluated by the `swegemma` harness. The scored metric is **Resolution Rate**:
the fraction of tasks the agent resolves within the harness budget.

Base model: one of the four permitted quantized variants
(`gemma-4-31b-it-qat-w4a16-ct` by default, or the 12B / E4B / E2B). The E4B
baseline run of 2026-10-31 targets the USD 10,000 small-model bonus.

## Working scope

From 2026-11-01 the work happens on **Kaggle**. The two notebooks under
`notebooks/` are the surface we change and the Kaggle platform is where runs
execute; do not start work in another area of the repository unless the task
names it explicitly.

- `notebooks/kaggle-remote-run-31b.ipynb` and
  `notebooks/kaggle-remote-run-e4b.ipynb` are one implementation in two files.
  They may differ **only** in the pinned model: `tests/test_kaggle_notebook.py`
  fails on any other drift and refuses a third `kaggle-remote-run-*.ipynb`.
- A run stays reproducible in **faithful** mode, and every flag that changes what
  is measured is recorded in `run_meta.json` and in the archived report. A number
  produced under a different mode is never compared against a faithful baseline.
- L4 sessions run with internet disabled, so everything a notebook needs arrives
  as an attached input: competition data, wheelhouse, code dataset, model.
- A notebook is development tooling and is never submitted. It reads
  `submission/` from the code dataset, so a notebook change cannot alter what the
  scorer receives; changing the agent itself is a `submission/` change and needs
  its own issue, PR and gate run.

## Competition rules bind every change

A submission that fails one contract point scores **zero**, and a local run that
ignores the L4 policy can cost the account. Before changing or running a
notebook, check the change against the six contract points below,
`docs/competition-research.md` and the competition pages those documents quote:

- one base model per submission, chosen from the four permitted quantized
  variants, identical on every agent and subagent;
- `submission/` stays declarative YAML with 12 skills and under 3 GiB unpacked;
- no network, pip, MCP or subprocess strings under `submission/`;
- per-task budgets inside 100 tool calls / 60 minutes / 500 turns, and 12 hours
  for the whole hidden set;
- L4 sessions run with internet disabled and nothing is downloaded at run time;
- the scorer strips tests and runner config from a patch, so a fix belongs in the
  library code.

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

Every document belongs to one of six genres:

- **living reference** — stable name, no date in the name, updated in place
  (`docs/`). Status `current`.
- **run analysis** — append-only, never rewritten; one directory per run id
  (`docs/runs/<run-id>/`). To revise one, add a new document and mark the old
  with `Status: superseded-by <path>`.
- **task digest** — regenerable from `data/raw/tasks.jsonl` (`docs/tasks/`);
  regenerate instead of hand-editing.
- **proposal** — dated, superseded but never deleted (`docs/proposals/`).
- **experience library** — append-only entries keyed by the situation that
  triggers the lesson, browsable through one index (`docs/harness-library/`).
  Status `current`; a superseded entry is never rewritten, it gains
  `Status: superseded-by <path>`.
- **journal** — append-only change log; one human file per UTC day
  (`docs/journal/YYYYMMDD.md`) rendered from the machine file
  `docs/journal/events.jsonl`. See `## Change journal` below.

Every attribution in a run analysis or proposal carries one of the four verdicts
defined in `docs/run-analysis-vocabulary.md` (`helped`, `hurt`, `no observed
effect`, `confounded`). `confounded` is the default when no execution contrast
isolates the change. A statement that only reports what an artifact contains is
an observation and carries none.

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

Any PR that touches `submission/`, `docs/`, `scripts/host-trial/`,
`src/kaggle_gemma_agent/harness_runs.py` or `src/kaggle_gemma_agent/run_report.py`
adds its journal entry in the same PR.
The CI job `journal` enforces this with `scripts/check_journal_entry.py`.

The token `[no-journal]` in the PR title or body is an escape hatch that must be
justified in the PR body. It is only legitimate for mechanical changes with no
decision and no new evidence: a plain revert, a typo or link fix, or a bot
commit. It is never legitimate for a change that alters agent behaviour,
submission content, prompts, skills or harness runs.

Format, schema and CLI: `docs/journal/README.md`.

## Experiment loop

A harness change is measured on a fixed subset against a pre-declared component:
`experiments/subsets/<id>.json`, then `experiments/<experiment-id>/experiment.json`
before the first rollout, then `comparison.json` after the two runs. The runs
stay in `runs/` (git-ignored); the subset and the declaration are committed.
`finish` refuses a comparison when the subset, backend, model, budgets or any
provenance hash other than the declared component differs, and it reports the
delivery signal separately from the resolution verdict. See
`docs/dev-experiment-loop.md`.

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
├── training/                     # LoRA SFT project, Python 3.12, RTX 3090 (own uv project)
├── notebooks/                    # Kaggle remote-run notebooks, one per base model
│   ├── kaggle-remote-run-31b.ipynb
│   └── kaggle-remote-run-e4b.ipynb
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

`experiments/` holds committed subset documents and experiment declarations; the
generated comparison sits beside each declaration. It is data and tool input,
not a documentation genre. The protocol is `docs/dev-experiment-loop.md`.

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
- **c** — a single base model id, drawn from the four permitted competition models
  (`gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`,
  `gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`). Every agent in
  the submission must declare the same one; mixing variants is a violation.
- **d** — budgets in `eval_config.yaml` within limits (100 calls / 60 min / 500 turns).
- **e** — no network / pip / MCP / subprocess strings under `submission/`.
- **f** — packed archive stays **< 3 GiB**.

Next to the contract, `check_harness_surface` validates the harness surface and
is reported as a second, independent line: every shipped skill is named in the
always-on prompt (**s1**), that prompt stays under `MAX_ALWAYS_ON_CHARS`
(**s2**), and every `scripts/<file>.py` a skill references ships in the archive
(**s3**). The layer prints `harness surface OK (3 checks)` and never renumbers
or changes the contract points; `--check` exits non-zero if any of the three
layers fails.

A third, independent layer, `check_answer_leak`, rejects shipped content that
encodes a grader answer: task instance ids, `tests/test_*.py` paths, test node
ids and `FAIL_TO_PASS` / `PASS_TO_PASS` markers. It prints
`answer leak OK (4 patterns)`, names the file and, for content matches, the
line, and never changes the contract points; `--check` exits non-zero if any of
the three layers fails.

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

- Never commit directly to `main`, and never push to it. Work on feature
  branches: every change travels branch → PR → review → merge, and a merged PR
  is the only way a commit reaches `main`.
- Branch naming: `docs/...`, `feat/...`, `fix/...`, `chore/...`.
- Open PRs against `main`.
- PR descriptions must include **real command outputs** for verification, not
  claims.
- PR bodies must follow `.github/PULL_REQUEST_TEMPLATE.md` (Summary, Changes,
  Verification with pasted output, Files changed, Design artifacts,
  Checklist) — no free-form bodies.
- **Emilio merges.** Do not merge your own PR.
- Do not add AI attribution / `Co-Authored-By` trailers; use conventional
  commit messages.

## Ownership

Every issue and every PR is assigned to the person developing it, in both
directions: an issue nobody owns and a PR nobody owns are incomplete, the same
as a missing template section. Today that person is `emiliodavola`. Agents may
create and edit these artifacts, but the assignee is that person unless the user
says otherwise.

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
