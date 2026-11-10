"""Make the training package importable from the root test suite."""

from __future__ import annotations

import sys
from pathlib import Path

TRAINING_SRC = Path(__file__).resolve().parents[1] / "training" / "src"
if str(TRAINING_SRC) not in sys.path:
    sys.path.insert(0, str(TRAINING_SRC))
