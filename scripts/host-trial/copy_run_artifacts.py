#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Copy the host-trial artifacts a WSL run leaves behind into a Windows checkout.

A representative host trial runs inside WSL2 (runbook section 1.5), so
``results/``, ``runs/`` and the journal entries land in the distro's
filesystem. The analysis, the documentation edits and the archiver all run on
Windows, which can reach the distro filesystem either as
``\\\\wsl.localhost\\<distro>\\home\\<you>\\<repo>`` or as ``/mnt/c/...`` from
inside WSL. Both roots are arguments, so the same script works in either
direction and on either side::

    # from Windows, reading the distro through its UNC share
    uv run python scripts/host-trial/copy_run_artifacts.py `
        --source "\\\\wsl.localhost\\Ubuntu\\home\\elaze\\kaggle-gemma-agent" `
        --dest "C:\\Users\\elaze\\Desktop\\robotina-data\\workspace\\kaggle-gemma-agent"

    # from inside WSL, writing the Windows checkout through /mnt/c
    uv run python scripts/host-trial/copy_run_artifacts.py `
        --source /home/elaze/kaggle-gemma-agent `
        --dest /mnt/c/Users/elaze/Desktop/robotina-data/workspace/kaggle-gemma-agent

Only ``docs/journal/``, ``results/`` and ``runs/`` are copied, never the whole
repository. The copy is incremental: a file is written only when the
destination is missing, its size differs, or the source is newer, and
``copy2`` preserves the mtime so a re-run skips what it already copied.
``--dry-run`` prints the same report without writing anything.

Exit codes: ``0`` success (including "nothing to copy"), ``2`` usage or
source/destination error.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

#: Repository-relative directories that hold a run's evidence.
ARTIFACT_DIRS: tuple[str, ...] = ("docs/journal", "results", "runs")

#: Filesystem mtime granularity differs between the distro (ext4) and Windows
#: (NTFS, and coarser through the 9p share), so a source is only considered
#: newer when it beats the destination by more than this many seconds.
MTIME_TOLERANCE_SECONDS = 1.0


class CopyError(Exception):
    """Raised when the source or destination cannot be used for a copy."""


@dataclass(frozen=True)
class CopiedFile:
    """One repository-relative file that was copied (or would be, in a dry run)."""

    relative: str
    size: int


@dataclass(frozen=True)
class TreeSummary:
    """Result of syncing one artifact directory."""

    name: str
    copied: tuple[CopiedFile, ...] = ()
    unchanged: int = 0
    missing: bool = False

    @property
    def copied_bytes(self) -> int:
        """Return the total size of the copied files in this tree."""
        return sum(entry.size for entry in self.copied)


@dataclass(frozen=True)
class CopySummary:
    """Result of syncing every artifact directory from one repository root."""

    source: Path
    dest: Path
    trees: tuple[TreeSummary, ...]
    dry_run: bool

    @property
    def copied_files(self) -> int:
        """Return how many files were copied (or would be, in a dry run)."""
        return sum(len(tree.copied) for tree in self.trees)

    @property
    def copied_bytes(self) -> int:
        """Return the total size of the copied files."""
        return sum(tree.copied_bytes for tree in self.trees)

    @property
    def unchanged_files(self) -> int:
        """Return how many destination files were already current."""
        return sum(tree.unchanged for tree in self.trees)

    @property
    def missing_trees(self) -> tuple[str, ...]:
        """Return the artifact directories the source does not have."""
        return tuple(tree.name for tree in self.trees if tree.missing)


def files_under(root: Path) -> tuple[Path, ...]:
    """Return every regular file under *root*, sorted by path for a stable report."""
    return tuple(sorted(path for path in Path(root).rglob("*") if path.is_file()))


def needs_copy(source_file: Path, dest_file: Path) -> bool:
    """Return whether *source_file* must be written over *dest_file*.

    A missing destination always needs a copy. Otherwise the size and the
    mtime decide: an identical size with the source no more than
    :data:`MTIME_TOLERANCE_SECONDS` newer is treated as already copied, which
    is what ``copy2`` leaves behind and keeps a re-run cheap.
    """
    try:
        dest_stat = Path(dest_file).stat()
    except FileNotFoundError:
        return True
    source_stat = Path(source_file).stat()
    if dest_stat.st_size != source_stat.st_size:
        return True
    return source_stat.st_mtime - dest_stat.st_mtime > MTIME_TOLERANCE_SECONDS


