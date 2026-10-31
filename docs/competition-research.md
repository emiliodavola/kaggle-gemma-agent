---
Date: 2026-10-31
Genre: living reference
Status: current
Scope: Competition research: the goal, submission format, metric, harness/hardware budgets, permitted models and LoRA guidance; it does not cover our own run results.
Source of truth: the Kaggle competition listing and rules pages, `Model Selection, Budget, and Harness Rules`, `Evaluation`, `Prizes`, `Upgraded Accelerators` and the data page; read 2026-10-31.
Limits: research snapshot; platform rules and figures may change. The numbers below are as of 2026-10-31.
---

# Gemma 4 Developer Agent — Research report

Competition: `gemma-4-developer-agent` (Google, sponsor Google LLC).
Account status: rules accepted, `userHasEntered=True`.

## 1. What must be built?

Post-train / configure **Gemma 4** as an **autonomous software engineering agent**: it navigates real Python repos, diagnoses bugs/feature requests and generates patches that pass tests. The sponsor's thesis: top agents depend on commercial models with internet access; here we must achieve an agent capable **offline, on a single local model** (`gemma-4-31b-it-qat-w4a16-ct`).

There are two sister competitions:
- **This one** (`gemma-4-developer-agent`): prediction/agent, USD 65.000.
- **Paper track** (`gemma-4-developer-agent-paper`): document the approach (tuning/RL, code-graphs, benchmarks, graph reasoning), USD 35.000, deadline 12-nov-2026. Optional but it adds up and gives visibility (Google's NeurIPS-style workshop).

## 2. Submission format

A zip (`submission.zip`) with **declarative YAML** config at root — no `agent.py`:

```
submission.zip
├── agent.yaml                  # REQUERIDO (o agent.yml / root_agent.yaml/.yml, uno solo)
├── eval_config.yaml            # opcional: presupuestos por tarea
├── configs/sampling.yaml       # opcional, vía !include
├── prompts/*.md                # system.md, analyzer.md, vía !include
├── sub_agents/*.yaml           # sub-agentes o AgentTools
├── adapters/<nombre>/          # LoRAs PEFT: adapter_config.json + adapter_model.safetensors
└── skills/<skill>/SKILL.md     # skills ADK con frontmatter name:
```

Hard rules:
- Declarative YAML only (`compile_submission`, no `importlib`, no dynamic imports).
- No `..`, no symlinks outside the root, no pickle (`.bin/.pt/.pth` rejected; only `.safetensors`).
- Total uncompressed size **< 3 GiB** including adapters.
- Submission limits: **1 submission per day**, up to **2 finalists** to be judged. Today: 0 submissions used, 1 left today.

## 3. Metric and evaluation

- **SWE-bench** style: for each issue your patch is applied to the repo at `base_commit`, the official `test_patch` is applied and hermetic `pytest` is run.
- Task resolved ⇔ `exit_code == 0` **and** a valid JUnit XML with `passed > 0`, `failures == 0`, `errors == 0`, all required tests (FAIL_TO_PASS + PASS_TO_PASS) in passed with no skips.
- Global score = **Resolution Rate** = resolved / total, in [0.0, 1.0].
- Two-phase isolated cycle: **Container A** (your agent works in `/workspace`, snapshot without future history, offline) → patch extraction (`git add -N . && git diff`) → **Container B** (clean verification: resets tests/configs touched by your patch, applies `test_patch`, runs pytest).
- Agent limit: **12 hours** for all tasks (includes setup, excludes validation). `eval_config.yaml` allows per-task caps.
- Hidden test set: "about 120 tasks … evenly divided between the public and private splits" (data page, 2026-10-31); the public split is 58 tasks, so one task is worth 0.017 of the score.
- Watch out!: since the 2026-10-13 harness, `strip_protected_files_from_patch` removes any hunk touching tests or runner config (`conftest.py`, `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, `*.pth`, …) **from the patch itself**, in both `submit_patch()` and the unsubmitted-diff fallback, and the scorer also resets those paths. You have to fix the library code, not the tests.
- Watch out 2!: scratch scripts inside `/workspace` (e.g. `repro.py`) **enter the diff**. Use `/tmp` or delete them before `submit_patch()`.

## 4. Harness, model and budget

- Scoring hardware: **4× NVIDIA L4 (96 GB VRAM)**. vLLM with `tensor_parallel_size=4`, `gpu_memory_utilization=0.90` (raised from `0.80` in the 2026-10-13 harness), `max_model_len=32768`, `scheduler_reserve_full_isl=False`. LoRA is right-sized from the submitted adapters (`enable_lora=bool(adapters)`, `max_loras=len(adapters)`, `max_lora_rank=max(detected ranks)`), not fixed at 8/128.
- **One base model per submission, chosen from four**: `gemma-4-31b-it-qat-w4a16-ct` (~16–18 GB), `gemma-4-12b-it-qat-w4a16-ct` (~6–8 GB), `gemma-4-e4b-it-qat-w4a16-ct` (~3–4 GB), `gemma-4-e2b-it-qat-w4a16-ct` (~2–3 GB). Every agent and subagent must declare the same variant; mixing variants is not possible. Different LoRA adapters per agent are allowed. The 12B needs `--hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'`, which the scorer applies itself. The other aliases in `models.yaml` (`gemma-4-27b-it`, `gemma-4-26b-a4b-it`, `gemma-4-9b-it`, …) are registered for **local CLI evaluation only** and are not permitted in a submission.
- LoRAs: an agent may use a different adapter (`adapter: main_lora`), up to 8 simultaneous, rank ≤ 128. Budget: rank 16 ≈ 110–220 MB (~8 fit), rank 32 ≈ 220–450 MB (6–8), rank 64 ≈ 450–900 MB (3–6), rank 128 ≈ 0.9–1.8 GB (1–3).
- Context: **32.768 tokens** ceiling (prompt + thinking + output). Defaults: `max_output_tokens` 16.384, `thinking_budget` 4.096. For vLLM it is better to use `include_thoughts: true + thinking_budget` instead of `thinking_level`.
- Default per-task budgets (Stage 1 `inference.py`): 60 min per session (container setup is **not** discounted), 100 tool calls, 500 turns, individual command 300 s, verification `pytest` 300 s, output truncated to 5.000 chars, `read_file` to 150 lines / 10.000 chars. These are per-task defaults, not the run budget.
- **Run budget: 12 h for every task of the hidden set**, including sandbox setup and excluding patch validation. With ~120 hidden tasks that is ~6 min per task; the 60-minute default is unusable unless `eval_config.yaml` lowers it.
- 9 tools: `run_command`, `submit_patch` (free, closes the session when the turn ends), `get_status` (free), `read_file`, `edit_file` (resilient 3-level engine: exact/flexible/regex), `write_file`, `get_code_neighbors`, `search_similar_code` (note: no live embedding server — pass **symbols**, not natural language), `get_code_subgraph`.
- Anti-truncation: if thinking + tool call exceeds `max_output_tokens`, the `<|tool_call|>` tag is cut and the harness sends nudges (max 3). Small, incremental edits, `thinking_budget` ~4096.

## 5. Available data

Public training set (at scoring time it is replaced by a hidden test set with the same pipeline):
- **129 tasks** in `tasks.jsonl`: repos `fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx`. Fields: `instance_id`, `repo`, `base_commit`, `problem_statement`, `hints_text`, `patch` (reference, train only), `test_patch` (train only), `created_at`.
- `snapshots/`: 129 `.tgz` of the repo at `base_commit`, without future history.
- `graphs/`: 256 JSON (129 per task + hardlinks per commit) — AST/NetworkX call graphs for `get_code_neighbors`/`get_code_subgraph`.
- `embeddings/`: 256 `.npz` (256-d vectors per symbol) for `search_similar_code`.
- `wheels/`: 124 offline wheels (fastapi, starlette, pydantic, requests, rich, httpx, pytest...) mounted at `/wheels` — the sandbox is **air-gapped** (`network_mode=none`), 4 GiB RAM, 2 vCPUs.
- `docker/`: `Dockerfile.sandbox` (base python:3.13-slim + git + pytest) and `Dockerfile.public` (+ public wheel cache). `imp.py`/`telnetlib.py` shims for compatibility.
- `HARNESS_README.md` (49 KB, 671 lines): complete technical reference of the `swegemma` + `adk-submission` + `adk-eval-core` stack.

## 6. Timeline (all 11:59 PM UTC)

- 23-sep-2026: start.
- 12-nov-2026: paper track deadline (optional).
- 25-nov-2026: **entry deadline** (accept rules) and **team merger deadline**.
- 2-dic-2026: **final submission deadline**.

## 7. Prizes

Total USD 110.000 (as of 2026-10-31). This competition USD 65.000: 1st 37.000 / 2nd 18.000 / 3rd 10.000. Paper track USD 35.000. **Bonus USD 10.000** to the highest private score that uses `gemma-4-e2b-it-qat-w4a16-ct` or `gemma-4-e4b-it-qat-w4a16-ct`; the submission must be one of the team's two selected finals and stays eligible for the general leaderboard. Winners grant an open source license (Apache 2.0) for the submission.

## 8. Rules that matter

- Teams of up to 5; mergers allow up to the cap of accumulated submissions.
- Standard Kaggle eligibility (18+, no sanctions/export-control).
- Data: commercial use permitted under Apache 2.0, but do not redistribute to non-participants.
- **L4 sessions must have internet disabled** (*Upgraded Accelerators*). Circumventing it can be enforced by moderation, up to a team or account ban. L4x4 also consumes GPU quota at twice the T4x2/P100 rate.

## 9. Risks and next steps

Risks:
1. Short window and 1 submission/day → every submission counts; validate locally with `swegemma eval` first.
2. 32k context + tool call truncation → compact prompts, analyzer sub-agent (`AgentTool`, `skip_summarization`) so as not to burn the coder's window.
3. `search_similar_code` offline by symbol key → it does not work with natural-language questions.
4. Leaderboard on 2026-10-31: top 0.29 (Yurnero), the next fifteen teams 0.22-0.24, 4,269 teams. The hidden test set may be harder than the public corpus.

Proposed next steps:
1. Download the full dataset (`tasks.jsonl` + snapshots + graphs) and count its size.
2. Build a minimal baseline: `agent.yaml` with an LlmAgent coder + analyzer as AgentTool, no LoRA, and run `swegemma eval --task-ids` on 2–3 fastapi tasks.
3. Measure local resolution and consumption (tool calls, time) → define `eval_config.yaml`.
4. Only after that: serious prompt engineering and, if needed, LoRA rank 16–32 on the coder.

## 10. Verification (real outputs, read 2026-10-31)

- `kaggle competitions list --search gemma-4-developer-agent` -> both tracks; main deadline 2026-12-02, reward shown as 75,000 USD (65,000 + the 10,000 bonus), 4,269 teams, `userHasEntered True`.
- `kaggle competitions pages list` -> 10 pages, including the new `Upgraded Accelerators` one (the 2026-10-06 snapshot had 9).
- `Model Selection, Budget, and Harness Rules` -> four permitted models; the 12B override; LoRA per agent allowed.
- `Evaluation` -> 12 hours for all tasks, including sandbox setup, excluding validation.
- `data-description` -> ~120 hidden tasks, evenly split public/private; 129 public development tasks.
- `Prizes` -> 110,000 USD total: 65,000 main, 35,000 paper track, 10,000 small-model bonus (E2B/E4B).
- `competitions files` -> `HARNESS_README.md` 55,940 B dated 2026-10-13 (our local copy was 49,356 B dated 2026-10-01); `docker/` 4 files dated 2026-10-13.
- `competitions submission-limits` -> 0 submitted today, 1 lifetime submission, 1 remaining today.
- `competitions submissions` -> one submission (57718689, 2026-10-28), `COMPLETE`, no public score: *"Your submission notebook exceeded the allowed runtime."*
- `kaggle models variations get google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct` -> version 2, 11,546,103,780 uncompressed bytes.
