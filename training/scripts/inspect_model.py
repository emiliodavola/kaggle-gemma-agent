"""Inspect the base model and write its report.

Usage:
    uv run --directory training python scripts/inspect_model.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from e4b_training.training.model_inspection import main

if __name__ == "__main__":
    raise SystemExit(main())
