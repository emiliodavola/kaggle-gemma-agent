# Autonomous E4B track, scoped to Resolution Rate

Objective: adapt the G4-PY-AGENT-001 specification and its RTX 3090 override to
this repository without leaving the competition contract, so the E4B agent
resolves more swegemma tasks within the 12 h hidden-set budget.
Branch: landing follows the normal feature-branch -> PR flow against `main`.
Delivery strategy: `ask-on-risk`; the adapter ships only if it beats the base
model by >= 3 resolved tasks on `ft-holdout` and `dev-v1` agrees.
Test runner: `uv run pytest -q` at the root; the training project is `training/`
(own uv project, Python 3.12, one RTX 3090 24 GB).

## Specs

**S1 — The competition contract is the outer boundary.** One base model
(`gemma-4-e4b-it-qat-w4a16-ct`) declared everywhere, adapter rank <= 128, packed
archive < 3 GiB, nothing under `submission/` that needs network, pip, MCP or
subprocess, per-task 100 tool calls / 60 min / 500 turns. The autonomous track
never changes those limits. Evidence: `AGENTS.md`, `submission/agent.yaml`,
`submission/eval_config.yaml`.

**S2 — Train on the unquantized checkpoint, score on the QAT one.** Training
loads `google/gemma-4-E4B-it` revision
`4ecc2ba63bcac23ba4a767fc87025b1450f84c9c`; the scorer serves
`gemma-4-e4b-it-qat-w4a16-ct` revision
`6cd26aaa2357fb2bad8c51699a7558a4d1a965bb`. An adapter that does not load in the
scorer's vLLM is a silent zero. Evidence: `training/README.md`,
`odd/tasks/lora-sft.md` S7.

**S3 — The measured memory envelope is the source of truth.** `training/smoke_qlora.json`
measures 10240 tokens at 19.66 GB peak and 12.6 s backward with manual per-layer
checkpointing, bf16 downcast of the embedding tables, chunked cross-entropy and
the per-layer table in int8. 12288 tokens allocates 22.29 GB and paginates
(822 s). The specification's 4096 default is a fresh-hardware floor, not a cap.
Evidence: `training/smoke_qlora.json`,
`docs/proposals/20261102-int8-embedding-table.md`.

**S4 — Standard gradient checkpointing is a no-op on this architecture.** The
first SFT experiment MUST wrap each language layer in
`torch.utils.checkpoint`; `gradient_checkpointing_enable()` alone peaks at
32.1 GB for a 1024-token step. Evidence: `training/smoke_qlora.py`,
`training/README.md`.

**S5 — LoRA targets are discovered, never assumed.** The candidate list
`q_proj/k_proj/v_proj/o_proj` must be validated against the loaded model; the
working implementation targets `language_model.layers.*`. The vision and audio
towers wrap projections in `Gemma4ClippableLinear`, which PEFT cannot inject
into. Evidence: `training/README.md`, `training/smoke_qlora.py`.

**S6 — Open-SWE-Traces is the only external dataset with usable filters.**
`nvidia/Open-SWE-Traces` revision
`4fa4c2ae9afc6b397bc50391d43450c79993c138`, license `cc-by-4.0`, exposes
`language` and `resolved` (int32) plus `repo`, `license`, `messages`, `tools`,
`metadata{category,teacher_model,reference_patch,model_patch}` and
`hf_dataset_name`. Configuration `v2.0` (teacher `Qwen3.8-Flash-Next`) is the
newest. Evidence: HF dataset API and rows, read 2026-11-09.

**S7 — SWE-Hero and SWE-Zero are deferred.** Both expose only
`instance_id, repo, license, trajectory_id, trajectory, model_patch, dataset`;
neither has `language` nor `resolved`. SWE-Zero is explicitly execution-free.
Filtering Python would require an unverified repository-name heuristic, and
"resolved" cannot be established at all. They stay out of SFT until a verified
language and execution signal exists. Evidence: HF dataset cards, read 2026-11-09.

