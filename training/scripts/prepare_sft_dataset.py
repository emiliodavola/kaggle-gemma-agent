"""Prepare the filtered, deduplicated and split SFT corpus.

Usage:
    uv run --directory training python scripts/prepare_sft_dataset.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from e4b_training.data.audit import SPLITS, stream_rows
from e4b_training.data.harness_records import shipped_system_prompt
from e4b_training.data.pipeline import prepare, write_jsonl
from e4b_training.utils.paths import TRAINING_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the processed SFT corpus.")
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=TRAINING_ROOT / "data" / "processed",
    )
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=TRAINING_ROOT / "data" / "manifests" / "dataset_manifest.json",
    )
    args = parser.parse_args(argv)

    prompt = shipped_system_prompt()
    rows = ((split, row) for split in sorted(SPLITS) for row in stream_rows(SPLITS[split]))
    result = prepare(rows, prompt)

    for split, records in result.records.items():
        count = write_jsonl(records, args.out_dir / f"sft_{split}.jsonl")
        print(f"{split}: {count} records -> {args.out_dir / f'sft_{split}.jsonl'}")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result.manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"kept={result.manifest['kept']} dropped={result.manifest['dropped']} "
        f"repos={result.manifest['distinct_repositories']} "
        f"reasons={result.manifest['drop_reasons']}"
    )
    print(f"wrote {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
