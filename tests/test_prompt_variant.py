"""Tests for the YAML-selected system prompt variant."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from kaggle_gemma_agent import pack, prompt_variant

REPO_ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_DIR = REPO_ROOT / "submission"


def _make_variant_source(root: Path, variant: str = "v2") -> Path:
    (root / "prompts").mkdir(parents=True)
    (root / "configs").mkdir(parents=True)
    (root / "skills").mkdir(parents=True)
    (root / "prompts" / "system.legacy.md").write_text("legacy prompt\n", encoding="utf-8")
    (root / "prompts" / "system.v2.md").write_text("v2 prompt\n", encoding="utf-8")
    (root / "prompts" / "system.md").write_text("legacy prompt\n", encoding="utf-8")
    (root / "configs" / "prompt_variant.yaml").write_text(f"variant: {variant}\n", encoding="utf-8")
    return root


def test_read_variant_returns_selection(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)

    assert prompt_variant.read_variant(source) == "v2"


def test_read_variant_rejects_missing_selector(tmp_path: Path) -> None:
    with pytest.raises(prompt_variant.PromptVariantError, match="selector file is required"):
        prompt_variant.read_variant(tmp_path)


def test_read_variant_rejects_unknown_variant(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)
    (source / "configs" / "prompt_variant.yaml").write_text("variant: nope\n", encoding="utf-8")

    with pytest.raises(prompt_variant.PromptVariantError, match="unknown variant 'nope'"):
        prompt_variant.read_variant(source)


def test_read_variant_requires_a_line(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)
    (source / "configs" / "prompt_variant.yaml").write_text("# no variant here\n", encoding="utf-8")

    with pytest.raises(prompt_variant.PromptVariantError, match="no 'variant:' line"):
        prompt_variant.read_variant(source)


def test_apply_variant_copies_selected_file(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)

    name, active = prompt_variant.apply_variant(source)

    assert name == "v2"
    assert active == source / "prompts" / "system.md"
    assert active.read_text(encoding="utf-8") == "v2 prompt\n"


def test_apply_variant_rejects_missing_variant_file(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)
    (source / "prompts" / "system.v2.md").unlink()

    with pytest.raises(prompt_variant.PromptVariantError, match="variant file not found"):
        prompt_variant.apply_variant(source)


def test_is_active_tracks_materialization(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)

    assert prompt_variant.is_active(source) is False
    prompt_variant.apply_variant(source)
    assert prompt_variant.is_active(source) is True


def test_cli_show_reports_out_of_sync(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _make_variant_source(tmp_path)

    assert prompt_variant.main(["show", "--cwd", str(source)]) == 0
    assert "OUT OF SYNC" in capsys.readouterr().out


def test_cli_apply_then_show_in_sync(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _make_variant_source(tmp_path)

    assert prompt_variant.main(["apply", "--cwd", str(source)]) == 0
    assert "applied variant 'v2'" in capsys.readouterr().out
    assert prompt_variant.main(["show", "--cwd", str(source)]) == 0
    assert "in sync" in capsys.readouterr().out


def test_cli_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert prompt_variant.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "legacy" in out
    assert "v2" in out


def test_cli_error_on_missing_selector(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert prompt_variant.main(["show", "--cwd", str(tmp_path)]) == 1
    assert "error:" in capsys.readouterr().err


def test_pack_build_materializes_selected_variant(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path, variant="v2")

    archive = pack.build_submission(source, tmp_path / "submission.zip")

    with zipfile.ZipFile(archive) as zf:
        assert zf.read("prompts/system.md").decode("utf-8") == "v2 prompt\n"


def test_pack_build_without_selector_keeps_prompt(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)
    (source / "configs" / "prompt_variant.yaml").unlink()
    (source / "prompts" / "system.md").write_text("active prompt\n", encoding="utf-8")

    archive = pack.build_submission(source, tmp_path / "submission.zip")

    with zipfile.ZipFile(archive) as zf:
        assert zf.read("prompts/system.md").decode("utf-8") == "active prompt\n"


def test_pack_build_rejects_invalid_selector(tmp_path: Path) -> None:
    source = _make_variant_source(tmp_path)
    (source / "configs" / "prompt_variant.yaml").write_text("variant: nope\n", encoding="utf-8")

    with pytest.raises(pack.PackError, match="unknown variant"):
        pack.build_submission(source, tmp_path / "submission.zip")


def test_shipped_submission_matches_selector() -> None:
    assert prompt_variant.is_active(SUBMISSION_DIR) is True, (
        "submission/prompts/system.md is out of sync with configs/prompt_variant.yaml; "
        "run: uv run python -m kaggle_gemma_agent.prompt_variant apply"
    )
