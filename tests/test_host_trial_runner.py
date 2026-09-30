"""Focused tests for the cross-platform host-trial runner (``.env`` + argv)."""

from __future__ import annotations

import http.server
import importlib.util
import os
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import ClassVar

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
        'HARNESS_MODEL="last wins"\n'
        "NO_EQUALS_HERE\n"
        "EMPTY=\n"
    )

    assert runner.parse_env_file(text) == {
        "OPENAI_API_KEY": "plain-value",
        "OPENAI_BASE_URL": "https://example.test/v1",
        "HARNESS_MODEL": "last wins",
        "EMPTY": "",
    }


def test_parse_env_file_caps_lines_at_twenty() -> None:
    text = "\n".join(f"KEY{i:02d}=value{i}" for i in range(25))

    parsed = runner.parse_env_file(text)

    assert len(parsed) == 20
    assert parsed["KEY00"] == "value0"
    assert parsed["KEY19"] == "value19"
    assert "KEY20" not in parsed


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
    assert resolved["OPENAI_BASE_URL"] == runner.DEFAULT_BASE_URL


def test_resolve_trial_env_applies_defaults_when_empty() -> None:
    resolved = runner.resolve_trial_env({}, {}, base_url="https://custom.test", harness_model="m")

    assert resolved[runner.OPENAI_BASE_URL] == "https://custom.test"
    assert resolved[runner.HARNESS_MODEL] == "m"
    assert runner.OPENAI_API_KEY not in resolved


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
    monkeypatch.delenv(runner.SESSION_ENV, raising=False)

    resolved = runner.resolve_backend_env(tmp_path / "absent.env")

    assert resolved[runner.SESSION_ENV] == runner.DEFAULT_TRIAL_SESSION
    assert resolved[runner.HARNESS_MODEL] == runner.DEFAULT_HARNESS_MODEL
    assert os.environ[runner.OPENAI_API_KEY] == "super-secret-key"


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


def test_ensure_trial_wheels_skips_when_a_wheel_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    paths.wheels_dir.mkdir(parents=True)
    (paths.wheels_dir / "pkg.whl").write_text("wheel-bytes", encoding="utf-8")
    monkeypatch.setattr(
        runner, "_list_competition_wheels", lambda: pytest.fail("must not list remote files")
    )

    runner.ensure_trial_wheels(paths)


def test_ensure_trial_wheels_downloads_into_the_wheels_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    monkeypatch.setattr(
        runner, "_list_competition_wheels", lambda: ["wheels/a.whl", "wheels/b.whl"]
    )
    fetched: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        runner,
        "_fetch_competition_file",
        lambda remote_file, dest_dir: fetched.append((remote_file, dest_dir)),
    )

    runner.ensure_trial_wheels(paths)

    assert fetched == [
        ("wheels/a.whl", paths.wheels_dir),
        ("wheels/b.whl", paths.wheels_dir),
    ]


def test_ensure_trial_wheels_errors_when_remote_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runner.paths_for(tmp_path, "run_01")
    monkeypatch.setattr(runner, "_list_competition_wheels", lambda: [])

    with pytest.raises(runner.TrialError):
        runner.ensure_trial_wheels(paths)


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
