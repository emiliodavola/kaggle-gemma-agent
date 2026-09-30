# Harness logging contract & local trial readiness

Scope: what the `swegemma` harness logs per task, where it lands, what is
missing for off-Kaggle trajectory training (SFT/RLVR), and what is required to
run a local trial in this container. Dev tooling only; nothing here ships
inside `submission.zip`.

## Harness source & version

| Item | Value |
| :--- | :--- |
| Authoritative spec | `data/raw/HARNESS_README.md` (49,356 bytes, 671 lines) |
| Competitor copy | Kaggle competition `gemma-4-developer-agent`, file `HARNESS_README.md`, creation date `2026-09-25T18:36:31Z` |
| Runtime packages | `swegemma` + `adk-submission` + `adk-eval-core` (Google ADK based) |
| Package distribution | Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse` (dataset id `12049435`, owner `metric`, ~867 MB, last updated `2026-09-27`); **not published on PyPI** (all three return HTTP 404) |
| Sandbox image | `swebench-sandbox:latest`, built from `data/raw/docker/Dockerfile.sandbox` (public variant: `Dockerfile.public`) |
| Pinned version / commit | Not exposed. There is no public repo or version tag; the README + wheelhouse snapshot is the reference. Treat the `2026-09-25` README as the spec baseline. |
| Local fixtures | `data/raw/tasks.jsonl` (129 tasks), `data/raw/sample_submission/`, `data/raw/sandbox/setup.py`, `data/raw/docker/*` |

## What the harness logs, per task, and where

Every `swegemma eval ... --results-dir <dir>` run writes incremental,
crash-safe artifacts (README section 9.2):

```text
<results-dir>/
├── summary.json                 # aggregate resolution_rate, resolved count, per-repo, errors
├── task_results.jsonl           # append-only, one JSON line per finished task (metrics, exit codes)
├── patches/<instance_id>.patch  # exact unified diff extracted from Container A
├── test_outputs/<instance_id>.log  # full STDOUT/STDERR of Phase 2 pytest in Container B
├── traces/trace_<instance_id>.json # ATIF v1.7 SessionTrace: steps, thoughts, tool calls, token usage
└── logs/<instance_id>.log       # rich formatted transcript of the Phase 1 agent session
```

| Signal needed for SFT | Logged? | Where |
| :--- | :--- | :--- |
| Raw transcript (messages) | Yes | `logs/<id>.log` |
| Structured trajectory (thoughts / actions / observations) | Yes | `traces/trace_<id>.json` (ATIF v1.7 `SessionTrace`) |
| Tool calls + arguments + results | Yes | `traces/trace_<id>.json` |
| Token usage / cost | Yes | `traces/trace_<id>.json` |
| Final patch | Yes | `patches/<id>.patch` |
| Phase 2 test stdout/stderr | Yes | `test_outputs/<id>.log` |
| Resolution verdict (pass/fail) | Yes | `task_results.jsonl`, `summary.json` |
| **JUnit XML** | **No (gap)** | Only inside Container B at `/tmp/_swegemma_junit_<id>.xml`; never copied to `--results-dir`, and warm-pooled containers are wiped after each phase |

### Gap summary

1. **JUnit XML is not persisted.** Pass/fail can be reconstructed from
   `task_results.jsonl`, but per-test node outcomes (`FAIL_TO_PASS` /
   `PASS_TO_PASS`) are lost. Extract with `docker cp` before teardown and pass
   the copy to the archiver via `--junit-dir`.
2. **Results are keyed by run directory**, not by task, so reusing a
   `--results-dir` overwrites prior runs.

## Local wiring added here

`src/kaggle_gemma_agent/harness_runs.py` is a stdlib-only archiver. It re-keys a
`swegemma --results-dir` into `runs/<UTC timestamp>/<instance_id>/`
(trace, transcript, patch, test output, optional `junit.xml`, per-task
`metadata.json`) plus a run-level `manifest.json`. `runs/` is git-ignored.

```bash
docker cp <container>:/tmp/_swegemma_junit_<id>.xml junit/
python -m kaggle_gemma_agent.harness_runs results/run_01 --junit-dir junit
```

This is the minimal wiring the harness does not do itself; it does not modify
harness internals (which we do not own).

On finish, the archiver also writes the file-based handoff
(`report.json` + `STATUS` + `runs/index.jsonl`) through
`src/kaggle_gemma_agent/run_report.py`, so a host operator and Hermes can read
results from the shared folder without pasting anything into chat. See
**`docs/run-reports.md`** for the schema, STATUS protocol, scale caps, and the
pick-up procedure; read it back with:

```bash
python -m kaggle_gemma_agent.harness_runs report runs/<UTC>
```

## Runtime requirements and what is missing in this container

| Requirement | Needed by | Present here |
| :--- | :--- | :--- |
| `swegemma`/`adk-submission`/`adk-eval-core` + `google-adk` | CLI + agent loop | No (not installed, not on PyPI) |
| Repository snapshots dir (`--snapshots-dir`, `base_commit` snapshots) | both containers | No (`data/raw/` has `tasks.jsonl` only) |
| Test-dependency wheelhouse (~867 MB) | container bootstrap | No |
| Docker daemon (`/var/run/docker.sock`) | `--sandbox docker` (default) | No (`docker` CLI present, daemon not running) |
| NVIDIA GPUs + vLLM | competition model serving | No (`nvidia-smi` absent) |
| OpenAI-compatible substitute backend | agent loop without Gemma | **Yes** |

`--sandbox subprocess` avoids Docker but still requires the packages, snapshots,
and wheelhouse above.

### Substitute backend (for when the harness is installed)

An OpenAI-compatible endpoint is available in this container and can be mapped
through the harness `--models-yaml` flag instead of the local vLLM server:

- `ROBOTINA_HERMES_MODEL_BASE_URL=https://opencode.ai/zen/go/v1`
- auth: `OPENCODE_GO_API_KEY`
- cheap substitute model: `ROBOTINA_HERMES_MODEL=muse-spark-1.3-contributor`

## Status

No local trial was executed: the harness runtime is absent (packages,
snapshots, wheelhouse, Docker daemon, GPUs). Logging feasibility is still
documented above; trajectory capture becomes fully sufficient once JUnit XML is
copied out of Container B (`--junit-dir`).
