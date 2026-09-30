#!/usr/bin/env sh
#
# run-host-trial.sh - runnable port of docs/host-trial-runbook.md, sections 1-7.
#
# Same trial as the PowerShell script: two tasks (fastapi_15661, fastapi_15588)
# against an OpenAI-compatible cloud backend, archived under runs/.
#
# Usage:
#   ./scripts/host-trial/run-host-trial.sh [results-name]
#
#   results-name is the only parameter; it names results/<results-name>.
#   Default: run_01.
#
# SECURITY: the backend key is read ONLY from the OPENAI_API_KEY environment
# variable. It is never accepted as an argument, echoed, or written to disk.
# Export it in this shell first, e.g.:
#   export OPENAI_API_KEY=...            # not committed, not logged
#   export OPENAI_BASE_URL=https://opencode.ai/zen/go/v1   # optional
#
# Values are sourced from docs/host-trial-runbook.md (facts table, sections 1-7)
# and data/raw/models-trial.yaml (the --models-yaml story).

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

RESULTS_NAME=${1:-run_01}

# --- fixed trial parameters (runbook facts table + sections 4/6) -------------
TASKS_FILE="data/raw/tasks.jsonl"
SNAPSHOTS_DIR="data/raw/snapshots"
WHEELHOUSE_DIR="data/raw/wheelhouse"
DOCKER_CONTEXT="data/raw/docker"
SUBMISSION_DIR="submission"
MODELS_YAML="data/raw/models-trial.yaml"
RESULTS_DIR="results/$RESULTS_NAME"
JUNIT_DIR="junit"
COMPETITION="gemma-4-developer-agent"
WHEELHOUSE_DATASET="metric/gemma-4-developer-agent-wheelhouse"
TASK_IDS="fastapi_15661 fastapi_15588"
BACKEND_ALIAS="deepseek-trial"

phase() { printf '\n=== %s ===\n' "$1"; }
note()  { printf '  %s\n' "$1"; }
die()   { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing prerequisite '$1'. $2"
}

fetch_comp_file() {
    remote_file=$1
    dest_dir=$2
    name=$(basename "$remote_file")
    if [ -f "$dest_dir/$name" ]; then
        note "skip (exists): $dest_dir/$name"
        return 0
    fi
    mkdir -p "$dest_dir"
    kaggle competitions download -c "$COMPETITION" -f "$remote_file" -p "$dest_dir"
}

