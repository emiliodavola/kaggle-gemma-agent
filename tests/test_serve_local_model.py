"""Focused tests for the local model launcher (``serve_local_model.py``)."""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "host-trial" / "serve_local_model.py"
)
_spec = importlib.util.spec_from_file_location("serve_local_model", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
launcher = importlib.util.module_from_spec(_spec)
sys.modules["serve_local_model"] = launcher
_spec.loader.exec_module(launcher)


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_is_wsl_detects_microsoft_kernel() -> None:
    assert launcher.is_wsl("Linux version 6.18-microsoft-standard-WSL2") is True
    assert launcher.is_wsl("Linux version 6.8.0-31-generic") is False


def test_windows_executable_appends_exe_only_on_wsl() -> None:
    assert launcher.windows_executable("lms", on_wsl=True) == "lms.exe"
    assert launcher.windows_executable("lms.exe", on_wsl=True) == "lms.exe"
    assert launcher.windows_executable("lms", on_wsl=False) == "lms"


def test_resolve_backend_from_explicit_env() -> None:
    assert launcher.resolve_backend(None, {"HARNESS_TRIAL_LAUNCH": "lmstudio"}) == "lmstudio"


def test_resolve_backend_auto_uses_backend_selector() -> None:
    env = {"HARNESS_TRIAL_LAUNCH": "auto", "HARNESS_TRIAL_BACKEND": "llamacpp"}
    assert launcher.resolve_backend(None, env) == "llamacpp"


def test_resolve_backend_none_falls_back_to_backend_selector() -> None:
    env = {"HARNESS_TRIAL_LAUNCH": "none", "HARNESS_TRIAL_BACKEND": "lmstudio"}
    assert launcher.resolve_backend(None, env) == "lmstudio"


def test_resolve_backend_raises_for_cloud_backend() -> None:
    with pytest.raises(launcher.LauncherError, match="no launchable backend"):
        launcher.resolve_backend(None, {"HARNESS_TRIAL_BACKEND": "opencode"})


def test_resolve_context_default_and_env() -> None:
    assert launcher.resolve_context(None, {}) == launcher.DEFAULT_CONTEXT == 26214
    assert launcher.resolve_context(None, {"HARNESS_TRIAL_CONTEXT": "16384"}) == 16384
    assert launcher.resolve_context(8192, {"HARNESS_TRIAL_CONTEXT": "16384"}) == 8192


def test_resolve_context_rejects_non_integer() -> None:
    with pytest.raises(launcher.LauncherError, match="not an integer"):
        launcher.resolve_context(None, {"HARNESS_TRIAL_CONTEXT": "abc"})


def test_resolve_port_defaults_per_backend() -> None:
    assert launcher.resolve_port("lmstudio", {}) == 1234
    assert launcher.resolve_port("llamacpp", {}) == 8080
    assert launcher.resolve_port("llamacpp", {"HARNESS_TRIAL_SERVER_PORT": "9000"}) == 9000


def test_build_llamacpp_command_has_required_flags() -> None:
    command = launcher.build_llamacpp_command(
        binary="llama-server",
        model_path="/models/gemma.gguf",
        context=26214,
        gpu_layers="all",
        host="127.0.0.1",
        port=8080,
        served_id="gemma-4-31b-it-qat",
    )
    assert command[0] == "llama-server"
    assert command[command.index("-m") + 1] == "/models/gemma.gguf"
    assert command[command.index("-c") + 1] == "26214"
    assert command[command.index("-ngl") + 1] == "all"
    assert "--jinja" in command
    assert command[command.index("--alias") + 1] == "gemma-4-31b-it-qat"
    assert command[command.index("--port") + 1] == "8080"
    assert "-fa" in command
    assert command[command.index("-ctk") + 1] == "q8_0"


def test_build_lms_commands() -> None:
    assert launcher.build_lms_server_command(binary="lms") == ["lms", "server", "start"]
    load = launcher.build_lms_load_command(
        binary="lms",
        model_key="gemma-key",
        context=26214,
        gpu="max",
        served_id="gemma-4-31b-it-qat",
    )
    assert load[:3] == ["lms", "load", "gemma-key"]
    assert load[load.index("--context-length") + 1] == "26214"
    assert load[load.index("--gpu") + 1] == "max"
    assert load[load.index("--identifier") + 1] == "gemma-4-31b-it-qat"
    assert "-y" in load
    assert launcher.build_lms_stop_commands(binary="lms") == [
        ["lms", "unload", "--all"],
        ["lms", "server", "stop"],
    ]


def test_wait_for_endpoint_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload: dict[str, Any] = {"data": [{"id": "gemma-4-31b-it-qat"}]}
    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(json.dumps(payload).encode("utf-8")),
    )
    assert launcher.wait_for_endpoint("http://127.0.0.1:8080/v1") == payload


def test_wait_for_endpoint_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_url(*args: object, **kwargs: object) -> _FakeResponse:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(launcher.urllib.request, "urlopen", raise_url)
    with pytest.raises(launcher.LauncherError, match="did not answer"):
        launcher.wait_for_endpoint("http://127.0.0.1:8080/v1", timeout_seconds=0.0)


def test_start_dry_run_prints_llamacpp_command(capsys: pytest.CaptureFixture[str]) -> None:
    args = launcher.argparse.Namespace(
        action="start", backend="llamacpp", context=26214, timeout=1.0, dry_run=True
    )
    env = {
        "HARNESS_TRIAL_MODEL_PATH": "/models/gemma.gguf",
        "HARNESS_MODEL": "gemma-4-31b-it-qat",
    }
    assert launcher.start(args, env) == 0
    out = capsys.readouterr().out
    assert "llama-server" in out
    assert "--jinja" in out
    assert "dry-run: not executing" in out
