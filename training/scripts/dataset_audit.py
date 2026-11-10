"""Audit the harness-native SFT dataset by streaming it.

Usage:
    uv run --directory training python scripts/dataset_audit.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from e4b_training.data.audit import main

if __name__ == "__main__":
    raise SystemExit(main())
