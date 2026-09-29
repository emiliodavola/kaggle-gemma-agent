"""Build ``submission.zip`` from a skill stack plus a minimal agent manifest.

The packer is intentionally dependency-free (stdlib only) so it can run inside
the air-gapped scored environment described in ``AGENTS.md`` without any network
access or package installation.

Archive layout::

    submission.zip
    ├── agent.yaml          # minimal manifest skeleton
    └── skill-stack/        # skill stack copied verbatim
        └── ...

Validation performed before writing the archive:

* the required root entry (``skill-stack/``) exists in the source directory;
* no file named ``agent.py`` is included;
* the total unpacked size stays strictly below the 3 GiB adapter budget.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

MAX_UNPACKED_BYTES = 3 * 1024**3
AGENT_MANIFEST = "agent.yaml"
STACK_DIR = "skill-stack"
FORBIDDEN_NAMES = frozenset({"agent.py"})

AGENT_YAML_SKELETON = """\
# Minimal agent manifest. Full content lands in a later phase.
name: kaggle-gemma-agent
version: "0.1.0"
skills: skill-stack
"""


class PackError(Exception):
    """Raised when the source tree cannot be packaged into a valid submission."""


def iter_source_files(source_dir: Path) -> list[Path]:
    """Return every regular file under *source_dir* that will be archived."""
    return sorted(path for path in source_dir.rglob("*") if path.is_file())


def total_unpacked_size(files: Sequence[Path]) -> int:
    """Return the summed size in bytes of *files*."""
    return sum(path.stat().st_size for path in files)


def find_forbidden_files(files: Sequence[Path]) -> list[Path]:
    """Return any file whose name is forbidden in a submission archive."""
    return [path for path in files if path.name in FORBIDDEN_NAMES]


def validate_source(source_dir: Path) -> None:
    """Validate the source tree and raise :class:`PackError` on any violation."""
    if not source_dir.is_dir():
        raise PackError(f"source directory does not exist: {source_dir}")
    missing = [name for name in (STACK_DIR,) if not (source_dir / name).exists()]
    if missing:
        raise PackError(f"missing required root entry: {', '.join(missing)}")
    forbidden = find_forbidden_files(iter_source_files(source_dir))
    if forbidden:
        names = ", ".join(str(path.relative_to(source_dir)) for path in forbidden)
        raise PackError(f"forbidden file(s) in submission: {names}")


def build_submission(
    source_dir: Path,
    output_path: Path,
    *,
    agent_manifest: str = AGENT_YAML_SKELETON,
    max_unpacked_bytes: int = MAX_UNPACKED_BYTES,
) -> Path:
    """Build *output_path* from *source_dir* and return its resolved path.

    ``agent_manifest`` is written verbatim at the archive root. Source files
    under ``skill-stack/`` are copied preserving their relative paths.
    """
    source_dir = Path(source_dir)
    output_path = Path(output_path)
    validate_source(source_dir)

    files = iter_source_files(source_dir)
    unpacked = total_unpacked_size(files) + len(agent_manifest.encode("utf-8"))
    if unpacked >= max_unpacked_bytes:
        raise PackError(
            f"unpacked size {unpacked} bytes exceeds limit of {max_unpacked_bytes} bytes"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(AGENT_MANIFEST, agent_manifest)
        for path in files:
            arcname = path.relative_to(source_dir)
            if str(arcname) == AGENT_MANIFEST:
                continue
            archive.write(path, arcname=str(arcname))

    return output_path.resolve()


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the submission packer."""
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-pack",
        description="Build submission.zip from a skill stack.",
    )
    parser.add_argument("source", nargs="?", default=".", type=Path)
    parser.add_argument("-o", "--output", default="submission.zip", type=Path)
    args = parser.parse_args(argv)

    try:
        archive = build_submission(args.source, args.output)
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {archive} ({archive.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
