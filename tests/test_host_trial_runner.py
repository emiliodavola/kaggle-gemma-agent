"""Focused tests for the cross-platform host-trial runner (``.env`` + argv)."""

from __future__ import annotations

import email.message
import http.server
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, ClassVar

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "host-trial" / "run_host_trial.py"
_spec = importlib.util.spec_from_file_location("run_host_trial", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules["run_host_trial"] = runner
_spec.loader.exec_module(runner)


def test_parse_env_file_handles_comments_quotes_and_export() -> None:
    text = (
        "# comment\n"
        "\n"
        "OPENAI_API_KEY=plain-value\n"
        "export OPENAI_BASE_URL=https://example.test/v1\n"
        "HARNESS_MODEL='quoted model'\n"
        'DOUBLE="quoted value"\n'
        "NO_EQUALS_HERE\n"
        "EMPTY=\n"
    )

    assert runner.parse_env_file(text) == {
        "OPENAI_API_KEY": "plain-value",
        "OPENAI_BASE_URL": "https://example.test/v1",
        "HARNESS_MODEL": "quoted model",
        "DOUBLE": "quoted value",
        "EMPTY": "",
    }


def test_parse_env_file_reads_beyond_line_twenty() -> None:
    text = "\n".join(f"KEY{i:02d}=value{i}" for i in range(25))

    parsed = runner.parse_env_file(text)

    assert len(parsed) == 25
    assert parsed["KEY00"] == "value0"
    assert parsed["KEY24"] == "value24"


def test_parse_env_file_rejects_a_duplicate_active_key() -> None:
    text = "OPENAI_API_KEY=first\nHARNESS_MODEL=a\nOPENAI_API_KEY=second\n"

    with pytest.raises(
        runner.TrialError,
        match=r"duplicate key 'OPENAI_API_KEY' in .env \(lines 1 and 3\)",
    ):
        runner.parse_env_file(text)


def test_load_env_file_rejects_a_duplicate_beyond_the_old_cap(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=active\n" + "\n" * 25 + "OPENAI_API_KEY=late-preset\n",
        encoding="utf-8",
    )

    with pytest.raises(runner.TrialError, match="duplicate key 'OPENAI_API_KEY'"):
        runner.load_env_file(env_file)


def test_load_env_file_absent_and_present(tmp_path: Path) -> None:
    assert runner.load_env_file(tmp_path / "missing.env") == {}

    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")
    assert runner.load_env_file(env_file) == {"OPENAI_API_KEY": "from-file"}


def test_resolve_trial_env_prefers_environment_and_fills_defaults() -> None:
    from_file = {"OPENAI_API_KEY": "file-key", "HARNESS_MODEL": "file-model"}
    environ = {"OPENAI_API_KEY": "env-key"}

    resolved = runner.resolve_trial_env(from_file, environ)

    assert resolved["OPENAI_API_KEY"] == "env-key"
    assert resolved["HARNESS_MODEL"] == "file-model"
    assert resolved[runner.BACKEND_ENV] == runner.DEFAULT_BACKEND
    assert resolved["OPENAI_BASE_URL"] == runner.BACKEND_PRESETS[runner.DEFAULT_BACKEND]


def test_resolve_trial_env_applies_defaults_when_empty() -> None:
    resolved = runner.resolve_trial_env({}, {}, harness_model="m")

    assert resolved[runner.OPENAI_BASE_URL] == runner.BACKEND_PRESETS[runner.DEFAULT_BACKEND]
    assert resolved[runner.HARNESS_MODEL] == "m"
    assert runner.OPENAI_API_KEY not in resolved


def test_resolve_trial_env_default_backend_is_opencode() -> None:
    resolved = runner.resolve_trial_env({}, {})

    assert resolved[runner.BACKEND_ENV] == "opencode"
    assert resolved[runner.OPENAI_BASE_URL] == "https://opencode.ai/zen/go/v1"


def test_resolve_trial_env_selects_the_lmstudio_preset() -> None:
    resolved = runner.resolve_trial_env({"HARNESS_TRIAL_BACKEND": "lmstudio"}, {})

    assert resolved[runner.BACKEND_ENV] == "lmstudio"
    assert resolved[runner.OPENAI_BASE_URL] == "http://127.0.0.1:1234/v1"


def test_resolve_trial_env_normalizes_the_backend_selector() -> None:
    resolved = runner.resolve_trial_env({"HARNESS_TRIAL_BACKEND": " LmStudio "}, {})

    assert resolved[runner.BACKEND_ENV] == "lmstudio"


def test_resolve_trial_env_explicit_base_url_wins_over_the_selector() -> None:
    resolved = runner.resolve_trial_env(
        {
            "HARNESS_TRIAL_BACKEND": "lmstudio",
            "OPENAI_BASE_URL": "https://explicit.test/v1",
        },
        {},
    )

    assert resolved[runner.OPENAI_BASE_URL] == "https://explicit.test/v1"


def test_resolve_trial_env_rejects_an_unknown_backend() -> None:
    with pytest.raises(
        runner.TrialError,
        match=r"unknown HARNESS_TRIAL_BACKEND='nope'; valid values:",
    ):
        runner.resolve_trial_env({"HARNESS_TRIAL_BACKEND": "nope"}, {})


def test_mask_secret_never_returns_the_secret() -> None:
    assert runner.mask_secret("") == "<unset>"
    masked = runner.mask_secret("super-secret-key")
    assert "super-secret-key" not in masked
    assert masked == "***"


def test_resolve_backend_env_aborts_when_key_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(runner.OPENAI_API_KEY, raising=False)

    with pytest.raises(runner.TrialError):
        runner.resolve_backend_env(tmp_path / "absent.env")


def test_resolve_backend_env_masks_key_and_sets_default_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(runner.OPENAI_API_KEY, "super-secret-key")
    monkeypatch.delenv(runner.OPENAI_BASE_URL, raising=False)
    monkeypatch.delenv(runner.HARNESS_MODEL, raising=False)
    monkeypatch.delenv(runner.BACKEND_ENV, raising=False)
    monkeypatch.delenv(runner.SESSION_ENV, raising=False)

    resolved = runner.resolve_backend_env(tmp_path / "absent.env")

    assert resolved[runner.BACKEND_ENV] == runner.DEFAULT_BACKEND
    assert resolved[runner.OPENAI_BASE_URL] == runner.BACKEND_PRESETS[runner.DEFAULT_BACKEND]
    assert resolved[runner.SESSION_ENV] == runner.DEFAULT_TRIAL_SESSION
    assert resolved[runner.HARNESS_MODEL] == runner.DEFAULT_HARNESS_MODEL
    assert os.environ[runner.OPENAI_API_KEY] == "super-secret-key"


def test_resolve_backend_env_notes_the_selected_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(runner.OPENAI_API_KEY, "super-secret-key")
    monkeypatch.setenv(runner.BACKEND_ENV, "lmstudio")
    monkeypatch.delenv(runner.OPENAI_BASE_URL, raising=False)
    monkeypatch.delenv(runner.HARNESS_MODEL, raising=False)

    resolved = runner.resolve_backend_env(tmp_path / "absent.env")

    assert resolved[runner.OPENAI_BASE_URL] == runner.BACKEND_PRESETS["lmstudio"]
    out = capsys.readouterr().out
    assert "trial backend: lmstudio -> http://127.0.0.1:1234/v1" in out


def test_provider_qualified_model_adds_prefix_once() -> None:
    assert runner.provider_qualified_model("muse-spark-1.3-contributor") == (
        "openai/muse-spark-1.3-contributor"
    )
    assert runner.provider_qualified_model("openai/already") == "openai/already"
    assert runner.provider_qualified_model("hosted_vllm/x") == "hosted_vllm/x"


def test_collect_declared_models_reads_agent_and_subagents(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    (submission / "sub_agents").mkdir(parents=True)
    (submission / "configs").mkdir()
    (submission / "agent.yaml").write_text(
        "name: a\nmodel: gemma-4-31b-it-qat-w4a16-ct\n", encoding="utf-8"
    )
    (submission / "sub_agents" / "code_analyzer.yaml").write_text(
        "name: b\nmodel: gemma-4-31b-it-qat-w4a16-ct\n", encoding="utf-8"
    )
    (submission / "sub_agents" / "other.yaml").write_text(
        "name: c\nmodel: 'other-model'  # inline comment\n", encoding="utf-8"
    )
    (submission / "configs" / "sampling.yaml").write_text("temperature: 0.2\n", encoding="utf-8")

    assert runner.collect_declared_models(submission) == [
        "gemma-4-31b-it-qat-w4a16-ct",
        "other-model",
    ]


def test_collect_declared_models_empty_when_none(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "agent.yaml").write_text("name: a\n", encoding="utf-8")

    assert runner.collect_declared_models(submission) == []


def test_render_models_yaml_maps_every_alias_to_harness_model() -> None:
    text = runner.render_models_yaml(
        ["gemma-4-31b-it-qat-w4a16-ct", "other"], "muse-spark-1.3-contributor"
    )

    assert "models:" in text
    assert "  gemma-4-31b-it-qat-w4a16-ct:" in text
    assert "  other:" in text
    assert "    path: openai/muse-spark-1.3-contributor" in text
    assert text.count("path: openai/muse-spark-1.3-contributor") == 2
    assert "api_base" not in text
    assert "api_key" not in text


def test_write_models_yaml_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "results" / "run_01" / runner.GENERATED_MODELS_FILENAME

    written = runner.write_models_yaml(target, ["alias"], "deepseek-v4.1-flash")

    assert written == target
    assert target.read_text(encoding="utf-8") == runner.render_models_yaml(
        ["alias"], "deepseek-v4.1-flash"
    )


def test_resolve_trial_session_prefers_env_then_file_then_default() -> None:
    assert runner.resolve_trial_session({}, {}) == runner.DEFAULT_TRIAL_SESSION
    assert runner.resolve_trial_session({"HARNESS_TRIAL_SESSION": "file"}, {}) == "file"
    assert (
        runner.resolve_trial_session(
            {"HARNESS_TRIAL_SESSION": "file"}, {"HARNESS_TRIAL_SESSION": "env"}
        )
        == "env"
    )


def test_resolve_trial_tasks_defaults_without_env() -> None:
    assert runner.resolve_trial_tasks({}, {}) == runner.TASK_IDS


def test_resolve_trial_tasks_env_overrides_file() -> None:
    assert runner.resolve_trial_tasks(
        {"HARNESS_TRIAL_TASKS": "file_task"}, {"HARNESS_TRIAL_TASKS": "env_task"}
    ) == ("env_task",)


def test_resolve_trial_tasks_reads_env_file() -> None:
    assert runner.resolve_trial_tasks({"HARNESS_TRIAL_TASKS": "a,b"}, {}) == ("a", "b")


def test_resolve_trial_tasks_supports_one_and_many_ids() -> None:
    assert runner.resolve_trial_tasks({}, {"HARNESS_TRIAL_TASKS": "fastapi_15661"}) == (
        "fastapi_15661",
    )
    assert runner.resolve_trial_tasks(
        {}, {"HARNESS_TRIAL_TASKS": "fastapi_15661,fastapi_15588,extra"}
    ) == ("fastapi_15661", "fastapi_15588", "extra")


def test_resolve_trial_tasks_trims_spaces_and_drops_blanks() -> None:
    assert runner.resolve_trial_tasks(
        {}, {"HARNESS_TRIAL_TASKS": "  fastapi_15661 , , fastapi_15588  "}
    ) == ("fastapi_15661", "fastapi_15588")


def test_resolve_trial_tasks_blank_falls_back_to_default() -> None:
    assert runner.resolve_trial_tasks({}, {"HARNESS_TRIAL_TASKS": "   "}) == runner.TASK_IDS
    assert runner.resolve_trial_tasks({}, {"HARNESS_TRIAL_TASKS": ""}) == runner.TASK_IDS


def test_resolve_backend_env_records_resolved_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(runner.OPENAI_API_KEY, "super-secret-key")
    monkeypatch.setenv(runner.TASKS_ENV, " fastapi_15661 , fastapi_15588 ")

    resolved = runner.resolve_backend_env(tmp_path / "absent.env")

    assert resolved[runner.TASKS_ENV] == "fastapi_15661,fastapi_15588"


def test_join_upstream_path_keeps_base_path_and_collapses_v1() -> None:
    base = "/zen/go/v1"

    assert runner.join_upstream_path(base, "/chat/completions") == ("/zen/go/v1/chat/completions")
    assert runner.join_upstream_path(base, "/v1/chat/completions") == (
        "/zen/go/v1/chat/completions"
    )
    assert runner.join_upstream_path(base, "/zen/go/v1/chat/completions") == (
        "/zen/go/v1/chat/completions"
    )
    assert runner.join_upstream_path(base, "/chat/completions?x=1") == (
        "/zen/go/v1/chat/completions?x=1"
    )
    assert runner.join_upstream_path("", "/chat/completions") == "/chat/completions"
    assert runner.join_upstream_path("/v1", "/v1/chat/completions") == ("/v1/chat/completions")


def test_paths_for_points_models_yaml_at_the_generated_file(tmp_path: Path) -> None:
    paths = runner.paths_for(tmp_path, "run_02")

    assert paths.models_yaml == (tmp_path / "results" / "run_02" / runner.GENERATED_MODELS_FILENAME)
    assert paths.wheels_dir == tmp_path / "data" / "raw" / "wheels"


def test_list_competition_wheels_paginates_and_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages: dict[str | None, str] = {
        None: (
            "Next Page Token = tok-1\n"
            "name              size  creationDate\n"
            "wheels/a.whl      10    2026-09-27\n"
            "snapshots/x.tgz   20    2026-09-27\n"
        ),
        "tok-1": "name  size  creationDate\nwheels/b.whl  30  2026-09-27\n",
    }
    seen_tokens: list[str | None] = []

    def fake_run(
        cmd: list[str],
        *,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        token = cmd[cmd.index("--page-token") + 1] if "--page-token" in cmd else None
        seen_tokens.append(token)
        return subprocess.CompletedProcess(cmd, 0, stdout=pages[token], stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner._list_competition_wheels() == ["wheels/a.whl", "wheels/b.whl"]
    assert seen_tokens == [None, "tok-1"]


def test_list_competition_wheels_raises_on_cli_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        cmd: list[str],
        *,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    with pytest.raises(runner.TrialError):
        runner._list_competition_wheels()


def _record_fetches(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Path]]:
    fetched: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        runner,
        "_fetch_competition_file",
        lambda remote_file, dest_dir, *, sleep=None: fetched.append((remote_file, dest_dir)),
    )
    return fetched


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps: list[float] = []
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    return sleeps


def test_ensure_trial_wheels_resumes_missing_wheels_instead_of_skipping_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    (paths.wheels_dir / "a.whl").write_text("wheel-bytes", encoding="utf-8")
    listed: list[bool] = []

    def fake_list() -> list[str]:
        listed.append(True)
        return ["wheels/a.whl", "wheels/b.whl"]

    monkeypatch.setattr(runner, "_list_competition_wheels", fake_list)
    fetched = _record_fetches(monkeypatch)
    _no_sleep(monkeypatch)

    runner.ensure_trial_wheels(paths)

    assert listed == [True]
    assert fetched == [("wheels/b.whl", paths.wheels_dir)]


def test_ensure_trial_wheels_refetches_a_zero_byte_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    (paths.wheels_dir / "a.whl").write_text("wheel-bytes", encoding="utf-8")
    (paths.wheels_dir / "b.whl").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        runner, "_list_competition_wheels", lambda: ["wheels/a.whl", "wheels/b.whl"]
    )
    fetched = _record_fetches(monkeypatch)
    _no_sleep(monkeypatch)

    runner.ensure_trial_wheels(paths)

    assert fetched == [("wheels/b.whl", paths.wheels_dir)]


def test_ensure_trial_wheels_downloads_into_the_wheels_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    monkeypatch.setattr(
        runner, "_list_competition_wheels", lambda: ["wheels/a.whl", "wheels/b.whl"]
    )
    fetched = _record_fetches(monkeypatch)
    sleeps: list[float] = []

    runner.ensure_trial_wheels(paths, sleep=sleeps.append)

    assert fetched == [
        ("wheels/a.whl", paths.wheels_dir),
        ("wheels/b.whl", paths.wheels_dir),
    ]
    assert sleeps == [runner.WHEEL_DOWNLOAD_PAUSE_SECONDS]


def test_ensure_trial_wheels_fails_fast_when_listing_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    (paths.wheels_dir / "a.whl").write_text("wheel-bytes", encoding="utf-8")

    def failing_list() -> list[str]:
        raise runner.TrialError("offline")

    monkeypatch.setattr(runner, "_list_competition_wheels", failing_list)
    monkeypatch.setattr(
        runner, "_fetch_competition_file", lambda *args, **kwargs: pytest.fail("no fetch")
    )

    with pytest.raises(runner.TrialError, match="cannot verify the local wheel set"):
        runner.ensure_trial_wheels(paths)


def test_ensure_trial_wheels_allows_partial_on_offline_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    (paths.wheels_dir / "a.whl").write_text("wheel-bytes", encoding="utf-8")

    def failing_list() -> list[str]:
        raise runner.TrialError("offline")

    monkeypatch.setattr(runner, "_list_competition_wheels", failing_list)
    monkeypatch.setattr(
        runner, "_fetch_competition_file", lambda *args, **kwargs: pytest.fail("no fetch")
    )

    runner.ensure_trial_wheels(paths, allow_partial=True)


def test_clear_swegemma_site_packages_cache_removes_matching_dirs(tmp_path: Path) -> None:
    cache_root = tmp_path / "temp"
    cache_root.mkdir()
    stale = cache_root / f"{runner.SWEGEMMA_SP_CACHE_PREFIX}v8"
    (stale / "sp_base").mkdir(parents=True)
    (stale / "sp_base" / "starlette.py").write_text("x", encoding="utf-8")
    keep = cache_root / "other_cache"
    keep.mkdir()

    removed = runner.clear_swegemma_site_packages_cache(cache_root)

    assert removed == [stale.name]
    assert not stale.exists()
    assert keep.exists()


def test_clear_swegemma_site_packages_cache_missing_root_is_noop(tmp_path: Path) -> None:
    assert runner.clear_swegemma_site_packages_cache(tmp_path / "nope") == []


def test_ensure_trial_wheels_propagates_listing_failure_without_local_wheels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")

    def failing_list() -> list[str]:
        raise runner.TrialError("offline")

    monkeypatch.setattr(runner, "_list_competition_wheels", failing_list)

    with pytest.raises(runner.TrialError):
        runner.ensure_trial_wheels(paths)


def test_fetch_competition_file_forwards_sleep_to_the_retry_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[object] = []
    monkeypatch.setattr(
        runner,
        "run_cmd_with_retry",
        lambda cmd, *, what=None, sleep=None: received.append(sleep),
    )

    def sentinel(_delay: float) -> None:
        raise AssertionError("sleep should only be forwarded, not called")

    runner._fetch_competition_file("wheels/a.whl", tmp_path, sleep=sentinel)

    assert received == [sentinel]


def test_ensure_trial_wheels_skips_only_when_every_wheel_is_staged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    (paths.wheels_dir / "a.whl").write_text("wheel-bytes", encoding="utf-8")
    (paths.wheels_dir / "b.whl").write_text("wheel-bytes", encoding="utf-8")
    monkeypatch.setattr(
        runner, "_list_competition_wheels", lambda: ["wheels/a.whl", "wheels/b.whl"]
    )
    monkeypatch.setattr(
        runner, "_fetch_competition_file", lambda remote_file, dest_dir: pytest.fail("no fetch")
    )

    runner.ensure_trial_wheels(paths)


def test_ensure_trial_wheels_errors_when_remote_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    monkeypatch.setattr(runner, "_list_competition_wheels", lambda: [])

    with pytest.raises(runner.TrialError):
        runner.ensure_trial_wheels(paths)


def test_fetch_competition_file_skips_a_complete_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.whl").write_text("wheel-bytes", encoding="utf-8")
    monkeypatch.setattr(
        runner, "run_cmd_with_retry", lambda cmd, *, what=None, sleep=None: pytest.fail("no fetch")
    )

    runner._fetch_competition_file("wheels/a.whl", tmp_path)


def test_fetch_competition_file_refetches_a_zero_byte_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.whl").write_text("", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runner, "run_cmd_with_retry", lambda cmd, *, what=None, sleep=None: calls.append(list(cmd))
    )

    runner._fetch_competition_file("wheels/a.whl", tmp_path)

    assert calls and calls[0][calls[0].index("-f") + 1] == "wheels/a.whl"
    assert not (tmp_path / "a.whl").exists()


