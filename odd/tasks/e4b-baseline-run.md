# E4B baseline run

Objective: run the tuned harness on `gemma-4-e4b-it-qat-w4a16-ct` on Kaggle and
produce the first complete small-model baseline of the 129-task public corpus.
Branch: `feat/e4b-baseline-run` (from `main`).
Delivery strategy: `ask-on-risk`; the competition submission stays manual.
Test runner: `uv run pytest -q`; notebook code cells are compile-checked before
the remote run, which is the only real verification.

## Specs

**S1 — One variable changed in the submission.** `submission/agent.yaml` and
`submission/sub_agents/code_analyzer.yaml` declare
`gemma-4-e4b-it-qat-w4a16-ct`. Prompts, skills, sampling and
`submission/eval_config.yaml` stay byte-identical, so a difference against the
31B runs is attributable to the base model.

**S2 — The compliance gate accepts the four permitted models.** Rule `c` of
`check_submission` accepts exactly
`gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`,
`gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`; a model outside
that set and two different models both stay violations. Without this the
notebook aborts at its gate cell before spending GPU time.

**S3 — The notebook fails fast, before 129 tasks, on a bad model.** After the
server starts it asserts the declared model equals the expected one
(`EXPECTED_MODEL` in the config cell), then runs a preflight: `/v1/models`
answers, one chat completion returns, and one tool-call round trip returns a
parsed call. Any of the three failing aborts the run with a named reason. The
E4B tool-call parser is a known risk (discussion 753973), so a broken parser must
cost minutes, not a whole session.

**S4 — Scoring parity and a clock guard.** `gpu_memory_utilization` is `0.90`
(the value `HARNESS_README.md` documents since 2026-10-13; the notebook carried
the stale `0.80`). The task-selection cell computes the worst-case wall clock
`tasks * max_time_minutes / concurrency` and refuses to start when it exceeds
`MAX_WORST_CASE_HOURS` (10.5 h), so one caught task cannot kill a 12 h session
before the archive cell runs.

**S5 — Offline run, provenance recorded.** L4 sessions must have internet
disabled, so the repository arrives as the attached dataset
`bistiarj/kaggle-gemma-agent-code` and its `COMMIT` file. The notebook records
the commit, the model source slug and the dataset version in `run_meta.json`;
the run is reproducible without reading chat logs.

**S6 — Delivery.** Branch, commits, push, PR assigned to `emiliodavola`. No
competition submission: the user selects it manually.

## Tasks

- [ ] T1 (S2) — `pack.py` rule c accepts the four models; tests cover accept, reject and mixed.
- [ ] T2 (S1) — both submission YAMLs declare E4B.
- [ ] T3 (S3, S4) — notebook: expected-model assert, preflight smoke, 0.90, clock guard, provenance.
- [ ] T4 (S5) — offline repo dataset refreshed from the branch, `COMMIT` written.
- [ ] T5 (S6) — docs (`kaggle-remote-run.md`, `competition-research.md`, `AGENTS.md` rule c) and the journal entry.
- [ ] T6 — full test suite green; every notebook code cell compiles.
- [ ] T7 — kernel pushed and launched on Kaggle (L4 x4, internet off).
- [ ] T8 — PR opened and assigned to `emiliodavola`.

## Log

**L1 — User request (verbatim):** "adaptá la notebook para correr E4B, versioná
todo en rama aparte, lanzá la ejecución en kaggle, luego pusheá, hacé PR
asignandomelo a mi / vamos a hacer la primera corrida, para tener un baseline
completo, esforzate que no haya ningún hueco o problema / el submission (si se
puede hagamoslo manual para decidir cuando y como)"

**L2 — Evidence read before the change (2026-10-31).**
`kaggle competitions pages` (Model Selection page lists four models; Prizes adds
the USD 10,000 small-model bonus; Evaluation states 12 h for all tasks;
data-description states ~120 hidden tasks split public/private).
`HARNESS_README.md` from the competition files is 55,940 B dated 2026-10-13,
ours was 49,356 B dated 2026-10-01; the diff documents
`gpu_memory_utilization=0.90`, LoRA right-sizing, `ToolErrorPlugin`,
`strip_protected_files_from_patch`, `compaction_interval=15` and a separate
`verification_timeout_seconds`.
`kaggle kernels pull bistiarj/kaggle-run -m` shows the working launch recipe:
`enable_internet: false`, `machine_shape: NvidiaL4`, a pinned python-3.12
`docker_image`, `dataset_sources` = wheelhouse + code dataset, `model_sources`
= `google/gemma-4/Other/<model>/2`.
`kaggle models variations get google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct`
returns version 2, `totalUncompressedBytes` 11,546,103,780.
The official getting-started notebook applies `--hf-overrides` only to the 12B,
so the E4B needs no override.

**L3 — Decision.** Change exactly one variable (the base model) and keep the
tuned tree, so the E4B number is comparable with `runs/20261027T140509Z` (31B,
11 tasks, 5 resolved) and `runs/20261028T031307Z` (31B, 11 tasks, 4 resolved).
The corpus stays the full 129 tasks at concurrency 4, which the earlier quota
math puts at 5.4–8.8 h for the 31B; the clock guard is what makes it safe for a
model we have never measured.