**S8 — External trajectories are auxiliary and must be re-serialized.** The
`openhands` split exposes four tools (`execute_bash`, `think`, `finish`,
`str_replace_editor`), not the harness's nine. A raw OpenHands record is
discarded or mapped; it is never trained as-is. The harness tools are
`run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`,
`write_file`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`.
Every record must replace the OpenHands system prompt with
`submission/prompts/system.md`, map tool calls and results, and be re-serialized
through the Gemma 4 chat template. Evidence: HF rows for `v2.0/openhands`,
`data/raw/HARNESS_README.md` section 6.

**S9 — The split is fixed and leakage is checked.** Training uses only
`experiments/subsets/ft-train.json` (100 tasks). `ft-holdout.json` (29 tasks) and
`dev-v1` are never trained or selected on. External records whose `repo` is one
of `fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx` are
excluded. Evidence: `experiments/subsets/`, `odd/tasks/lora-sft.md` S5.

**S10 — Loss is masked to assistant behaviour.** Tool outputs are never trained
as assistant text; tool-call arguments and the assistant turn after a tool
result do carry loss. Truncation preserves complete message boundaries and never
leaves an unmatched tool call. Evidence: `training/train_lora.py` (masked loss),
G4-PY-AGENT-001 section 10.1.

**S11 — Success is measured, not claimed.** The only shipping signal is
`ft-holdout`: >= 3 more resolved tasks than the base model, with `dev-v1`
agreeing, reported per repository. SWE-bench, HumanEval and MBPP are optional
diagnostics, never shipping gates. Evidence: `odd/tasks/lora-sft.md` S8.

## Tasks

- [x] T0 (S1, S3, S6, S7, S8) — write this tracker, the spec-aligned
  `training/` scaffold, configs, environment validator and layout test; prove
  the competition gate is unchanged.
- [ ] T1 (S3) — make `training/scripts/validate_environment.py` emit the full
  hardware report (GPU, VRAM, CUDA, torch, compute capability, BF16, BnB 4-bit
  init, headroom) and record it under `training/artifacts/reports/`.
- [ ] T2 (S5) — `inspect_model.py`: record revision, architecture, real module
  names, tokenizer/template, tool-call support and PEFT/quantization
  compatibility.
- [ ] T3 (S6, S7) — dataset census: for `Open-SWE-Traces` v2.0, download only
  `repo`, `language`, `resolved`, `license`, `metadata` columns; count Python,
  resolved, per-repository and tool-mapping coverage per split; pick the split
  by count, not by guess; record Hero/Zero as deferred.
- [ ] T4 (S8, S10) — canonical message/tool schema and deterministic OpenHands
  -> harness mapper, with round-trip test on representative records.
- [ ] T5 (S6, S9) — filters: Python, `resolved == 1`, per-row license allowlist,
  mappable tools, competition-repository exclusion; provenance preserved.
- [ ] T6 (S9) — deduplication (exact/normalized conversation hash, task hash,
  repo+issue, patch hash) and repository-level leakage report.
- [ ] T7 (S9) — repository-grouped splits and versioned manifests for the
  auxiliary corpus, separate from `ft-train`/`ft-holdout`.
- [ ] T8 (S3, S4, S10) — first SFT at the measured 10240 configuration with the
  mandatory preflight (forward, backward, optimizer step, >= 2 GB headroom,
  adapter save/reload); checkpoint and resume.
- [ ] T9 (S11) — evaluate on `ft-holdout` and `dev-v1`, per repository, JSON and
  Markdown reports; decide ship/no-ship at +3 resolved tasks.
- [ ] T10 (S2) — load the adapter through vLLM with `qat-w4a16` (WSL or Kaggle)
  and prove parity with the training checkpoint.
- [ ] T11 (S1) — package the adapter under `submission/adapters/`, run the
  compliance gate and record the journal entry.
- [ ] T12 (optional) — DPO only if >= 500 verified preference pairs exist;
  otherwise defer.

## Log

**L1 — User request (verbatim):** "podrias leer @gemma-4-e4b-autonomous.md y
@hardware.md y crear un issue super detallado y sin ambiguedades de ningun tipo
para luego implementarlo? necesito que hagas todas las pasadas necesarias para
documentarlo correctamente, si necesitás dejar en el repo un .md para enriquecer
el issue hacelo"

**L2 — User request (verbatim):** "quiero que reestructures el proyecto para que
se adapte a los .md pero sin romper las reglas de la competencia"

**L3 — User request (verbatim):** "concentrate en los datasets en los que puedas
obtener mejores resultados con sus filtros, si hay algunos que no podes
seleccionar lenguaje, creo que deberiamos dejarlos para otro momento, no?"

**L4 — User request (verbatim):** "el uso de openhands rompe algo de lo que
estamos haciendo?"

**L5 — Decisions taken with the user.**
- Scope: extend `training/` and aim at the submission; the competition contract
  is the outer boundary.
- Dataset: `Open-SWE-Traces` is the only external source kept; SWE-Hero and
  SWE-Zero are deferred for lack of `language`/`resolved`.
- OpenHands trajectories are auxiliary and require normalization; they are not
  trained raw.
- The measured 10240 window supersedes the specification's 4096 default because
  the raw artifact is the source of truth.

**L6 — Known gaps.** T3 must measure which `Open-SWE-Traces` split yields the
most Python resolved records with mappable tools; the datasets-server
`filter`/`search` endpoints returned HTTP 500 on 2026-11-09, so the count comes
from a column-pruned local download, not from the web API.

## Next

T1 and T3 first: the environment report and the dataset census decide whether the
auxiliary corpus is worth normalizing before any training change.
