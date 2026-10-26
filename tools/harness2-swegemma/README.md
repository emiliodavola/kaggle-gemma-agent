# harness2 <-> swegemma adapter (dev-only)

A versioned delta that teaches [Harness²](https://github.com/google-research/harness2) to
drive the `swegemma` harness. The clone lives in `tmp/harness2` (git-ignored); only
this directory is committed. Nothing here ships in `submission/`.

The patch is pinned to harness2 commit `1cfe254e8d25b15f37048c3730134686abe60335`
(2026-10-13). `setup.sh` refuses any other HEAD.

## What the patch changes

| File | Change |
| :--- | :--- |
| `harness2/benchmarks/swegemma.py` | New adapter + substrate: the 12 protocol methods over the `swegemma` CLI and its raw results. |
| `harness2/cli/_common.py` | `sw` joins `BENCHES`/`SUBSTRATES`; `make_adapter` returns `SwegemmaAdapter`. |
| `harness2/cli/check.py` | `--bench sw --substrate sw` is accepted by the readiness CLI. |
| `harness2/cli/run_sweep.py` | The run identity records the swegemma model and the local backend URL. |
| `harness2/config.py` | `HARNESS2_SWEGEMMA_ROOT`, `HARNESS2_SWEGEMMA_SUBSET`, `HARNESS2_SWEGEMMA_RUNS`, `HARNESS_MODEL`. |
| `harness2/core/tree.py` | `SurfaceSpec.extra_globs` (so `sub_agents/*.yaml`, `configs/*.yaml`, `prompts/*.md` are editable) and POSIX tree keys on Windows. |
| `harness2/preflight.py` | A swegemma cell checks the repo/Docker/backend, not harness2's three third-party benchmarks. |

The adapter maps the harness tree to the declarative submission:
`agent.yaml` and `prompts/system.md` are always-on; `skills/<name>/SKILL.md`,
`prompts/*.md`, `configs/*.yaml`, `eval_config.yaml` and `sub_agents/*.yaml` are
editable. `validate_tree()` materialises the tree and runs all three pack checks
(`check_submission`, `check_harness_surface`, `check_answer_leak`).

## Requirements

- WSL2 Ubuntu with Docker, the `swebench-sandbox:latest` image, and `swegemma`
  installed from the competition wheelhouse.
- `data/raw/tasks.jsonl` and `data/raw/snapshots/*.tgz` (129 files).
- The local backend reachable from WSL at `OPENAI_BASE_URL` (LM Studio on
  `http://127.0.0.1:1234/v1` on this machine), and the served model id.
- `experiments/subsets/dev-v1.json` (11 tasks).

## Setup

```bash
cd /mnt/c/Users/elaze/Desktop/robotina-data/workspace/kaggle-gemma-agent
bash tools/harness2-swegemma/setup.sh
```

`setup.sh` clones/checks the pin, applies `swegemma-adapter.patch`, and (when
`uv` is available) creates a 3.13 venv under `tmp/harness2/.venv`. Without the
venv, run with `PYTHONPATH=tmp/harness2 python3` (3.12+).

## Environment

```bash
export OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export HARNESS_MODEL=gemma-4-31b-it-qat
export HARNESS2_SWEGEMMA_ROOT=$PWD
export HARNESS2_SWEGEMMA_SUBSET=dev-v1
```

The falsifier needs only these. The full `harness2` loop (proposer/selector) also
needs an OpenCode channel model, provider-prefixed:

```bash
export HARNESS2_SOLVER_MODEL=opencode/deepseek-v4.1-flash
export HARNESS2_IMPROVER_MODEL=opencode/deepseek-v4.1-flash
```

`OPENAI_API_KEY` is read from the repository's git-ignored `.env` by the adapter
(with `setdefault`, so the shell wins). Nothing is printed.

## Falsifier (4 rollouts)

```bash
PYTHONPATH=tmp/harness2 python3 tools/harness2-swegemma/falsifier.py
```

It runs `requests_6644` and `requests_7315` against the base tree and against the
same tree plus one INV edit to `prompts/system.md`. It passes only when:

1. all four rollouts are archived (`summary.json` present);
2. the base and variant `harness.json` tree fingerprints differ;
3. at least one task differs in `delivered` or `patch_sha256`.

The result goes to `runs/harness2-falsifier/<tag>.json` (git-ignored). A failure
of (2) means `execute()` is not using the tree; a failure of (3) means `k=1`
carries no signal and the full loop is not worth its cost. Cost is four serial
rollouts, about 14 minutes each at the archived mean; no proposer model is used.

## Full loop (only after the falsifier passes)

```bash
# Preview the stream and namespace; no model call.
PYTHONPATH=tmp/harness2 python3 -m harness2.cli.run_sweep \
  --bench sw --substrate sw --k 1 --mode parallel \
  --only-domains psf/requests --max-tasks 1 --dry-run

# One task, one Propose-Probe-Compose step: 4 rollouts plus 3 proposer sessions.
PYTHONPATH=tmp/harness2 python3 -m harness2.cli.run_sweep \
  --bench sw --substrate sw --k 1 --mode parallel \
  --only-domains psf/requests --max-tasks 1
```

The loop writes under `runs/harness2/` (git-ignored). `harness2-judge` is not
used: `score()` reads the harness's own pytest verdict from `task_results.jsonl`,
so no judge model is involved. `harness2-report` reads the sweep record.

## Rules and limits

- No file under `submission/` is modified by this tooling; the loop edits only a
  copy. `uv run python -m kaggle_gemma_agent.pack submission --check` stays green.
- The adapter rolls **one task per invocation**; `execute_many()` runs serially so
  two Docker sandboxes do not compete for host memory.
- The subset is a contrast set, not a resolution-rate estimate.
- `tmp/` is git-ignored: do not commit the clone, the venv, or any rollout. The
  patch, `setup.sh`, this README and `falsifier.py` are the versioned delta.
- The upstream project is Apache-2.0; this patch is a development tool, not a
  redistribution of the benchmark data.
