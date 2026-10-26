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


def test_resolve_binary_uses_which_and_keeps_the_bare_name() -> None:
    seen: list[str] = []

    def fake_which(name: str) -> str | None:
        seen.append(name)
        return "/mnt/c/Users/elaze/.lmstudio/bin/lms.exe"

    resolved = launcher.resolve_binary(
        "lms",
        on_wsl=True,
        env_var="HARNESS_TRIAL_LMS_BIN",
        which=fake_which,
        fallbacks=[],
    )
    assert resolved == "lms.exe"
    assert seen == ["lms.exe"]


def test_resolve_binary_accepts_explicit_existing_path(tmp_path: Path) -> None:
    binary = tmp_path / "lms.exe"
    binary.write_text("", encoding="utf-8")
    resolved = launcher.resolve_binary(
        str(binary).removesuffix(".exe"),
        on_wsl=True,
        env_var="HARNESS_TRIAL_LMS_BIN",
        which=lambda name: None,
        fallbacks=[],
    )
    assert resolved == str(binary)


def test_resolve_binary_falls_back_to_known_install_location(tmp_path: Path) -> None:
    binary = tmp_path / "lms.exe"
    binary.write_text("", encoding="utf-8")
    resolved = launcher.resolve_binary(
        "lms",
        on_wsl=True,
        env_var="HARNESS_TRIAL_LMS_BIN",
        which=lambda name: None,
        fallbacks=[binary],
    )
    assert resolved == str(binary)


def test_resolve_binary_raises_actionable_error_when_missing() -> None:
    with pytest.raises(launcher.LauncherError) as excinfo:
        launcher.resolve_binary(
            "lms",
            on_wsl=True,
            env_var="HARNESS_TRIAL_LMS_BIN",
            which=lambda name: None,
            fallbacks=[],
        )
    message = str(excinfo.value)
    assert "lms.exe" in message
    assert "HARNESS_TRIAL_LMS_BIN" in message


def test_resolve_binary_rejects_ambiguous_fallbacks(tmp_path: Path) -> None:
    first = tmp_path / "a" / "lms.exe"
    second = tmp_path / "b" / "lms.exe"
    for path in (first, second):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    with pytest.raises(launcher.LauncherError, match="ambiguous"):
        launcher.resolve_binary(
            "lms",
            on_wsl=True,
            env_var="HARNESS_TRIAL_LMS_BIN",
            which=lambda name: None,
            fallbacks=[first, second],
        )


def test_fallback_binary_paths_finds_lmstudio_under_wsl_users_root(tmp_path: Path) -> None:
    binary = tmp_path / "elaze" / ".lmstudio" / "bin" / "lms.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    found = launcher.fallback_binary_paths("lms.exe", on_wsl=True, wsl_users_root=tmp_path)
    assert found == [binary]


def test_fallback_binary_paths_uses_home_off_wsl(tmp_path: Path) -> None:
    expected = tmp_path / ".lmstudio" / "bin" / "lms.exe"
    found = launcher.fallback_binary_paths("lms.exe", on_wsl=False, home=tmp_path)
    assert found == [expected]


def test_fallback_binary_paths_ignores_unknown_binaries() -> None:
    assert launcher.fallback_binary_paths("llama-server.exe", on_wsl=True) == []


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


