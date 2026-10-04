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
``HARNESS_TRIAL_LAUNCH``     ``none`` (default) | ``lmstudio`` | ``llamacpp`` | ``auto``
``HARNESS_TRIAL_CONTEXT``    context tokens (default 26214)
``HARNESS_TRIAL_MODEL_KEY``  LM Studio model key to load (default = ``HARNESS_MODEL``)
``HARNESS_TRIAL_MODEL_PATH`` llama.cpp ``.gguf`` path (required for llamacpp)
``HARNESS_TRIAL_GPU``        LM Studio ``--gpu`` value (default ``max``)
``HARNESS_TRIAL_GPU_LAYERS`` llama.cpp ``-ngl`` value (default ``all``)
``HARNESS_TRIAL_SERVER_HOST`` default ``127.0.0.1``
``HARNESS_TRIAL_SERVER_PORT`` default ``1234`` (lmstudio) / ``8080`` (llamacpp)
``HARNESS_TRIAL_LMS_BIN``    LM Studio CLI name (default ``lms``)
``HARNESS_TRIAL_LLAMACPP_BIN`` llama.cpp server name (default ``llama-server``)
``HARNESS_MODEL``            served id the runner expects (default gemma alias)
"""

from __future__ import annotations

import argparse
import json
import os
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
BACKEND_PORTS = {"lmstudio": DEFAULT_LMSTUDIO_PORT, "llamacpp": DEFAULT_LLAMACPP_PORT}


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
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], check=True)
    else:
        subprocess.Popen(list(command))


def _print_command(command: Sequence[str]) -> None:
    print("  $ " + " ".join(command))


def _run(command: Sequence[str]) -> None:
    _print_command(command)
    result = subprocess.run(list(command), check=False)
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
        binary = windows_executable(env.get("HARNESS_TRIAL_LMS_BIN", "lms"), on_wsl=on_wsl)
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
        binary = windows_executable(
            env.get("HARNESS_TRIAL_LLAMACPP_BIN", "llama-server"), on_wsl=on_wsl
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

    for command in commands:
        _print_command(command)
    if args.dry_run:
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
        binary = windows_executable(env.get("HARNESS_TRIAL_LMS_BIN", "lms"), on_wsl=on_wsl)
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
    args = parser.parse_args(list(argv) if argv is not None else None)

    env = os.environ
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
