"""Focused tests for the stdlib-only submission packer."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from kaggle_gemma_agent import pack


def _make_source(root: Path, *, extra: str | None = None) -> Path:
    skill_dir = root / pack.STACK_DIR / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Demo skill\n", encoding="utf-8")
    if extra is not None:
        (root / pack.STACK_DIR / extra).write_text("x", encoding="utf-8")
    return root


def test_build_submission_writes_manifest_and_stack(tmp_path: Path) -> None:
    source = _make_source(tmp_path)
    output = tmp_path / "out" / "submission.zip"

    archive = pack.build_submission(source, output)

    assert archive == output.resolve()
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert pack.AGENT_MANIFEST in names
        assert f"{pack.STACK_DIR}/demo-skill/SKILL.md" in names
        assert zf.read(pack.AGENT_MANIFEST).decode("utf-8") == pack.AGENT_YAML_SKELETON


def test_source_agent_manifest_is_used(tmp_path: Path) -> None:
    source = _make_source(tmp_path)
    manifest = "name: custom_agent\nmodel: gemma-4-31b-it-qat-w4a16-ct\n"
    (source / pack.AGENT_MANIFEST).write_text(manifest, encoding="utf-8")

    archive = pack.build_submission(source, tmp_path / "submission.zip")

    with zipfile.ZipFile(archive) as zf:
        assert zf.read(pack.AGENT_MANIFEST).decode("utf-8") == manifest
        assert zf.namelist().count(pack.AGENT_MANIFEST) == 1


def test_missing_required_root_entry_raises(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.mkdir()

    with pytest.raises(pack.PackError, match="missing required root entry"):
        pack.build_submission(source, tmp_path / "submission.zip")


def test_unpacked_size_limit_is_enforced(tmp_path: Path) -> None:
    source = _make_source(tmp_path)
    (source / pack.STACK_DIR / "blob.bin").write_bytes(b"0" * 2048)

    with pytest.raises(pack.PackError, match="unpacked size"):
        pack.build_submission(source, tmp_path / "submission.zip", max_unpacked_bytes=1024)


def test_agent_py_is_rejected(tmp_path: Path) -> None:
    source = _make_source(tmp_path, extra="agent.py")

    with pytest.raises(pack.PackError, match="forbidden file"):
        pack.build_submission(source, tmp_path / "submission.zip")


def test_nonexistent_source_raises(tmp_path: Path) -> None:
    with pytest.raises(pack.PackError, match="source directory does not exist"):
        pack.build_submission(tmp_path / "nope", tmp_path / "submission.zip")


def _make_compliant_source(root: Path) -> Path:
    for index in range(pack.REQUIRED_SKILLS):
        skill_dir = root / pack.STACK_DIR / f"skill-{index:02d}"
        skill_dir.mkdir(parents=True)
        (skill_dir / pack.SKILL_MANIFEST).write_text("# Skill\n", encoding="utf-8")
    (root / pack.AGENT_MANIFEST).write_text(
        f"name: demo\nmodel: {pack.EXPECTED_MODEL}\n", encoding="utf-8"
    )
    (root / pack.EVAL_CONFIG).write_text(
        "evaluation:\n"
        f"  max_tool_calls: {pack.MAX_TOOL_CALLS}\n"
        f"  max_time_minutes: {pack.MAX_TIME_MINUTES}\n"
        f"  max_turns: {pack.MAX_TURNS}\n",
        encoding="utf-8",
    )
    return root


def test_check_submission_passes_on_compliant_source(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)

    assert pack.check_submission(source) == []


def test_check_flags_missing_skill_manifest(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / pack.STACK_DIR / "skill-00" / pack.SKILL_MANIFEST).unlink()

    violations = pack.check_submission(source)

    assert any("skill-00" in v and "missing SKILL.md" in v and "rule b" in v for v in violations)


def test_check_flags_multiple_models(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / "sub_agents").mkdir()
    (source / "sub_agents" / "other.yaml").write_text("model: some-other-model\n", encoding="utf-8")

    violations = pack.check_submission(source)

    assert any("exactly one base model id" in v and "rule c" in v for v in violations)


def test_check_flags_budget_over_limit(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / pack.EVAL_CONFIG).write_text(
        f"max_tool_calls: {pack.MAX_TOOL_CALLS + 1}\n", encoding="utf-8"
    )

    violations = pack.check_submission(source)

    assert any("max_tool_calls" in v and "exceeds limit" in v and "rule d" in v for v in violations)


def test_check_flags_forbidden_string(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / "prompts").mkdir()
    (source / "prompts" / "system.md").write_text(
        "Do not run pip install anything.\n", encoding="utf-8"
    )

    violations = pack.check_submission(source)

    assert any("forbidden string" in v and "rule e" in v for v in violations)


def test_check_flags_agent_py(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / "agent.py").write_text("import importlib\n", encoding="utf-8")

    violations = pack.check_submission(source)

    assert any("agent.py" in v and "rule a" in v for v in violations)


def test_load_agent_manifest_override_wins(tmp_path: Path) -> None:
    source = _make_source(tmp_path)

    assert pack.load_agent_manifest(source, "override: true\n") == "override: true\n"


def test_check_flags_missing_agent_manifest(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / pack.AGENT_MANIFEST).unlink()

    violations = pack.check_submission(source)

    assert any("declarative manifest required" in v and "rule a" in v for v in violations)


def test_check_flags_missing_skill_stack_dir(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / pack.STACK_DIR / "skill-00" / pack.SKILL_MANIFEST).unlink()
    (source / pack.STACK_DIR / "skill-00").rmdir()

    violations = pack.check_submission(source)

    assert any("expected" in v and "skills" in v and "rule b" in v for v in violations)


def test_check_flags_absent_skill_stack(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    for skill_dir in (source / pack.STACK_DIR).iterdir():
        (skill_dir / pack.SKILL_MANIFEST).unlink()
        skill_dir.rmdir()
    (source / pack.STACK_DIR).rmdir()

    violations = pack.check_submission(source)

    assert any("skill stack directory is required" in v and "rule b" in v for v in violations)


def test_check_flags_wrong_model(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / pack.AGENT_MANIFEST).write_text("model: not-the-expected-model\n", encoding="utf-8")

    violations = pack.check_submission(source)

    assert any("expected" in v and pack.EXPECTED_MODEL in v and "rule c" in v for v in violations)


def test_check_flags_missing_eval_config(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / pack.EVAL_CONFIG).unlink()

    violations = pack.check_submission(source)

    assert any("per-task budgets" in v and "rule d" in v for v in violations)


def test_check_flags_oversized_submission(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)

    violations = pack.check_submission(source, max_unpacked_bytes=1)

    assert any("exceeds limit" in v and "rule f" in v for v in violations)


def test_check_submission_missing_source_dir(tmp_path: Path) -> None:
    violations = pack.check_submission(tmp_path / "nope")

    assert violations == [f"{tmp_path / 'nope'}: source directory does not exist (rule a)"]


def test_main_check_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _make_compliant_source(tmp_path)

    assert pack.main([str(source), "--check"]) == 0
    assert "submission contract OK" in capsys.readouterr().out


def test_main_check_reports_failures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _make_compliant_source(tmp_path)
    (source / pack.EVAL_CONFIG).unlink()

    assert pack.main([str(source), "--check"]) == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.err
    assert "error:" in captured.err


def test_main_builds_archive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _make_source(tmp_path)
    output = tmp_path / "submission.zip"

    assert pack.main([str(source), "-o", str(output)]) == 0
    assert output.is_file()
    assert "wrote" in capsys.readouterr().out


def test_main_build_error_returns_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "submission.zip"

    assert pack.main([str(tmp_path / "nope"), "-o", str(output)]) == 1
    assert not output.exists()
    assert "error:" in capsys.readouterr().err
