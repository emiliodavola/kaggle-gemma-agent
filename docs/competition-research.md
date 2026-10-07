---
Date: 2026-10-06
Genre: living reference
Status: current
Scope: Competition research: the goal, submission format, metric, harness/hardware budgets and LoRA guidance; it does not cover our own run results.
Source of truth: the Kaggle competition listing and rules pages; read 2026-10-06.
Limits: research snapshot; platform rules and figures may change.
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
- Watch out!: if your agent modifies tests or configs (`conftest.py`, `pytest.ini`, `pyproject.toml`, etc.), the harness **reverts** them before verifying. You have to fix the library code, not the tests.
- Watch out 2!: scratch scripts inside `/workspace` (e.g. `repro.py`) **enter the diff**. Use `/tmp` or delete them before `submit_patch()`.

## 4. Harness, model and budget

- Scoring hardware: **4× NVIDIA L4 (96 GB VRAM)**. vLLM with `tensor_parallel_size=4`, `gpu_memory_utilization=0.80`, `max_model_len=32768`, `enable_lora=True`, `max_loras=8`, `max_lora_rank=128`.
- **A single base model per submission, mandatory**: `gemma-4-31b-it-qat-w4a16-ct` (QAT INT4 variant, ~16–18 GB). All agents/sub-agents must declare it.
- LoRAs: an agent may use a different adapter (`adapter: main_lora`), up to 8 simultaneous, rank ≤ 128. Budget: rank 16 ≈ 110–220 MB (~8 fit), rank 32 ≈ 220–450 MB (6–8), rank 64 ≈ 450–900 MB (3–6), rank 128 ≈ 0.9–1.8 GB (1–3).
- Context: **32.768 tokens** ceiling (prompt + thinking + output). Defaults: `max_output_tokens` 16.384, `thinking_budget` 4.096. For vLLM it is better to use `include_thoughts: true + thinking_budget` instead of `thinking_level`.
- Default budgets (Stage 1 `inference.py`): 60 min per session (container setup is **not** discounted), 100 tool calls, 500 turns, individual command 300 s, output truncated to 5.000 chars, `read_file` to 150 lines / 10.000 chars.
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

Total USD 100.000. This competition USD 65.000: 1st 37.000 / 2nd 18.000 / 3rd 10.000. Paper track USD 35.000. Winners grant an open source license (Apache 2.0) for the submission.

## 8. Rules that matter

- Teams of up to 5; mergers allow up to the cap of accumulated submissions.
- Standard Kaggle eligibility (18+, no sanctions/export-control).
- Data: commercial use permitted under Apache 2.0, but do not redistribute to non-participants.

## 9. Risks and next steps

Risks:
1. Short window and 1 submission/day → every submission counts; validate locally with `swegemma eval` first.
2. 32k context + tool call truncation → compact prompts, analyzer sub-agent (`AgentTool`, `skip_summarization`) so as not to burn the coder's window.
3. `search_similar_code` offline by symbol key → it does not work with natural-language questions.
4. Current leaderboard low (top ~0.15): there is room, but the hidden test set may be harder.

Proposed next steps:
1. Download the full dataset (`tasks.jsonl` + snapshots + graphs) and count its size.
2. Build a minimal baseline: `agent.yaml` with an LlmAgent coder + analyzer as AgentTool, no LoRA, and run `swegemma eval --task-ids` on 2–3 fastapi tasks.
3. Measure local resolution and consumption (tool calls, time) → define `eval_config.yaml`.
4. Only after that: serious prompt engineering and, if needed, LoRA rank 16–32 on the coder.

## 10. Verification (real outputs from this session)

- `kaggle competitions list --search gemma-4-developer-agent` → detects both, main with deadline 2026-12-02, 65.000 USD, 502 teams, `userHasEntered True`.
- `competitions files` → `HARNESS_README.md` (49.356 B) + `docker/` (4 files) + hundreds of `embeddings/*.npz` (~4–6 MB each).
- `competitions pages` → 9 pages: data-description, Description, Evaluation, rules, abstract, Timeline, foundational-rules, Prizes, Model Selection Budget and Harness Rules.
- `competitions pages list --content --page-name <p>` (with `config set competition`) → full content of the 9 (total ~52 KB).
- `competitions leaderboard --show` → top Makus 0.15 (26-sep-2026).
- `competitions submission-limits` → 0 submissions today and lifetime, 1 left today.
- Downloads OK: `HARNESS_README.md`, `Dockerfile.public/sandbox`, `imp.py` (telnetlib.py of 23 KB was left pending, it is only a shim).
