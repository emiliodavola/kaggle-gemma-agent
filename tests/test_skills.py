"""Guards for the compact submission skills.

These lock the invariants the compaction introduced: exactly 12 skills, a
per-file and total line budget, a short ``Trigger:`` description, no forbidden
tokens (rule e), and no extra files inside a skill directory.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[1] / "submission" / "skills"
REQUIRED_SKILLS = 12
MAX_TOTAL_LINES = 380
MAX_SKILL_LINES = 40
MAX_TRIGGER_WORDS = 20
FORBIDDEN = re.compile(
    r"https?://|socket|urllib|requests\.|pip install|uv add|mcp|subprocess|\bcurl\b|\bwget\b",
    re.IGNORECASE,
)
TRIGGER = re.compile(r'^description:\s*"Trigger:\s*(.+?)"\s*$', re.MULTILINE)


def _skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def test_exactly_twelve_skills() -> None:
    assert len(_skill_files()) == REQUIRED_SKILLS


def test_total_lines_within_budget() -> None:
    total = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in _skill_files())
    assert total <= MAX_TOTAL_LINES, f"skills total {total} lines > {MAX_TOTAL_LINES}"


def test_each_skill_within_line_budget() -> None:
    for path in _skill_files():
        lines = len(path.read_text(encoding="utf-8").splitlines())
        assert lines <= MAX_SKILL_LINES, f"{path}: {lines} lines > {MAX_SKILL_LINES}"


def test_each_skill_has_a_short_trigger() -> None:
    for path in _skill_files():
        match = TRIGGER.search(path.read_text(encoding="utf-8"))
        assert match, f"{path}: no 'Trigger:' description line"
        words = len(match.group(1).split())
        assert words <= MAX_TRIGGER_WORDS, f"{path}: trigger has {words} words"


def test_no_forbidden_tokens() -> None:
    for path in _skill_files():
        text = path.read_text(encoding="utf-8")
        hits = sorted({match.group(0).lower() for match in FORBIDDEN.finditer(text)})
        assert not hits, f"{path}: forbidden token(s) {hits}"


def test_skill_directories_hold_only_the_skill_file() -> None:
    for path in _skill_files():
        siblings = sorted(p.name for p in path.parent.iterdir() if p.name != "SKILL.md")
        assert not siblings, f"{path.parent}: unexpected files {siblings}"
