# Competitive options playbook — `gemma-4-developer-agent`

Working document. It covers **only what relates to the competition**: how to
raise the resolution rate. It does not deal with eligibility, taxes or the legal
framework.

It rests on what already exists in the repo (`submission/`, `scripts/host-trial/`,
`docs/`) and on the findings in `odd/tasks/trial-collect-and-open-items.md`.
The budget numbers and the file paths are the project's real ones.

---

## 0. Operating constraints that condition every decision

| Constraint | Value | Source / where to change |
|---|---|---|
| Base model | single and mandatory: `gemma-4-31b-it-qat-w4a16-ct` (~16–18 GB, INT4 QAT) | `submission/agent.yaml` |
| Maximum context | 32.768 tokens (prompt + thinking + output) | `submission/configs/sampling.yaml` |
| Effective context (compaction) | **~14.336 tokens**: the evaluator compacts before the ceiling (see §10.1) | §10.1 |
| Window with LoRA | the KV cache shrinks; fewer adapters and low rank = more window (see §10.1) | §10.1 |
| Maximum output | `max_output_tokens: 16384` | `sampling.yaml` |
| Thinking budget | `thinking_budget: 4096` | `sampling.yaml` |
| Total agent time | **12 h** for all tasks (includes environment setup, excludes validation) | `eval_config.yaml` (per-task caps) |
| Per task | 100 calls / 60 min / 500 turns; command 300 s; command output 5.000 characters; `read_file` 150 lines / 10.000 characters | `submission/eval_config.yaml` |
| Tools | 9: `run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`, `write_file`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph` | `submission/agent.yaml` |
| Scoring environment | offline: no network, no installs, no servers, no background processes | system constraint |
| Adapters | up to 8 simultaneous, rank ≤ 128, total < 3 GiB | `submission/adapters/` folder |
| Delivery | `submission.zip` with `agent.yaml` at the root, declarative ADK config | `src/kaggle_gemma_agent/pack.py` |
| Submissions | 1 per day, up to 2 final ones | platform |
| Public set | 129 tasks (`fastapi`, `rich`, `requests`, `httpx`), with a reference `patch` | `data/raw/tasks.jsonl` |

**Consequence:** the order of power is: (1) measure, (2) use context and tools
better, (3) tune what the model is asked for, (4) only at the end, train.
The context (32.768 ceiling, but compaction to ~14.336) and the 100 calls are the
real bottleneck, not the model's knowledge.

---

## 1. Golden rule: measure before changing

Every change is tested against a local trial **before** spending a submission.
Without a baseline there is no way to know whether an idea adds anything.

### 1.1 How to run a local trial

```bash
# entorno
uv sync --locked
cp .env.example .env        # completar backend y clave (nunca commitear)

# un run sobre 2 tareas (default: fastapi_15661,fastapi_15588)
uv run python scripts/host-trial/run_host_trial.py run_01 --repair-sandbox-deps

# elegir tareas
HARNESS_TRIAL_TASKS=fastapi_14962,fastapi_15589 \
  uv run python scripts/host-trial/run_host_trial.py run_02 --repair-sandbox-deps

