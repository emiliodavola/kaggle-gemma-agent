"""Full-conversation SFT entry point.

Usage:
    uv run --directory training python scripts/train_sft.py --preflight
    uv run --directory training python scripts/train_sft.py --epochs 2
"""

from __future__ import annotations

import pathlib
import sys

TRAINING = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(TRAINING / "src"))

from e4b_training.training.sft import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
