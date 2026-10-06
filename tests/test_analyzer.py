"""Guards for the code_analyzer sub-agent contract (playbook 2.4)."""

from __future__ import annotations

import re
from pathlib import Path

SUBMISSION = Path(__file__).resolve().parents[1] / "submission"
AGENT = SUBMISSION / "agent.yaml"
ANALYZER_YAML = SUBMISSION / "sub_agents" / "code_analyzer.yaml"
ANALYZER_PROMPT = SUBMISSION / "prompts" / "analyzer.md"
EXPECTED_MODEL = "gemma-4-31b-it-qat-w4a16-ct"
ANALYZER_TOOLS = ("read_file", "search_similar_code", "get_code_neighbors", "get_code_subgraph")
MAX_PROMPT_LINES = 30
FORBIDDEN = re.compile(
    r"https?://|socket|urllib|requests\.|pip install|uv add|mcp|subprocess|\bcurl\b|\bwget\b",
    re.IGNORECASE,
)


def test_agent_keeps_skip_summarization() -> None:
    text = AGENT.read_text(encoding="utf-8")

    assert "agent_tool:" in text
    assert "config_path: sub_agents/code_analyzer.yaml" in text
    assert "skip_summarization: true" in text


def test_analyzer_declares_expected_tools_and_model() -> None:
    text = ANALYZER_YAML.read_text(encoding="utf-8")

    assert f"model: {EXPECTED_MODEL}" in text
    for tool in ANALYZER_TOOLS:
        assert f"- {tool}" in text, f"analyzer missing tool {tool}"
    assert "instruction: !include ../prompts/analyzer.md" in text


def test_analyzer_prompt_is_localization_only_with_the_contract() -> None:
    text = ANALYZER_PROMPT.read_text(encoding="utf-8")

    assert len(text.splitlines()) <= MAX_PROMPT_LINES
    assert "signature" in text.lower()
    assert "at most" in text.lower()
    assert "file:line" in text


def test_analyzer_files_have_no_forbidden_tokens() -> None:
    for path in (ANALYZER_YAML, ANALYZER_PROMPT):
        text = path.read_text(encoding="utf-8")
        hits = sorted({match.group(0).lower() for match in FORBIDDEN.finditer(text)})
        assert not hits, f"{path}: forbidden token(s) {hits}"
