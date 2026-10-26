---
Date: 2026-10-26
Genre: living reference
Status: current
Scope: The declared A/B loop over archived runs: fixed subsets, the pre-declared component and direction, the isolated-run checks, and the two comparison signals. It does not run trials, score tasks or define the run-report schema.
Source of truth: experiments/subsets/dev-v1.json, src/kaggle_gemma_agent/{subsets,experiments}.py, src/kaggle_gemma_agent/harness_runs.py, docs/run-analysis-vocabulary.md (read 2026-10-26)
Limits: A protocol and its tooling, not an inferential method: no randomisation, no confidence intervals, no causal estimate.
---

# Development experiment loop

A harness change is measured on a **fixed batch**, against a **declared
component**, and is only called a contrast when the record shows that nothing
else moved. Before this loop the latest analysis could say only:

```text
2/13 -> 1/13 on a different batch
```

Twelve of thirteen statuses were identical and the recorded prompt, sampling and
eval-config hashes did not differ, yet no change was named before the runs and
the skills bytes had no hash. Every attribution was `confounded`
(`docs/runs/20261009T122847Z/01-attribution-audit.md`). The loop fixes the
missing preconditions; it does not make a single run conclusive.

## Three artifacts

| Artifact | Path | Committed | Role |
| :--- | :--- | :--- | :--- |
| Subset | `experiments/subsets/<id>.json` | yes | The fixed task list, its per-repository counts and the selection rule. |
| Declaration | `experiments/<experiment-id>/experiment.json` | yes | The one component that may change, the intended direction and the current provenance, written **before** the first rollout. |
| Comparison | `experiments/<experiment-id>/comparison.json` | yes | The generated per-task matrix, the delivery counts and the resolution verdict. |

The runs themselves stay under `runs/` (git-ignored). The declaration is the
durable half: a reader can see what was expected before the result existed.

## Workflow

```sh
# 1. Validate the batch (ids, counts, corpus membership).
uv run python -m kaggle_gemma_agent.subsets validate dev-v1

# 2. Declare the experiment before any rollout.
uv run python -m kaggle_gemma_agent.experiments start \
  --id 20261027-prompt-module-path \
  --subset dev-v1 \
  --component prompt \
  --direction helped \
  --change "Resolve the loaded module path before diagnosing a source/disk mismatch" \
  --backend lmstudio \
  --model gemma-4-31b-it-qat

# 3. Run the base from the same commit, with no harness edit.
uv run python scripts/host-trial/run_host_trial.py base \
  --subset dev-v1 --experiment 20261027-prompt-module-path

# 4. Apply the one edit. Do not commit it yet.
#    submission/prompts/system.md

# 5. Run the variant from the same commit.
uv run python scripts/host-trial/run_host_trial.py variant \
  --subset dev-v1 --experiment 20261027-prompt-module-path

# 6. Compare. This prints the table and writes comparison.json.
uv run python -m kaggle_gemma_agent.experiments finish \
  --id 20261027-prompt-module-path \
  --base runs/<base-stamp> \
  --variant runs/<variant-stamp>
```

`run_host_trial.py --subset` wins over `--tasks` and `HARNESS_TRIAL_TASKS`; the
two flags are mutually exclusive. The runner records the subset identity, the
experiment id, the backend name and the served model in `manifest.json`, and the
report carries the same block.

## Rules for a valid contrast

1. **One component.** The declared component is one of `prompt`, `skills`,
   `sampling`, `eval_config`, `repo_commit`. The other four hashes must be
   identical in the two manifests; the comparison refuses otherwise and names
   the differing set.
2. **Same commit.** Run both sides from the same `repo_commit`. Leave the edit
   uncommitted between the two runs, so both manifests record the same
   `HEAD-dirty` value. Committing between runs makes the comparison refuse: a
   different commit can carry unrelated code changes the hashes do not cover.
   The `repo_commit` component exists for the deliberate case where the code
   itself is the change; it is never a shortcut around the other rules.
3. **Same batch.** Same subset sha256, same task ids, no missing task. A task
   that the harness failed to archive makes the batch incomplete and refuses the
   comparison.
4. **Same backend, model and budgets.** A trial on a different backend is a
   different execution, not a contrast.
5. **Direction declared first.** `--direction` is recorded before the runs. A
   direction chosen after reading the result is not a contrast
   (`docs/run-analysis-vocabulary.md` R3.4).
6. **A refusal is a result.** Fix the confound and start a new experiment. Do
   not weaken the check to make a comparison pass.

## Two signals, one verdict

The comparison prints two separate sections, and they answer different questions.

- **Delivery signal** — `submitted`, `clean_src_only`, `edits_tests`,
  `config_only`, `scratch`, `none`, `corrupted`, with deltas. This is
  descriptive context (R8). It says whether a usable artifact appeared more
  often; it never establishes an attribution.
- **Resolution verdict** — exactly one of `helped`, `hurt`, `no observed
  effect`, `confounded`, under R3/R4. `helped` and `hurt` require the resolved
  count to move under an isolated contrast. `no observed effect` requires every
  task's `resolved` and `failure_kind` to be identical. Anything else is
  `confounded`.

The intended use is the one the competition metric rewards: delivery tells you
whether a candidate is worth more rollouts, while the verdict tells you whether
the official outcome moved. A candidate that raises `submitted` but leaves
`resolved` and `failure_kind` unchanged earns `no observed effect`, not a
shipping decision.

## The current subset: `dev-v1`

`experiments/subsets/dev-v1.json` holds 11 tasks: `rich` 5, `requests` 3,
`fastapi` 2, `httpx` 1. Six resolved at least once in the archived runs; the
other five cover `test_failure` and `collection_error`. Tasks whose archived
runs were `infra_error` are excluded. It is a **contrast set**, deliberately not
corpus-proportional: fastapi has 67 tasks but only three non-infra archived
results, so a proportional sample would mostly measure a broken wheelhouse.

Do not compute an official resolution rate from `dev-v1`. It is selected for
signal, not sampled at random. A new fixed set gets a new id (`dev-v2`) and a
new declaration; an existing subset is never edited in place.

## What this does not do

- It does not run trials; `scripts/host-trial/run_host_trial.py` does.
- It does not replace the run analyses under `docs/runs/` or the change journal.
- It does not randomise, repeat, or bound uncertainty. One A/B pair is one
  observation; a claim that generalises needs its own evidence.
- It does not merge, approve or submit anything.
- It does not hash source code outside `submission/`. Uncommitted code changes
  between the two runs are outside the recorded identity; keep the worktree
  otherwise still, and prefer the `repo_commit` component when code is the
  change.
