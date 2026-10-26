---
Date: 2026-10-26
Genre: proposal
Status: open
Scope: Go/no-go on writing a `swegemma` `BenchmarkAdapter` for harness2, with the execute path read from the shipped wheel, the 12-method mapping, the cost of a fixed 20-rollout experiment, the blockers and a falsifying experiment. It writes no code and changes no submission file.
Source of truth: data/raw/wheelhouse/gemma-4-developer-agent-wheelhouse.zip (swegemma 0.2.7, adk_submission 0.2.11, adk_eval_core 0.1.0), runs/20261009T122847Z/, data/raw/tasks.jsonl, scripts/host-trial/run_host_trial.py, docs/host-trial-runbook.md (read 2026-10-26)
Limits: A decision document only. No rollout was run for it, so every cost figure is derived from run `20261009T122847Z` and inherits that run's batch, backend and machine; harness2 has no local checkout, so its protocol is cited from upstream, not read locally.
---

# harness2 adapter: go / no-go

Harness changes are proposed by hand and validated by a resolution rate the
container dominates: `1/13` in run `20261009T122847Z` (13 `psf/requests` tasks,
12 delivered patches, 1 resolved). Harness2 offers the missing method - improve a
harness from execution contrast without a grade - but it needs a benchmark
adapter, and the question is whether our seams support one.

