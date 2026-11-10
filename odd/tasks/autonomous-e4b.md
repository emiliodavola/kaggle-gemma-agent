# Autonomous E4B track, scoped to Resolution Rate

Objective: adapt the G4-PY-AGENT-001 specification and its RTX 3090 override to
this repository without leaving the competition contract, so the E4B agent
resolves more swegemma tasks within the 12 h hidden-set budget.
Branch: landing follows the normal feature-branch -> PR flow against `main`.
Delivery strategy: `ask-on-risk`; the adapter ships only if it beats the base
model by >= 3 resolved tasks on `ft-holdout` and `dev-v1` agrees.
Test runner: `uv run pytest -q` at the root; the training project is `training/`
(own uv project, Python 3.12, one RTX 3090 24 GB).
Tracking issue: #180.
Source specifications: `training/specs/gemma-4-e4b-autonomous.md`,
`training/specs/rtx3090-hardware-profile.md`.

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

**S6 — The harness-native dataset is the only training source.**
`vishalxyzabc7527/gemma4-swe-agent-sft-harness` revision
`7b3c7d619fa3c2f5d24a33bce5b413dcc48b2680`, config `sft`, splits `train`
(1,217) and `validation` (133). It ships 1,350 records, all `VERIFIED` and
`is_successful_demonstration`, with 722 repositories, 18,202 tool calls, 26,633
assistant messages, 407 multi-call turns, no orphan tool results and no unknown
tool names. It uses the harness tools directly (`run_command`, `read_file`,
`edit_file`, `write_file`, `submit_patch`, `get_status`). Dataset license is
`cc-by-4.0`; per-row repository licenses are permissive. Evidence:
`training/artifacts/reports/dataset_audit.json`, read 2026-11-09.

**S7 — Open-SWE-Traces is superseded; Hero and Zero stay deferred.**
`nvidia/Open-SWE-Traces` uses four foreign tools and a foreign system prompt, so
it is no longer a training source. `SWE-Hero` and `SWE-Zero` expose neither
`language` nor `resolved`, and SWE-Zero is execution-free; both remain out of
SFT until a verified language and execution signal exists.

**S8 — The dataset is validated, not translated.** No tool-name mapping is
applied: every record already carries the harness tool names and a
`tool_call_id` on every tool result. The mapper only replaces the dataset system
message with `submission/prompts/system.md`, strips null tool arguments, maps
`VERIFIED` -> `verified`, `PARTIALLY_VERIFIED` -> `declared`, `FAILED` ->
`failed`, `UNVERIFIED` -> `unknown`, and preserves multiple tool calls in one
assistant turn. A record that fails validation is dropped with a reason.

**S9 — The split is fixed and leakage is checked.** Training uses the dataset's
own `train` split. `ft-holdout.json` (29 tasks) and `dev-v1` are never trained or
selected on. Records whose repository is one of `fastapi/fastapi`,
`Textualize/rich`, `psf/requests`, `encode/httpx` are excluded; the audit found
zero such rows and zero holdout repository overlap. Evidence:
`experiments/subsets/`, `training/artifacts/reports/dataset_audit.json`.

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
- [x] T1 (S3) — `training/scripts/validate_environment.py` emits the hardware
  report and writes `training/artifacts/reports/environment.json`: RTX 3090,
  24 GB, CUDA 12.8, BF16 true, NF4 true, `compatibility_problems: []`.
- [ ] T2 (S5) — `inspect_model.py`: record revision, architecture, real module
  names, tokenizer/template, tool-call support and PEFT/quantization
  compatibility.
- [x] T3 (S6, S7) — dataset audit by streaming `data/sft_train.jsonl` and
  `data/sft_val.jsonl` (no JSONL persisted): 1,350 rows (1,217/133), 1,350
  distinct tasks, 722 repositories, all `VERIFIED` and successful, 18,202 tool
  calls, 26,633 assistant messages, 407 multi-call turns, 0 orphan results, 0
  unknown tools, 0 excluded competition repositories, 0 holdout repository
  overlap. Evidence: `training/artifacts/reports/dataset_audit.json`.
- [ ] T4 (S8, S10) — canonical message/tool schema and harness-native record
  mapper: replace the system prompt, strip null arguments, map verification
  status, preserve multiple calls per turn, pair results by `tool_call_id`, and
  drop invalid records with a reason. Round-trip test plus fixtures from the
  audited schema.
- [ ] T5 (S6, S9) — filters: `verification_status == VERIFIED`,
  `is_successful_demonstration == true`, per-row repository license allowlist
  and competition-repository exclusion; provenance preserved.
- [ ] T6 (S9) — deduplication (exact/normalized conversation hash, task hash,
  repo+issue, patch hash) and repository-level leakage report.
- [ ] T7 (S9) — repository-grouped splits and versioned manifests for the
  training corpus, separate from `ft-holdout`/`dev-v1`.
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
- Dataset: the harness-native `vishalxyzabc7527/gemma4-swe-agent-sft-harness`
  replaces `Open-SWE-Traces`; the OpenHands adaptation is dropped.
- SWE-Hero and SWE-Zero remain deferred for lack of `language`/`resolved`.
- The measured 10240 window supersedes the specification's 4096 default because
  the raw artifact is the source of truth.

**L6 — Known gaps.** The dataset's `test_results.exit_code` is 1 in 242 records
even though the row is `VERIFIED`; the status reasons, not the shell exit, are
the verdict. The dataset system prompt differs from the shipped prompt, so the
replacement is a distribution shift that T8/T9 must measure. The dataset has no
`language` column; every source task is a Python repository tested with pytest,
and the audit records that inference.

**L7 — User request (verbatim):** "necesito que cambiemos algo importante, el
dataset tiene que cambiar a
https://huggingface.co/datasets/vishalxyzabc7527/gemma4-swe-agent-sft-harness
dejemos de lado la adaptación de openhands y usemos este, rediseña todo, y si es
necesario cambiá el issue o la documentación"

## Next

T2 and T4 next: the model inspection report and the harness-native record mapper.
T4 is the gate that decides whether the 1,350 audited trajectories can be
serialized without losing a tool call.
