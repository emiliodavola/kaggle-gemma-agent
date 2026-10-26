#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Launch the local OpenAI-compatible model server for the host trial.

Separate helper the host-trial runner calls before the backend probe. It builds
the exact command for the selected local backend and, unless ``--dry-run`` is
set, runs it and waits for ``/v1/models`` to answer.

The model servers (LM Studio, llama.cpp) usually live on the **Windows host**
while the runner runs inside **WSL**. WSL2 interoperability lets WSL execute
Windows binaries (``lms.exe`` / ``llama-server.exe`` / ``powershell.exe``), and
mirrored networking makes the Windows ``127.0.0.1`` reachable from WSL, so the
same script works from either side. Nothing here ships in the submission.

Backends
--------
``lmstudio``
    ``lms server start`` then ``lms load <key> --context-length <ctx> --gpu max
    -y --identifier <served-id>``.
``llamacpp``
    ``llama-server -m <gguf> -c <ctx> -ngl <layers> -fa on --jinja --alias
    <served-id> --host <host> --port <port>`` launched detached.

Environment (all optional; CLI flags win)
-----------------------------------------
Values are read from ``<repo root>/.env`` first and then the process environment
(the process env wins), so running this script directly behaves like the runner.

``HARNESS_TRIAL_LAUNCH``     ``none`` (default) | ``lmstudio`` | ``llamacpp`` | ``auto``
``HARNESS_TRIAL_CONTEXT``    context tokens (default 26214)
``HARNESS_TRIAL_MODEL_KEY``  LM Studio model key to load (default = ``HARNESS_MODEL``)
``HARNESS_TRIAL_MODEL_PATH`` llama.cpp ``.gguf`` path (required for llamacpp)
``HARNESS_TRIAL_GPU``        LM Studio ``--gpu`` value (default ``max``)
``HARNESS_TRIAL_GPU_LAYERS`` llama.cpp ``-ngl`` value (default ``all``)
``HARNESS_TRIAL_SERVER_HOST`` default ``127.0.0.1``
``HARNESS_TRIAL_SERVER_PORT`` default ``1234`` (lmstudio) / ``8080`` (llamacpp)
``HARNESS_TRIAL_LMS_BIN``    LM Studio CLI name or full path (default ``lms``)
``HARNESS_TRIAL_LLAMACPP_BIN`` llama.cpp server name or full path (default ``llama-server``)
``HARNESS_MODEL``            served id the runner expects (default gemma alias)

A bare binary name is resolved with ``shutil.which`` and, when that misses, against
the standard LM Studio install location, because WSL fixes ``PATH`` when a shell
starts: a shell opened before LM Studio added itself stays blind to ``lms.exe``.
A binary that cannot be resolved raises a :class:`LauncherError` naming the env var
above, never a raw ``FileNotFoundError``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

DEFAULT_CONTEXT = 26214
DEFAULT_MODEL_ID = "gemma-4-31b-it-qat"
DEFAULT_LLAMACPP_PORT = 8080
DEFAULT_LMSTUDIO_PORT = 1234
WSL_WINDOWS_USERS_ROOT = Path("/mnt/c/Users")
BACKEND_PORTS = {"lmstudio": DEFAULT_LMSTUDIO_PORT, "llamacpp": DEFAULT_LLAMACPP_PORT}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


class LauncherError(Exception):
    """Raised when the model server cannot be launched or reached."""


def is_wsl(proc_version: str | None = None) -> bool:
    """Return whether this process runs under WSL (Windows interop needed)."""
    if proc_version is None:
        try:
            proc_version = Path("/proc/version").read_text(encoding="utf-8")
        except OSError:
            return False
    lowered = proc_version.lower()
    return "microsoft" in lowered or "wsl" in lowered


def windows_executable(name: str, *, on_wsl: bool) -> str:
    """Return *name* with a ``.exe`` suffix when running under WSL."""
    if on_wsl and not name.lower().endswith(".exe"):
        return f"{name}.exe"
    return name


def fallback_binary_paths(
    binary_name: str,
    *,
    on_wsl: bool,
    wsl_users_root: Path | None = None,
    home: Path | None = None,
) -> list[Path]:
    """Return known install locations for *binary_name*, empty when unknown.

    LM Studio ships ``lms.exe`` under ``%USERPROFILE%\\.lmstudio\\bin`` and adds
    that directory to the Windows user ``PATH``. WSL derives ``PATH`` when a shell
    starts, so a shell opened before that install keeps the stale value and cannot
    resolve ``lms.exe`` by name; its install location is tried instead.
    """
    if Path(binary_name).name.lower() != "lms.exe":
        return []
    if on_wsl:
        root = Path(wsl_users_root) if wsl_users_root is not None else WSL_WINDOWS_USERS_ROOT
        return sorted(root.glob("*/.lmstudio/bin/lms.exe"))
    home_dir = Path(home) if home is not None else Path.home()
    return [home_dir / ".lmstudio" / "bin" / "lms.exe"]


