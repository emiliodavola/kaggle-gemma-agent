"""Focused tests for the cross-platform host-trial runner (``.env`` + argv)."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

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
        runner.resolve_backend_env(tmp_path / "absent.env", tmp_path / "models.yaml")


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