def test_run_converts_missing_binary_into_launcher_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_missing(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError(2, "No such file or directory", "lms.exe")

    monkeypatch.setattr(launcher.subprocess, "run", raise_missing)
    with pytest.raises(launcher.LauncherError, match=r"lms\.exe"):
        launcher._run(["lms.exe", "server", "start"])


def test_launch_detached_converts_failure_into_launcher_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_called(*args: object, **kwargs: object) -> object:
        raise launcher.subprocess.CalledProcessError(1, "powershell.exe")

    monkeypatch.setattr(launcher.subprocess, "run", raise_called)
    with pytest.raises(launcher.LauncherError, match=r"powershell\.exe"):
        launcher.launch_detached(["powershell.exe", "-Command", "Start-Process"], on_wsl=True)


def test_start_runs_each_lms_command_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], check: bool = False) -> object:
        calls.append(list(command))
        return launcher.subprocess.CompletedProcess(list(command), 0)

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(launcher, "resolve_binary", lambda *args, **kwargs: "lms.exe")
    monkeypatch.setattr(launcher, "wait_for_endpoint", lambda *args, **kwargs: {})
    args = launcher.argparse.Namespace(
        action="start", backend="lmstudio", context=26214, timeout=1.0, dry_run=False
    )
    env = {"HARNESS_MODEL": "gemma-4-31b-it-qat"}

    assert launcher.start(args, env) == 0
    out = capsys.readouterr().out
    assert out.count("$ lms.exe server start") == 1
    assert out.count("$ lms.exe load") == 1
    assert calls == [
        ["lms.exe", "server", "start"],
        [
            "lms.exe",
            "load",
            "gemma-4-31b-it-qat",
            "--context-length",
            "26214",
            "--gpu",
            "max",
            "-y",
            "--identifier",
            "gemma-4-31b-it-qat",
        ],
    ]


def test_resolve_binary_required_false_returns_the_bare_name() -> None:
    resolved = launcher.resolve_binary(
        "lms",
        on_wsl=True,
        env_var="HARNESS_TRIAL_LMS_BIN",
        which=lambda name: None,
        fallbacks=[],
        required=False,
    )
    assert resolved == "lms.exe"


def test_start_dry_run_tolerates_missing_binary(capsys: pytest.CaptureFixture[str]) -> None:
    args = launcher.argparse.Namespace(
        action="start", backend="lmstudio", context=26214, timeout=1.0, dry_run=True
    )
    env = {
        "HARNESS_TRIAL_LMS_BIN": "not-installed-yet",
        "HARNESS_MODEL": "gemma-4-31b-it-qat",
    }

    assert launcher.start(args, env) == 0
    out = capsys.readouterr().out
    assert "not-installed-yet".removesuffix(".exe") in out
    assert "dry-run: not executing" in out


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


def test_parse_env_file_handles_comments_quotes_and_export() -> None:
    text = (
        "# comment\n"
        "\n"
        "OPENAI_API_KEY=plain\n"
        "export HARNESS_TRIAL_LAUNCH=lmstudio\n"
        "HARNESS_MODEL='quoted model'\n"
        'HARNESS_TRIAL_CONTEXT="26214"\n'
        "NO_EQUALS_HERE\n"
    )
    values = launcher.parse_env_file(text)
    assert values["OPENAI_API_KEY"] == "plain"
    assert values["HARNESS_TRIAL_LAUNCH"] == "lmstudio"
    assert values["HARNESS_MODEL"] == "quoted model"
    assert values["HARNESS_TRIAL_CONTEXT"] == "26214"
    assert "NO_EQUALS_HERE" not in values


def test_parse_env_file_rejects_duplicate_keys() -> None:
    with pytest.raises(launcher.LauncherError, match="duplicate key"):
        launcher.parse_env_file("A=1\nB=2\nA=3\n")


def test_load_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert launcher.load_env_file(tmp_path / "nope.env") == {}


def test_merged_env_process_wins() -> None:
    merged = launcher.merged_env({"HARNESS_MODEL": "from-file"}, {"HARNESS_MODEL": "from-env"})
    assert merged["HARNESS_MODEL"] == "from-env"


def test_env_file_drives_backend_and_context(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "HARNESS_TRIAL_LAUNCH=lmstudio\n"
        "HARNESS_TRIAL_CONTEXT=16384\n"
        "HARNESS_MODEL=gemma-4-31b-it-qat\n",
        encoding="utf-8",
    )
    env = launcher.merged_env(launcher.load_env_file(env_file), {})
    assert launcher.resolve_backend(None, env) == "lmstudio"
    assert launcher.resolve_context(None, env) == 16384
