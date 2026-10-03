# Host trial runbook — `swegemma` on Windows 11 + Docker Desktop

This runbook lets a **human operator** run a real `swegemma` trial on their own
host (Windows 11 + Docker Desktop). It exists because the agent container is
unprivileged and has no Docker daemon (`robotina#80`, `#81`), so the harness
cannot be exercised in CI/dev. **No GPU is needed**: the agent loop is pointed
at an OpenAI-compatible cloud backend instead of the local vLLM server.

The examples below are **PowerShell** (Windows 11), kept as phase reference; the
runnable entry point is the Python runner in section 0. Do not translate them
to bash-style `head`/`tail`/`grep`.

## 0. Runner — `scripts/host-trial/run_host_trial.py`

The runnable entry point is the single cross-platform Python runner (the former
`run-host-trial.ps1` / `.sh` were removed). It walks the eight phases below
(prereqs → data → install → image → key guard → `swegemma eval` → archive/report):

```sh
uv run python scripts/host-trial/run_host_trial.py run_01
# ...or, without the repo venv:
uv run --script scripts/host-trial/run_host_trial.py run_01
```

Backend settings come from the process environment or a git-ignored `.env` in
the repo root (the real environment wins). Copy `.env.example` and fill it in;
`OPENAI_API_KEY` is required and never echoed (masked). `OPENAI_BASE_URL`
defaults to `https://opencode.ai/zen/go/v1`; `HARNESS_MODEL` is the trial-only
opencode model id (meaningless for the Kaggle submission).

Two backend requirements are handled automatically by phase 7:

- **Model wiring.** The runner generates the `--models-yaml` at run time from
  `HARNESS_MODEL`, mapping **every** `model:` alias declared in
  `submission/agent.yaml` and `submission/sub_agents/*.yaml` to
  `openai/<HARNESS_MODEL>`. The git-ignored host-local
  `data/raw/models-trial.yaml` is no longer read, so a stale alias cannot
  silently send Gemma (or any other model) to the wire.
- **Session header.** The opencode.ai Go backend rejects requests without a
  stable `x-opencode-session` header. `swegemma` 0.2.7 builds its `LiteLlm`
  clients with a fixed kwargs set and has no `extra_headers` hook, so the runner
  starts a short-lived local forwarding proxy and points `OPENAI_BASE_URL` at
  it; the proxy stamps the header and forwards to the real backend. Set
  `HARNESS_TRIAL_SESSION` to pin the id (default `swegemma-host-trial`). The
  proxy is a daemon thread that dies with the runner — it is not shipped in the
  submission.

## Facts and provenance

Every value below was read from a file in this repo. Anything not backed by a
file is flagged `TODO` — do not treat it as verified.

| Fact | Value | Source |
| :--- | :--- | :--- |
| Base model (single, mandatory) | `gemma-4-31b-it-qat-w4a16-ct` | `docs/competition-data.md:17` |
| Scored metric | Resolution Rate (`[0.0, 1.0]`) | `docs/competition-data.md:12` |
| Public dev set | 129 tasks in `tasks.jsonl` | `docs/competition-data.md:18` |
| Runtime packages | `swegemma` + `adk-submission` + `adk-eval-core` (Google ADK based); **not on PyPI** | `docs/harness-logging-contract.md:14,20,74` |
| Package distribution | Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse` (dataset id `12049435`, owner `metric`, ~867 MB, updated `2026-09-27`) | `docs/harness-logging-contract.md:20` |
| Sandbox image | `swebench-sandbox:latest`, built from `data/raw/docker/Dockerfile.sandbox` | `docs/harness-logging-contract.md:21` |
| Per-task budgets | 60 min wall-clock, 100 tool calls, 500 turns, 300 s per command | `data/raw/HARNESS_README.md:540-545` |
| `swegemma eval` invocation | `HARNESS_README.md` §9.1 | `data/raw/HARNESS_README.md:617-631` |
| Results layout | `summary.json`, `task_results.jsonl`, `patches/`, `test_outputs/`, `traces/`, `logs/` | `data/raw/HARNESS_README.md:641-656` |
| JUnit XML gap | Only at `/tmp/_swegemma_junit_<id>.xml` inside Container B; never copied out; warm-pooled containers wiped | `docs/harness-logging-contract.md:44` |
| Archiver | `python -m kaggle_gemma_agent.harness_runs <results-dir> [--junit-dir junit]` → `runs/<UTC stamp>/<instance_id>/` | `docs/harness-logging-contract.md:57-64`; `src/kaggle_gemma_agent/harness_runs.py` |
| Substitute backend (no Gemma) | `ROBOTINA_HERMES_MODEL_BASE_URL=https://opencode.ai/zen/go/v1`, `OPENCODE_GO_API_KEY`, `ROBOTINA_HERMES_MODEL=muse-spark-1.3-contributor` | `docs/harness-logging-contract.md` (substitute-backend section) |
| Example task ids | `fastapi_15661`, `fastapi_15588` (first two records of `data/raw/tasks.jsonl`) | `data/raw/tasks.jsonl` |