# leer el resultado
cat runs/<UTC>/STATUS
```

The runner archives into `runs/<UTC>/` and `report.json` already distinguishes
environment failures from agent failures (`environment_blocked`, `failure_kind`,
`verdict_source`).

### 1.2 What to record per experiment

- Resolution rate (resolved / measured).
- Calls and minutes per task (budget consumed).
- Failure reason (`collection_error`, `test_failure`, `timeout`, no verdict).
- Missing modules (so as not to confuse infrastructure with agent).

### 1.3 Filter "winnable" tasks before measuring seriously

Finding F2 in the repo: `fastapi_15661` is **unreachable without the hidden test**
(it requires names/signatures that do not appear in the statement). Measuring the
rate over tasks that are lost in advance distorts it. Proposal:

1. Run a broad trial (10–15 tasks).
2. Mark the ones that fail due to "unknown exact API" with no chance of deducing it.
3. Define a subset of "winnable" tasks to compare A/B changes.

It does not change the official score (the set is hidden), but it makes your
decisions rest on signal, not noise. Careful: there are public tasks that **nobody**
can solve because of bugs in the public wheelhouse (missing test dependencies,
`VERIFY_X509_STRICT` on py3.13); see §10.4.

---

## 2. Levers without training (highest return today)

### 2.1 System prompt — `submission/prompts/system.md`

It is the cheapest lever and usually yields more than an adapter. In addition to
the current text, consider:

- **Output contract**: force diagnosing, editing, verifying and **submitting**,
  with an explicit "done" criterion.
- **Anti-exploration rule**: forbid sightseeing commands (`git fsck`, listing
  `/root`, `pip download`) that do not get you closer to the patch.
- **Tool order**: prefer `edit_file` for editing; `run_command` only to run
  tests and bounded commands.
- **Point of no return**: at X calls remaining, stop exploring.
- **Sub-agent response format**: require exact paths and lines.

Verification: A/B with the same task set; compare calls and resolved.

### 2.2 Skills — `submission/skills/<nombre>/SKILL.md`

There are 12. Each one costs context on every turn (they load as reading
material). Recommended audit:

1. Measure the length of each `SKILL.md` (the very long ones cost tokens every turn).
2. Remove overlaps (for example, `systematic-debugging` vs
   `differential-diagnosis`; `test-driven-development` vs
   `python-testing-patterns`).
3. Ensure each step uses **only** the 9 tools.
4. That each one has a clear activation criterion ("Trigger: ...").

Example of correct mapping: `repo-mapping` → `run_command ls` + `read_file`;
`code-graph-navigation` → `get_code_neighbors` / `get_code_subgraph` /
`search_similar_code` with **symbols, not natural language**.

### 2.3 Tool policy / agent-tool interface

Fewer, larger calls:

- Prefer one broad and correct edit over many small edits.
- Do not re-read a file that has not changed (already in `budget-aware-tool-use`).
- Use `get_status` (free) to control the budget.
- Batch reads at the start; then edit and verify.

Finding F3 says the proxy model overuses `run_command`. Explicit rule:
"edit with `edit_file`/`write_file`; `run_command` is for tests".

### 2.4 Analyzer sub-agent — `submission/sub_agents/code_analyzer.yaml`

Today it analyses and returns a 15-line report. Ideas:

- Delegate localisation **only** when the repository is large.
- Keep `skip_summarization: true` so the report arrives raw.
- Limit its budget (so it does not eat calls the main agent needs).
- Tune `prompts/analyzer.md`: ask for paths+lines+exact symbol signature.

### 2.5 Context and truncation

The enemy is the tool-call block being cut off for exceeding
`max_output_tokens`. Rules:

- Low `thinking_budget` (≈4096) and incremental edits.
- Bounded command output (`| head`, `-q`).
- Do not dump whole files into context.
- Close each turn with a concrete action, not a monologue.

Also, the evaluator **compacts to ~14.336 tokens** and, with LoRA, the KV cache
shrinks (§10.1): plan for a small effective window, not 32k.

### 2.6 Generation parameters — `submission/configs/sampling.yaml`

```yaml
temperature: 0.2      # subir si el agente se traba; bajar si divaga
top_p: 0.95
max_output_tokens: 16384
thinking_config:
  thinking_budget: 4096   # subir si falla razonamiento; bajar si trunca
  include_thoughts: true
```

Test each change separately and measure.
Note (§10.1): `include_thoughts` was **disabling** reasoning instead of only
hiding it; verify before trusting that setting.

### 2.7 Pre-submission verification (already implemented)

The `verification-before-submit` skill now runs `python -m py_compile` on the
changed files and rejects junk files from the diff. Natural extension: have the
agent run the target test **once** and paste the output before submitting.

### 2.8 Graphs and vectors — use them well

`data/raw/graphs/` (call networks) and `data/raw/embeddings/` (per-symbol
vectors) back `get_code_neighbors`, `get_code_subgraph` and
`search_similar_code`.

- `search_similar_code` expects **symbols**, not questions: "serialize_response",
  not "how is it serialized?".
- Use `get_code_neighbors`/`get_code_subgraph` for blast-radius before editing.
- Document the pattern in `code-graph-navigation` so the agent repeats it.

### 2.9 Per-task budget — `submission/eval_config.yaml`

```yaml
evaluation:
  timeout_seconds: 3600
  max_tool_calls: 100
  max_time_minutes: 60
  max_turns: 500
