"""Every shipped module must parse on the Kaggle notebook image's Python.

The repository targets Python 3.14, but ``notebooks/kaggle_run.ipynb``
imports ``scripts/host-trial/run_host_trial.py`` and runs
``python -m kaggle_gemma_agent.harness_runs`` on the Kaggle notebook image, whose
interpreter can be older. Syntax newer than 3.11 breaks the remote run before the
submission gate even starts, so the contract is pinned here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_ROOTS = ("src", "scripts")
NOTEBOOK_PYTHON = (3, 11)


def _shipped_modules() -> list[Path]:
    modules: list[Path] = []
    for root in SHIPPED_ROOTS:
        modules.extend(sorted((REPO_ROOT / root).rglob("*.py")))
    return modules


@pytest.mark.parametrize(
    "path",
    _shipped_modules(),
    ids=lambda path: path.relative_to(REPO_ROOT).as_posix(),
)
def test_shipped_module_parses_on_the_notebook_python(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path), feature_version=NOTEBOOK_PYTHON)