The harness code lives on `exp/harness-trial-1`, **not** `main` (as of this
runbook). `docs/harness-logging-contract.md`, `src/kaggle_gemma_agent/harness_runs.py`
and `tests/test_harness_runs.py` exist only there.

## 1. Prerequisites

### 1.1 Docker Desktop

Install Docker Desktop, start it, and confirm the Linux engine is reachable:

```powershell
docker info
```

Expected: a `Server:` section with `OSType: linux`. If it errors, Docker
Desktop is not running (or is in Windows-containers mode).

### 1.2 uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

### 1.3 git

```powershell
git --version
```

### 1.4 Kaggle CLI + API token

Accept the competition rules **on kaggle.com first** (Kaggle API returns an
authorization error for downloads until you have joined the competition).

```powershell
uv tool install kaggle
kaggle --version
```

Place your token at `$env:USERPROFILE\.kaggle\kaggle.json` (download it from
your Kaggle account page; do **not** commit it). Verify:

```powershell
kaggle competitions list --search gemma-4-developer-agent
```

## 2. Clone and check out the trial branch

```powershell
git clone https://github.com/emiliodavola/kaggle-gemma-agent.git
Set-Location kaggle-gemma-agent
git fetch origin
git checkout exp/harness-trial-1
```

The remote URL was confirmed from `git remote get-url origin` on this repo
(`https://github.com/emiliodavola/kaggle-gemma-agent.git`). If
`exp/harness-trial-1` has already merged to `main`, check first and use `main`
instead:

```powershell
git show origin/main:docs/harness-logging-contract.md
```

If that prints the contract, `main` already has it — use `main`. Otherwise keep
`exp/harness-trial-1`.

## 3. Build the sandbox image

The harness runs Container A (agent) and Container B (verification) from the
sandbox image (`docs/harness-logging-contract.md:21`).

```powershell
docker build -t swebench-sandbox:latest -f data\raw\docker\Dockerfile.sandbox data\raw\docker
```

`TODO`: the build context above (`data\raw\docker`) is assumed; the contract
only names the Dockerfile. Confirm from the Dockerfile's `COPY`/`ADD` lines.

## 4. Download data — wheelhouse + small fixtures ONLY

> **WARNING — never bulk-pull `snapshots/` or `embeddings/`.** The full public
> listing is 21,378.3 MiB (≈ 20.9 GiB): `snapshots/` alone is 20,501.0 MiB and
> `embeddings/` 445.9 MiB. Bulk-pulling them is beyond trial scope and will
> blow your disk budget. Source: `docs/competition-data.md:37-49,160-173`.

### 4.1 Runtime wheelhouse (~867 MB) — required

```powershell
New-Item -ItemType Directory -Force -Path data\raw\wheelhouse | Out-Null
kaggle datasets download -d metric/gemma-4-developer-agent-wheelhouse -p data\raw\wheelhouse
Expand-Archive -Path data\raw\wheelhouse\*.zip -DestinationPath data\raw\wheelhouse -Force
```

#### Install `swegemma` from the wheelhouse

None of the three harness distributions (`swegemma`, `adk-submission`,
`adk-eval-core`) are on PyPI, so install the CLI with `--find-links` pointed at
the extracted wheelhouse. Only **`swegemma`** ships the
`swegemma = swegemma.cli:main` console entry point; the other two are pulled in
as its dependencies from the same directory. Their public dependencies
(e.g. `google-adk`, `transformers`) resolve normally.

```powershell
uv tool install --find-links data\raw\wheelhouse swegemma
uv tool dir --bin   # the bin dir holding swegemma.exe; must be on PATH
```

The runner (section 0) runs this automatically as phase 4 and skips it when
`swegemma` is already on `PATH`; it prepends `uv tool dir --bin` to `PATH` for
the rest of the run. Run it by hand only if you invoke `swegemma eval` outside
the runner.

