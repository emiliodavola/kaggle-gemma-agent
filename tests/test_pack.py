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