def _completed(returncode: int, *, stdout: str = "", stderr: str = "") -> Any:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def test_run_cmd_with_retry_retries_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            _completed(1, stderr="429 Too Many Requests"),
            _completed(0, stdout="downloaded\n"),
        ]
    )
    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kwargs: next(responses))
    sleeps = _no_sleep(monkeypatch)

    runner.run_cmd_with_retry(["kaggle", "download", "x"], attempts=3)

    assert sleeps == [runner.WHEEL_DOWNLOAD_BACKOFF_SECONDS]


def test_run_cmd_with_retry_does_not_retry_a_non_rate_limit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.subprocess, "run", lambda cmd, **kwargs: _completed(1, stderr="404 Not Found")
    )
    sleeps = _no_sleep(monkeypatch)

    with pytest.raises(runner.TrialError):
        runner.run_cmd_with_retry(["kaggle", "download", "x"], attempts=3)

    assert sleeps == []


def test_run_cmd_with_retry_exhausts_attempts_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.subprocess, "run", lambda cmd, **kwargs: _completed(1, stderr="429 rate limit")
    )
    sleeps = _no_sleep(monkeypatch)

    with pytest.raises(runner.TrialError):
        runner.run_cmd_with_retry(["kaggle", "download", "x"], attempts=3)

    assert sleeps == [2.0, 4.0]


