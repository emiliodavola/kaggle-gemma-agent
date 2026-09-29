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