def _posix(relative: Path) -> str:
    """Render a repository-relative path with ``/`` separators on every OS."""
    return "/".join(relative.parts)


def _validate_roots(source: Path, dest: Path) -> None:
    """Fail fast on a missing source, an unrelated source, or overlapping roots."""
    if not source.is_dir():
        raise CopyError(f"source repository not found: {source}")
    if not any((source / name).is_dir() for name in ARTIFACT_DIRS):
        raise CopyError(
            f"source has none of {', '.join(ARTIFACT_DIRS)} under {source}; "
            "pass the repository root of the checkout that ran the trial as --source"
        )
    source_root = source.resolve()
    dest_root = dest.resolve()
    if source_root == dest_root:
        raise CopyError(f"source and dest are the same directory: {source}")
    if dest_root.is_relative_to(source_root) or source_root.is_relative_to(dest_root):
        raise CopyError(
            f"source and dest overlap ({source} -> {dest}); pass two separate "
            "repository roots so the copy cannot recurse into itself"
        )


def copy_artifacts(
    source: Path,
    dest: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> CopySummary:
    """Sync the artifact directories from *source* into *dest*.

    Raises :class:`CopyError` when *source* is missing or holds none of
    :data:`ARTIFACT_DIRS`, and when both roots are the same or overlap. A
    source directory that is absent is reported as missing, not as an error, so
    a run that produced no ``results/`` yet still syncs its journal.
    """
    source = Path(source)
    dest = Path(dest)
    _validate_roots(source, dest)

    trees: list[TreeSummary] = []
    for name in ARTIFACT_DIRS:
        tree_source = source / name
        if not tree_source.is_dir():
            trees.append(TreeSummary(name=name, missing=True))
            continue
        copied: list[CopiedFile] = []
        unchanged = 0
        for file_path in files_under(tree_source):
            relative = file_path.relative_to(source)
            target = dest / relative
            if not force and not needs_copy(file_path, target):
                unchanged += 1
                continue
            size = file_path.stat().st_size
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, target)
            copied.append(CopiedFile(relative=_posix(relative), size=size))
        trees.append(TreeSummary(name=name, copied=tuple(copied), unchanged=unchanged))
    return CopySummary(source=source, dest=dest, trees=tuple(trees), dry_run=dry_run)


def _human_bytes(size: int) -> str:
    """Render a byte count with one decimal and a binary unit suffix."""
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    raise AssertionError("unreachable")


def format_summary(summary: CopySummary) -> str:
    """Render the human-readable report a run prints (and a dry run previews)."""
    verb = "would copy" if summary.dry_run else "copied"
    mode = "dry run (nothing written)" if summary.dry_run else "copy"
    lines = [
        f"source: {summary.source}",
        f"dest:   {summary.dest}",
        f"mode:   {mode}",
        "",
    ]
    for tree in summary.trees:
        if tree.missing:
            lines.append(f"  {tree.name:<14} not present in source (skipped)")
            continue
        lines.append(
            f"  {tree.name:<14} {verb} {len(tree.copied)} file(s), "
            f"{_human_bytes(tree.copied_bytes)}, {tree.unchanged} unchanged"
        )
    lines.append(
        f"  {'total':<14} {verb} {summary.copied_files} file(s), "
        f"{_human_bytes(summary.copied_bytes)}, {summary.unchanged_files} unchanged"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: copy the three artifact trees between roots."""
    parser = argparse.ArgumentParser(
        prog="copy_run_artifacts.py",
        description=(
            "Copy docs/journal/, results/ and runs/ from a WSL checkout of this "
            "repository into a Windows checkout (or the reverse)."
        ),
        epilog=(
            "Windows reaches the distro filesystem as "
            "\\\\wsl.localhost\\<distro>\\home\\<you>\\<repo>; WSL reaches the "
            "Windows checkout as /mnt/c/.... The copy is incremental; --dry-run "
            "prints the plan without writing."
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="repository root that produced the run (the WSL checkout)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        required=True,
        help="repository root to copy into (the Windows checkout)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be copied and write nothing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="copy every source file even when the destination already matches",
    )
    args = parser.parse_args(argv)

    try:
        summary = copy_artifacts(
            args.source,
            args.dest,
            dry_run=args.dry_run,
            force=args.force,
        )
    except CopyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
