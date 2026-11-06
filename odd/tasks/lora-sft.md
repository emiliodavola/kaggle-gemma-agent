# LoRA SFT of the E4B

Objective: raise the resolution rate of the shipped agent by fine-tuning
`gemma-4-e4b-it` on trajectories a stronger teacher produces, without leaving the
competition contract (one base model, rank <= 128, archive < 3 GiB).
Branch: work lands as small feature branches against `main`; this file tracks the
feature, not a branch.
Delivery strategy: `ask-on-risk`; the adapter ships only if it beats the baseline
on the holdout.
Test runner: `uv run pytest -q` at the root; the training project is
`training/` (own uv project, Python 3.12, RTX 3090).

## Specs

**S1 — The prompt is closed.** The agent ignores nothing: the pre-submit gate ran
in 113 of 129 tasks and still 18 patches did not parse, while 48 failures were
`AssertionError`. More wording does not move it. Evidence:
`docs/runs/20261101T213823Z/01-pilot.md`, `runs/20261101T192008Z`.

**S2 — The 31B is not the answer.** Same submission tree, 30/122 resolved at
22.8 min/task. Against a 12 h budget for ~116 tasks that is `31 x 0.246 / 116 =
0.066`, below the E4B's 0.101 with every task completed. Throughput binds.

**S3 — The training window is 10240 tokens.** Measured on the 3090: 19.66 GB
peak, 12.6 s backward. Reached by four levers together — manual per-layer
checkpointing (the standard call is a no-op on this architecture), downcast of the
13 GiB fp32 embedding tables, chunked cross-entropy (the 262k-vocabulary logits
dominate otherwise) and the per-layer table in int8. 12288 allocates 22.29 GB and
collapses to an 822 s backward on paging. Evidence:
`training/smoke_qlora.json`, `docs/proposals/20261102-int8-embedding-table.md`.

**S4 — The teacher yields 32 trajectories.** `deepseek-v4.1-flash` over the 100
training tasks: 32 resolved (32.0%), 191.3 M tokens, zero API failures. It is
strong on rich (24/37) and weak on fastapi (6/52), so the dataset is not
corpus-shaped. Evidence: `docs/runs/20261102T214038Z/01-batch.md`.

**S5 — The split is fixed.** 100 train / 29 holdout, repository-stratified,
committed before any data existed (`experiments/subsets/ft-*.json`). The holdout
is the only selection signal; `dev-v1` is the secondary contrast.

**S6 — Measured per repository, never aggregated only.** The dataset skews to
rich and the holdout skews to fastapi, so a single aggregate number can hide a
real gain.

**S7 — The adapter must load where the scorer runs it.** Training uses the
unquantized checkpoint; the scorer serves `gemma-4-e4b-it-qat-w4a16-ct` through
vLLM. An adapter that trains but does not load there is a silent zero. This is
unvalidated and it is the cheapest risk to close.

**S8 — Nothing ships unless it beats the baseline by 3 tasks on the holdout**,
and `dev-v1` agrees.

## Tasks

- [x] T1 (S3) — environment: `training/` on Python 3.12, torch 2.11.0+cu128, verified against the 3090.
- [x] T2 (S3) — memory: the 10240 window, measured and recorded.
- [x] T3 (S4) — teacher batch: 100 tasks, 32 accepted, archived.
- [x] T4 (S5) — split committed with its `counts`.
- [x] T5 (S4) — resumable, quota-aware batch driver.
- [ ] T6 (S7) — **prove an adapter trains, saves and reloads.** No data cost.
- [ ] T7 (S6) — decision-point dataset builder at 10240.
- [ ] T8 — training script and first adapter.
- [ ] T9 (S6, S8) — evaluate on the holdout and `dev-v1`, per repository.
- [ ] T10 (S7) — load the adapter through vLLM with `qat-w4a16` (WSL or Kaggle).
- [ ] T11 — package under `submission/adapters/` and run the gate.

## Log

**L1 — User request (verbatim):** "necesito que nos concentremos solamente en las
notebooks, de ahora en adelante vamos a laburar en la plataforma de kaggle, si
necesitás anotarlo en AGENTS.md hacelo. Todos los cambios que hagas SIEMPRE tienen
que respetar las reglas de la competencia"

**L2 — User request (verbatim):** "#126 necesito que modifiquemos submission/
para mover el score, la medición creo que ya está completa por ahora"

**L3 — User request (verbatim):** "si creés que los prompts estan suficientemente
refinados tocar las configuraciones de tiempo no creo que logren mejores
resultados, que opciones nos quedan?"

**L4 — User request (verbatim):** "con una rama aparte arrancá con el fine-tuning,
necesito que vuelques todo el plan en un .md dentro de docs/ y tengas presente que
tenemos que entrenar en una RTX 3090"

**L5 — Decisions taken with the user.**
- Teaching, not instructing: the prompt plateaued, so the next lever is
  imitation.
- Teacher by API (`deepseek-v4.1-flash`), not a local model: the 3090 has one
  card and it is for the student.
- The window target moved from 12288 to 10240 because 12288 paginates; the
  measurement changed the plan, not the other way round.
- The dataset is built from resolved **and** `src_only` patches only.

**L6 — Known gaps.** Volume: ~30 usable trajectories is thin. Shape: the dataset
skews to rich while the holdout skews to fastapi. Both are recorded in T9 rather
than discovered later.

**L7 — Operational notes.** The host-trial runner has no resume and no
rate-limit handling on the eval path; `scripts/host-trial/batch_teacher.py` adds
both. The runner's phase 4 skips the wheelhouse install when `sweegemma` is on
`PATH`, so a stale global tool can shadow it (runbook 6.4).

## Next

T6 first, because it is unconditional: half an hour, no data, and it decides
whether T8 has a destination. T7 and T8 follow; T9 is the first number that
matters.
