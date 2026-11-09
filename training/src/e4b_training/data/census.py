"""Count Python and resolved records in a remote Open-SWE-Traces split.

The dataset is about 98 GB across all configurations. This module never
downloads a parquet file: it opens each file over HTTP and asks Parquet for only
the four small columns the census needs (``language``, ``resolved``, ``repo``,
``license``). The ``messages`` payload is never read. The tool set is read from
the smallest file's first batch, because it is constant per split.

The output is JSON under ``training/artifacts/reports/`` and a short summary on
stdout. A file that cannot be read is reported and the scan continues.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import fsspec
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_url

from e4b_training.utils.paths import ARTIFACTS_DIR

DATASET = "nvidia/Open-SWE-Traces"
REVISION = "4fa4c2ae9afc6b397bc50391d43450c79993c138"
COLUMNS = ["language", "resolved", "repo", "license"]
EXCLUDED_REPOS = {
    "fastapi/fastapi",
    "Textualize/rich",
    "psf/requests",
    "encode/httpx",
}
LICENSE_ALLOWLIST = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"}


@dataclass
class Census:
    split: str
    files: int = 0
    declared_bytes: int = 0
    rows: int = 0
    languages: Counter = field(default_factory=Counter)
    resolved: Counter = field(default_factory=Counter)
    licenses: Counter = field(default_factory=Counter)
    excluded_repo_rows: Counter = field(default_factory=Counter)
    per_repo_python_resolved: Counter = field(default_factory=Counter)
    python_resolved: int = 0
    python_resolved_license_ok: int = 0
    tool_sets: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


def list_files(prefix: str) -> list[tuple[str, int]]:
    api = HfApi()
    files = []
    for entry in api.list_repo_tree(
        DATASET,
        path_in_repo=prefix,
        repo_type="dataset",
        revision=REVISION,
        recursive=True,
    ):
        size = getattr(entry, "size", None)
        if size is not None:
            files.append((entry.path, int(size)))
    return sorted(files, key=lambda item: item[1])


def _tool_names(raw_tools) -> list[str]:
    names = []
    for item in raw_tools or []:
        try:
            payload = json.loads(item) if isinstance(item, str) else item
            name = payload.get("function", {}).get("name")
        except (TypeError, ValueError, AttributeError):
            continue
        if name:
            names.append(name)
    return sorted(set(names))


def read_tool_set(path: str) -> list[str]:
    url = hf_hub_url(DATASET, path, repo_type="dataset", revision=REVISION)
    with fsspec.open(url, "rb", block_size=2**20) as handle:
        batch = next(pq.ParquetFile(handle).iter_batches(batch_size=1, columns=["tools"]))
        return _tool_names(batch.column("tools")[0].as_py())


def scan_file(path: str, census: Census) -> None:
    url = hf_hub_url(DATASET, path, repo_type="dataset", revision=REVISION)
    try:
        with fsspec.open(url, "rb", block_size=2**20) as handle:
            table = pq.ParquetFile(handle).read(columns=COLUMNS)
    except Exception as error:
        census.errors.append({"file": path, "error": str(error)})
        return

    for batch in table.to_batches(max_chunksize=65536):
        data = batch.to_pydict()
        for language, resolved, repo, license_name in zip(
            data["language"], data["resolved"], data["repo"], data["license"]
        ):
            census.rows += 1
            census.languages[language or "unknown"] += 1
            census.resolved[str(resolved)] += 1
            census.licenses[license_name or "unknown"] += 1
            if repo in EXCLUDED_REPOS:
                census.excluded_repo_rows[repo] += 1
            if language == "python" and resolved == 1:
                census.python_resolved += 1
                census.per_repo_python_resolved[repo] += 1
                if license_name in LICENSE_ALLOWLIST:
                    census.python_resolved_license_ok += 1
    census.files += 1


def build_report(census: Census) -> dict:
    return {
        "schema_version": "1.0",
        "dataset": DATASET,
        "revision": REVISION,
        "split": census.split,
        "read_mode": "remote-column-pruned",
        "columns_read": COLUMNS,
        "files": census.files,
        "declared_bytes": census.declared_bytes,
        "rows": census.rows,
        "languages": dict(census.languages.most_common()),
        "resolved": dict(census.resolved.most_common()),
        "licenses": dict(census.licenses.most_common()),
        "python_resolved": census.python_resolved,
        "python_resolved_license_ok": census.python_resolved_license_ok,
        "excluded_repo_rows": dict(census.excluded_repo_rows),
        "top_repos_python_resolved": dict(census.per_repo_python_resolved.most_common(25)),
        "distinct_repos_python_resolved": len(census.per_repo_python_resolved),
        "tool_sets": census.tool_sets,
        "errors": census.errors,
        "disk_note": "no parquet file is persisted; columns are read over HTTP range requests",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Census a remote Open-SWE-Traces split.")
    parser.add_argument("--split", default="openhands")
    parser.add_argument(
        "--prefix",
        default=None,
        help="override the path prefix; default data/<split>/qwen38_flash_next",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="scan only the first N files, smallest first (0 = all)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="JSON output path; default under training/artifacts/reports",
    )
    args = parser.parse_args(argv)

    prefix = args.prefix or f"data/{args.split}/qwen38_flash_next"
    files = list_files(prefix)
    if args.max_files:
        files = files[: args.max_files]
    if not files:
        print(f"no parquet files under {prefix}")
        return 1

    census = Census(split=args.split)
    census.declared_bytes = sum(size for _, size in files)
    census.tool_sets = {"first-file": read_tool_set(files[0][0])}
    for path, _size in files:
        scan_file(path, census)

    out = args.out or (ARTIFACTS_DIR / "reports" / f"dataset_census_{args.split}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_report(census)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        f"{args.split}: {census.rows} rows from {census.files} files, "
        f"python+resolved={census.python_resolved}, "
        f"license-ok={census.python_resolved_license_ok}, "
        f"repos={len(census.per_repo_python_resolved)}, errors={len(census.errors)}"
    )
    print(f"wrote {out}")
    return 0 if not census.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