```

The sum of the caps must fit within the 12 h. Strategy: give less to simple tasks
and reserve margin for the hard ones; do not give away an hour to all of them.
Tasks run **sequentially** and the scorer reads **only four fields**
(`timeout_seconds`, `max_tool_calls`, `max_time_minutes`, `max_turns`). Exceeding
the 12 h today **throws an error** (they plan to change it to "unfinished = 0");
set a moderate `max_time_minutes` as a lifeline (§10.3).

### 2.10 Packaging and compliance check

Before any submission:

```bash
uv run python -m kaggle_gemma_agent.pack submission --check   # 6/6
uv run pytest tests/ -q
uv run ruff check src/ tests/ scripts/
ruff format --check src/ tests/ ; uv run mypy src/ scripts/ ; uv run pyright
```

---

## 3. Data and context (without training)

### 3.1 What is in `data/raw/`

| Folder | Content | Use |
|---|---|---|
| `tasks.jsonl` | 129 tasks with `problem_statement`, `patch` (reference) and `test_patch` (training only) | understand problems; generate training data |
| `snapshots/` | 129 `.tgz` of the repo at `base_commit` | run the agent as in the competition |
| `graphs/` | 127 call-graph JSON files | feed the graph tools |
| `embeddings/` | 127 `.npz` (256-d per symbol) | feed `search_similar_code` |
| `wheels/` | offline packages | dependencies of the hermetic environment |

### 3.2 How to use them without training

- Build a per-repo symbol map (from `graphs/`) and dump it as a compact
  reference in a skill, so the agent does not guess names.
- Extract the reference patches (`patch`) and study the fix patterns per repo;
  turn them into skill rules.

### 3.3 External data

The competition allows external data and tools if they are publicly accessible
or "reasonable". For implementation: any data you use must be downloadable at no
cost by any participant. Document the source.

---

## 4. Training

It only makes sense **after** a measured baseline. Every adapter is packaged in
`submission/adapters/<nombre>/` and referenced with `adapter: <nombre>` in
`agent.yaml` or in a sub-agent.

### 4.0 Data format

Two sources:

1. **Direct pairs** (from the public set): `problem_statement` → reference
   `patch`. It is the cleanest supervision you have.
2. **Trajectories** (from your trials): agent steps up to a patch that passes
   the tests. They come from `runs/<UTC>/<tarea>/trace.json` and `session.log`.

Format of each example: list of messages (user/problem, assistant/call,
tool result, …, final patch), applying Gemma's chat template. Save as JSONL.

### 4.1 Supervised fine-tuning (SFT) with an adapter

Starting points evaluated in `docs/skill-stack-inventory.md`: **TRL**,
**PEFT**, **Unsloth**, **Axolotl**, **LlamaFactory**.

Base adapter configuration (adjust rank and target to the 3 GiB cap):

```python
from peft import LoraConfig
config = LoraConfig(
    r=32, lora_alpha=64, lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    bias="none", task_type="CAUSAL_LM",
)
```

Training (sketch):

```python
from trl import SFTTrainer, SFTConfig
trainer = SFTTrainer(
    model=base, tokenizer=tok, train_dataset=ds,
    args=SFTConfig(output_dir="out", num_train_epochs=2,
                   per_device_train_batch_size=1, gradient_accumulation_steps=8,
                   learning_rate=2e-4, max_seq_length=32768),
)
trainer.train()
```

Export to the adapter folder:

```python
model.save_pretrained("submission/adapters/main_lora")   # adapter_model.safetensors
tok.save_pretrained("submission/adapters/main_lora")     # + adapter_config.json
```

Verify: `rank ≤ 128`, `< 3 GiB`, and that `pack --check` is still 6/6.
To test adapters locally you must use **the patched wheel from the wheelhouse**
(the public PyPI wheel fails with Gemma4+LoRA, §10.5). And each adapter consumes
KV cache: low rank and few adapters (§10.1).

### 4.2 Preference optimization (DPO / KTO / ORPO)

With "patch that passes" vs "patch that fails" pairs for the same problem:

```python
from trl import DPOTrainer, DPOConfig
DPOTrainer(model=base, ref_model=ref, args=DPOConfig(...), train_dataset=pairs)
```

Useful when SFT has already learned the format but the model chooses badly
between two solutions. KTO tolerates unpaired data.

### 4.3 Reinforcement with verifiable reward (GRPO)

Reward = **the patch passes the tests**. It requires a parallel execution
environment (the same hermetic sandbox) that applies the patch and runs `pytest`.

```python
from trl import GRPOTrainer, GRPOConfig
GRPOTrainer(model=base, reward_funcs=[reward_patch_passes], args=GRPOConfig(...))
```

It is the most powerful lever and the most expensive: it demands orchestrating
containers and is sensitive to reward variance. It is justified only with a
baseline and SFT already working.

### 4.4 Distillation

Generate successful trajectories with a stronger model **outside** the
competition and use them as SFT data. It lowers the cost of getting good
examples. Officially enabled, with the caveat of licenses (§10.6).

### 4.5 Several adapters at once (up to 8)

One adapter per role:

- `main_lora` for the main agent.
- `analyzer_lora` for the analysis sub-agent.

In `agent.yaml` / `sub_agents/*.yaml`: `adapter: main_lora`. Keep the total
< 3 GiB by splitting rank between both.

### 4.6 Variants within budget

- **QLoRA** (4-bit + LoRA) to train with less memory.
- **DoRA** as an alternative to LoRA.
- Choose `target_modules` and rank according to the size cap; measure the real
  effect, do not assume.

### 4.7 Adapter packaging

- `adapter_config.json` + `adapter_model.safetensors` inside
  `submission/adapters/<nombre>/`.
- No `.bin`/`.pt`/`.pth` (rejected).
- Run `pack --check` to confirm size and format.

### 4.8 Training infrastructure

Scoring uses 4×L4 (96 GB). Training locally requires a GPU with enough memory
(QLoRA/Unsloth for the 31B model). Document the platform and the reproduction
steps, because a winner must be able to reproduce.

### 4.9 Adapter wiring

```yaml
# submission/agent.yaml (y/o sub_agents/code_analyzer.yaml)
name: kaggle_gemma_agent
model: gemma-4-31b-it-qat-w4a16-ct
adapter: main_lora      # <-- agrega esta línea cuando exista el adaptador
```

### 4.10 How to evaluate an adapter

1. `pack --check`.
2. Local trial over the "winnable" subset.
3. Compare rate, calls and time against the baseline **without** an adapter.
4. If it does not improve the rate, it is not submitted.

---

## 5. Article track (optional, $35.000)

It closes on **12-nov-2026**. Topics the organizer asks for:

- **Fine-tuning and optimization**: PEFT and RL for software agents.
- **Code understanding**: code graph, parsing, embeddings.
- **Tasks and benchmarks**: new sets/resources.
- **Reasoning over graphs**.

You can write about the same competition work (using the graphs/embeddings
dataset they published adds to it).

---

## 6. Submission strategy

- Validate **everything** locally before spending the day's submission.
- 1 submission per day: save it for a measured change, not for a hunch.
- Choose the **2 final ones** carefully: the one with the best local rate, not
  the last one you uploaded.
- Do not leave the compliance safety zone (format, caps, adapters).

---

## 7. Suggested week-by-week roadmap

| Week | Focus |
|---|---|
| 1 | Clean local baseline on WSL/Linux + winnable-task filter (section 1) |
| 2 | Levers 2.1–2.6 (prompt, skills, interface, context, sampling) with A/B |
| 3 | Graphs/embeddings (2.8) + per-task budget (2.9) + consolidation |
| 4 | Training data (4.0) + first SFT (4.1) and evaluation (4.10) |
| 5 | Preferences (4.2) or verifiable RL (4.3) if SFT showed a ceiling |
| 6 | Fine-tuning the best combination; multi-adapter (4.5) |
| 7 | Final submissions + article (section 5) if applicable |
| 8 | Reserve for unforeseen events |

---

## 8. Experiment log (template)

| Date | Change | File(s) | Tasks | Resolved | Calls | Note |
|---|---|---|---|---|---|---|
| | baseline | — | | | | |
| | | | | | | |

Rule: one change per experiment; if it cannot be isolated, it cannot be attributed.

---

## 9. Recommended implementation order

1. Measurement and task filter (§1).
2. Prompt + skills + interface + context + sampling (§2.1–2.6).
3. Graphs and budget (§2.8–2.9).
4. SFT (§4.0–4.1, 4.7–4.10).
5. Preferences or RL (§4.2–4.3).
6. Consolidation, submissions and article (§5–6).

---

## 10. Kaggle forum findings and their impact

**Method and caveat.** I read the threads with the Kaggle API
(`kaggle competitions topics show <id>`). I could not list the official hosts (the
API returned 403), so I mark as an **official answer** only those from authors who
speak on behalf of the organization and perform evaluator maintenance —
mainly **Ryan Holbrook** (who also publishes the official notebook) and, in
an institutional answer, **Ashley Oldacre**. The rest is from participants:
useful, but **not official**. I did not invent authorships or quotes.

### 10.1 Context, compaction and KV cache (corrects section 0)

- The hard ceiling is **32.768** combined tokens, but the evaluator **compacts to
  ~14.336** (`token_threshold = 14.336`). The real working context is ~14k. A
  participant asked to confirm whether the scorer uses 14.336 or 32.768; the staff
  said they would look into it.
- **With LoRA enabled, the KV cache shrinks.** It was reported that with a rank-64
  adapter the KV cache dropped to ~7.600 tokens and prompts of ~14.000 tokens
  **hung**. Official answer: vLLM now adjusts the LoRA parameters according to what
  you submitted; **fewer adapters and lower rank (or none) leave more
  memory for the KV cache**.
- `include_thoughts` was **disabling** reasoning instead of only
  hiding it (reported on `adk_submission 0.2.12`; no official answer yet).

Implication: plan for an effective window of ~7–14k tokens, not 32k; and treat each
adapter as a context cost.

### 10.2 Evaluator bugs and status

- **Thoughts dropped between calls** (vLLM ignored `reasoning_content`):
  confirmed as a bug; fixed in the current wheelhouse. **Old submissions are not
  rescored.**
- **Tool results with double JSON encoding**: fixed in the
  Sep-30 wheelhouse; `edit_file` added a fallback.
- **`thinking_budget` and `seed` were not sent**: fixed in the recent
  wheelhouse.
- **Adapters silently deleted** (patched vLLM 0.19.1): fixed since
  wheelhouse v23.
- **Official `sample_submission` failed**: fixed.
- **Undeclared tool ends the task and discards the patch**: the staff said
  they would implement it. → Declare only the tools you use.
- **Bug with skills + `run_skill_script`** (`file_path` as a list → exception that
  ends the task): reported. → Be careful with scripts in skills.
- **Submission errors after Sep-30**: it was a GPU outage; resolved.

### 10.3 Budget and execution

- Tasks run **sequentially**.
- The scorer reads **only four fields** of `eval_config.yaml`: `timeout_seconds`,
  `max_tool_calls`, `max_time_minutes`, `max_turns`; by default, no limit.
- Exceeding the 12 h **today throws an error**; they plan to change it to
  "unfinished tasks = 0". The staff recommends setting a moderate
  `max_time_minutes` as a lifeline.

### 10.4 Broken public tasks (do not over-optimize)

- Test dependencies are missing from the public wheelhouse (`typing_inspection`,
  `inline_snapshot`, `dirty_equals`, `ujson`/`orjson`, `python-multipart`,
  `pytest-httpbin`): the reference patch fails on many FastAPI/requests tasks.
- Python 3.13 enables `VERIFY_X509_STRICT`, and the `pytest-httpbin` certificate has
  no AKI → https tests always fail (≈8 requests tasks).
- Version-gated tests with `skipif` that are skipped on 3.13.
- There is **domain shift** between the public repos and the hidden evaluation
  (open thread).

Implication: the rate over the 129 public tasks **is not** comparable with the
official score; filter out the unsolvable ones (§1.3) and use the official
getting-started notebook.

### 10.5 Adapters and vLLM

- Only the patched wheel from the wheelhouse supports LoRA for Gemma4; the public
  PyPI wheel fails at startup ("does not support LoRA yet"). → To test adapters
  locally, use the competition wheelhouse.
- `discover_adapters` expects the **submission root**, not the adapter folder.

### 10.6 Distillation

Institutional answer (Ashley Oldacre): external models may be used to
distill **provided that** they are used according to their license and that the
result does not conflict with the competition rules. → Enables the approach of
§4.4, with the caveat of licenses.

### 10.7 Leaderboard signals

Official `sample_submission` ~0.01; reported minimum submissions 0.08–0.12; the
public ceiling is around ~0.15. There is margin.

### 10.8 Reference threads

| Thread | Topic | Official answer |
|---|---|---|
| 744354 | Thoughts dropped between calls | Yes (fixed) |
| 744331 | KV cache with LoRA / hangs | Yes (dynamic adjustment) |
| 744692 | Compaction threshold | Yes ("I'll look into it") |
| 744794 | Bug and status summary | Yes |
| 743063 | Concurrency, `eval_config`, 12 h | Yes |
| 743213 / 743508 | Adapters/LoRA, `sample_submission` | Yes |
| 744272 | Tool result with double JSON | Yes |
| 745028 | Undeclared tool | Yes (to be implemented) |
| 744807 | Errors after the Sep-30 wheelhouse | Yes (GPU outage) |
| 742882 | Local evaluation, missing deps | Yes |
| 742911 | Empty graphs/embeddings | Yes (partial) |
| 742807 | Distillation from external LLMs | Yes (Ashley Oldacre) |
| 743973 | Reference patches fail offline | No (participants) |
| 743186 | Infra for SFT/RL | No (participant) |
| 745059 | `include_thoughts` disables reasoning | No |
| 745774 | The agent repeats the same command | No |
| 745796 | Domain shift | No |

### 10.9 Rectification after host trial `20261006T103737Z` (run_03)

Full audit in `docs/runs/20261006T103737Z/01-audit.md`; the breakdown
by system-prompt version is in
`docs/runs/20261006T103737Z/03-failures-by-prompt-version.md`. The comparison between
prompt phases that follows is **descriptive** and suggested by this analysis: **Emilio did
not ask for or require an A/B**, it is not a requirement and it is not a technique applicable with
statistical rigor on this run (confounded phases, small n, no
randomisation). Actionable summary:

- **The premise "only the prompt changed to v2" is false.** run_02 was already running v2,
  and run_03 mixed **v2 (21 tasks) + v3a (11) + v3 (16)** because the shared
  checkout materialised the prompt as commits landed; moreover the
  set became 100 % `rich` (previously mixed). There is no interpretable comparison
  (nor an A/B, which was not requested).
- **§2.1 (prompt)**: the v3 phase performed **worse** (0.438) than v2 (0.714), with
  task order as a confounder. v3 **removed** strong rules from v2 (40-call
  cap, "do not stop at analysis", `git status` cleanup). Recommendation: do not
  adopt v3; redesign from v2 and compare again (descriptively) with a
  mixed batch + a no-patch control.
- **§1 (measure)**: the current report does not distinguish `pass_to_pass`
  regression, a patch with no source changes, or broken baseline nodes. There were **3 tasks
  "resolved" without editing source** (real rate ≤ 0.542) and **4 console tests that
  fail without the patch causing them**. Without a no-patch control the metric is
  inflated and contaminated.
- **§2.3 (`run_command` abuse)**: confirmed; it is the dominant tool in
  almost all the failures.
- **§2.5 / §2.6 (latency)**: **47 % of failures are process failures** (6 timeouts
  of 60 min, 2 exhaustions of 100 calls, 1 without `submit_patch`); ≈ 35–58 s per
  tool call. The bottleneck is time, not knowledge.
- **§10.2 / §10.4**: confirmed with new evidence (test imports to
  `site-packages`, required node that "does not pass" with `exit 0` in `rich_3486`).
- **Hygiene**: 26/46 patches include scratch; 1 modifies a test. Add
  a pre-submit self-check.
- **Runner golden rule**: add a hash of the materialised prompt, install/pytest
  command, `fail_to_pass`/`pass_to_pass` per node, no-patch
  control and a "resolved without source hunks" warning.
- **Caveat**: validating only with `rich_*` is **overfitting**; use the 4
  repos (fastapi/requests/rich/httpx) in any future comparison
  (suggested by the analysis, not a required A/B).