Two premises of the original framing were checkable in this repository and are
corrected here instead of being left to the implementer: a single-task runner
already exists (`--tasks <id>` through the repository's own `submission/` tree),
and `execute()` is therefore not the blocker. What was open is whether
`swegemma eval` accepts an arbitrary submission directory. It does.

## Execute path

The exact command for one task against an arbitrary tree. Tokens marked
**generated** must be produced at run time; every other token is passed through:

```text
swegemma eval \
  --tasks data/raw/tasks.jsonl \
  --snapshots-dir data/raw/snapshots \
  --submission-dir <tree> \
  --task-ids <id> \
  --results-dir <dir> \
  --sandbox docker \
  --max-tool-calls 100 \
  --max-time-minutes 60 \
  --concurrency 1 \
  --display auto \
  --models-yaml <generated models.yaml>
```

`<generated models.yaml>` is the only derived argument, and the repository
already derives it: `render_models_yaml` / `write_models_yaml`
(`scripts/host-trial/run_host_trial.py` L361-L387) map **every** `model:` alias
the submission declares to `openai/<HARNESS_MODEL>`. `--models-yaml` is optional
on the CLI (`swegemma/cli.py` L84-L89) but required in practice: without it
`setup_gemma_model_registry` builds the default registry and a submission alias
fails to resolve at compile time.

Generated rather than passed: `--models-yaml`. The three angle-bracket
placeholders in the other lines (`<tree>`, `<id>`, `<dir>`) are the adapter's own
per-rollout arguments.

### (a) Does `--submission-dir` accept a directory outside this repository?

**Yes.** Nothing in the harness anchors that path to a repository, a working
directory or a package layout:

- `swegemma/cli.py` L45-L50 declares it as `type=Path`, required, with no
  containment check, and L145 passes it straight into `EvalConfig`.
- `swegemma/config.py` L95 stores `submission_dir: Path`; `EvalConfig.__post_init__`
  validates `display_mode` and the shard pair only.
- `adk_submission/discovery.py` L89 resolves whatever path it is given
  (`root = Path(submission_dir).resolve()`) and L91-L94 rejects only a path that
  is not a directory.
- The single consumer is `compile_submission(submission_dir=config.submission_dir,
  ...)` at `swegemma/harness/agent_runner.py` L334-L335, inside
  `run_agent_sandbox` (L193).

Consequently **neither a `--submission-dir` flag on
`scripts/host-trial/run_host_trial.py` nor an adapter-local reimplementation of
the runner's argv builder is required.** The adapter needs the `models.yaml`
generation only. When the adapter is built it should load `render_models_yaml`
from the runner by file path (`scripts/host-trial/` is not an importable
package) rather than duplicating the alias-derivation logic, so the alias list
cannot drift between the runner and the adapter. `build_eval_args` - not
`build_eval_argv`, which does not exist - is the argv reference at
`scripts/host-trial/run_host_trial.py` L876-L911.

### (b) What is validated before the container starts?

`compile_submission` (`adk_submission/compiler.py` L119-L130) calls
`validate_directory` first, then loads and validates the root YAML:

1. `submission_dir` must be a directory (`discovery.py` L91-L94).
2. A recursive scan rejects any symlink (`discovery.py` L101-L105).
3. At most 10 000 files and at most 3 GiB total, from the limits
   `swegemma/config.py` L19-L56 builds (`discovery.py` L111-L119).
4. Every file extension must be in `.yaml .yml .md .txt .py .json .safetensors`
   (`config.py` L20-L30, enforced at `discovery.py` L120-L126).
5. At most 1 000 YAML files, each at most 50 MiB, and each `SKILL.md` directory
   at most 50 MiB (`discovery.py` L135-L157).
6. A root config must be found: `agent.yaml`, else `root_agent.yaml`, else the
   single root-level YAML; zero root YAMLs and two-plus unnamed root YAMLs both
   raise (`discovery.py` L171-L253, `_ROOT_CONFIG_NAMES` at L24). So
   `agent.yaml` is **preferred by name but not required by name**.
7. The root YAML is loaded with sandboxed `!include`, then validated against a
   `extra="forbid"` Pydantic schema (`compiler.py` L132-L143,
   `adk_submission/schema.py` `SandboxedAgentConfig`), and every tool, model,
   callback, skill and adapter reference must resolve in a closed registry.

The **single-declared-model** contract is *not* enforced on this path.
`swegemma/models/discovery.py` L93 defines `validate_single_declared_model` and
`swegemma/models/__init__.py` L25 exports it, but no code in `swegemma` calls it;
the `eval` path checks that each alias resolves in the registry, not how many
models the submission declares. A `validate_tree` that relies on the harness for
that check would be wrong.

### (c) Is the tree copied into the container, so a mutable tree is safe?

**No copy and no mount.** `swegemma/evaluate.py` never references
`submission_dir`; the container receives the wheels
(`setup_container_wheels`), the snapshot (`extract_snapshot`) and an optional
`/tmp/setup.py` (`harness/container_setup.py` L535), and the submission tree is
read in the host process. Three consequences for the adapter:

- Mutating the tree **between** rollouts is safe: the next task compiles it
  again, because `compile_submission` runs inside the per-task
  `run_agent_sandbox` (L193, call at L334).
- Mutating the tree **during** a rollout does not reach the running task.
- `base_harness()` must still hand harness2 a fresh copy of `submission/` from a
  named commit, never the working tree in place, because the compile is
  host-side and a dirty worktree would change the identity the run records.

## Adapter mapping

One row per protocol method; `Optional` marks the two the protocol does not
require.

| method | source, precisely |
|---|---|
| `tasks(split)` | every `instance_id` in `data/raw/tasks.jsonl` (**129**), not the 13-task run subset; `split` is ignored and the document says so; experiments name their subset explicitly |
| `domain_of(task_id)` | the `repo` field: 4 values (`fastapi/fastapi` 67, `psf/requests` 13, `Textualize/rich` 48, `encode/httpx` 1), so the domain library does not collapse to one bucket; the 13-task experiment touches one of the four |
| `task_prompt(task_id)` | `problem_statement` from `data/raw/tasks.jsonl`. **Not** `trace.json` step 2: that message is the whole harness preamble plus budgets and instructions (5 175 characters for `requests_7427`), and feeding it to another substrate would re-inject our own procedure as if it were the user's problem |
| `task_files(task_id)` | `None` - `Optional`, deliberately unimplemented: the checkout lives inside the container and is not reproducible host-side from the archive |
| `execute(...)` | the command from `## Execute path`; archives the results directory into the per-task layout before returning, because `delivered`/`trajectory`/`deliverable_text` read the archived per-task directory, not `--results-dir` |
| `delivered(run_dir)` | the run root's `report.json` (the **parent** of `run_dir`, since `run_dir` is the per-task directory) has a non-null `patch_path` for that task **and** `<run_dir>/agent_patch.diff` is a non-empty file. `patch_sha256` alone is not the signal: it is also present for patches later classified `edits_tests`, `config_only` or `scratch` |
| `trajectory(run_dir, obs_trunc)` | `session.log` (human transcript) plus `trace.json` steps rendered as `[ACTION]` / `[OBSERVATION]`, observations truncated to `obs_trunc` |
| `deliverable_files(run_dir)` | `Optional`, deliberately unimplemented: the deliverable is one diff, not a tree |
| `deliverable_text(run_dir)` | the `agent_patch.diff` text |
| `base_harness()` | a **fresh copy** of `submission/` from a named commit into a temp directory, never `submission/` in place; harness2 may mutate the tree it is given between rollouts, which is safe on the harness side (see `## Execute path` (c)) and must not touch the repository |
| `validate_tree(tree)` | the argument is `dict[str, str]` (relative path to contents), so materialise it into a temp directory and run all three checks on that directory: `pack.check_submission(source_dir)`, `pack.check_harness_surface(source_dir)`, `pack.check_answer_leak(source_dir)`; raise on a non-empty violation list |
| `score(run_dir, task_id)` | `report.json` `tasks[].resolved` for that task, where `verdict_source` is `pytest`. Deterministic: harness2's judged-model default is **not** adopted |

`run_dir` means the per-task archived directory `runs/<run-id>/<task-id>/`
throughout; the run root is its parent and is read separately for `report.json`.

## Cost

Inputs, all from `runs/20261009T122847Z/report.json`:

| Quantity | Value |
|---|---|
| Tasks in the run | 13 |
| Wall clock, whole run | 10 694.5 s |
| Tool calls, whole run | 537 |
| Tokens, whole run | 10 621 717 (sum of `final_metrics.total_tokens` over the 13 `trace.json` files) |
| Mean per rollout | 10 694.5 / 13 = **822.65 s** (13.71 min), 537 / 13 = **41.3** calls, 10 621 717 / 13 = **817 055** tokens |
| Worst observed rollout by calls | `requests_7502`: 87 calls, 1 557.25 s |
| Slowest observed rollout | `requests_7433`: 1 984.93 s (33.1 min) |

The fixed experiment is **5 tasks x 4 rollouts (base, INV, DOM, COMPOSE) = 20
rollouts**. The subset is fixed so the estimate is reproducible:

| Task | Calls | Wall (s) | `resolved` | Patch delivered | Why it is in the subset |
|---|---|---|---|---|---|
| `requests_7427` | 41 | 847.7 | True | True | the only resolved task, i.e. the positive control |
| `requests_6644` | 17 | 409.32 | False | True | `test_failure`, patch delivered |
| `requests_7205` | 40 | 606.61 | False | True | `test_failure`, patch delivered |
| `requests_7315` | 22 | 445.63 | False | False | no patch delivered - the procedure failure |
| `requests_6589` | 30 | 351.34 | False | True | `failure_kind=unknown`, the largest unexplained bucket |

Arithmetic:

- Serial at the mean: `20 x 822.65 s = 16 453 s = 4.57 h`.
- Serial at the observed maximum: `20 x 1 984.93 s = 39 698.6 s = 11.03 h`.
- Cross-check against the subset itself: the five base rollouts sum to
  `2 660.6 s`, so four passes over them is `10 642.4 s = 2.96 h`. The mean-based
  figure is the conservative one and is the one quoted.
- Tool calls, not a budget line: `20 x 41.3 = 826` calls in total, while each
  rollout keeps the harness budget of 100 calls / 60 minutes / 500 turns.
- Tokens: `20 x 817 055 = 16 341 100`, i.e. about **16.3 M tokens**. No currency
  figure is derivable from the archive: the rollouts were produced by the trial
  backend (`HARNESS_MODEL` through the local forwarding proxy), not by
  `gemma-4-31b-it-qat-w4a16-ct`, and the archive records no price. Any price
  quoted for this experiment prices the *substitute* backend, not the scored one.
- `--concurrency` is 1 in the runner (`scripts/host-trial/run_host_trial.py`
  L905-L906). At `--concurrency 2` the ideal wall time halves to 2.29 h, but two
  sandbox containers per task compete for the same Docker memory, and the archive
  gives no evidence about that; the estimate stays at concurrency 1.

## Blockers

| Blocker | Verdict | Detail |
|---|---|---|
| Host: Windows dev box with Docker; WSL2 required | real | `docs/host-trial-runbook.md` L132 and L183. The adapter can run the CLI from Windows, but a trial that matches the scored environment runs inside the distro. |
| Python 3.12 plus `uv`, harness CLI from the local wheelhouse, not PyPI | already solved | `scripts/host-trial/run_host_trial.py` L946-L959 builds `uv tool install --find-links <wheelhouse> swegemma`; `docs/host-trial-runbook.md` L265 has the one-liner. |
| Git-ignored inputs must be re-downloaded before any rollout | real | `data/raw/` is not in the repository; `tasks.jsonl`, `HARNESS_README.md`, `sandbox/setup.py` and the docker shims come from `kaggle competitions download` (runbook L277-L305), and the 129 snapshots are per task. |
| Backend credential | real | `HARNESS_BACKEND_API_KEY` or `OPENAI_API_KEY` from the process environment or a git-ignored `.env` (runbook L317-L339); Container A runs with no network, so the key never enters the sandbox. |
| Judge mismatch: harness2 defaults to a model judge | already solved | `score()` reads `report.json` `tasks[].resolved` with `verdict_source` = `pytest`; no judge is invoked and no model call is added. |
| `harness2` has no local checkout | real | Upstream `google-research/harness2` (arXiv 2610.14224): `harness2/core/spec.py`, `core/recursion.py`, `core/library.py`, `core/prompts.py`, `docs/EXPERIMENTS.md` are cited, not vendored; nothing is added to `pyproject.toml`. |
| Answer leak: `tasks.jsonl` carries `patch` and `test_patch` | real | The adapter reads only `instance_id`, `repo` and `problem_statement`, and `validate_tree` runs `pack.check_answer_leak` on every produced tree (issue #91). |
| The tree is compiled host-side once per task | already solved | `## Execute path` (c): edits between rollouts take effect, edits during a rollout do not, and the container never sees the tree. |

## Decision

**go.**

The execute path needs no new harness code: `--submission-dir` accepts any
directory the host can read (`## Execute path` (a)), the tree is never mounted
so a mutable harness tree is safe between rollouts (c), and the only generated
argument is a `models.yaml` the repository already renders. The method therefore
reduces to a 12-method mapping over files the archiver already writes.

The cost is bounded and affordable: 20 rollouts is 4.57 h serial at the mean and
11.03 h at the observed worst case, 826 tool calls and about 16.3 M tokens, with
the scored artifact untouched - the loop runs offline and `submission/` stays
declarative. The falsifying experiment in the next section costs 4 of those
rollouts and can kill the method before the other 16 are spent.

This decision commits to nothing in `submission/` and starts no rollout.

## Falsifying experiment

2 tasks (`requests_6644`, `requests_7315`) x 2 harnesses (base tree, base plus one
`INV` edit) = 4 rollouts, all under the budget of 100 calls / 60 min / 500 turns.

Assertions, in this order:

1. All four rollouts are archived: four per-task directories with
   `report.json` at the run root.
2. `manifest.json` `provenance.prompt` differs between the base and the edited
   harness. If it does not, the tree was not used.
3. At least one of the two tasks differs in `delivered` or `patch_sha256`
   between the two harnesses.

Kill criteria, stated before running:

- If (2) fails, `execute()` is wrong and the decision drops to `no-go` until it
  is fixed.
- If (2) passes and (3) fails on 2 of 2 tasks, `k=1` carries no signal and the
  decision becomes `no-go` for `k=1`; reviving it for `k>=2` needs its own issue.

## Prerequisites

Environment, in order:

```powershell
# 0. WSL2 + Docker Desktop with WSL integration enabled for the distro.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install kaggle

# 1. Git-ignored inputs (data/raw/ is not in the repository).
kaggle competitions download -c gemma-4-developer-agent -f tasks.jsonl -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f HARNESS_README.md -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f sandbox/setup.py -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/Dockerfile.sandbox -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/Dockerfile.public -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/imp.py -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f docker/telnetlib.py -p data\raw
kaggle competitions download -c gemma-4-developer-agent -f snapshots/requests_6644.tgz -p data\raw\snapshots
kaggle competitions download -c gemma-4-developer-agent -f snapshots/requests_7315.tgz -p data\raw\snapshots

# 2. Sandbox image and harness CLI, both offline from the wheelhouse.
docker build -t swebench-sandbox:latest -f data\raw\docker\Dockerfile.sandbox data\raw\docker
uv tool install --find-links data\raw\wheelhouse swegemma

# 3. Backend, session-scoped only; never committed.
$env:HARNESS_BACKEND_API_KEY = "<your-backend-key>"
$env:HARNESS_MODEL = "<exact model id the server exposes>"
```

`data/raw/snapshots` held 129 files on this checkout (`-f snapshots/<task>.tgz`
per task, never the whole directory), and
`data/raw/wheelhouse/gemma-4-developer-agent-wheelhouse.zip` holds
`swegemma-0.2.7-py3-none-any.whl`, `adk_submission-0.2.11-py3-none-any.whl` and
`adk_eval_core-0.1.0-py3-none-any.whl` among the backend wheels. A fresh clone
has none of it.
