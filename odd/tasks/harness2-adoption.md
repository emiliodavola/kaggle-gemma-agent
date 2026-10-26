# Harness2 adoption: a comparable experiment loop (Level 0) and a swegemma adapter (Level 1)

Objective: make every harness change measurable on a fixed task set before it is shipped, and
prove that harness2's Propose-Probe-Compose loop can drive `swegemma` without touching the
submission contract.
Branch: `feat/harness2-adoption` (from `main`).
Delivery strategy: `ask-on-risk`; two work units (Level 0, Level 1).
Test runner: `uv run pytest tests/ -q`; baseline on this Windows checkout is `5 failed, 389 passed`
(the five path-separator/CRLF assertions already failing before any change).

## Specs

**S1 - Fixed contrast set.** The first experiment set is `dev-v1`, committed at
`experiments/subsets/dev-v1.json`, with exactly these 11 instance ids and per-repo counts
`rich 5 / requests 3 / fastapi 2 / httpx 1`:

```text
rich_3006, rich_3063, rich_3061, rich_3468, rich_3777,
requests_7427, requests_7315, requests_6644,
fastapi_15589, fastapi_15588, httpx_3672
```

It is a contrast set, not a rate estimate. Six of the 11 resolved at least once in `runs/`; the
other five never did and cover `test_failure` and `collection_error`. Tasks whose archived runs
were `infra_error` are excluded. The JSON records the selection rule and the archived evidence.

**S2 - Subset identity.** A subset file has `schema_version`, `id`, `description`, `selection`,
`task_ids` and `counts`. Loading it validates: unique ids, every id present in
`data/raw/tasks.jsonl`, and the recorded `counts` agree with the ids. Its identity is the
`sha256` of the file bytes.

**S3 - Run identity.** An archived run records, in `manifest.json`, an `experiment` block with
the experiment id, the subset id/sha256/task ids, backend, model, budgets and the provenance
hashes. `report.json` carries the same block and `STATUS` prints one `experiment <id>
subset <id>@<sha8>` line. An old manifest without the block stays readable and reports
`experiment unknown`.

**S4 - Pre-declared change.** `experiments start` writes `experiments/<id>/experiment.json`
before any rollout. It requires `--subset`, `--component` (one of `prompt`, `skills`,
`sampling`, `eval_config`, `repo_commit`), `--direction` (`helped` or `hurt`) and `--change`
(one line). It refuses an existing id and a subset that does not validate.

**S5 - Isolated contrast.** `experiments finish` accepts the experiment id and two archived run
directories. It refuses a comparison, and writes no verdict, when any of these differs between
the runs: subset sha256, task set, backend, model, budgets, or when a task of the subset is
missing. It also refuses when the set of differing provenance keys is not exactly the declared
component. Otherwise it writes `experiments/<id>/comparison.json` and prints one Markdown table.

**S6 - Two signals, one verdict.** The comparison reports `delivery_signal` as descriptive
counts only (`submitted`, `clean_src_only`, `edits_tests`, `config_only`, `scratch`, `none`,
`corrupted`), never as an attribution (R8). It reports `resolution_verdict` as exactly one of
`helped`, `hurt`, `no observed effect`, `confounded` under R3/R4: `helped`/`hurt` only when the
resolved count moved in the declared direction under an isolated contrast; `no observed effect`
only when every task's `resolved` and `failure_kind` are identical; `confounded` otherwise.

**S7 - Runner flags.** `scripts/host-trial/run_host_trial.py` gains `--subset <name|path>` and
`--experiment <id>`. `--subset` resolves a bare name to `experiments/subsets/<name>.json`, wins
over `--tasks`, and passes the subset to the archiver. `--experiment` is recorded, never guessed.
The runner remains cross-platform and does not require WSL2 to parse its arguments.

**S8 - Versioned delta, disposable clone.** The harness2 clone lives in `tmp/harness2`
(gitignored). Only the delta is committed under `tools/harness2-swegemma/`: `README.md`,
`setup.sh`, `swegemma-adapter.patch` and `falsifier.py`. `setup.sh` clones the pinned commit
`1cfe254e8d25b15f37048c3730134686abe60335`, applies the patch and refuses a different HEAD.

**S9 - Adapter surface.** The patch implements the 12 `BenchmarkAdapter` methods plus `spec` and
`substrate`. The `SurfaceSpec` makes editable: `agent.yaml`, `prompts/system.md`, every
`skills/<name>/SKILL.md`, every `sub_agents/*.yaml`, every `configs/*.yaml` and
`eval_config.yaml`; always-on text is `agent.yaml` plus `prompts/system.md`; the autotrigger file
is `prompts/system.md`. `validate_tree()` runs the three pack checks on a materialised copy.

**S10 - Falsifier.** The falsifier runs two tasks (`requests_6644`, `requests_7315`) against two
harnesses (base, base plus one INV edit to `prompts/system.md`) = 4 rollouts. It asserts (1) all
four rollouts are archived, (2) `manifest.json` provenance differs between the two harnesses,
(3) at least one task differs in `delivered` or `patch_sha256`. It writes its evidence under
`runs/harness2-falsifier/` (gitignored) and its conclusion in a run-analysis document.

**S11 - Submission untouched.** No file under `submission/` changes. Every rollout runs offline
against a copy; `uv run python -m kaggle_gemma_agent.pack submission --check` stays green.