def test_run_cmd_with_retry_finds_a_marker_on_stdout_alongside_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            _completed(1, stdout="429 Too Many Requests\n", stderr="warning: retrying\n"),
            _completed(0),
        ]
    )
    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kwargs: next(responses))
    sleeps = _no_sleep(monkeypatch)

    runner.run_cmd_with_retry(["kaggle", "download", "x"], attempts=3)

    assert sleeps == [runner.WHEEL_DOWNLOAD_BACKOFF_SECONDS]


def test_looks_rate_limited_ignores_a_bare_429_number() -> None:
    assert runner._looks_rate_limited("downloaded 429 KB") is False
    assert runner._looks_rate_limited("offset 429") is False
    assert runner._looks_rate_limited("429 Client Error: Too Many Requests") is True


def test_run_cmd_with_retry_forwards_stderr_on_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda cmd, **kwargs: _completed(0, stdout="done\n", stderr="progress 1/3\n"),
    )
    _no_sleep(monkeypatch)

    runner.run_cmd_with_retry(["kaggle", "download", "x"])

    captured = capsys.readouterr()
    assert "done" in captured.out
    assert "progress 1/3" in captured.err


class _StubUpstream(http.server.BaseHTTPRequestHandler):
    headers_seen: ClassVar[dict[str, str]] = {}
    body_seen: ClassVar[bytes] = b""
    path_seen: ClassVar[str] = ""

    def log_message(self, format: str, *args: object) -> None:
        """Silence per-request logging."""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        type(self).body_seen = self.rfile.read(length)
        type(self).headers_seen = {k.lower(): v for k, v in self.headers.items()}
        type(self).path_seen = self.path
        payload = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def test_header_injecting_proxy_forwards_and_stamps_session() -> None:
    _StubUpstream.headers_seen = {}
    _StubUpstream.body_seen = b""
    _StubUpstream.path_seen = ""
    upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _StubUpstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    port = upstream.server_address[1]
    proxy = runner.HeaderInjectingProxy(f"http://127.0.0.1:{port}/zen/go/v1", "sess-abc")
    proxy.start()

    try:
        request = urllib.request.Request(
            proxy.base_url + "/chat/completions",
            data=b'{"model": "x"}',
            headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 200
            assert response.read() == b'{"ok": true}'
    finally:
        proxy.stop()
        upstream.shutdown()
        upstream.server_close()
        upstream_thread.join(timeout=5.0)

    assert _StubUpstream.headers_seen["x-opencode-session"] == "sess-abc"
    assert _StubUpstream.headers_seen["authorization"] == "Bearer test-key"
    assert "host" in _StubUpstream.headers_seen
    assert _StubUpstream.body_seen == b'{"model": "x"}'
    assert _StubUpstream.path_seen == "/zen/go/v1/chat/completions"


def test_header_injecting_proxy_rejects_bad_upstream() -> None:
    with pytest.raises(runner.TrialError):
        runner.HeaderInjectingProxy("ftp://nope", "s")


def test_header_injecting_proxy_base_url_requires_start() -> None:
    proxy = runner.HeaderInjectingProxy("https://example.test/v1", "s")

    with pytest.raises(runner.TrialError):
        _ = proxy.base_url


class _FakeResponse:
    """Minimal context-managed ``urlopen`` response for smoke tests."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_smoke_test_backend_posts_tool_aware_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        seen["request"] = request
        seen["timeout"] = timeout
        return _FakeResponse(b'{"choices":[{"message":{"content":"ok"}}]}')

    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)

    reply = runner.smoke_test_backend("http://127.0.0.1:5555", "my-model", "sk-key")

    assert reply == "ok"
    request = seen["request"]
    assert request.full_url == "http://127.0.0.1:5555/chat/completions"
    assert request.method == "POST"
    assert request.get_header("Authorization") == "Bearer sk-key"
    payload = json.loads(request.data)
    assert payload["model"] == "my-model"
    assert payload["tools"][0]["function"]["name"] == "noop"
    assert payload["max_tokens"] == runner.SMOKE_MAX_TOKENS
    assert payload["max_tokens"] > 16


def test_smoke_test_backend_accepts_a_tool_call_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(
            b'{"choices":[{"message":{"tool_calls":[{"id":"1"}]}}]}'
        ),
    )

    assert runner.smoke_test_backend("http://x", "m", "k") == "tool call returned"


def test_smoke_test_backend_accepts_a_reasoning_only_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(
            b'{"choices":[{"message":{"content":"","reasoning_content":"thinking"}}]}'
        ),
    )

    assert runner.smoke_test_backend("http://x", "m", "k") == "reasoning-only reply"


def test_smoke_test_backend_reports_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_http(*args: object, **kwargs: object) -> _FakeResponse:
        raise urllib.error.HTTPError(
            "http://x",
            401,
            "unauthorized",
            email.message.Message(),
            io.BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr(runner.urllib.request, "urlopen", raise_http)

    with pytest.raises(runner.TrialError, match="HTTP 401"):
        runner.smoke_test_backend("http://x", "m", "k")


def test_smoke_test_backend_reports_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_url(*args: object, **kwargs: object) -> _FakeResponse:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(runner.urllib.request, "urlopen", raise_url)

    with pytest.raises(runner.TrialError, match="cannot reach"):
        runner.smoke_test_backend("http://x", "m", "k")


def test_smoke_test_backend_reports_missing_and_empty_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b'{"choices":[]}'),
    )
    with pytest.raises(runner.TrialError, match="no choices"):
        runner.smoke_test_backend("http://x", "m", "k")

    monkeypatch.setattr(
        runner.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b'{"choices":[{"message":{}}]}'),
    )
    with pytest.raises(runner.TrialError, match="empty reply"):
        runner.smoke_test_backend("http://x", "m", "k")


def test_smoke_test_backend_reports_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runner.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b"<html>not json</html>"),
    )

    with pytest.raises(runner.TrialError, match="non-JSON"):
        runner.smoke_test_backend("http://x", "m", "k")


def test_build_eval_args_matches_trial_contract() -> None:
    args = runner.build_eval_args(
        tasks_file=Path("data/raw/tasks.jsonl"),
        snapshots_dir=Path("data/raw/snapshots"),
        submission_dir=Path("submission"),
        results_dir=Path("results/run_01"),
        models_yaml=Path("data/raw/models-trial.yaml"),
    )

    assert args[:2] == ["swegemma", "eval"]
    start = args.index("--task-ids")
    assert args[start + 1 : start + 3] == list(runner.TASK_IDS)
    assert args[args.index("--models-yaml") + 1] == str(Path("data/raw/models-trial.yaml"))
    assert args[args.index("--sandbox") + 1] == "docker"
    assert args[args.index("--max-tool-calls") + 1] == "100"
    assert args[args.index("--max-time-minutes") + 1] == "60"


def test_build_eval_args_honors_task_id_override() -> None:
    args = runner.build_eval_args(
        tasks_file=Path("t.jsonl"),
        snapshots_dir=Path("s"),
        submission_dir=Path("sub"),
        results_dir=Path("r"),
        models_yaml=Path("m.yaml"),
        task_ids=("only_one",),
    )

    assert args[args.index("--task-ids") + 1] == "only_one"
    assert "only_one" in args


def test_build_archive_and_report_args() -> None:
    archive = runner.build_archive_args(
        Path("results/run_01"), Path("junit"), Path("data/raw/tasks.jsonl")
    )
    assert archive[:5] == list(runner.HARNESS_RUNS)
    assert archive[5] == "archive"
    assert archive[archive.index("--backend") + 1] == runner.BACKEND_ALIAS
    assert "--sandbox-deps-mode" not in archive

    repaired = runner.build_archive_args(
        Path("results/run_01"),
        Path("junit"),
        Path("data/raw/tasks.jsonl"),
        sandbox_deps_mode="repaired",
    )
    assert repaired[repaired.index("--sandbox-deps-mode") + 1] == "repaired"

    report = runner.build_report_args(Path("runs/20260101T000000Z"))
    assert report == [*runner.HARNESS_RUNS, "report", str(Path("runs/20260101T000000Z"))]


def test_fetch_data_places_docker_shims_in_build_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheelhouse_dir.mkdir(parents=True)
    (paths.wheelhouse_dir / "pkg.whl").write_text("wheel-bytes", encoding="utf-8")

    fetched: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        runner,
        "_fetch_competition_file",
        lambda remote_file, dest_dir: fetched.append((remote_file, dest_dir)),
    )

    runner.fetch_data(paths)

    docker_files = {remote for remote, dest in fetched if dest == paths.docker_context}
    assert {
        "docker/Dockerfile.sandbox",
        "docker/Dockerfile.public",
        "docker/imp.py",
        "docker/telnetlib.py",
    } <= docker_files


def _seed_wheelhouse(paths: Any) -> None:
    """Pre-create a wheel so ``fetch_data`` skips the wheelhouse download."""
    paths.wheelhouse_dir.mkdir(parents=True)
    (paths.wheelhouse_dir / "pkg.whl").write_text("wheel-bytes", encoding="utf-8")


def _snapshot_downloads(calls: list[list[str]]) -> list[str]:
    """Return the ``snapshots/`` ``-f`` targets of every recorded kaggle download."""
    return [
        cmd[cmd.index("-f") + 1]
        for cmd in calls
        if cmd[:3] == ["kaggle", "competitions", "download"]
        and cmd[cmd.index("-f") + 1].startswith("snapshots/")
    ]


def _record_runs(monkeypatch: pytest.MonkeyPatch, calls: list[list[str]]) -> None:
    """Replace ``subprocess.run`` with a recorder returning a zero exit code."""

    def fake_run(
        cmd: list[str],
        *,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)


def test_snapshot_remote_files_derives_one_path_per_id() -> None:
    assert runner.snapshot_remote_files(()) == []
    assert runner.snapshot_remote_files(("a", "b")) == [
        "snapshots/a.tgz",
        "snapshots/b.tgz",
    ]


def test_fetch_data_defaults_to_the_two_trial_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    _seed_wheelhouse(paths)
    monkeypatch.delenv(runner.TASKS_ENV, raising=False)
    calls: list[list[str]] = []
    _record_runs(monkeypatch, calls)

    runner.fetch_data(paths)

    assert _snapshot_downloads(calls) == [f"snapshots/{task_id}.tgz" for task_id in runner.TASK_IDS]
    assert {
        cmd[cmd.index("-p") + 1]
        for cmd in calls
        if cmd[:3] == ["kaggle", "competitions", "download"]
        and cmd[cmd.index("-f") + 1].startswith("snapshots/")
    } == {str(paths.snapshots_dir)}


def test_fetch_data_downloads_n_snapshots_for_n_env_task_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    _seed_wheelhouse(paths)
    monkeypatch.setenv(runner.TASKS_ENV, "fastapi_16000, fastapi_16001, fastapi_16002")
    calls: list[list[str]] = []
    _record_runs(monkeypatch, calls)

    runner.fetch_data(paths)

    assert _snapshot_downloads(calls) == [
        "snapshots/fastapi_16000.tgz",
        "snapshots/fastapi_16001.tgz",
        "snapshots/fastapi_16002.tgz",
    ]


def test_fetch_data_skips_snapshots_already_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    _seed_wheelhouse(paths)
    paths.snapshots_dir.mkdir(parents=True)
    (paths.snapshots_dir / "fastapi_16000.tgz").write_bytes(b"cached")
    calls: list[list[str]] = []
    _record_runs(monkeypatch, calls)

    runner.fetch_data(paths, task_ids=("fastapi_16000", "fastapi_16001"))

    assert _snapshot_downloads(calls) == ["snapshots/fastapi_16001.tgz"]


def test_extract_zips_unpacks_archives_in_place(tmp_path: Path) -> None:
    archive = tmp_path / "payload.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("pkg/thing.whl", "wheel-bytes")

    runner.extract_zips(tmp_path)

    assert (tmp_path / "pkg" / "thing.whl").read_text(encoding="utf-8") == "wheel-bytes"


def test_build_swegemma_install_args_points_uv_at_the_local_wheelhouse() -> None:
    args = runner.build_swegemma_install_args(Path("data/raw/wheelhouse"))

    assert args == [
        "uv",
        "tool",
        "install",
        "--find-links",
        str(Path("data/raw/wheelhouse")),
        runner.SWEGEMMA_TOOL,
    ]


def test_install_swegemma_skips_when_already_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/swegemma")
    called: list[list[str]] = []
    monkeypatch.setattr(runner, "run_cmd", lambda cmd, *, what=None: called.append(list(cmd)))

    assert runner.install_swegemma(paths) is False
    assert called == []


def test_install_swegemma_requires_the_wheelhouse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheelhouse_dir.mkdir(parents=True)
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)

    with pytest.raises(runner.TrialError):
        runner.install_swegemma(paths)


def test_install_swegemma_installs_and_prepends_the_tool_bin_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheelhouse_dir.mkdir(parents=True)
    (paths.wheelhouse_dir / "swegemma-0.2.7-py3-none-any.whl").write_text("wheel", encoding="utf-8")

    bin_dir = tmp_path / "toolbin"
    bin_dir.mkdir()
    which_result: dict[str, str | None] = {"value": None}
    monkeypatch.setattr(runner.shutil, "which", lambda name: which_result["value"])
    monkeypatch.setattr(runner, "uv_tool_bin_dir", lambda: bin_dir)
    monkeypatch.setenv("PATH", "/usr/bin")

    called: list[tuple[list[str], str | None]] = []

    def fake_run_cmd(cmd: list[str], *, what: str | None = None) -> None:
        called.append((list(cmd), what))
        which_result["value"] = str(bin_dir / "swegemma")

    monkeypatch.setattr(runner, "run_cmd", fake_run_cmd)

    assert runner.install_swegemma(paths) is True
    assert called == [
        (runner.build_swegemma_install_args(paths.wheelhouse_dir), "uv tool install swegemma")
    ]
    assert os.environ["PATH"].startswith(str(bin_dir) + os.pathsep)


def test_install_swegemma_errors_when_binary_missing_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheelhouse_dir.mkdir(parents=True)
    (paths.wheelhouse_dir / "swegemma-0.2.7-py3-none-any.whl").write_text("wheel", encoding="utf-8")

    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    monkeypatch.setattr(runner, "uv_tool_bin_dir", lambda: None)
    monkeypatch.setattr(runner, "run_cmd", lambda cmd, *, what=None: None)

    with pytest.raises(runner.TrialError):
        runner.install_swegemma(paths)


# --------------------------------------------------------------------------- #
# wheel closure (issue #39)
# --------------------------------------------------------------------------- #
def _write_wheel(
    directory: Path,
    distribution: str,
    version: str,
    *,
    requires: tuple[str, ...] = (),
) -> Path:
    """Write a minimal valid wheel carrying a ``*.dist-info/METADATA``."""
    directory.mkdir(parents=True, exist_ok=True)
    wheel = directory / f"{distribution}-{version}-py3-none-any.whl"
    metadata = [
        "Metadata-Version: 2.1",
        f"Name: {distribution}",
        f"Version: {version}",
        *(f"Requires-Dist: {requirement}" for requirement in requires),
    ]
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr(f"{distribution}-{version}.dist-info/METADATA", "\n".join(metadata) + "\n")
    return wheel


def _add_tar_member(tar: tarfile.TarFile, name: str, text: str) -> None:
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _write_snapshot(
    path: Path,
    *,
    pyproject: str | None = None,
    requirements: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tar:
        if pyproject is not None:
            _add_tar_member(tar, "./pyproject.toml", pyproject)
        if requirements is not None:
            _add_tar_member(tar, "./requirements-tests.txt", requirements)
    return path


def test_select_wheels_picks_the_highest_version_per_name(tmp_path: Path) -> None:
    _write_wheel(tmp_path, "pkg", "1.0")
    newer = _write_wheel(tmp_path, "pkg", "2.1")

    assert runner.select_wheels(tmp_path) == {"pkg": newer}


def test_wheel_dependency_closure_flags_a_missing_transitive_dependency(
    tmp_path: Path,
) -> None:
    _write_wheel(tmp_path, "root", "1.0", requires=("Pydantic>=2",))
    _write_wheel(tmp_path, "pydantic", "2.13.4", requires=("typing-inspection>=0.4.2",))

    closure = runner.wheel_dependency_closure(tmp_path, ["root"])

    assert closure.provided == {"root": "1.0", "pydantic": "2.13.4"}
    assert closure.missing == {"typing-inspection": ("pydantic",)}


def test_wheel_dependency_closure_flags_a_missing_root(tmp_path: Path) -> None:
    _write_wheel(tmp_path, "present", "1.0")

    closure = runner.wheel_dependency_closure(tmp_path, ["absent"])

    assert closure.missing == {"absent": (runner.TASK_REPO_REQUIRER,)}


def test_wheel_dependency_closure_ignores_wheels_outside_the_roots(tmp_path: Path) -> None:
    _write_wheel(tmp_path, "root", "1.0")
    _write_wheel(tmp_path, "blinker", "1.9", requires=("flask",))

    closure = runner.wheel_dependency_closure(tmp_path, ["root"])

    assert closure.missing == {}


def test_merge_supplemental_wheels_copies_missing_and_skips_existing(tmp_path: Path) -> None:
    wheels = tmp_path / "wheels"
    extra = tmp_path / "wheels-extra"
    wheels.mkdir()
    extra.mkdir()
    _write_wheel(wheels, "pkg", "1.0")
    _write_wheel(extra, "pkg", "1.0")
    added = _write_wheel(extra, "typing_inspection", "0.4.2")

    copied = runner.merge_supplemental_wheels(wheels, [extra])

    assert copied == [added.name]
    assert (wheels / added.name).is_file()


def test_resolve_wheels_extra_dirs_prefers_env_override(tmp_path: Path) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    override = [tmp_path / "one", tmp_path / "two"]

    assert runner.resolve_wheels_extra_dirs(paths, {}) == [paths.wheels_extra_dir]
    assert (
        runner.resolve_wheels_extra_dirs(
            paths, {runner.WHEELS_EXTRA_ENV: os.pathsep.join(str(p) for p in override)}
        )
        == override
    )


def test_read_repo_requirement_names_reads_pyproject_and_requirements(tmp_path: Path) -> None:
    snapshot = _write_snapshot(
        tmp_path / "task.tgz",
        pyproject=(
            "[project]\n"
            'name = "demo"\n'
            'dependencies = ["FastAPI>=0.1", "pydantic"]\n'
            "[project.optional-dependencies]\n"
            'test = ["pytest>=8"]\n'
        ),
        requirements="starlette==0.1\n# comment\n-r other.txt\n",
    )

    assert runner.read_repo_requirement_names(snapshot) == {
        "fastapi",
        "pydantic",
        "pytest",
        "starlette",
    }


def test_read_repo_requirements_splits_core_and_optional(tmp_path: Path) -> None:
    snapshot = _write_snapshot(
        tmp_path / "task.tgz",
        pyproject=(
            "[project]\n"
            'name = "demo"\n'
            'dependencies = ["FastAPI>=0.1"]\n'
            "[project.optional-dependencies]\n"
            'test = ["pytest>=8"]\n'
        ),
        requirements="starlette==0.1\n",
    )

    requirements = runner.read_repo_requirements(snapshot)

    assert requirements.core == frozenset({"fastapi"})
    assert requirements.optional == frozenset({"pytest", "starlette"})


def test_ensure_trial_wheels_fails_fast_on_a_missing_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0", requires=("missing-dep",))
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["root"]\n',
    )
    monkeypatch.setattr(
        runner,
        "_list_competition_wheels",
        lambda: [f"wheels/{wheel.name}" for wheel in paths.wheels_dir.glob("*.whl")],
    )
    monkeypatch.setattr(
        runner, "_fetch_competition_file", lambda *args, **kwargs: pytest.fail("no fetch")
    )

    with pytest.raises(runner.TrialError, match="missing-dep"):
        runner.ensure_trial_wheels(paths, snapshots=[snapshot])

    runner.ensure_trial_wheels(paths, snapshots=[snapshot], allow_incomplete=True)


def test_ensure_trial_wheels_fails_fast_on_a_missing_core_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "present", "1.0")
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["absent-core"]\n',
    )
    monkeypatch.setattr(
        runner,
        "_list_competition_wheels",
        lambda: [f"wheels/{wheel.name}" for wheel in paths.wheels_dir.glob("*.whl")],
    )
    monkeypatch.setattr(
        runner, "_fetch_competition_file", lambda *args, **kwargs: pytest.fail("no fetch")
    )

    with pytest.raises(runner.TrialError, match="absent-core"):
        runner.ensure_trial_wheels(paths, snapshots=[snapshot])


def test_ensure_trial_wheels_warns_but_does_not_raise_for_optional_only_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0")
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject=(
            '[project]\nname = "demo"\ndependencies = ["root"]\n'
            '[project.optional-dependencies]\ntest = ["optional-dep"]\n'
        ),
    )
    monkeypatch.setattr(
        runner,
        "_list_competition_wheels",
        lambda: [f"wheels/{wheel.name}" for wheel in paths.wheels_dir.glob("*.whl")],
    )
    monkeypatch.setattr(
        runner, "_fetch_competition_file", lambda *args, **kwargs: pytest.fail("no fetch")
    )

    runner.ensure_trial_wheels(paths, snapshots=[snapshot])

    out = capsys.readouterr().out
    assert "wheel core closure ok" in out
    assert "test/optional dependencies missing" in out
    assert "optional-dep" in out


# --------------------------------------------------------------------------- #
# sandbox dependency repair (issue #41)
# --------------------------------------------------------------------------- #
def _staged_remote_wheels(paths: Any) -> list[str]:
    """Return the competition listing for the wheels currently staged in *paths*."""
    return [f"wheels/{wheel.name}" for wheel in paths.wheels_dir.glob("*.whl")]


def _no_fetch(*args: Any, **kwargs: Any) -> None:
    pytest.fail("no competition fetch expected")


def test_ensure_trial_wheels_without_repair_ignores_supplemental_wheels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0")
    extra = tmp_path / "wheels-extra"
    added = _write_wheel(extra, "supplemental", "1.0")
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["root"]\n',
    )
    monkeypatch.setattr(runner, "_list_competition_wheels", lambda: _staged_remote_wheels(paths))
    monkeypatch.setattr(runner, "_fetch_competition_file", _no_fetch)

    runner.ensure_trial_wheels(paths, extra_dirs=[extra], snapshots=[snapshot])

    assert not (paths.wheels_dir / added.name).is_file()
    out = capsys.readouterr().out
    assert "supplemental wheels not merged" in out


def test_ensure_trial_wheels_with_repair_merges_supplemental_wheels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0")
    extra = tmp_path / "wheels-extra"
    added = _write_wheel(extra, "supplemental", "1.0")
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["root"]\n',
    )
    monkeypatch.setattr(runner, "_list_competition_wheels", lambda: _staged_remote_wheels(paths))
    monkeypatch.setattr(runner, "_fetch_competition_file", _no_fetch)

    runner.ensure_trial_wheels(paths, extra_dirs=[extra], snapshots=[snapshot], repair=True)

    assert (paths.wheels_dir / added.name).is_file()
    out = capsys.readouterr().out
    assert "merged 1 supplemental wheel(s)" in out


def test_ensure_trial_wheels_repair_fetches_a_missing_core_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0", requires=("missing-dep>=1",))
    extra = tmp_path / "wheels-extra"
    extra.mkdir()
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["root"]\n',
    )
    monkeypatch.setattr(runner, "_list_competition_wheels", lambda: _staged_remote_wheels(paths))
    monkeypatch.setattr(runner, "_fetch_competition_file", _no_fetch)
    calls: list[tuple[list[str], Path]] = []

    def fake_download(names: list[str], dest: Path) -> list[str]:
        calls.append((list(names), Path(dest)))
        _write_wheel(Path(dest), "missing_dep", "1.0")
        return sorted(path.name for path in Path(dest).glob("*.whl"))

    monkeypatch.setattr(runner, "download_missing_wheels", fake_download)

    runner.ensure_trial_wheels(paths, extra_dirs=[extra], snapshots=[snapshot], repair=True)

    assert calls == [(["missing-dep"], extra)]
    out = capsys.readouterr().out
    assert "fetched 1 core wheel(s)" in out
    assert "wheel core closure ok" in out


def test_ensure_trial_wheels_repair_off_fails_fast_on_a_missing_core_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0", requires=("missing-dep>=1",))
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["root"]\n',
    )
    monkeypatch.setattr(runner, "_list_competition_wheels", lambda: _staged_remote_wheels(paths))
    monkeypatch.setattr(runner, "_fetch_competition_file", _no_fetch)
    monkeypatch.setattr(
        runner,
        "download_missing_wheels",
        lambda *args, **kwargs: pytest.fail("repair off must not fetch"),
    )

    with pytest.raises(runner.TrialError, match="missing-dep"):
        runner.ensure_trial_wheels(paths, snapshots=[snapshot], repair=False)


def test_ensure_trial_wheels_allow_partial_still_repairs_merge_and_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0", requires=("missing-dep>=1",))
    extra = tmp_path / "wheels-extra"
    added = _write_wheel(extra, "supplemental", "1.0")
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["root"]\n',
    )

    def failing_list() -> list[str]:
        raise runner.TrialError("offline")

    monkeypatch.setattr(runner, "_list_competition_wheels", failing_list)
    monkeypatch.setattr(runner, "_fetch_competition_file", _no_fetch)
    download_calls: list[tuple[list[str], Path]] = []

    def fake_download(names: list[str], dest: Path) -> list[str]:
        download_calls.append((list(names), Path(dest)))
        _write_wheel(Path(dest), "missing_dep", "1.0")
        return sorted(path.name for path in Path(dest).glob("*.whl"))

    monkeypatch.setattr(runner, "download_missing_wheels", fake_download)

    runner.ensure_trial_wheels(
        paths, extra_dirs=[extra], snapshots=[snapshot], allow_partial=True, repair=True
    )

    assert (paths.wheels_dir / added.name).is_file()
    assert download_calls == [(["missing-dep"], extra)]
    out = capsys.readouterr().out
    assert "could not list remote wheels" in out
    assert "wheel core closure ok" in out


def test_ensure_trial_wheels_allow_partial_without_repair_does_not_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    _write_wheel(paths.wheels_dir, "root", "1.0")
    extra = tmp_path / "wheels-extra"
    added = _write_wheel(extra, "supplemental", "1.0")
    snapshot = _write_snapshot(
        paths.snapshots_dir / "task_a.tgz",
        pyproject='[project]\nname = "demo"\ndependencies = ["root"]\n',
    )

    def failing_list() -> list[str]:
        raise runner.TrialError("offline")

    monkeypatch.setattr(runner, "_list_competition_wheels", failing_list)
    monkeypatch.setattr(runner, "_fetch_competition_file", _no_fetch)
    monkeypatch.setattr(
        runner, "download_missing_wheels", lambda *args, **kwargs: pytest.fail("no fetch")
    )

    runner.ensure_trial_wheels(
        paths, extra_dirs=[extra], snapshots=[snapshot], allow_partial=True, repair=False
    )

    assert not (paths.wheels_dir / added.name).is_file()
    out = capsys.readouterr().out
    assert "supplemental wheels not merged" in out


def test_download_missing_wheels_builds_the_container_target_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "wheels-extra"
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        _write_wheel(dest, "typing_inspection", "0.4.2")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.download_missing_wheels([], tmp_path / "unused") == []

    fetched = runner.download_missing_wheels(["typing-inspection"], dest)

    assert calls == [
        [
            *runner.PIP_DOWNLOAD_CMD,
            "typing-inspection",
            "-d",
            str(dest),
            *runner.PIP_CONTAINER_TARGET,
        ]
    ]
    assert fetched == ["typing_inspection-0.4.2-py3-none-any.whl"]


def test_download_missing_wheels_raises_on_a_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 1, stdout="", stderr="ERROR: no matching distribution found"
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    with pytest.raises(runner.TrialError, match="no matching distribution found"):
        runner.download_missing_wheels(["typing-inspection"], tmp_path / "wheels-extra")
