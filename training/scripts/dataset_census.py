"""Census a remote Open-SWE-Traces split without downloading it.

Usage:
    uv run --directory training python scripts/dataset_census.py --split openhands
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from e4b_training.data.census import main

if __name__ == "__main__":
    raise SystemExit(main())
