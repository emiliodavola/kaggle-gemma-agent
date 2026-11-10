"""Report the training host and exit non-zero when it is incompatible.

Usage:
    uv run --directory training python scripts/validate_environment.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from e4b_training.utils.environment import main

if __name__ == "__main__":
    raise SystemExit(main())