### 4.2 `tasks.jsonl` + small fixtures — required

```powershell
kaggle competitions download -c gemma-4-developer-agent -f tasks.jsonl -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f HARNESS_README.md -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f sandbox/setup.py -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/Dockerfile.sandbox -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/Dockerfile.public -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/imp.py -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/telnetlib.py -p data\raw
```

`Dockerfile.sandbox` `COPY`s `imp.py` and `telnetlib.py` from the
`data\raw\docker` build context. Those stdlib modules were removed upstream
(`imp` in 3.12, `telnetlib` in 3.13) and the `python:3.13-slim` base no longer
ships them, so both shims (§3) are required fixtures or `docker build` fails
with `"/imp.py": not found` / `"/telnetlib.py": not found`.

`sample_submission/` (10 files, 0.42 MiB) is the schema reference — fetch it
only if you want a submission dir to point `--submission-dir` at; the repo
already ships `submission/`.

### 4.3 Snapshots — required by `--snapshots-dir`, but per-task only

The §9.1 command uses `--snapshots-dir`. A real trial needs the snapshot(s) for
the chosen task id(s). **Do not pull the whole `snapshots/` directory.** Fetch
only the specific `<instance_id>.tgz` for your 1–2 tasks:

```powershell
New-Item -ItemType Directory -Force -Path data\raw\snapshots | Out-Null
kaggle competitions download -c gemma-4-developer-agent -f snapshots/fastapi_15661.tgz -p data\raw\snapshots
kaggle competitions download -c gemma-4-developer-agent -f snapshots/fastapi_15588.tgz -p data\raw\snapshots
```

`TODO`: the per-task snapshot fetch is inferred from `docs/competition-data.md:160-162`
(“the largest single `.tgz` is ~334 MiB”); confirm it is in scope and unzip as
`<instance_id>.tgz` if the harness expects an extracted tree.

## 5. Backend key — this PowerShell session only

> **WARNING — never commit the key, never paste it into any file in the repo.**
> Set it as a process-scoped environment variable so it dies with the window.

The Python runner reads `OPENAI_API_KEY` from the process environment or a
git-ignored `.env` (see `.env.example`); never commit it. Shell equivalent:

```sh
export OPENAI_API_KEY="<your-backend-key>"
```

The operator-specified variable for this trial:

```powershell
$env:HARNESS_BACKEND_API_KEY = "<your-backend-key>"
```

`TODO`: the logging contract documents the substitute backend under different
names — `ROBOTINA_HERMES_MODEL_BASE_URL`, `OPENCODE_GO_API_KEY`,
`ROBOTINA_HERMES_MODEL` (`docs/harness-logging-contract.md`). Confirm which
variable the harness's `--models-yaml` actually reads; if it is
`OPENCODE_GO_API_KEY`, set that instead (same session-only rule):

```powershell
$env:OPENCODE_GO_API_KEY = "<your-backend-key>"
$env:ROBOTINA_HERMES_MODEL_BASE_URL = "https://opencode.ai/zen/go/v1"
$env:ROBOTINA_HERMES_MODEL = "muse-spark-1.3-contributor"
```

Close the window when done; the variables do not persist.

## 6. Run the trial — 1–2 tasks, max

Exact invocation shape from `HARNESS_README.md` §9.1:

```bash
swegemma eval \
  --tasks tasks.jsonl \
  --snapshots-dir snapshots \
  --submission-dir sample_submission \
  --results-dir results/run_01 \
  --sandbox docker \
  --max-tool-calls 50 \
  --max-time-minutes 30 \
  --concurrency 2 \
  --display auto
```

PowerShell equivalent, scoped to **two tasks**, against this repo's
`submission/`, with the competition budgets (60 min / 100 tool calls,
`HARNESS_README.md:540-541`). `--task-ids` is documented at
`HARNESS_README.md:634`:

```powershell
swegemma eval `
  --tasks data\raw\tasks.jsonl `
  --snapshots-dir data\raw\snapshots `
  --submission-dir submission `
  --task-ids fastapi_15661 fastapi_15588 `
  --results-dir results\run_01 `
  --sandbox docker `
  --max-tool-calls 100 `
  --max-time-minutes 60 `
  --concurrency 1 `
  --display auto
```

Notes:
- `--sandbox docker` is the default; it requires the image from step 3.
- `swegemma` must be on `PATH`; the runner installs it from the local wheelhouse
  as phase 4 (§4.1) and skips the install when it is already there.