extract_zips() {
    dir=$1
    if command -v unzip >/dev/null 2>&1; then
        for z in "$dir"/*.zip; do
            [ -e "$z" ] || continue
            unzip -o -q "$z" -d "$dir"
        done
    else
        uv run python - "$dir" <<'PY'
import glob
import os
import sys
import zipfile

directory = sys.argv[1]
for archive in glob.glob(os.path.join(directory, "*.zip")):
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(directory)
PY
    fi
}

# --- Phase 1 (runbook section 1): prerequisites ------------------------------
phase "Phase 1/7 (runbook sec. 1): prerequisites"

need_cmd git "Install git first."
need_cmd uv "Install uv first: https://astral.sh/uv"
need_cmd docker "Install Docker Desktop and start it."
need_cmd kaggle "Install the Kaggle CLI: uv tool install kaggle"

docker_os=$(docker info --format '{{.OSType}}' 2>/dev/null || true)
[ "$docker_os" = "linux" ] || die "Docker engine is not reachable in Linux mode (got '${docker_os:-<none>}'). Start Docker Desktop and confirm the Linux engine (runbook sec. 1.1)."

[ -f "$HOME/.kaggle/kaggle.json" ] || die "Kaggle token not found at $HOME/.kaggle/kaggle.json. Download it from your Kaggle account (runbook sec. 1.4)."

git --version
uv --version
kaggle --version
note "Docker engine OSType: linux"

# --- Phase 2 (runbook section 2): repository + harness branch ----------------
phase "Phase 2/7 (runbook sec. 2): repository and harness branch"

cd "$REPO_ROOT"
git fetch origin

if [ ! -f docs/harness-logging-contract.md ] || [ ! -f src/kaggle_gemma_agent/harness_runs.py ]; then
    if git show origin/main:docs/harness-logging-contract.md >/dev/null 2>&1; then
        note "harness code absent on this branch; switching to main"
        git checkout main
        git pull --ff-only origin main
    else
        die "harness code (docs/harness-logging-contract.md, harness_runs.py) is not available. Check out main or exp/harness-trial-1 (runbook sec. 2)."
    fi
fi

[ -f docs/harness-logging-contract.md ] || die "docs/harness-logging-contract.md still missing after update."
[ -f src/kaggle_gemma_agent/harness_runs.py ] || die "src/kaggle_gemma_agent/harness_runs.py still missing after update."

# --- Phase 3 (runbook section 4): data - wheelhouse + small fixtures ONLY ----
# Bulk snapshots/ and embeddings/ are intentionally NOT pulled (approx. 20.9 GiB).
phase "Phase 3/7 (runbook sec. 4): fetch wheelhouse + small fixtures (NO bulk)"

if ls "$WHEELHOUSE_DIR"/*.whl >/dev/null 2>&1; then
    note "skip (exists): runtime wheelhouse already extracted"
else
    mkdir -p "$WHEELHOUSE_DIR"
    kaggle datasets download -d "$WHEELHOUSE_DATASET" -p "$WHEELHOUSE_DIR"
    extract_zips "$WHEELHOUSE_DIR"
fi

fetch_comp_file "tasks.jsonl" "data/raw"
fetch_comp_file "HARNESS_README.md" "data/raw"
fetch_comp_file "sandbox/setup.py" "data/raw/sandbox"
fetch_comp_file "docker/Dockerfile.sandbox" "data/raw/docker"
fetch_comp_file "docker/Dockerfile.public" "data/raw/docker"

note "fetching only the two trial snapshots (never the whole snapshots/ tree)"
fetch_comp_file "snapshots/fastapi_15661.tgz" "$SNAPSHOTS_DIR"
fetch_comp_file "snapshots/fastapi_15588.tgz" "$SNAPSHOTS_DIR"

# --- Phase 4 (runbook section 3): build the sandbox image --------------------
phase "Phase 4/7 (runbook sec. 3): build sandbox image"

[ -f "$DOCKER_CONTEXT/Dockerfile.sandbox" ] || die "missing $DOCKER_CONTEXT/Dockerfile.sandbox (fetched in phase 3)."
docker build -t swebench-sandbox:latest -f "$DOCKER_CONTEXT/Dockerfile.sandbox" "$DOCKER_CONTEXT"

# --- Phase 5 (runbook section 5): backend key - env only ---------------------
phase "Phase 5/7 (runbook sec. 5): backend key (environment only)"

[ -n "${OPENAI_API_KEY:-}" ] || die "OPENAI_API_KEY is empty. Export it in this shell before running (never pass it as an argument): export OPENAI_API_KEY=... (runbook sec. 5)."
if [ -z "${OPENAI_BASE_URL:-}" ]; then
    OPENAI_BASE_URL="https://opencode.ai/zen/go/v1"
    export OPENAI_BASE_URL
    note "OPENAI_BASE_URL defaulted to https://opencode.ai/zen/go/v1"
fi
[ -f "$MODELS_YAML" ] || die "missing $MODELS_YAML (the --models-yaml mapping; runbook sec. 6 / data/raw/models-trial.yaml)."
note "OPENAI_API_KEY is set (value not shown); base URL: $OPENAI_BASE_URL"

# --- Phase 6 (runbook section 6): run the trial, two tasks -------------------
phase "Phase 6/7 (runbook sec. 6): swegemma eval (2 tasks, competition budgets)"

command -v swegemma >/dev/null 2>&1 || die "swegemma is not on PATH. Install it from the wheelhouse dataset (runbook sec. 4.1; install command is an open TODO in the runbook)."

mkdir -p "$RESULTS_DIR"
swegemma eval \
    --tasks "$TASKS_FILE" \
    --snapshots-dir "$SNAPSHOTS_DIR" \
    --submission-dir "$SUBMISSION_DIR" \
    --task-ids $TASK_IDS \
    --results-dir "$RESULTS_DIR" \
    --sandbox docker \
    --max-tool-calls 100 \
    --max-time-minutes 60 \
    --concurrency 1 \
    --display auto \
    --models-yaml "$MODELS_YAML"

# --- Phase 7 (runbook sections 7-9): archive into runs/ ----------------------
phase "Phase 7/7 (runbook sec. 7-9): archive + report under runs/"

note "JUnit note (runbook sec. 8): the harness writes JUnit XML only inside Container B"
note "at /tmp/_swegemma_junit_<id>.xml and warm-pooled containers are wiped. If a"
note "container is still alive, copy it out before teardown:"
note "  docker ps"
note "  docker cp <container>:/tmp/_swegemma_junit_fastapi_15661.xml $JUNIT_DIR/"
note "If it is already gone, pass/fail is still readable from task_results.jsonl."

mkdir -p "$JUNIT_DIR"
uv run python -m kaggle_gemma_agent.harness_runs archive "$RESULTS_DIR" \
    --junit-dir "$JUNIT_DIR" --tasks "$TASKS_FILE" --backend "$BACKEND_ALIAS"

LATEST_RUN=$(ls -dt runs/*/ 2>/dev/null | head -n 1 || true)
[ -n "$LATEST_RUN" ] || die "archiver produced no runs/<UTC>/ directory."
LATEST_RUN=${LATEST_RUN%/}

uv run python -m kaggle_gemma_agent.harness_runs report "$LATEST_RUN"

printf '\nTrial complete. Archived under %s (report: %s/report.json).\n' "$LATEST_RUN" "$LATEST_RUN"
