# Competition data inventory — `gemma-4-developer-agent`

Snapshot of the public dataset for the Kaggle **Gemma 4 Developer Agent**
competition, captured off-Kaggle during the data-exploration phase. Every
figure below comes from a real command run against the Kaggle API; the raw
outputs are quoted in [Provenance](#provenance) and in the PR body.

- **Slug**: `gemma-4-developer-agent` (Google, sponsor Google LLC).
  `competition-metadata.json` in this repo is still the `INSERT_SLUG_HERE`
  template, so the slug was taken from `docs/competition-research.md` and
  confirmed with `kaggle competitions list --search gemma-4-developer-agent`.
- **Metric**: **Resolution Rate** = resolved tasks / total tasks ∈ `[0.0, 1.0]`.
  Per issue it is SWE-bench style PASS/FAIL: the agent patch is applied to the
  repo at `base_commit`, the official `test_patch` is applied, and hermetic
  `pytest` must exit `0` with a valid JUnit XML (`passed > 0`, `failures == 0`,
  `errors == 0`, no skips among the required tests).
- **Base model (mandatory, single)**: `gemma-4-31b-it-qat-w4a16-ct`.
- **Public dev set**: **129 tasks** in `tasks.jsonl`.
- **Hidden test set**: ~120 tasks, evenly split public/private, curated from
  private repositories under the same pipeline (per the `data-description`
  page). Submissions are scored against the hidden set, not the 129 dev tasks.

### Timeline (all at 23:59 UTC)

| Date | Event |
|------|-------|
| 2026-09-23 | Start |
| 2026-11-12 | Paper-track deadline (optional, separate competition) |
| 2026-11-25 | Entry deadline (rules must be accepted) and team-merger deadline |
| 2026-12-02 | Final submission deadline |

Account state at capture time: rules accepted, `userHasEntered = True`;
competition team count `973` (from `competitions list`).

## File inventory (full public listing)

524 files, **21,378.3 MiB (≈ 20.9 GiB)** total. Listed with
`kaggle competitions files --page-size 200` over three pages.

| Directory | Files | Size | Purpose |
|-----------|------:|-----:|---------|
| `snapshots/` | 129 | 20,501.0 MiB | Per-task repo working tree at `base_commit` (`<instance_id>.tgz`), future history stripped |
| `embeddings/` | 127 | 445.9 MiB | Commit-named `.npz` node embeddings (256-dim `float32`) backing `search_similar_code` |
| `graphs/` | 127 | 402.5 MiB | Commit-named NetworkX AST call/dependency graphs (JSON) backing `get_code_neighbors`/`get_code_subgraph` |
| `wheels/` | 124 | 26.5 MiB | Offline binary wheels mounted read-only at `/wheels` for air-gapped `pip` installs |
| `sample_submission/` | 10 | 0.42 MiB | Ready-to-run baseline ADK submission (schema reference) |
| `docker/` | 4 | 25,931 B | `Dockerfile.sandbox`, `Dockerfile.public`, `imp.py`, `telnetlib.py` |
| `sandbox/` | 1 | 13,883 B | `setup.py` container bootstrap (offline editable install + baseline commit) |
| root | 2 | 1.94 MiB | `HARNESS_README.md` (49,356 B), `tasks.jsonl` (1,984,455 B) |

**Listing discrepancy (verified, not assumed):** the `data-description` page
describes `graphs/` and `embeddings/` as *256 files each* — 129 task-named
files hard-linked to 127 commit-named files. The public file listing exposes
**only the 127 commit-named files per directory**; zero task-named
(`<instance_id>.json` / `.npz`) entries are downloadable. All 127 graphs and
127 embeddings map exactly onto the 127 distinct `(repo, base_commit)` pairs
present in `tasks.jsonl`; no task commit is missing a graph or embedding.

Also advertised but **absent from the public listing**: `submission.parquet`
(produced only during scoring) and the private `secret/solution.parquet`
archive.

## Schema notes for training design

### `tasks.jsonl` (129 records, one JSON object per line)

Field coverage is 129/129 for every field; there are no optional/missing keys.

| Field | Notes |
|-------|-------|
| `instance_id` | `<repo_short>_<issue_or_pr_number>`, e.g. `fastapi_15661` |
| `repo` | `owner/repo`; one of `fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx` |
| `base_commit` | 40-char Git SHA; snapshot/repo state immediately before the fix |
| `problem_statement` | Natural-language issue (len min 42 / median 418 / max 10,095 chars) |
| `hints_text` | Present as a key in all 129 records but **empty in all 129** — no usable hints |
| `patch` | Reference unified diff that resolves the issue (train only; excluded from hidden `rerun/tasks.jsonl`) |
| `test_patch` | Unified diff with the verification tests (train only; private at scoring) |
| `created_at` | ISO-8601, observed range `2023-07-29T07:06:41Z` … `2026-06-20T00:20:49Z` |

Per-repo task counts and distinct base commits (129 tasks but only 127 distinct
commits — two commits are each shared by two tasks):

| Repo | Tasks | Distinct `base_commit` |
|------|------:|-----------------------:|
| `fastapi/fastapi` | 67 | 67 |
| `Textualize/rich` | 48 | 47 |
| `psf/requests` | 13 | 12 |
| `encode/httpx` | 1 | 1 |
| **Total** | **129** | **127** |

### `graphs/<repo>_<commit>.json`

NetworkX `CustomMultiDiGraph` serialization: `directed=true`,
`multigraph=true`, `graph` (global attrs), `nodes`, `edges`.

- `nodes[*].id` — fully-qualified symbol path (e.g.
  `fastapi.routing._prepare_response_content`)
- `nodes[*].name` — qualified symbol name matching `id`
- `nodes[*].text` — full Python source of the function/method/class at `base_commit`
- `edges[*]` — `source`, `target`, `type` (e.g. `calls`), `key` (parallel-edge index)

### `embeddings/<repo>_<commit>.npz`

Compressed NumPy archive keyed by node id; each entry is a `float32` vector of
length 256 (`embedding_[0-255]`) for the corresponding graph symbol.

### `wheels/` and `sandbox/setup.py`

124 pinned wheels covering `fastapi`, `starlette`, `pydantic`, `requests`,
`urllib3`, `rich`, `httpx`, `httpcore`, `pytest` and transitives, mounted at
`/wheels`. `sandbox/setup.py` inspects `pyproject.toml` / `setup.cfg` /
`requirements.txt`, does
`pip install --no-index --find-links=/wheels -e .`, and creates the clean
baseline commit so `git diff HEAD` captures only agent edits.

### `sample_submission/` (schema reference)

`agent.yaml` (root `swe_baseline_agent`, model `gemma-4-31b-it-qat-w4a16-ct`,
`adapter: main_lora`, all 9 tools + one `agent_tool` wrapping
`sub_agents/code_analyzer.yaml` with `skip_summarization: true`),
`configs/sampling.yaml` (`temperature 0.2`, `top_p 0.95`,
`max_output_tokens 16384`, `thinking_config.thinking_budget 4096`,
`include_thoughts true`), `prompts/system.md` + `prompts/analyzer.md`, and two
dummy LoRA dirs.

> **The sample `agent.yaml` is only a schema example.** Its `eval_config.yaml`
> sets placeholder budgets (`timeout_seconds 60`, `max_tool_calls 10`,
> `max_time_minutes 1`, `max_turns 50`) that are far tighter than the harness
> defaults (`60 min`, `100 tool calls`, `500 turns`, `300 s` per command).
> The bundled adapters are draft rank-4 LoRAs (`r=4`, `lora_alpha=8`,
> `layers_to_transform [0]`, `q_proj`/`o_proj` only, ~217 KB each), not usable
> trained weights.

## Downloaded vs. deliberately skipped

Only small metadata/inspection artifacts were fetched into `data/raw/`
(git-ignored). **15 files, 2,080,519 B ≈ 1.984 MiB.** Nothing downloaded is
tracked by git (`git status --short` is empty).

| File | Bytes | Why kept |
|------|------:|----------|
| `tasks.jsonl` | 1,984,455 | Task list + schemas; the core training input |
| `HARNESS_README.md` | 49,356 | Full harness contract (tools, budgets, lifecycle) |
| `sandbox/setup.py` | 13,883 | Container bootstrap behavior |
| `docker/telnetlib.py` | 23,336 | Compatibility shim shipped in the sandbox |
| `docker/imp.py` | 834 | Compatibility shim |
| `docker/Dockerfile.sandbox` | 773 | Base sandbox spec |
| `docker/Dockerfile.public` | 988 | Public sandbox spec (+ `/wheels` cache) |
| `sample_submission/agent.yaml` | 438 | Declarative schema reference |
| `sample_submission/eval_config.yaml` | 232 | Budget config schema reference |
| `sample_submission/configs/sampling.yaml` | 120 | Generation-params reference |
| `sample_submission/prompts/system.md` | 3,888 | Baseline agent prompt |
| `sample_submission/prompts/analyzer.md` | 527 | Baseline sub-agent prompt |
| `sample_submission/sub_agents/code_analyzer.yaml` | 361 | Sub-agent / `agent_tool` reference |
| `sample_submission/adapters/main_lora/adapter_config.json` | 664 | PEFT LoRA config schema |
| `sample_submission/adapters/tool_lora/adapter_config.json` | 664 | PEFT LoRA config schema |

Deliberately **not** downloaded, and why:

- **`snapshots/` (129 files, 20.0 GiB).** Bulk; the largest single `.tgz` is
  ~334 MiB. Needed only when a local `swegemma eval` harness run is wired up,
  not for schema exploration. Deferred to the harness-trial phase.
- **`embeddings/` (127 files, 445.9 MiB) and `graphs/` (127 files, 402.5 MiB).**
  Bulk per-repo artifacts consumed by the offline `search_similar_code` /
  graph tools inside the sandbox. Not needed to design the agent; downloading
  all of them now would be a bulk pull beyond inspection scope.
- **`wheels/` (124 files, 26.5 MiB).** Dependency artifacts used only by the
  air-gapped sandbox bootstrap; not inspection material.
- **`sample_submission/adapters/*/adapter_model.safetensors` (2 × ~217 KB).**
  Untrained dummy weights; the `adapter_config.json` files are enough to record
  the adapter schema.
- **The paper-track competition** (`gemma-4-developer-agent-paper`) — separate
  competition, out of scope for this phase.

## Provenance

Real command outputs backing the figures above.

```console
$ HOME=/opt/data kaggle competitions list --search gemma-4-developer-agent
ref                                                              deadline                 category  reward      teamCount  userHasEntered  userRank
https://www.kaggle.com/competitions/gemma-4-developer-agent      2026-12-02 23:59:00      Featured  65,000 Usd        973            True         0
https://www.kaggle.com/competitions/gemma-4-developer-agent-paper 2026-11-12 23:59:00.807 Featured 35,000 Usd         75           False         0

$ HOME=/opt/data kaggle competitions files -c gemma-4-developer-agent --page-size 200 --format csv
# 3 pages; after de-duplication and parsing:
#   total files: 524
#   total bytes: 22416766904  (= 21378.3 MiB)
#   snapshots 129 | embeddings 127 | graphs 127 | wheels 124
#   sample_submission 10 | docker 4 | sandbox 1 | root 2

$ HOME=/opt/data kaggle competitions download -c gemma-4-developer-agent -f <file> -p data/raw -o -q
# 15 small files fetched; 2,080,519 B total (1.984 MiB)

$ uv run python  # parse data/raw/tasks.jsonl
tasks: 129
field coverage: instance_id/repo/base_commit/patch/test_patch/problem_statement/hints_text/created_at = 129 each
by repo: fastapi/fastapi 67, Textualize/rich 48, psf/requests 13, encode/httpx 1
distinct (repo, base_commit): 127  →  127 graphs and 127 embeddings match exactly
tasks with non-empty hints_text: 0

$ git status --short
# (empty — data/raw/ is git-ignored)
```

Page content was read with
`kaggle competitions pages -c gemma-4-developer-agent --content --format json`
(9 pages: `data-description`, `Description`, `Evaluation`, `rules`, `abstract`,
`Timeline`, `foundational-rules`, `Prizes`,
`Model Selection, Budget, and Harness Rules`).