- `--concurrency 1` keeps the trial cheap; bump only if you want the dashboard.
- `--models-yaml` (`HARNESS_README.md:638`) is generated by the runner from
  `HARNESS_MODEL` (section 0); do not hand-maintain a mapping file. The runner
  also inserts the local `x-opencode-session` proxy, so no manual header wiring
  is needed.

> **Why not set the header in the harness?** `swegemma/models/registry.py`
> constructs `LiteLlm(model=..., api_base=..., api_key=..., num_retries=...)`
> and ignores any other `--models-yaml` keys; Google ADK's `LiteLlm` would
> forward `extra_headers` in `_additional_args`, but the harness never passes it.
> Adding the header therefore needs a harness change or the local proxy used
> here. The LLM calls originate in the host `swegemma` process (the ADK `Runner`
> runs host-side; Container A is `network_mode='none'` with no env
> pass-through), so a host-local proxy is sufficient.

### 6.1 Backend: local OpenAI-compatible server (Docker Model Runner / llama.cpp / LM Studio)

The runner starts a host-local forwarding proxy and points `OPENAI_BASE_URL` at
it (section 0), so the upstream may be **any** OpenAI-compatible `http(s)` origin:
the `x-opencode-session` header it adds is ignored by local servers. The LLM
calls originate in the host `swegemma` process, so a server on the Windows host is
reachable even though Container A is `network_mode='none'`.

`.env` for a local backend:

```dotenv
OPENAI_BASE_URL=http://127.0.0.1:1234/v1
OPENAI_API_KEY=sk-local-not-used
HARNESS_MODEL=<exact model id the server exposes>
```

- **Docker Model Runner** is the option that runs the competition checkpoint:
  `google/gemma-4-31B-it-qat-w4a16-ct` is **safetensors** (weight-only INT4 QAT),
  and DMR serves it through its vLLM backend. Enable Docker Desktop → Settings →
  AI → *host-side TCP support* on port `12434` (standalone Docker Engine has it on
  by default), then:

  ```bash
  docker model run --detach hf.co/google/gemma-4-31B-it-qat-w4a16-ct
  docker model list                 # exact model id for HARNESS_MODEL
  curl -s http://localhost:12434/models
  ```

  The model manifest reports `format: safetensors`; the registered id is e.g.
  `huggingface.co/google/gemma-4-31b-it-qat-w4a16-ct:latest`. Use the id the
  OpenAI API expects, confirmed by
  `curl -s http://localhost:12434/engines/vllm/v1/models`.

  The OpenAI base URL is per-engine:

  ```dotenv
  OPENAI_BASE_URL=http://localhost:12434/engines/vllm/v1   # safetensors (this model)
  # OPENAI_BASE_URL=http://localhost:12434/engines/llama.cpp/v1   # GGUF
  ```

  If the trial runs **inside a container** instead of the host, use
  `http://model-runner.docker.internal/engines/vllm/v1` and make sure that
  container can reach it (Robotina's internal network cannot, by design).
- **LM Studio / llama.cpp** are GGUF-only, so they cannot load this safetensors
  checkpoint; they remain useful for a GGUF substitute. LM Studio: enable the
  local server (default `http://127.0.0.1:1234/v1`) and copy the model id shown
  in the UI. llama.cpp: `llama-server -m <gguf> --port 8080 --jinja` exposes
  `http://127.0.0.1:8080/v1`; `--jinja` is required for OpenAI tool calling.
- `OPENAI_API_KEY` must be non-empty (the runner aborts otherwise); local servers
  ignore its value.
- The model must support **OpenAI function/tool calling** — the agent executes
  tools; a non-tool chat model will loop and fail regardless of the harness.

This is a trial-only knob: the submission still declares the competition model in
`agent.yaml`; `HARNESS_MODEL` never ships.

Before the eval, the runner probes the backend once through the same proxy with a
minimal tool-aware chat completion and fails fast on an unreachable endpoint, an
HTTP error, or an unusable reply — so a misconfigured local backend (server
stopped, wrong model id, model without tool calling) is caught in seconds instead
of after a full run. `--skip-backend-smoke` skips that single probe.

### 6.2 Wheel-set integrity and the swegemma cache

The runner clears `swegemma`'s cached unpacked-wheel tars
(`<temp>/swegemma_sp_cache_*`) before phase 7 so they are rebuilt from the
current `data/raw/wheels/` set. If the remote wheel listing is unavailable and
the local set is unverified, phase 3b/8 fails fast; pass
`--allow-partial-wheels` only for a deliberate offline run, and expect that an
incomplete set can produce containers missing `starlette`/`pydantic` and score
0/2 with a `collection_error` (see `docs/run-reports.md`).

#### Confirmed competition gap: a complete set can still be missing a transitive dependency

The competition `wheels/` set is **complete by filename but incomplete by
dependency graph**. Confirmed against Kaggle: 124 wheels including
`pydantic-2.13.4`, which declares `Requires-Dist: typing-inspection>=0.4.2`, but
**no `typing-inspection` wheel** (and no `inline-snapshot`). The harness installs
with `pip install --no-index --find-links=/wheels --no-deps -e /workspace`, so
the missing transitive dependency breaks `import fastapi` during pytest
collection and every task scores 0 regardless of the agent's patch (see issue
#39 / run `20261002T204541Z`).

A naive closure over the **whole** wheelhouse is wrong: the directory is a union
of several repos' wheels and over-reports many distributions (`blinker`, `attrs`,
`py`, `toml`, `pathspec`, `trove-classifiers`, `shellingham`). The correct root
is the task repo's **declared** dependencies, discovered from the task snapshot
exactly like `data/raw/sandbox/setup.py`.