def _is_explicit_path(candidate: str) -> bool:
    """Return whether *candidate* names a path instead of a bare command name."""
    return "/" in candidate or "\\" in candidate or Path(candidate).is_absolute()


def _missing_binary_message(
    candidate: str, env_var: str, *, tried: Sequence[Path], on_wsl: bool
) -> str:
    """Build the actionable error raised when the binary cannot be resolved."""
    message = f"cannot run {candidate!r}: not found on PATH"
    if tried:
        message += " or at " + ", ".join(str(path) for path in tried)
    if on_wsl:
        message += (
            "; WSL builds PATH when the shell starts, so a shell opened before the "
            "install does not see it"
        )
    return f"{message}. Set {env_var} to the full path and retry."


def resolve_binary(
    name: str,
    *,
    on_wsl: bool,
    env_var: str,
    which: Callable[[str], str | None] | None = None,
    fallbacks: Sequence[Path] | None = None,
    required: bool = True,
) -> str:
    """Return a runnable path for *name*, or raise :class:`LauncherError`.

    Resolution order: an explicit path is validated as given, otherwise the name
    goes through ``PATH`` with the ``.exe`` suffix WSL interop needs, otherwise
    the standard install locations are tried. Every failure names *env_var* so the
    operator has an escape hatch instead of a bare :class:`FileNotFoundError`.

    ``required=False`` keeps a ``--dry-run`` preview usable before the server is
    installed: it returns *name* unchanged instead of raising.
    """
    candidate = windows_executable(name, on_wsl=on_wsl)
    if _is_explicit_path(candidate):
        path = Path(candidate)
        if path.is_file():
            return str(path)
        if not required:
            return candidate
        raise LauncherError(
            f"{candidate!r} does not exist. Fix {env_var}, or unset it to search PATH."
        )

    finder = which or shutil.which
    if finder(candidate):
        # Keep the bare name: PATH already resolves it, so the printed commands and
        # the argv stay exactly what they were before this resolution step existed.
        return candidate

    locations = (
        list(fallbacks)
        if fallbacks is not None
        else fallback_binary_paths(candidate, on_wsl=on_wsl)
    )
    existing = [path for path in locations if path.is_file()]
    if len(existing) == 1:
        return str(existing[0])
    if len(existing) > 1:
        listed = ", ".join(str(path) for path in existing)
        raise LauncherError(
            f"ambiguous {candidate}: found {len(existing)} candidates ({listed}). "
            f"Set {env_var} to the one to use."
        )
    if not required:
        return candidate
    raise LauncherError(_missing_binary_message(candidate, env_var, tried=locations, on_wsl=on_wsl))