**S12 - Checks.** Every turn ends with `uv run ruff check src/ tests/` clean, the focused tests
green, and `uv run pytest tests/ -q` with no new failing node id relative to the baseline.

## Tasks

- [x] T1 - Baseline and tracker. Route: inline. Evidence: `5 failed, 389 passed`; `ruff` clean.
- [x] T2 - `subsets.py`, `dev-v1.json`, validation tests. Route: inline. Commit: `c2fe171`.
  Evidence: `uv run python -m kaggle_gemma_agent.subsets validate dev-v1` -> 11 tasks,
  sha256 `a9ba8994...`; `uv run pytest tests/test_subsets.py -q` -> 9 passed; mypy and pyright clean.
- [x] T3 - Manifest experiment block, report/STATUS line, archiver flags, tests. Route: inline. Commit: `92a14b6`.
- [x] T4 - Runner `--subset`/`--experiment`, tests. Route: inline. Commit: `92a14b6`.
  Evidence: focused runner tests 5 passed; `run_host_trial.py --help` lists both flags;
  full suite `5 failed, 409 passed` (same five baseline node ids).
- [x] T5 - `experiments.py` start/finish/compare, tests, docs and journal entry. Route: inline. Commit: `f2d583e` (closes Level 0).
  Evidence: 12 focused tests; `experiments --help` lists start/finish/show; full suite
  `5 failed, 421 passed`; `pack submission --check` -> 6/6 + surface + answer leak;
  journal `J-20261026-07` and `journal OK (46 events)`.
- [x] T6 - harness2 fork, adapter patch, `setup.sh`, dry-run validation. Route: inline. Commit: `5e063e0`.
  Evidence: the patch applies cleanly to `1cfe254` on a fresh clone; `python -m
  harness2.cli.check --bench sw --substrate sw` -> `Ready: swegemma/sw; 11 tasks`;
  the dry-run prints 1 task / 1 domain; `validate_tree` returns `pack OK`.
- [x] T7 - Falsifier, 4 rollouts, run analysis, journal entry. Route: inline. Commit: `5e063e0` (closes Level 1).
  Evidence: PASS (`four_archived`, `fingerprints_differ`, `signal` all true); total
  5 204.30 s; `requests_7315` variant 3 626.02 s / 89 tool calls; result
  `runs/harness2-falsifier/20261026T152738Z.json`; analysis
  `docs/runs/20261026T152738Z/01-falsifier.md`.
- [x] T8 - Close: observed results, Risk line, next step.
  Risk: none (dev-only tooling and docs; no submission file changes; pack 6/6 + surface
  + answer leak green; the adapter runs swegemma against a copy and writes only under
  `runs/`).

## Log

- L1 (2026-10-26, translated from the original Spanish because the repository is English-only;
  the verbatim original is in the Engram mirror): review the cloned repository at
  `tmp/harness2` and analyse whether changes can improve how we work on this repository's
  problem. Ask every needed question, assume nothing, make the questions easy, and give enough
  context to decide.
- L2 (2026-10-26, answers): improve both the development loop and the harness, without violating
  the Kaggle competition rules; decide on `Delivered + resolved`; run on WSL2 + Docker with the
  fork in `tmp`; start with Level 0 + Level 1.
- L3 (2026-10-26, environment): WSL2 `Ubuntu-26.04`, Docker 29.9.2, `swegemma` installed, image
  `swebench-sandbox:latest`, 129 snapshots, LM Studio serving `gemma-4-31b-it-qat` at
  `127.0.0.1:1234`, `opencode` 1.18.25 in WSL with `opencode/deepseek-v4.1-flash`.
- L4 (2026-10-26, baseline): `uv run ruff check src/ tests/` clean; `uv run pytest tests/ -q` =
  `5 failed, 389 passed` (five known Windows path-separator/CRLF assertions).
- L5 (2026-10-26, design correction): issue #95's 12-method table omits `spec` and `substrate`,
  and `cli/_common.py` has a closed `BENCHES` tuple plus a hardcoded benchmark-to-dependency map
  in `preflight.py`. Level 1 is therefore a versioned patch, not a drop-in adapter.
- L6 (2026-10-26, Level 0 closed): fixed subset `dev-v1` (11 tasks, sha256 `a9ba8994...`),
  manifest/report experiment identity, runner `--subset`/`--experiment`, and the
  `experiments start|finish|show` CLI. Full suite `5 failed, 421 passed` (same five baseline
  node ids); `pack submission --check` green; journal `J-20261026-07`. `run-reports.md` also
  gained its missing six-field header while it was being updated.
- L7 (2026-10-26, Level 1 falsifier): PASS on 2 tasks x 2 trees (4 serial rollouts).
  All four archived; base/variant fingerprints `790d06db...` vs `602f49e9...`; all four
  patches differ. Total 5 204.30 s. Three rollouts 7.3-9.7 min; `requests_7315` variant
  3 626.02 s (60 min 26 s), 89/100 tool calls, 107 LLM calls, still resolved. No
  attribution: the falsifier declared no direction and ran one pair per task.
- L8 (2026-10-26, Level 1 closed): the adapter is versioned as a patch under
  `tools/harness2-swegemma/`; the clone and rollouts stay under `tmp/`/`runs/`. Level 2
  (full `k=1` Propose-Probe-Compose) is technically possible and deliberately not started;
  the next decision is its cost and domain, with the 60-minute outlier as the first warning.