#### Core gate vs optional warning

After staging, `ensure_trial_wheels` resolves the dependency closure of each
snapshot's declared requirements against the staged wheels (METADATA
`Requires-Dist`; environment-marked requirements are skipped), split in two:

- **Core** — `[project].dependencies` only. A missing core dependency (or a
  declared root that is itself absent, reported as required by `the task repo`)
  is a **hard gate**: phase 3b/8 **fails fast** with the missing distribution and
  who requires it, before the eval burns a run. `--allow-incomplete-wheels`
  bypasses that gate for a deliberate offline run.
- **Optional/test** — every `[project.optional-dependencies]` group plus
  `requirements*.txt` / `test-requirements*.txt`. A gap here is only a
  **warning** (`tests may fail; stage them in data/raw/wheels-extra/`): docs-only
  or extra dependencies the target tests never import (`uvicorn`, `orjson`,
  `ujson`, `email-validator`, `python-multipart`, `pydantic-settings`,
  `pydantic-extra-types`, `fastapi-cli`, `pyyaml`) must not block a valid run.
  The archived run had `httpx` working even though `h11` (reached via
  `httpx → httpcore`) is absent, so `h11` is not treated as a core blocker.

#### Supplemental wheels

Stage the missing wheel(s) under `data/raw/wheels-extra/` (merged into
`data/raw/wheels/` before the closure check) — this is how you fix a core gap or
an optional warning. Override the directory with the
`HARNESS_TRIAL_WHEELS_EXTRA` environment variable (`os.pathsep`-separated for
multiple dirs). For the confirmed gap:

```sh
uv run --with pip python -m pip download typing-inspection inline-snapshot \
    -d data/raw/wheels-extra --only-binary=:all: --no-deps
```

The merge is additive and idempotent: a wheel whose basename is already staged is
skipped, so re-running is safe. `--allow-incomplete-wheels` bypasses only the
core gate (the run still records any missing module — see the
`environment_blocked` / `env missing` handling in `docs/run-reports.md`). Do not
use it to mask a fixable missing core dependency.

#### Faithful vs repaired sandbox dependencies (`--repair-sandbox-deps`)

The Docker sandbox installs every base wheel (< 20 MB) into site-packages
**without resolving dependencies** and picks the highest py3.13 version. The
competition set ships `pydantic 2.13.4` without `typing-inspection`, so
`import fastapi` fails during pytest collection; the Kaggle notebook/subprocess
image does not have the problem (`pydantic 2.12.3` + `typing-inspection`) — see
[discussion 744370](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744370).

The flag separates the two modes:

- **Off (default) — faithful.** `ensure_trial_wheels` does not merge
  `data/raw/wheels-extra/` and does not fetch anything; the run uses the
  competition set exactly as shipped. A missing core dependency still fails fast
  (see the core gate above).
- **On — repaired.** The runner merges `data/raw/wheels-extra/` (override with
  `HARNESS_TRIAL_WHEELS_EXTRA`), then downloads any still-missing **core**
  dependency from PyPI for the container target (python:3.13-slim, linux x86_64;
  `cp313` / manylinux, `--only-binary=:all: --no-deps`) via
  `uv run --with pip python -m pip download`, re-merges, and re-checks the core
  closure. This makes the local Docker sandbox match the notebook image.