def parse_env_file(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from a ``.env`` body, mirroring the runner.

    Blank lines and ``#`` comments are skipped, an optional ``export`` prefix is
    accepted, a single matching quote pair is stripped, and an active key defined
    twice raises :class:`LauncherError` naming the key and both line numbers, so a
    colliding value is never silently ignored.
    """
    values: dict[str, str] = {}
    first_lines: dict[str, int] = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        if key in values:
            raise LauncherError(
                f"duplicate key {key!r} in .env (lines {first_lines[key]} and {lineno}); "
                "keep only one active definition"
            )
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
        first_lines[key] = lineno
    return values


def load_env_file(path: Path) -> dict[str, str]:
    """Return the parsed ``.env`` at *path*, or ``{}`` when it does not exist."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_env_file(text)


def merged_env(env_file_values: Mapping[str, str], environ: Mapping[str, str]) -> dict[str, str]:
    """Merge ``.env`` under the process environment (the process env wins)."""
    return {**env_file_values, **environ}


def resolve_backend(cli_value: str | None, env: Mapping[str, str]) -> str:
    """Resolve the launch backend from the CLI flag, then the environment."""
    candidate = (cli_value or env.get("HARNESS_TRIAL_LAUNCH") or "").strip().lower()
    if candidate in {"", "none"}:
        backend = (env.get("HARNESS_TRIAL_BACKEND") or "").strip().lower()
        candidate = backend if backend in BACKEND_PORTS else ""
    elif candidate == "auto":
        backend = (env.get("HARNESS_TRIAL_BACKEND") or "").strip().lower()
        candidate = backend if backend in BACKEND_PORTS else ""
    if candidate not in BACKEND_PORTS:
        raise LauncherError(
            "no launchable backend. Set HARNESS_TRIAL_LAUNCH=lmstudio|llamacpp "
            "(or HARNESS_TRIAL_BACKEND to one of those)."
        )
    return candidate


def resolve_context(cli_value: int | None, env: Mapping[str, str]) -> int:
    """Resolve the context size, defaulting to a VRAM-friendly value."""
    if cli_value is not None:
        return cli_value
    raw = env.get("HARNESS_TRIAL_CONTEXT", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError as exc:
            raise LauncherError(f"HARNESS_TRIAL_CONTEXT is not an integer: {raw!r}") from exc
    return DEFAULT_CONTEXT


def resolve_port(backend: str, env: Mapping[str, str]) -> int:
    """Resolve the server port, defaulting per backend."""
    raw = env.get("HARNESS_TRIAL_SERVER_PORT", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError as exc:
            raise LauncherError(f"HARNESS_TRIAL_SERVER_PORT is not an integer: {raw!r}") from exc
    return BACKEND_PORTS[backend]


def build_llamacpp_command(
    *,
    binary: str,
    model_path: str,
    context: int,
    gpu_layers: str,
    host: str,
    port: int,
    served_id: str,
    flash_attn: bool = True,
    kv_cache_type: str = "q8_0",
) -> list[str]:
    """Build the ``llama-server`` argv with the verified flags.

    ``--jinja`` is required for tool calling (the agent depends on it); ``-fa``
    and a quantized KV cache buy headroom for a larger context on a 24 GB card.
    """
    command = [
        binary,
        "-m",
        model_path,
        "-c",
        str(context),
        "-ngl",
        gpu_layers,
        "--jinja",
        "--alias",
        served_id,
        "--host",
        host,
        "--port",
        str(port),
    ]
    if flash_attn:
        command += ["-fa", "on"]
    if kv_cache_type:
        command += ["-ctk", kv_cache_type, "-ctv", kv_cache_type]
    return command


def build_lms_server_command(*, binary: str) -> list[str]:
    """Build ``lms server start``."""
    return [binary, "server", "start"]


def build_lms_load_command(
    *,
    binary: str,
    model_key: str,
    context: int,
    gpu: str,
    served_id: str,
) -> list[str]:
    """Build ``lms load`` with context, full GPU offload and a stable id."""
    return [
        binary,
        "load",
        model_key,
        "--context-length",
        str(context),
        "--gpu",
        gpu,
        "-y",
        "--identifier",
        served_id,
    ]


def build_lms_stop_commands(*, binary: str) -> list[list[str]]:
    """Build the LM Studio teardown commands (unload then stop the server)."""
    return [[binary, "unload", "--all"], [binary, "server", "stop"]]


def _endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/models"


def wait_for_endpoint(
    base_url: str,
    *,
    timeout_seconds: float = 120.0,
    interval_seconds: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Poll ``GET /v1/models`` until it answers, or raise after the timeout."""
    deadline = time.monotonic() + timeout_seconds
    last_error = "no response"
    while True:
        try:
            with urllib.request.urlopen(_endpoint(base_url), timeout=5.0) as response:
                data = json.loads(response.read().decode("utf-8", "replace"))
                return data if isinstance(data, dict) else {}
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            raise LauncherError(
                f"model server did not answer {_endpoint(base_url)} within "
                f"{timeout_seconds:.0f}s ({last_error})"
            )
        sleep(interval_seconds)


def launch_detached(command: Sequence[str], *, on_wsl: bool) -> None:
    """Start *command* detached so it outlives this script.

    On WSL the target is a Windows binary, so PowerShell ``Start-Process`` is
    used to detach it from the WSL session. On Windows/Linux a plain
    ``subprocess.Popen`` starts it in the background.
    """
    if on_wsl:
        quoted = ",".join(f"'{arg}'" for arg in command)
        ps = f"Start-Process -FilePath '{command[0]}' -ArgumentList {quoted}"
        try:
            subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise LauncherError(f"cannot launch {command[0]!r}: {exc}") from exc
    else:
        try:
            subprocess.Popen(list(command))
        except OSError as exc:
            raise LauncherError(f"cannot launch {command[0]!r}: {exc}") from exc


def _print_command(command: Sequence[str]) -> None:
    print("  $ " + " ".join(command))


def _run(command: Sequence[str]) -> None:
    _print_command(command)
    try:
        result = subprocess.run(list(command), check=False)
    except OSError as exc:
        raise LauncherError(f"cannot execute {command[0]!r}: {exc}") from exc
    if result.returncode != 0:
        raise LauncherError(f"command failed (exit {result.returncode}): {command[0]}")


def start(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    """Launch the resolved backend and wait for its endpoint."""
    on_wsl = is_wsl()
    backend = resolve_backend(args.backend, env)
    context = resolve_context(args.context, env)
    host = env.get("HARNESS_TRIAL_SERVER_HOST", "127.0.0.1")
    port = resolve_port(backend, env)
    served_id = env.get("HARNESS_MODEL", DEFAULT_MODEL_ID)
    base_url = f"http://{host}:{port}/v1"

    print(f"launch backend={backend} context={context} served_id={served_id} ({host}:{port})")
    if backend == "lmstudio":
        binary = resolve_binary(
            env.get("HARNESS_TRIAL_LMS_BIN", "lms"),
            on_wsl=on_wsl,
            env_var="HARNESS_TRIAL_LMS_BIN",
            required=not args.dry_run,
        )
        model_key = env.get("HARNESS_TRIAL_MODEL_KEY", served_id)
        commands = [
            build_lms_server_command(binary=binary),
            build_lms_load_command(
                binary=binary,
                model_key=model_key,
                context=context,
                gpu=env.get("HARNESS_TRIAL_GPU", "max"),
                served_id=served_id,
            ),
        ]
    else:
        model_path = env.get("HARNESS_TRIAL_MODEL_PATH", "").strip()
        if not model_path:
            raise LauncherError("HARNESS_TRIAL_MODEL_PATH is required for llamacpp")
        binary = resolve_binary(
            env.get("HARNESS_TRIAL_LLAMACPP_BIN", "llama-server"),
            on_wsl=on_wsl,
            env_var="HARNESS_TRIAL_LLAMACPP_BIN",
            required=not args.dry_run,
        )
        commands = [
            build_llamacpp_command(
                binary=binary,
                model_path=model_path,
                context=context,
                gpu_layers=env.get("HARNESS_TRIAL_GPU_LAYERS", "all"),
                host=host,
                port=port,
                served_id=served_id,
            )
        ]

    if args.dry_run:
        for command in commands:
            _print_command(command)
        print("dry-run: not executing")
        return 0
    if backend == "llamacpp":
        launch_detached(commands[0], on_wsl=on_wsl)
    else:
        for command in commands:
            _run(command)
    wait_for_endpoint(base_url, timeout_seconds=args.timeout)
    print(f"ready: {base_url}")
    return 0


def stop(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    """Tear down the resolved backend."""
    on_wsl = is_wsl()
    try:
        backend = resolve_backend(args.backend, env)
    except LauncherError:
        backend = "lmstudio"
    if backend == "lmstudio":
        binary = resolve_binary(
            env.get("HARNESS_TRIAL_LMS_BIN", "lms"),
            on_wsl=on_wsl,
            env_var="HARNESS_TRIAL_LMS_BIN",
        )
        for command in build_lms_stop_commands(binary=binary):
            _run(command)
        return 0
    print("llamacpp: no managed teardown; close the llama-server process on the host")
    return 0


def status(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    """Report whether the resolved backend endpoint answers."""
    backend = resolve_backend(args.backend, env)
    host = env.get("HARNESS_TRIAL_SERVER_HOST", "127.0.0.1")
    port = resolve_port(backend, env)
    base_url = f"http://{host}:{port}/v1"
    try:
        payload = wait_for_endpoint(base_url, timeout_seconds=args.timeout)
    except LauncherError as exc:
        print(f"not ready: {exc}")
        return 1
    data = payload.get("data")
    entries = data if isinstance(data, list) else []
    models = [item.get("id") for item in entries if isinstance(item, dict)]
    print(f"ready: {base_url} models={models}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the local model launcher."""
    parser = argparse.ArgumentParser(
        prog="serve_local_model.py",
        description="Launch the local OpenAI-compatible model server for the host trial.",
    )
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument(
        "--backend",
        choices=("lmstudio", "llamacpp", "auto"),
        default=None,
        help="override HARNESS_TRIAL_LAUNCH",
    )
    parser.add_argument("--context", type=int, default=None, help="context tokens")
    parser.add_argument("--timeout", type=float, default=120.0, help="readiness timeout (s)")
    parser.add_argument("--dry-run", action="store_true", help="print commands without running")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help=".env to read (default: <repo root>/.env); the process env wins",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    env = merged_env(load_env_file(args.env_file), os.environ)
    try:
        if args.action == "start":
            return start(args, env)
        if args.action == "stop":
            return stop(args, env)
        return status(args, env)
    except LauncherError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
