#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Single cross-platform runner for the host ``swegemma`` trial.

Port of the former ``run-host-trial.sh`` / ``run-host-trial.ps1`` (PR #15):
the same eight phases, by default two tasks (``fastapi_15661``,
``fastapi_15588``) against an OpenAI-compatible cloud backend, archived under
``runs/``. Set ``HARNESS_TRIAL_TASKS`` (comma-separated instance ids) to
override the default task set. Stdlib only, so it runs on Windows and Linux
either as a uv script::

    uv run --script scripts/host-trial/run_host_trial.py --results-name run_01

or with the repo venv::

    uv run python scripts/host-trial/run_host_trial.py --results-name run_01

Secrets come from the process environment or a git-ignored ``.env`` in the repo
root, parsed here (no python-dotenv). The real environment always wins over
``.env``. ``OPENAI_API_KEY`` is never echoed: it is masked on every line this
script prints. See ``.env.example`` for the schema.

Backend wiring (see ``docs/host-trial-runbook.md`` section 6):

* The opencode.ai Go backend rejects any request without a stable
  ``x-opencode-session`` header. ``swegemma`` 0.2.7 builds its ADK ``LiteLlm``
  clients with a fixed kwargs set and exposes no ``extra_headers`` hook, so the
  header cannot be added from a models-yaml or an env var. The runner instead
  starts a short-lived local forwarding proxy and points ``OPENAI_BASE_URL`` at
  it; the proxy stamps the header and forwards to the real backend. The LLM
  calls originate in the host ``swegemma`` process (the ADK ``Runner`` runs
  host-side and Container A is ``network_mode='none'``), so a host-local proxy
  is sufficient.
* The wire model follows ``HARNESS_MODEL``. The runner generates a
  ``models.yaml`` at run time that maps every ``model:`` alias declared by the
  submission to ``openai/<HARNESS_MODEL>``; the host-local
  ``data/raw/models-trial.yaml`` is no longer read.
"""

from __future__ import annotations

import argparse
import http.client
import http.server
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPETITION = "gemma-4-developer-agent"
WHEELHOUSE_DATASET = "metric/gemma-4-developer-agent-wheelhouse"
WHEELS_DIRNAME = "wheels/"
LIST_PAGE_SIZE = 200
PAGE_TOKEN_MARKER = "Next Page Token ="
WHEEL_DOWNLOAD_ATTEMPTS = 5
WHEEL_DOWNLOAD_BACKOFF_SECONDS = 2.0
WHEEL_DOWNLOAD_PAUSE_SECONDS = 1.5
RATE_LIMIT_MARKERS: tuple[str, ...] = ("too many requests", "rate limit", "429 client error")
TASK_IDS: tuple[str, ...] = ("fastapi_15661", "fastapi_15588")
BACKEND_ALIAS = "deepseek-trial"
SWEGEMMA_TOOL = "swegemma"
#: swegemma caches unpacked wheels as ``<temp>/swegemma_sp_cache_v<N>/sp_base.tar``
#: keyed by name only (no wheel-set hash), so a tar built from a partial wheel set
#: poisons every later run. The runner clears matching dirs before each eval.
SWEGEMMA_SP_CACHE_PREFIX = "swegemma_sp_cache_"

OPENAI_API_KEY = "OPENAI_API_KEY"
OPENAI_BASE_URL = "OPENAI_BASE_URL"
HARNESS_MODEL = "HARNESS_MODEL"
SESSION_ENV = "HARNESS_TRIAL_SESSION"
TASKS_ENV = "HARNESS_TRIAL_TASKS"
ENV_KEYS: tuple[str, ...] = (OPENAI_API_KEY, OPENAI_BASE_URL, HARNESS_MODEL)
ENV_MAX_LINES = 20

DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_HARNESS_MODEL = "deepseek-v4.1-flash"

OPENCODE_SESSION_HEADER = "x-opencode-session"
DEFAULT_TRIAL_SESSION = "swegemma-host-trial"
CLIENT_USER_AGENT = "swegemma-host-trial/1.0"
GENERATED_MODELS_FILENAME = "models-trial.generated.yaml"
MODEL_PROVIDER_PREFIXES: tuple[str, ...] = ("openai/", "hosted_vllm/", "custom/")
MODEL_LINE_RE = re.compile(r"^\s*model:\s*(?P<model>[^#\n]+?)\s*(?:#.*)?$")
HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)
PROXY_CONTROLLED_HEADERS = HOP_BY_HOP_HEADERS | {
    "accept-encoding",
    "content-length",
    "host",
    "user-agent",
    OPENCODE_SESSION_HEADER,
}

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
    wheels_dir: Path
    docker_context: Path
    submission_dir: Path
    models_yaml: Path
    results_dir: Path
    junit_dir: Path


def paths_for(repo_root: Path, results_name: str) -> TrialPaths:
    """Build the fixed trial paths for *results_name* under *repo_root*."""
    repo_root = Path(repo_root)
    data_raw = repo_root / "data" / "raw"
    results_dir = repo_root / "results" / results_name
    return TrialPaths(
        repo_root=repo_root,
        data_raw=data_raw,
        tasks_file=data_raw / "tasks.jsonl",
        snapshots_dir=data_raw / "snapshots",
        wheelhouse_dir=data_raw / "wheelhouse",
        wheels_dir=data_raw / "wheels",
        docker_context=data_raw / "docker",
        submission_dir=repo_root / "submission",
        models_yaml=results_dir / GENERATED_MODELS_FILENAME,
        results_dir=results_dir,
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


def provider_qualified_model(model: str) -> str:
    """Return *model* with an ``openai/`` provider prefix when it has none."""
    if model.startswith(MODEL_PROVIDER_PREFIXES):
        return model
    return f"openai/{model}"


def collect_declared_models(submission_dir: Path) -> list[str]:
    """Return every ``model:`` value declared under *submission_dir* (deduped).

    Scans ``*.yaml`` recursively so ``agent.yaml`` and every
    ``sub_agents/*.yaml`` are covered, mirroring the harness's single-model
    validation. Order of first appearance is preserved.
    """
    models: list[str] = []
    for yaml_path in sorted(Path(submission_dir).rglob("*.yaml")):
        try:
            text = yaml_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            match = MODEL_LINE_RE.match(line)
            if match is None:
                continue
            value = match.group("model").strip().strip("'\"")
            if value and value not in models:
                models.append(value)
    return models


def render_models_yaml(aliases: Sequence[str], harness_model: str) -> str:
    """Render a ``models.yaml`` mapping every *alias* to the HARNESS_MODEL target.

    The generated file carries no ``api_base``/``api_key`` on purpose: the
    registry then falls back to ``OPENAI_BASE_URL`` (the local header proxy) and
    ``OPENAI_API_KEY`` from the process environment.
    """
    target = provider_qualified_model(harness_model)
    lines = [
        "# GENERATED by scripts/host-trial/run_host_trial.py - do not edit or commit.",
        "# Maps every model alias declared by the submission to the trial backend",
        f"# model selected by HARNESS_MODEL={harness_model} via OPENAI_BASE_URL.",
        "models:",
    ]
    for alias in aliases:
        lines.append(f"  {alias}:")
        lines.append(f"    path: {target}")
        lines.append(f"    display_name: Trial substitute ({target})")
    lines.append("")
    return "\n".join(lines)


def write_models_yaml(path: Path, aliases: Sequence[str], harness_model: str) -> Path:
    """Write the generated ``models.yaml`` to *path* (creating parents) and return it."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_models_yaml(aliases, harness_model), encoding="utf-8")
    return output


def resolve_trial_session(
    env_file_values: Mapping[str, str],
    environ: Mapping[str, str],
) -> str:
    """Resolve the trial session id (real env wins over ``.env``, then default)."""
    return environ.get(SESSION_ENV) or env_file_values.get(SESSION_ENV) or DEFAULT_TRIAL_SESSION


def parse_trial_tasks(
    raw: str,
    *,
    default: tuple[str, ...] = TASK_IDS,
) -> tuple[str, ...]:
    """Parse a comma-separated instance-id list, falling back to *default*.

    Entries are stripped and blank entries dropped, so ``" a , ,b "`` becomes
    ``("a", "b")``. An empty or all-blank *raw* yields *default*.
    """
    task_ids = tuple(part.strip() for part in raw.split(",") if part.strip())
    return task_ids or default


def resolve_trial_tasks(
    env_file_values: Mapping[str, str],
    environ: Mapping[str, str],
    *,
    default: tuple[str, ...] = TASK_IDS,
) -> tuple[str, ...]:
    """Resolve the trial task ids (real env wins over ``.env``, then *default*)."""
    raw = environ.get(TASKS_ENV) or env_file_values.get(TASKS_ENV) or ""
    return parse_trial_tasks(raw, default=default)


def join_upstream_path(base_path: str, request_target: str) -> str:
    """Join an upstream base path with a client request target (``path?query``).

    Litellm hands the OpenAI SDK a bare proxy origin and the SDK appends
    ``/chat/completions``; some providers additionally append ``/v1``. This
    keeps the upstream base path (e.g. ``/zen/go/v1``) and collapses a
    duplicated leading version segment so both shapes reach the right URL.
    """
    split = urllib.parse.urlsplit(request_target)
    base = base_path.rstrip("/")
    path = split.path or "/"
    if not base:
        joined = path
    elif path == base or path.startswith(base + "/"):
        joined = path
    elif base.rsplit("/", 1)[-1] == path.lstrip("/").split("/", 1)[0]:
        head = path.lstrip("/").split("/", 1)[0]
        joined = base + path[len("/" + head) :]
    else:
        joined = f"{base}/{path.lstrip('/')}"
    return f"{joined}?{split.query}" if split.query else joined


class HeaderInjectingProxy:
    """Local HTTP proxy that stamps ``x-opencode-session`` on every request.

    ``swegemma`` 0.2.7 constructs its ADK ``LiteLlm`` clients with a fixed
    kwargs set and offers no ``extra_headers`` mechanism, so the opencode.ai
    routing header cannot be supplied from the harness. This proxy owns the
    origin instead: ``OPENAI_BASE_URL`` is pointed at it and it forwards every
    request to the real backend with the header added, without forking the
    harness. It binds to ``127.0.0.1`` on an ephemeral port and runs a daemon
    thread that dies with the runner process.
    """

    def __init__(
        self,
        upstream: str,
        session: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        parsed = urllib.parse.urlsplit(upstream)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise TrialError(f"invalid upstream base URL: {upstream!r}")
        self._scheme = parsed.scheme
        self._host = parsed.hostname or ""
        self._port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self._base_path = parsed.path.rstrip("/")
        self._session = session
        self._extra_headers = dict(extra_headers or {})
        self._timeout_seconds = timeout_seconds
        self._server: _ProxyServer | None = None
        self._thread: threading.Thread | None = None
        self._bound_port: int | None = None

    @property
    def base_url(self) -> str:
        """Return the proxy origin to hand to ``OPENAI_BASE_URL`` (no path)."""
        if self._bound_port is None:
            raise TrialError("header proxy has not been started")
        return f"http://127.0.0.1:{self._bound_port}"

    def start(self) -> str:
        """Start serving in a daemon thread and return :attr:`base_url`."""
        server = _ProxyServer(("127.0.0.1", 0), self)
        self._server = server
        self._bound_port = int(server.server_address[1])
        thread = threading.Thread(
            target=server.serve_forever,
            name="host-trial-header-proxy",
            daemon=True,
        )
        thread.start()
        self._thread = thread
        return self.base_url

    def stop(self) -> None:
        """Shut the proxy down and join its thread."""
        server = self._server
        if server is not None:
            server.shutdown()
            server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._server = None
        self._thread = None
        self._bound_port = None

    def _upstream_connection(self) -> http.client.HTTPConnection:
        if self._scheme == "https":
            return http.client.HTTPSConnection(
                self._host, self._port, timeout=self._timeout_seconds
            )
        return http.client.HTTPConnection(self._host, self._port, timeout=self._timeout_seconds)

    def _forward_headers(self, incoming: Message[str, str], body_length: int) -> dict[str, str]:
        headers: dict[str, str] = {}
        for name, value in incoming.items():
            if name.lower() in PROXY_CONTROLLED_HEADERS:
                continue
            headers[name] = value
        default_port = 443 if self._scheme == "https" else 80
        headers["Host"] = self._host if self._port == default_port else f"{self._host}:{self._port}"
        if body_length:
            headers["Content-Length"] = str(body_length)
        headers[OPENCODE_SESSION_HEADER] = self._session
        headers["User-Agent"] = CLIENT_USER_AGENT
        for name, value in self._extra_headers.items():
            headers[name] = value
        return headers

    def handle(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        """Forward one request from *handler* to the upstream backend."""
        length = int(handler.headers.get("Content-Length") or 0)
        body = handler.rfile.read(length) if length else b""
        connection = self._upstream_connection()
        try:
            connection.request(
                handler.command,
                join_upstream_path(self._base_path, handler.path),
                body=body,
                headers=self._forward_headers(handler.headers, len(body)),
            )
            response = connection.getresponse()
            payload = response.read()
            handler.send_response(response.status)
            for name, value in response.getheaders():
                lowered = name.lower()
                if lowered in HOP_BY_HOP_HEADERS or lowered in {
                    "content-length",
                    "content-encoding",
                }:
                    continue
                handler.send_header(name, value)
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            if handler.command != "HEAD":
                handler.wfile.write(payload)
        except (OSError, http.client.HTTPException) as exc:
            handler.send_error(502, f"header proxy upstream error: {exc}")
        finally:
            connection.close()


class _ProxyServer(http.server.ThreadingHTTPServer):
    """Threaded HTTP server that carries its owning proxy instance."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], proxy: HeaderInjectingProxy) -> None:
        super().__init__(address, _ProxyHandler)
        self.proxy = proxy


class _ProxyHandler(http.server.BaseHTTPRequestHandler):
    """Minimal request handler delegating every method to the proxy."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        """Silence per-request logging."""

    def do_GET(self) -> None:
        cast(_ProxyServer, self.server).proxy.handle(self)

    def do_POST(self) -> None:
        cast(_ProxyServer, self.server).proxy.handle(self)


def build_eval_args(
    *,
    tasks_file: Path,
    snapshots_dir: Path,
    submission_dir: Path,
    results_dir: Path,
    models_yaml: Path,
    task_ids: Sequence[str] = TASK_IDS,
) -> list[str]:
    """Build the ``swegemma eval`` argv for the resolved trial task ids."""
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


def build_swegemma_install_args(wheelhouse_dir: Path) -> list[str]:
    """Build the ``uv tool install`` argv for the harness CLI from the wheelhouse.

    Only ``swegemma`` ships a console entry point (``swegemma = swegemma.cli:main``);
    ``adk-submission`` and ``adk-eval-core`` are its transitive dependencies. None of
    the three are on PyPI, so ``--find-links`` points uv at the local wheelhouse;
    their public dependencies resolve normally (cached or from PyPI).
    """
    return [
        "uv",
        "tool",
        "install",
        "--find-links",
        str(wheelhouse_dir),
        SWEGEMMA_TOOL,
    ]


def uv_tool_bin_dir() -> Path | None:
    """Return the directory uv installs tool executables into, or ``None``."""
    result = subprocess.run(
        ["uv", "tool", "dir", "--bin"],
        capture_output=True,
        text=True,
        check=False,
    )
    location = result.stdout.strip()
    if result.returncode != 0 or not location:
        return None
    return Path(location)


def _prepend_path(directory: Path) -> None:
    """Prepend *directory* to ``PATH`` for the rest of this process."""
    current = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{directory}{os.pathsep}{current}" if current else str(directory)


def install_swegemma(paths: TrialPaths) -> bool:
    """Phase 4: install the harness CLI from the local wheelhouse when absent.

    Skips when ``swegemma`` is already on ``PATH``. uv installs the CLI as an
    isolated tool; its bin directory is prepended to ``PATH`` so phase 7 can
    invoke the ``swegemma`` executable directly.
    """
    phase("Phase 4/8 (runbook sec. 4.1): install swegemma from the local wheelhouse")
    if shutil.which(SWEGEMMA_TOOL) is not None:
        note(f"{SWEGEMMA_TOOL} already on PATH; skipping install")
        return False

    if not any(paths.wheelhouse_dir.glob("swegemma-*.whl")):
        raise TrialError(
            f"no swegemma wheel under {paths.wheelhouse_dir}; fetch the wheelhouse "
            "first (runbook sec. 4.1)."
        )

    run_cmd(
        build_swegemma_install_args(paths.wheelhouse_dir),
        what="uv tool install swegemma",
    )

    bin_dir = uv_tool_bin_dir()
    if bin_dir is not None:
        _prepend_path(bin_dir)

    found = shutil.which(SWEGEMMA_TOOL)
    if found is None:
        raise TrialError(
            "swegemma was installed but is not on PATH; add the uv tool bin directory "
            "(uv tool dir --bin) to PATH and re-run (runbook sec. 4.1)."
        )
    note(f"installed {SWEGEMMA_TOOL}: {found}")
    return True


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


def _looks_rate_limited(detail: str) -> bool:
    """Return whether *detail* (CLI stderr/stdout) signals a transient rate limit.

    Only rate-limit phrases are matched; a bare ``429`` is not, so a payload that
    merely contains that number (a byte size, an offset) is not misread as
    transient and does not burn the whole backoff budget.
    """
    lowered = detail.lower()
    return any(marker in lowered for marker in RATE_LIMIT_MARKERS)


def run_cmd_with_retry(
    cmd: Sequence[str],
    *,
    what: str | None = None,
    attempts: int = WHEEL_DOWNLOAD_ATTEMPTS,
    base_delay: float = WHEEL_DOWNLOAD_BACKOFF_SECONDS,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Echo and run *cmd*, retrying a rate-limited (``429``) failure with backoff.

    Output is captured so a rate-limit marker can be detected. Both streams are
    inspected, so a marker on stdout is found even when stderr carries unrelated
    output. Stderr is forwarded on success too, so download progress that
    ``kaggle`` writes there is not swallowed. A non-zero exit that is not a rate
    limit, or that survives *attempts* tries, raises :class:`TrialError` with the
    captured output. *sleep* is injectable for tests.
    """
    label = what or cmd[0]
    sleeper = sleep or time.sleep
    print("  $ " + " ".join(cmd))
    attempt = 0
    while True:
        attempt += 1
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            return
        detail = "\n".join(part.strip() for part in (result.stderr, result.stdout) if part.strip())
        if attempt >= attempts or not _looks_rate_limited(detail):
            raise TrialError(f"{label} failed (exit {result.returncode}): {detail}")
        delay = base_delay * (2 ** (attempt - 1))
        note(f"{label} rate limited (attempt {attempt}/{attempts}); retrying in {delay:.1f}s")
        sleeper(delay)


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
    phase("Phase 1/8 (runbook sec. 1): prerequisites")
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
    phase("Phase 2/8 (runbook sec. 2): repository and harness branch")
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


def _fetch_competition_file(
    remote_file: str, dest_dir: Path, *, sleep: Callable[[float], None] | None = None
) -> None:
    """Download one competition file unless a complete copy is already present.

    A zero-byte file counts as an aborted download (for example a ``429`` that
    killed the CLI mid-write): it is removed and fetched again instead of being
    skipped forever. Rate-limited failures are retried with backoff. *sleep* is
    forwarded to the retry loop and is injectable for tests.
    """
    name = Path(remote_file).name
    dest = dest_dir / name
    if dest.is_file() and dest.stat().st_size > 0:
        note(f"skip (exists): {dest}")
        return
    if dest.exists():
        note(f"refetch (empty/incomplete): {dest}")
        dest.unlink()
    dest_dir.mkdir(parents=True, exist_ok=True)
    run_cmd_with_retry(
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
        sleep=sleep,
    )


def snapshot_remote_files(task_ids: Sequence[str]) -> list[str]:
    """Return the ``snapshots/<id>.tgz`` remote paths derived from *task_ids*."""
    return [f"snapshots/{task_id}.tgz" for task_id in task_ids]


def fetch_data(paths: TrialPaths, task_ids: Sequence[str] | None = None) -> None:
    """Phase 3: fetch the wheelhouse, small fixtures, and the resolved snapshots.

    Snapshots are derived from the resolved task ids (``HARNESS_TRIAL_TASKS`` or
    the default ``TASK_IDS``): one ``snapshots/<id>.tgz`` per id, never the whole
    ``snapshots/`` tree. When *task_ids* is omitted it is resolved from the
    process environment, falling back to the default task set.
    """
    phase("Phase 3/8 (runbook sec. 4): fetch wheelhouse + small fixtures (NO bulk)")

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
    _fetch_competition_file("docker/imp.py", paths.docker_context)
    _fetch_competition_file("docker/telnetlib.py", paths.docker_context)

    resolved_tasks = (
        tuple(task_ids) if task_ids is not None else resolve_trial_tasks({}, os.environ)
    )
    snapshots = snapshot_remote_files(resolved_tasks)
    note(f"fetching {len(snapshots)} trial snapshot(s) (never the whole snapshots/ tree)")
    for remote_file in snapshots:
        _fetch_competition_file(remote_file, paths.snapshots_dir)


def _list_competition_wheels() -> list[str]:
    """List remote competition files under ``wheels/``, paginating until exhausted.

    ``kaggle competitions files`` prints a ``Next Page Token = <token>`` line
    while further pages exist, so the listing is walked with ``--page-token``
    until no token comes back. Table rows whose first field starts with
    ``wheels/`` are the trial dependency artifacts.
    """
    remote: list[str] = []
    page_token: str | None = None
    while True:
        cmd = [
            "kaggle",
            "competitions",
            "files",
            "-c",
            COMPETITION,
            "--page-size",
            str(LIST_PAGE_SIZE),
        ]
        if page_token is not None:
            cmd += ["--page-token", page_token]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise TrialError(
                f"kaggle competitions files failed (exit {result.returncode}): {detail}"
            )
        page_token = None
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith(PAGE_TOKEN_MARKER):
                page_token = stripped[len(PAGE_TOKEN_MARKER) :].strip() or None
            elif stripped.startswith(WHEELS_DIRNAME):
                remote.append(stripped.split(maxsplit=1)[0])
        if page_token is None:
            break
    return remote


def _staged_wheel_names(wheels_dir: Path) -> set[str]:
    """Return valid local wheel basenames, ignoring zero-byte partials."""
    return {
        wheel.name
        for wheel in Path(wheels_dir).glob("*.whl")
        if wheel.is_file() and wheel.stat().st_size > 0
    }


def clear_swegemma_site_packages_cache(temp_root: Path | None = None) -> list[str]:
    """Remove swegemma's cached unpacked-wheel tars so they rebuild from the current set.

    swegemma keys the cache only by name (``swegemma_sp_cache_<N>``), not by the
    wheel set, so a tar built while the wheel directory was partial (an
    interrupted/429 staging run) is reused by every later run and silently
    produces containers without the repo's dependencies. Returns the removed
    directory names for logging; a missing cache or a removal error is ignored.
    """
    root = Path(temp_root) if temp_root is not None else Path(tempfile.gettempdir())
    removed: list[str] = []
    if not root.is_dir():
        return removed
    for cache_dir in sorted(root.glob(f"{SWEGEMMA_SP_CACHE_PREFIX}*")):
        if not cache_dir.is_dir():
            continue
        shutil.rmtree(cache_dir, ignore_errors=True)
        if not cache_dir.exists():
            removed.append(cache_dir.name)
    return removed


def ensure_trial_wheels(
    paths: TrialPaths,
    *,
    sleep: Callable[[float], None] | None = None,
    allow_partial: bool = False,
) -> None:
    """Phase 3b/8: stage the competition's ``wheels/`` deps into ``data/raw/wheels/``.

    ``swegemma`` resolves the task dependency wheels from the directory next to
    ``tasks.jsonl`` (``resolve_wheels_dir`` in ``swegemma.harness.container_setup``
    checks ``<tasks_path parent>/wheels``), so staging them here is what lets the
    air-gapped sandbox bootstrap install the task test dependencies.

    The local set is inspected first. The remote ``wheels/`` listing is then
    consulted and only the missing wheels are downloaded, so a run interrupted by
    a ``429`` (leaving a partial set on disk) resumes on the next run instead of
    being skipped forever by a ``any(*.whl)`` early return. When the listing is
    unavailable (offline host or rate-limited listing) but some wheels are
    already staged, the phase **fails fast** unless *allow_partial* is set: an
    unverified/partial set can poison the swegemma site-packages cache and score
    0/2 with a container missing its dependencies. A listing that succeeds but is
    empty is still an error: it means the competition has no ``wheels/`` to
    stage. *sleep* is injectable for tests.
    """
    phase("Phase 3b/8: ensure trial dependency wheels (data/raw/wheels/)")
    sleeper = sleep or time.sleep

    staged = _staged_wheel_names(paths.wheels_dir)
    try:
        remote_wheels = _list_competition_wheels()
    except TrialError as exc:
        if staged and allow_partial:
            note(
                f"warning: could not list remote wheels ({exc}); continuing with "
                f"{len(staged)} staged wheel(s) in {paths.wheels_dir} "
                "(--allow-partial-wheels)"
            )
            return
        if staged:
            raise TrialError(
                f"cannot verify the local wheel set ({len(staged)} staged in "
                f"{paths.wheels_dir}): the competition wheel listing failed ({exc}). "
                "Re-run when the listing is reachable, or pass --allow-partial-wheels "
                "to proceed with the unverified set (an incomplete set can poison the "
                "swegemma site-packages cache)."
            ) from exc
        raise

    if not remote_wheels:
        raise TrialError(
            f"no files under '{WHEELS_DIRNAME}' in competition {COMPETITION}; "
            "cannot stage the trial dependency wheels."
        )

    missing = [remote for remote in remote_wheels if Path(remote).name not in staged]
    if not missing:
        note(f"skip (complete): {len(remote_wheels)} wheel(s) already staged in {paths.wheels_dir}")
        return

    note(
        f"staging {len(missing)}/{len(remote_wheels)} wheel(s) into {paths.wheels_dir} "
        f"({len(remote_wheels) - len(missing)} already present)"
    )
    paths.wheels_dir.mkdir(parents=True, exist_ok=True)
    for index, remote_file in enumerate(missing):
        _fetch_competition_file(remote_file, paths.wheels_dir, sleep=sleep)
        if index < len(missing) - 1:
            sleeper(WHEEL_DOWNLOAD_PAUSE_SECONDS)


def build_image(paths: TrialPaths) -> None:
    """Phase 5: build the sandbox image from the fetched Dockerfile."""
    phase("Phase 5/8 (runbook sec. 3): build sandbox image")
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


def resolve_backend_env(env_file: Path) -> dict[str, str]:
    """Phase 6: load ``.env``/environment, abort if the key is empty, mask output."""
    phase("Phase 6/8 (runbook sec. 5): backend key (environment only)")

    file_values = load_env_file(env_file)
    resolved = resolve_trial_env(file_values, os.environ)
    if not resolved.get(OPENAI_API_KEY):
        raise TrialError(
            f"{OPENAI_API_KEY} is empty. Put it in {env_file} (git-ignored) or export it "
            "before running; never pass it as an argument (runbook sec. 5)."
        )
    resolved[SESSION_ENV] = resolve_trial_session(file_values, os.environ)
    task_ids = resolve_trial_tasks(file_values, os.environ)
    resolved[TASKS_ENV] = ",".join(task_ids)

    for name, value in resolved.items():
        if value:
            os.environ[name] = value

    note(
        f"{OPENAI_API_KEY} is set (value not shown: {mask_secret(resolved[OPENAI_API_KEY])}); "
        f"base URL: {resolved[OPENAI_BASE_URL]}"
    )
    note(f"{HARNESS_MODEL}: {resolved[HARNESS_MODEL]} (trial-only; not part of the submission)")
    note(f"trial session: {resolved[SESSION_ENV]} -> {OPENCODE_SESSION_HEADER} header")
    note(f"trial tasks: {', '.join(task_ids)}")
    return resolved


def run_eval(paths: TrialPaths, env: Mapping[str, str]) -> None:
    """Phase 7: generate the models.yaml, start the header proxy, run ``swegemma eval``."""
    phase("Phase 7/8 (runbook sec. 6): swegemma eval (trial tasks, competition budgets)")
    note(f"task wheels: {paths.wheels_dir} (auto-discovered via the tasks directory)")
    removed = clear_swegemma_site_packages_cache()
    if removed:
        note(f"cleared stale swegemma site-packages cache: {', '.join(removed)}")
    else:
        note("no stale swegemma site-packages cache to clear")
    if shutil.which(SWEGEMMA_TOOL) is None:
        raise TrialError(
            "swegemma is not on PATH; phase 4 installs it from the local wheelhouse "
            "(runbook sec. 4.1)."
        )

    aliases = collect_declared_models(paths.submission_dir)
    if not aliases:
        raise TrialError(
            f"no `model:` declaration found under {paths.submission_dir}; cannot map the "
            "trial backend model to the submission aliases (check agent.yaml / "
            "sub_agents/*.yaml)."
        )
    harness_model = env[HARNESS_MODEL]
    write_models_yaml(paths.models_yaml, aliases, harness_model)
    note(f"effective trial model: {provider_qualified_model(harness_model)} for aliases {aliases}")

    upstream = env[OPENAI_BASE_URL]
    session = env.get(SESSION_ENV, DEFAULT_TRIAL_SESSION)
    proxy = HeaderInjectingProxy(upstream, session)
    proxy.start()
    note(f"header proxy: {proxy.base_url} -> {upstream} (+{OPENCODE_SESSION_HEADER})")
    previous_base_url = os.environ.get(OPENAI_BASE_URL)
    os.environ[OPENAI_BASE_URL] = proxy.base_url

    paths.results_dir.mkdir(parents=True, exist_ok=True)
    task_ids = parse_trial_tasks(env.get(TASKS_ENV, ""))
    try:
        run_cmd(
            build_eval_args(
                tasks_file=paths.tasks_file,
                snapshots_dir=paths.snapshots_dir,
                submission_dir=paths.submission_dir,
                results_dir=paths.results_dir,
                models_yaml=paths.models_yaml,
                task_ids=task_ids,
            ),
            what="swegemma eval",
        )
    finally:
        proxy.stop()
        if previous_base_url is not None:
            os.environ[OPENAI_BASE_URL] = previous_base_url


def archive_and_report(paths: TrialPaths, backend: str) -> Path:
    """Phase 8: archive into ``runs/<UTC>/`` and print the report."""
    phase("Phase 8/8 (runbook sec. 7-9): archive + report under runs/")
    note("JUnit note (runbook sec. 8): the harness writes JUnit XML only inside Container B")
    note("at /tmp/_swegemma_junit_<id>.xml and warm-pooled containers are wiped. If a")
    note("container is still alive, copy it out before teardown:")
    note("  docker ps")
    note(f"  docker cp <container>:/tmp/_swegemma_junit_fastapi_15661.xml {paths.junit_dir}/")
    note("If it is already gone, pass/fail is still readable from task_results.jsonl.")

    paths.junit_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(
        build_archive_args(paths.results_dir, paths.junit_dir, paths.tasks_file, backend),
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


def run(
    repo_root: Path,
    results_name: str,
    env_file: Path,
    *,
    allow_partial_wheels: bool = False,
) -> Path:
    """Execute all eight trial phases and return the archived run directory."""
    paths = paths_for(repo_root, results_name)
    check_prerequisites()
    ensure_harness_branch(Path(repo_root))
    task_ids = resolve_trial_tasks(load_env_file(env_file), os.environ)
    fetch_data(paths, task_ids)
    ensure_trial_wheels(paths, allow_partial=allow_partial_wheels)
    install_swegemma(paths)
    build_image(paths)
    env = resolve_backend_env(env_file)
    run_eval(paths, env)
    return archive_and_report(paths, env[HARNESS_MODEL])


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
    parser.add_argument(
        "--allow-partial-wheels",
        action="store_true",
        help=(
            "proceed when the competition wheel listing is unavailable even though "
            "the local set is unverified (may poison the swegemma site-packages cache)"
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = REPO_ROOT
    env_file = args.env_file if args.env_file is not None else repo_root / ".env"
    try:
        run_dir = run(
            repo_root,
            args.results_name,
            env_file,
            allow_partial_wheels=args.allow_partial_wheels,
        )
    except TrialError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nTrial complete. Archived under {run_dir} (report: {run_dir / 'report.json'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