The repair touches **core runtime dependencies only**. Test/optional gaps
(`inline_snapshot`, `dirty_equals`, ...) stay warnings because the notebook image
lacks them too, so fetching them would make the local trial less faithful than
the scored environment. `--allow-incomplete-wheels` remains the explicit bypass
for a deliberate offline run.

## 7. Where results land

Under your `--results-dir` (`HARNESS_README.md:641-656`):

```text
results\run_01\
├── summary.json                  # resolution_rate, resolved count, per-repo, errors
├── task_results.jsonl            # append-only, one JSON line per finished task
├── patches\<instance_id>.patch   # unified diff from Container A
├── test_outputs\<instance_id>.log# Phase 2 pytest STDOUT/STDERR
├── traces\trace_<instance_id>.json# ATIF v1.7 trajectory (steps, tools, tokens)
└── logs\<instance_id>.log        # Phase 1 agent transcript
```

`results/` is git-ignored and keyed by run name — reusing `results\run_01`
overwrites the previous run. To re-key into the reusable archive:

```powershell
uv run python -m kaggle_gemma_agent.harness_runs results\run_01 --junit-dir junit
```

This writes `runs\<UTC timestamp>\<instance_id>\` (trace, transcript, patch,
test output, optional `junit.xml`, `metadata.json`) plus a run-level
`manifest.json`. `--junit-dir` is optional here (`src/kaggle_gemma_agent/harness_runs.py`,
`archive_run`).

## 8. Extract JUnit XML before teardown (if applicable)

The harness never persists JUnit XML to `--results-dir`; it lives only inside
Container B at `/tmp/_swegemma_junit_<id>.xml`, and warm-pooled containers are
wiped after each phase (`docs/harness-logging-contract.md:44`). The harness emits
the XML with:

```bash
--junitxml=/tmp/_swegemma_junit_<id>.xml
```

(`data/raw/HARNESS_README.md:602`). While Container B is still alive, copy it
out, then feed it to the archiver via `--junit-dir`:

```powershell
New-Item -ItemType Directory -Force -Path junit | Out-Null
docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Image}}"
docker cp <container>:/tmp/_swegemma_junit_fastapi_15661.xml junit\
```

`TODO`: the container name/ID for the `docker cp` is not documented; discover it
from `docker ps` (or `docker ps -a` during the run). If the container is already
torn down, the XML is unrecoverable — pass/fail can still be read from
`task_results.jsonl`.

## 9. Report back through `runs/` (no chat paste)

Do **not** paste logs into chat. Finalize the run into the shared-folder
handoff and stop; Hermes reads `runs/` directly. The protocol, schema, and
scale caps live in **`docs/run-reports.md`**.

1. **Archive + report** (extract JUnit XML first, per §8; skip if the
   container is already gone):

```powershell
uv run python -m kaggle_gemma_agent.harness_runs archive results\run_01 `
    --junit-dir junit --tasks data\raw\tasks.jsonl --backend <model-name>
```

2. **Confirm the rollup** — the same six lines Hermes will read:

```powershell
uv run python -m kaggle_gemma_agent.harness_runs report runs\<UTC>
```

`runs\<UTC>\STATUS` is the polling signal: `DONE`, `BLOCKED`, or `PARTIAL`,
followed by a five-line summary (backend; tasks/resolved/rate; tool calls,
wall time, and turns against budget; failures; report/index paths).
`runs\<UTC>\report.json` carries the per-task records (tool calls vs 100,
turns, pass/fail, JUnit `FAIL_TO_PASS`/`PASS_TO_PASS`, patch `sha256`, and
every artifact's path/size/hash). `runs/index.jsonl` gets one line per
finished run. `runs/` is git-ignored — never commit it.

If you post anything at all, post the `STATUS` block plus the `runs\<UTC>`
path. Backend, wall time, tool calls, pass/fail, log paths/sizes, and JUnit
status need no manual transcription — they are already in `report.json`.

## Open TODOs (not verifiable from repo files)

- Sandbox build context (§3).
- The backend key env-var name the harness reads (§5).
- Whether per-task snapshots are in scope (§4.3) and the Container B
  name/ID discovery for `docker cp` (§8).

Resolved: the `--models-yaml` path/shape for a cloud backend (§6). The runner
generates it from `HARNESS_MODEL` and injects the required
`x-opencode-session` header through a local proxy (section 0).
