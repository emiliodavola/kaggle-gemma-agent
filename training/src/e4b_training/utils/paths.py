"""Filesystem roots shared by every training module.

Keeping the two roots in one place is what lets a module move into
``src/e4b_training`` without silently changing where it reads datasets, runs or
adapters from.
"""

from __future__ import annotations

from pathlib import Path

# .../training/src/e4b_training/utils/paths.py
TRAINING_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = TRAINING_ROOT.parent

DATASET_DIR = TRAINING_ROOT / "dataset"
RUNS_DIR = REPO_ROOT / "runs"
ADAPTERS_DIR = TRAINING_ROOT / "adapters"
ARTIFACTS_DIR = TRAINING_ROOT / "artifacts"
CONFIGS_DIR = TRAINING_ROOT / "configs"


def ensure_runtime_dirs() -> None:
    """Create the local artifact directories without touching tracked files."""
    for directory in (DATASET_DIR, ADAPTERS_DIR, ARTIFACTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
