#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Single cross-platform runner for the host ``swegemma`` trial.

Port of the former ``run-host-trial.sh`` / ``run-host-trial.ps1`` (PR #15):
the same seven phases, two tasks (``fastapi_15661``, ``fastapi_15588``) against
an OpenAI-compatible cloud backend, archived under ``runs/``. Stdlib only, so
it runs on Windows and Linux either as a uv script::

    uv run --script scripts/host-trial/run_host_trial.py --results-name run_01

or with the repo venv::

    uv run python scripts/host-trial/run_host_trial.py --results-name run_01

Secrets come from the process environment or a git-ignored ``.env`` in the repo
root, parsed here (no python-dotenv). The real environment always wins over
``.env``. ``OPENAI_API_KEY`` is never echoed: it is masked on every line this
script prints. See ``.env.example`` for the schema.

Values mirror ``docs/host-trial-runbook.md`` (sections 1-7) and the
``--models-yaml`` mapping in ``data/raw/models-trial.yaml``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPETITION = "gemma-4-developer-agent"
WHEELHOUSE_DATASET = "metric/gemma-4-developer-agent-wheelhouse"
TASK_IDS: tuple[str, ...] = ("fastapi_15661", "fastapi_15588")
BACKEND_ALIAS = "deepseek-trial"

OPENAI_API_KEY = "OPENAI_API_KEY"
OPENAI_BASE_URL = "OPENAI_BASE_URL"
HARNESS_MODEL = "HARNESS_MODEL"
ENV_KEYS: tuple[str, ...] = (OPENAI_API_KEY, OPENAI_BASE_URL, HARNESS_MODEL)
ENV_MAX_LINES = 20

DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_HARNESS_MODEL = "deepseek-v4.1-flash"

HARNESS_RUNS: tuple[str, ...] = ("uv", "run", "python", "-m", "kaggle_gemma_agent.harness_runs")


class TrialError(Exception):
    """Raised when a trial phase cannot continue."""


@dataclass(frozen=True)
class TrialPaths:
    """Repository paths used across the seven trial phases."""

    repo_root: Path
    data_raw: Path
    tasks_file: Path
    snapshots_dir: Path
    wheelhouse_dir: Path
    docker_context: Path
    submission_dir: Path
    models_yaml: Path
    results_dir: Path
    junit_dir: Path


def paths_for(repo_root: Path, results_name: str) -> TrialPaths:
    """Build the fixed trial paths for *results_name* under *repo_root*."""
    repo_root = Path(repo_root)
    data_raw = repo_root / "data" / "raw"
    return TrialPaths(
        repo_root=repo_root,
        data_raw=data_raw,
        tasks_file=data_raw / "tasks.jsonl",
        snapshots_dir=data_raw / "snapshots",
        wheelhouse_dir=data_raw / "wheelhouse",
        docker_context=data_raw / "docker",
        submission_dir=repo_root / "submission",
        models_yaml=data_raw / "models-trial.yaml",
        results_dir=repo_root / "results" / results_name,
        junit_dir=repo_root / "junit",
    )


def parse_env_file(text: str, *, max_lines: int = ENV_MAX_LINES) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from a ``.env`` body (no dotenv dependency).

    Blank lines and ``#`` comments are skipped, an optional ``export`` prefix is
    accepted, and a single pair of matching quotes is stripped from the value.
    Only the first *max_lines* lines are read; later keys win on duplicates.
    """
    values: dict[str, str] = {}
    for raw in text.splitlines()[:max_lines]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_env_file(path: Path) -> dict[str, str]:
    """Return the parsed ``.env`` at *path*, or ``{}`` when it does not exist."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    return parse_env_file(text)


def resolve_trial_env(
    env_file_values: Mapping[str, str],
    environ: Mapping[str, str],
    *,
    base_url: str = DEFAULT_BASE_URL,
    harness_model: str = DEFAULT_HARNESS_MODEL,
) -> dict[str, str]:
    """Merge ``.env`` with the real environment, then fill the trial defaults.

    The process environment wins over ``.env`` for every key. Base URL and
    harness model fall back to their documented trial defaults.
    """
    resolved: dict[str, str] = {}
    for name in ENV_KEYS:
        value = environ.get(name) or env_file_values.get(name)
        if value:
            resolved[name] = value
    resolved.setdefault(OPENAI_BASE_URL, base_url)
    resolved.setdefault(HARNESS_MODEL, harness_model)
    return resolved


def mask_secret(value: str) -> str:
    """Return a non-reversible placeholder so secrets are never printed."""
    return "<unset>" if not value else "***"


def build_eval_args(
    *,
    tasks_file: Path,
    snapshots_dir: Path,
    submission_dir: Path,
    results_dir: Path,
    models_yaml: Path,
    task_ids: Sequence[str] = TASK_IDS,
) -> list[str]:
    """Build the ``swegemma eval`` argv for the two-task trial."""
    return [
        "swegemma",
        "eval",
        "--tasks",
        str(tasks_file),
        "--snapshots-dir",
        str(snapshots_dir),
        "--submission-dir",
        str(submission_dir),
        "--task-ids",
        *task_ids,
        "--results-dir",
        str(results_dir),
        "--sandbox",
        "docker",
        "--max-tool-calls",
        "100",
        "--max-time-minutes",
        "60",
        "--concurrency",
        "1",
        "--display",
        "auto",
        "--models-yaml",
        str(models_yaml),
    ]


def build_archive_args(
    results_dir: Path,
    junit_dir: Path,
    tasks_file: Path,
    backend: str = BACKEND_ALIAS,
) -> list[str]:
    """Build the ``harness_runs archive`` argv."""
    return [
        *HARNESS_RUNS,
        "archive",
        str(results_dir),
        "--junit-dir",
        str(junit_dir),
        "--tasks",
        str(tasks_file),
        "--backend",
        backend,
    ]


def build_report_args(run_dir: Path) -> list[str]:
    """Build the ``harness_runs report`` argv."""
    return [*HARNESS_RUNS, "report", str(run_dir)]


def phase(title: str) -> None:
    """Print a phase banner."""
    print(f"\n=== {title} ===")


def note(text: str) -> None:
    """Print an indented phase note."""
    print(f"  {text}")


def run_cmd(cmd: Sequence[str], *, what: str | None = None) -> None:
    """Echo and run *cmd*, raising :class:`TrialError` on a non-zero exit."""
    print("  $ " + " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        label = what or cmd[0]
        raise TrialError(f"{label} failed (exit {result.returncode})")


def _docker_ostype() -> str:
    """Return ``docker info --format {{.OSType}}`` output, or ``""`` on failure."""
    result = subprocess.run(
        ["docker", "info", "--format", "{{.OSType}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_has_file(spec: str) -> bool:
    """Return whether ``git show <spec>`` succeeds (quietly)."""
    result = subprocess.run(
        ["git", "show", spec],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def extract_zips(directory: Path) -> None:
    """Extract every ``*.zip`` in *directory* in place, stdlib only."""
    for archive in sorted(Path(directory).glob("*.zip")):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(directory)


def check_prerequisites() -> None:
    """Phase 1: require git/uv/docker/kaggle and a Linux Docker engine."""
    phase("Phase 1/7 (runbook sec. 1): prerequisites")
    requirements = (
        ("git", "Install git first."),
        ("uv", "Install uv first: https://astral.sh/uv"),
        ("docker", "Install Docker Desktop and start it."),
        ("kaggle", "Install the Kaggle CLI: uv tool install kaggle"),
    )
    for name, hint in requirements:
        if shutil.which(name) is None:
            raise TrialError(f"missing prerequisite '{name}'. {hint}")

    docker_os = _docker_ostype()
    if docker_os != "linux":
        raise TrialError(
            f"Docker engine is not reachable in Linux mode (got '{docker_os or '<none>'}'). "
            "Start Docker Desktop and confirm the Linux engine (runbook sec. 1.1)."
        )

    kaggle_token = Path.home() / ".kaggle" / "kaggle.json"
    if not kaggle_token.is_file():
        raise TrialError(
            f"Kaggle token not found at {kaggle_token}. Download it from your Kaggle "
            "account (runbook sec. 1.4)."
        )

    run_cmd(["git", "--version"])
    run_cmd(["uv", "--version"])
    run_cmd(["kaggle", "--version"])
    note("Docker engine OSType: linux")


def ensure_harness_branch(repo_root: Path) -> None:
    """Phase 2: fetch origin and fall back to ``main`` when harness code is absent."""
    phase("Phase 2/7 (runbook sec. 2): repository and harness branch")
    os.chdir(repo_root)
    run_cmd(["git", "fetch", "origin"])

    contract = repo_root / "docs" / "harness-logging-contract.md"
    archiver = repo_root / "src" / "kaggle_gemma_agent" / "harness_runs.py"
    if not contract.is_file() or not archiver.is_file():
        if _git_has_file("origin/main:docs/harness-logging-contract.md"):
            note("harness code absent on this branch; switching to main")
            run_cmd(["git", "checkout", "main"])
            run_cmd(["git", "pull", "--ff-only", "origin", "main"])
        else:
            raise TrialError(
                "harness code (docs/harness-logging-contract.md, harness_runs.py) is not "
                "available. Check out main or exp/harness-trial-1 (runbook sec. 2)."
            )

    if not contract.is_file():
        raise TrialError("docs/harness-logging-contract.md still missing after update.")
    if not archiver.is_file():
        raise TrialError("src/kaggle_gemma_agent/harness_runs.py still missing after update.")


def _fetch_competition_file(remote_file: str, dest_dir: Path) -> None:
    """Download one competition file unless it is already present."""
    name = Path(remote_file).name
    dest = dest_dir / name
    if dest.is_file():
        note(f"skip (exists): {dest}")
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(
        [
            "kaggle",
            "competitions",
            "download",
            "-c",
            COMPETITION,
            "-f",
            remote_file,
            "-p",
            str(dest_dir),
        ],
        what=f"kaggle download {remote_file}",
    )


def fetch_data(paths: TrialPaths) -> None:
    """Phase 3: fetch the wheelhouse + small fixtures only (never bulk snapshots)."""
    phase("Phase 3/7 (runbook sec. 4): fetch wheelhouse + small fixtures (NO bulk)")

    if any(paths.wheelhouse_dir.glob("*.whl")):
        note("skip (exists): runtime wheelhouse already extracted")
    else:
        paths.wheelhouse_dir.mkdir(parents=True, exist_ok=True)
        run_cmd(
            [
                "kaggle",
                "datasets",
                "download",
                "-d",
                WHEELHOUSE_DATASET,
                "-p",
                str(paths.wheelhouse_dir),
            ],
            what="kaggle datasets download wheelhouse",
        )
        extract_zips(paths.wheelhouse_dir)

    _fetch_competition_file("tasks.jsonl", paths.data_raw)
    _fetch_competition_file("HARNESS_README.md", paths.data_raw)
    _fetch_competition_file("sandbox/setup.py", paths.data_raw / "sandbox")
    _fetch_competition_file("docker/Dockerfile.sandbox", paths.docker_context)
    _fetch_competition_file("docker/Dockerfile.public", paths.docker_context)

    note("fetching only the two trial snapshots (never the whole snapshots/ tree)")
    _fetch_competition_file("snapshots/fastapi_15661.tgz", paths.snapshots_dir)
    _fetch_competition_file("snapshots/fastapi_15588.tgz", paths.snapshots_dir)


def build_image(paths: TrialPaths) -> None:
    """Phase 4: build the sandbox image from the fetched Dockerfile."""
    phase("Phase 4/7 (runbook sec. 3): build sandbox image")
    dockerfile = paths.docker_context / "Dockerfile.sandbox"
    if not dockerfile.is_file():
        raise TrialError(f"missing {dockerfile} (fetched in phase 3).")
    run_cmd(
        [
            "docker",
            "build",
            "-t",
            "swebench-sandbox:latest",
            "-f",
            str(dockerfile),
            str(paths.docker_context),
        ],
        what="docker build swebench-sandbox:latest",
    )


def resolve_backend_env(env_file: Path, models_yaml: Path) -> dict[str, str]:
    """Phase 5: load ``.env``/environment, abort if the key is empty, mask output."""
    phase("Phase 5/7 (runbook sec. 5): backend key (environment only)")

    resolved = resolve_trial_env(load_env_file(env_file), os.environ)
    if not resolved.get(OPENAI_API_KEY):
        raise TrialError(
            f"{OPENAI_API_KEY} is empty. Put it in {env_file} (git-ignored) or export it "
            "before running; never pass it as an argument (runbook sec. 5)."
        )
    if not Path(models_yaml).is_file():
        raise TrialError(
            f"missing {models_yaml} (the --models-yaml mapping; runbook sec. 6 / "
            "data/raw/models-trial.yaml)."
        )

    for name, value in resolved.items():
        if value:
            os.environ[name] = value

    note(
        f"{OPENAI_API_KEY} is set (value not shown: {mask_secret(resolved[OPENAI_API_KEY])}); "
        f"base URL: {resolved[OPENAI_BASE_URL]}"
    )
    note(f"{HARNESS_MODEL}: {resolved[HARNESS_MODEL]} (trial-only; not part of the submission)")
    return resolved


def run_eval(paths: TrialPaths) -> None:
    """Phase 6: run ``swegemma eval`` for the two tasks."""
    phase("Phase 6/7 (runbook sec. 6): swegemma eval (2 tasks, competition budgets)")
    if shutil.which("swegemma") is None:
        raise TrialError(
            "swegemma is not on PATH. Install it from the wheelhouse dataset "
            "(runbook sec. 4.1; install command is an open TODO in the runbook)."
        )
    paths.results_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(
        build_eval_args(
            tasks_file=paths.tasks_file,
            snapshots_dir=paths.snapshots_dir,
            submission_dir=paths.submission_dir,
            results_dir=paths.results_dir,
            models_yaml=paths.models_yaml,
        ),
        what="swegemma eval",
    )


def archive_and_report(paths: TrialPaths) -> Path:
    """Phase 7: archive into ``runs/<UTC>/`` and print the report."""
    phase("Phase 7/7 (runbook sec. 7-9): archive + report under runs/")
    note("JUnit note (runbook sec. 8): the harness writes JUnit XML only inside Container B")
    note("at /tmp/_swegemma_junit_<id>.xml and warm-pooled containers are wiped. If a")
    note("container is still alive, copy it out before teardown:")
    note("  docker ps")
    note(f"  docker cp <container>:/tmp/_swegemma_junit_fastapi_15661.xml {paths.junit_dir}/")
    note("If it is already gone, pass/fail is still readable from task_results.jsonl.")

    paths.junit_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(
        build_archive_args(paths.results_dir, paths.junit_dir, paths.tasks_file),
        what="harness_runs archive",
    )

    runs_root = paths.repo_root / "runs"
    candidates = sorted(
        (path for path in runs_root.glob("*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise TrialError("archiver produced no runs/<UTC>/ directory.")
    latest = candidates[-1]

    run_cmd(build_report_args(latest), what="harness_runs report")
    return latest


def run(repo_root: Path, results_name: str, env_file: Path) -> Path:
    """Execute all seven trial phases and return the archived run directory."""
    paths = paths_for(repo_root, results_name)
    check_prerequisites()
    ensure_harness_branch(Path(repo_root))
    fetch_data(paths)
    build_image(paths)
    resolve_backend_env(env_file, paths.models_yaml)
    run_eval(paths)
    return archive_and_report(paths)


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the cross-platform host trial runner."""
    parser = argparse.ArgumentParser(
        prog="run_host_trial.py",
        description="Run the two-task host swegemma trial and archive it under runs/.",
    )
    parser.add_argument(
        "results_name",
        nargs="?",
        default="run_01",
        help="names results/<name> (default: run_01)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="path to the .env file (default: <repo root>/.env)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = REPO_ROOT
    env_file = args.env_file if args.env_file is not None else repo_root / ".env"
    try:
        run_dir = run(repo_root, args.results_name, env_file)
    except TrialError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nTrial complete. Archived under {run_dir} (report: {run_dir / 'report.json'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
