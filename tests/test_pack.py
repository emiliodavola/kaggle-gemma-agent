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
    names: list[str] = []
    for index in range(pack.REQUIRED_SKILLS):
        name = f"skill-{index:02d}"
        skill_dir = root / pack.STACK_DIR / name
        skill_dir.mkdir(parents=True)
        (skill_dir / pack.SKILL_MANIFEST).write_text("# Skill\n", encoding="utf-8")
        names.append(name)
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text(
        "\n".join(f"- {name}" for name in names) + "\n", encoding="utf-8"
    )
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


def _skill_names(source: Path) -> list[str]:
    return sorted(path.name for path in (source / pack.STACK_DIR).iterdir() if path.is_dir())


def _write_always_on(source: Path, text: str) -> None:
    (source / "prompts").mkdir(exist_ok=True)
    (source / "prompts" / "system.md").write_text(text, encoding="utf-8")


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
    (source / "prompts").mkdir(exist_ok=True)
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


def test_check_harness_surface_passes_on_compliant_source(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)

    assert pack.check_harness_surface(source) == []


def test_harness_surface_flags_untriggered_skill(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    names = [name for name in _skill_names(source) if name != "skill-03"]
    _write_always_on(source, "\n".join(f"- {name}" for name in names) + "\n")

    violations = pack.check_harness_surface(source)

    assert len(violations) == 1
    assert "skill-03" in violations[0]
    assert "rule s1" in violations[0]


def test_harness_surface_flags_oversized_prompt(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    text = "\n".join(_skill_names(source)) + "x" * (pack.MAX_ALWAYS_ON_CHARS + 1)
    _write_always_on(source, text)

    violations = pack.check_harness_surface(source)

    assert len(violations) == 1
    assert "rule s2" in violations[0]
    assert str(pack.MAX_ALWAYS_ON_CHARS) in violations[0]


def test_harness_surface_flags_missing_script_reference(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    manifest = source / pack.STACK_DIR / "skill-00" / pack.SKILL_MANIFEST
    manifest.write_text("# Skill\nRun `python3 scripts/missing.py`.\n", encoding="utf-8")

    violations = pack.check_harness_surface(source)

    assert len(violations) == 1
    assert "scripts/missing.py" in violations[0]
    assert "rule s3" in violations[0]

    (source / pack.SCRIPTS_DIR).mkdir()
    (source / pack.SCRIPTS_DIR / "missing.py").write_text("", encoding="utf-8")

    assert pack.check_harness_surface(source) == []


def test_harness_surface_follows_selected_variant(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    names = _skill_names(source)
    (source / "configs").mkdir()
    (source / "configs" / "prompt_variant.yaml").write_text("variant: v2\n", encoding="utf-8")
    (source / "prompts" / "system.v2.md").write_text("\n".join(names), encoding="utf-8")
    _write_always_on(source, "no skill is named here\n")

    assert pack.check_harness_surface(source) == []

    (source / "prompts" / "system.v2.md").write_text("no skill is named here\n", encoding="utf-8")
    _write_always_on(source, "\n".join(names))

    violations = pack.check_harness_surface(source)

    assert len(violations) == len(names)
    assert all("rule s1" in v for v in violations)


def test_harness_surface_ignores_prose_script_mentions(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    text = (
        "\n".join(_skill_names(source))
        + "\nKeep scratch under the scripts/ directory, never at /tmp/scripts/x.py"
        " or foo/scripts/x.py.\n"
        "Byte-compile every changed `.py` file; see `conftest.py`."
        " Use python3 - <<'PY' for scratch.\n"
    )
    _write_always_on(source, text)

    assert pack.check_harness_surface(source) == []


def test_harness_surface_reports_unresolvable_selector(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / "configs").mkdir()
    (source / "configs" / "prompt_variant.yaml").write_text("variant: nope\n", encoding="utf-8")

    violations = pack.check_harness_surface(source)

    assert len(violations) == 1
    assert "unknown variant" in violations[0]
    assert "rules s1/s2" in violations[0]


def test_harness_surface_reports_missing_prompt(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / "prompts" / "system.md").unlink()

    violations = pack.check_harness_surface(source)

    assert len(violations) == 1
    assert "selected always-on prompt not found" in violations[0]
    assert "rules s1/s2" in violations[0]


def test_main_check_prints_harness_surface_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _make_compliant_source(tmp_path)

    assert pack.main([str(source), "--check"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "submission contract OK (6/6 points)",
        "harness surface OK (3 checks)",
        "answer leak OK (4 patterns)",
    ]


def test_main_check_reports_harness_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _make_compliant_source(tmp_path)
    names = [name for name in _skill_names(source) if name != "skill-07"]
    _write_always_on(source, "\n".join(f"- {name}" for name in names) + "\n")

    assert pack.main([str(source), "--check"]) == 1
    captured = capsys.readouterr()
    assert "harness surface FAILED" in captured.err
    assert "submission contract OK (6/6 points)" in captured.out


def test_harness_surface_size_counts_decoded_chars(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    names_text = "\n".join(_skill_names(source)) + "\n"
    exact = names_text + "x" * (pack.MAX_ALWAYS_ON_CHARS - len(names_text))
    _write_always_on(source, exact)

    assert len(exact) == pack.MAX_ALWAYS_ON_CHARS
    assert pack.check_harness_surface(source) == []

    _write_always_on(source, exact + "x")

    violations = pack.check_harness_surface(source)

    assert len(violations) == 1
    assert "rule s2" in violations[0]


def _write_skill(source: Path, text: str) -> None:
    (source / pack.STACK_DIR / "skill-00" / pack.SKILL_MANIFEST).write_text(text, encoding="utf-8")


def test_answer_leak_passes_on_compliant_source(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)

    assert pack.check_answer_leak(source) == []


def test_answer_leak_flags_task_id(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    _write_skill(source, "# Skill\nrequests_7309\n")

    violations = pack.check_answer_leak(source)

    assert len(violations) == 1
    assert "skills/skill-00/SKILL.md:2" in violations[0]
    assert "requests_7309" in violations[0]


def test_answer_leak_flags_node_id(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    _write_skill(source, "# Skill\n::test_parse_header\n")

    violations = pack.check_answer_leak(source)

    assert len(violations) == 1
    assert "::test_" in violations[0]
    assert "skills/skill-00/SKILL.md:2" in violations[0]


def test_answer_leak_flags_test_path(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    _write_skill(source, "# Skill\ntests/test_utils.py\n")

    violations = pack.check_answer_leak(source)

    assert len(violations) == 1
    assert "tests/test_utils.py" in violations[0]


def test_answer_leak_flags_split_marker(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    _write_skill(source, "# Skill\nFAIL_TO_PASS\n")

    violations = pack.check_answer_leak(source)

    assert len(violations) == 1
    assert "FAIL_TO_PASS" in violations[0]


def test_answer_leak_reports_line_and_deduplicates(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    _write_skill(source, "# Skill\nrequests_7309 requests_7309\n")

    violations = pack.check_answer_leak(source)

    task_ids = [violation for violation in violations if "requests_7309" in violation]
    assert len(task_ids) == 1
    assert "skills/skill-00/SKILL.md:2" in task_ids[0]


def test_answer_leak_scans_file_names(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / "requests_7309.md").write_text("clean content\n", encoding="utf-8")

    violations = pack.check_answer_leak(source)

    assert violations == ["requests_7309.md: answer leak in file name 'requests_7309'"]


def test_answer_leak_skips_non_text_suffix(tmp_path: Path) -> None:
    source = _make_compliant_source(tmp_path)
    (source / "weights.safetensors").write_bytes(b"requests_7309")

    assert pack.check_answer_leak(source) == []


def test_answer_leak_handles_missing_source(tmp_path: Path) -> None:
    missing = tmp_path / "nope"

    assert pack.check_answer_leak(missing) == [
        f"{missing}: source directory does not exist (answer leak)"
    ]


def test_answer_leak_passes_on_shipped_submission() -> None:
    submission = Path(__file__).resolve().parents[1] / "submission"

    assert pack.check_answer_leak(submission) == []


def test_main_check_prints_answer_leak_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _make_compliant_source(tmp_path)

    assert pack.main([str(source), "--check"]) == 0
    out = capsys.readouterr().out
    assert "submission contract OK (6/6 points)" in out
    assert "harness surface OK (3 checks)" in out
    assert "answer leak OK (4 patterns)" in out


def test_main_check_reports_answer_leak_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _make_compliant_source(tmp_path)
    _write_skill(source, "# Skill\nrequests_7309\n")

    assert pack.main([str(source), "--check"]) == 1
    captured = capsys.readouterr()
    assert "answer leak FAILED" in captured.err
    assert "submission contract OK (6/6 points)" in captured.out
