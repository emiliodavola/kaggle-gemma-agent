"""The remote-run notebook must stay loadable, unique and parseable.

``notebooks/kaggle_run.ipynb`` is edited by hand and by scripts, and a broken
cell or a duplicated cell id only fails once the GPU session is already running.
Every invariant the run depends on is pinned here so the failure surfaces in CI.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO_ROOT / "notebooks" / "kaggle_run.ipynb"
NOTEBOOK_PYTHON = (3, 11)


def _notebook() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _code_cells(nb: dict) -> list[dict]:
    return [cell for cell in nb["cells"] if cell["cell_type"] == "code"]


def test_notebook_is_valid_nbformat_json() -> None:
    nb = _notebook()

    assert nb["nbformat"] == 4
    assert nb["cells"], "the notebook has no cells"


def test_cell_ids_are_unique() -> None:
    ids = [cell.get("id") for cell in _notebook()["cells"]]

    assert all(ids), f"a cell carries no id: {ids}"
    assert len(ids) == len(set(ids)), f"duplicate cell ids: {ids}"


@pytest.mark.parametrize("cell", _code_cells(_notebook()), ids=lambda cell: cell.get("id"))
def test_code_cell_parses_on_the_notebook_python(cell: dict) -> None:
    source = "".join(cell["source"])

    ast.parse(source, filename=cell["id"], feature_version=NOTEBOOK_PYTHON)


def test_notebook_pins_the_model_it_measures() -> None:
    """A run must refuse to start when submission/ declines a different model."""
    source = "".join("".join(cell["source"]) for cell in _code_cells(_notebook()))

    assert "EXPECTED_MODEL = " in source
    assert "DECLARED_MODEL != EXPECTED_MODEL" in source


def test_notebook_guards_the_session_wall_clock() -> None:
    source = "".join("".join(cell["source"]) for cell in _code_cells(_notebook()))

    assert "MAX_WORST_CASE_HOURS" in source
    assert "worst_case_hours > MAX_WORST_CASE_HOURS" in source


def test_notebook_preflights_the_served_model() -> None:
    source = "".join("".join(cell["source"]) for cell in _code_cells(_notebook()))

    assert "def preflight(" in source
    assert "tool_choice" in source, "the preflight must exercise a tool call"
