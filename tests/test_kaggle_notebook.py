"""The remote-run notebooks must stay loadable, unique, parseable and in sync.

There is one notebook per pinned base model: `kaggle-remote-run-31b.ipynb` and
`kaggle-remote-run-e4b.ipynb`. They are edited by hand and by scripts, and a broken
cell, a duplicated cell id or a silent drift between the two only fails once the
GPU session is already running. Every invariant the run depends on is pinned
here so the failure surfaces in CI.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = REPO_ROOT / "notebooks"
NOTEBOOK_PYTHON = (3, 11)
VARIANTS = {
    "kaggle-remote-run-31b.ipynb": "gemma-4-31b-it-qat-w4a16-ct",
    "kaggle-remote-run-e4b.ipynb": "gemma-4-e4b-it-qat-w4a16-ct",
}
MODEL_IDS = (
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-12b-it-qat-w4a16-ct",
    "gemma-4-e4b-it-qat-w4a16-ct",
    "gemma-4-e2b-it-qat-w4a16-ct",
)
VARIANT_TOKEN = re.compile(r"(kaggle-remote-run-|\*\*)(31b|e4b)(\.ipynb|\*\*)")
MODEL_TOKEN = "<MODEL>"


def _notebook(name: str) -> dict:
    return json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))


def _code_cells(nb: dict) -> list[dict]:
    return [cell for cell in nb["cells"] if cell["cell_type"] == "code"]


def _all_code(nb: dict) -> str:
    return "".join("".join(cell["source"]) for cell in _code_cells(nb))


def _normalized(name: str) -> list[str]:
    text = (NOTEBOOKS / name).read_text(encoding="utf-8")
    for model_id in MODEL_IDS:
        text = text.replace(model_id, MODEL_TOKEN)
    text = VARIANT_TOKEN.sub(lambda match: match.group(1) + "<VARIANT>" + match.group(3), text)
    return text.splitlines()


def test_only_the_two_variants_exist() -> None:
    found = {path.name for path in NOTEBOOKS.glob("kaggle-remote-run-*.ipynb")}

    assert found == set(VARIANTS), f"unexpected remote-run notebooks: {sorted(found)}"


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_notebook_is_valid_nbformat_json(name: str) -> None:
    nb = _notebook(name)

    assert nb["nbformat"] == 4
    assert nb["cells"], "the notebook has no cells"


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_cell_ids_are_unique(name: str) -> None:
    ids = [cell.get("id") for cell in _notebook(name)["cells"]]

    assert all(ids), f"a cell carries no id: {ids}"
    assert len(ids) == len(set(ids)), f"duplicate cell ids: {ids}"


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_code_cells_parse_on_the_notebook_python(name: str) -> None:
    failures = []
    for cell in _code_cells(_notebook(name)):
        try:
            ast.parse("".join(cell["source"]), filename=cell["id"], feature_version=NOTEBOOK_PYTHON)
        except SyntaxError as exc:  # pragma: no cover - only on a real break
            failures.append(f"{cell['id']}: {exc}")
    assert not failures, failures


@pytest.mark.parametrize("name,model_id", sorted(VARIANTS.items()))
def test_notebook_pins_the_model_named_in_the_file(name: str, model_id: str) -> None:
    """A run must refuse to start when submission/ declares a different model."""
    source = _all_code(_notebook(name))

    assert f'EXPECTED_MODEL = "{model_id}"' in source
    assert f'MODEL_SOURCE = "google/gemma-4/Other/{model_id}/2"' in source
    assert "DECLARED_MODEL != EXPECTED_MODEL" in source


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_notebook_guards_the_session_wall_clock(name: str) -> None:
    source = _all_code(_notebook(name))

    assert "MAX_WORST_CASE_HOURS" in source
    assert "worst_case_hours > MAX_WORST_CASE_HOURS" in source


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_notebook_preflights_the_served_model(name: str) -> None:
    source = _all_code(_notebook(name))

    assert "def preflight(" in source
    assert "tool_choice" in source, "the preflight must exercise a tool call"


def test_variants_differ_only_in_the_pinned_model() -> None:
    """One notebook per model, one implementation: drift is a CI failure."""
    first, second = sorted(VARIANTS)
    left, right = _normalized(first), _normalized(second)

    assert len(left) == len(right)
    differing = [
        (index, a, b)
        for index, (a, b) in enumerate(zip(left, right, strict=True), start=1)
        if a != b
    ]
    assert not differing, f"{first} and {second} drifted: {differing[:3]}"
