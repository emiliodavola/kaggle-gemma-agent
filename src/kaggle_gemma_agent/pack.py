"""Build ``submission.zip`` from a skill stack plus a minimal agent manifest.

The packer is intentionally dependency-free (stdlib only) so it can run inside
the air-gapped scored environment described in ``AGENTS.md`` without any network
access or package installation.

Archive layout::

    submission.zip
    ├── agent.yaml          # declarative manifest (read from the source root)
    ├── eval_config.yaml    # optional per-task budgets
    ├── configs/            # sampling / generation config
    ├── prompts/            # ``!include`` targets
    ├── sub_agents/         # optional AgentTool configs
    └── skills/             # skill stack copied verbatim
        └── <skill>/SKILL.md

Validation performed before writing the archive:

* the required root entry (``skills/``) exists in the source directory;
* no file named ``agent.py`` is included;
* the total unpacked size stays strictly below the 3 GiB adapter budget.

``agent.yaml`` is read from the source root when present, so the shipped
manifest lives under ``submission/`` instead of being hard-coded here.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

MAX_UNPACKED_BYTES = 3 * 1024**3
AGENT_MANIFEST = "agent.yaml"
STACK_DIR = "skills"
FORBIDDEN_NAMES = frozenset({"agent.py"})

# Fallback used only when the source tree ships no ``agent.yaml``; the shipped
# manifest is ``submission/agent.yaml``.
AGENT_YAML_SKELETON = """\
name: kaggle_gemma_agent
model: gemma-4-31b-it-qat-w4a16-ct
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


def load_agent_manifest(source_dir: Path, override: str | None = None) -> str:
    """Return the manifest text to write at the archive root.

    *override* wins when provided. Otherwise ``agent.yaml`` at the source root
    is used, falling back to :data:`AGENT_YAML_SKELETON` when absent.
    """
    if override is not None:
        return override
    candidate = source_dir / AGENT_MANIFEST
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return AGENT_YAML_SKELETON


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
    agent_manifest: str | None = None,
    max_unpacked_bytes: int = MAX_UNPACKED_BYTES,
) -> Path:
    """Build *output_path* from *source_dir* and return its resolved path.

    The manifest is read from *source_dir* unless ``agent_manifest`` overrides
    it, then written verbatim at the archive root. Source files under
    ``skills/`` are copied preserving their relative paths.
    """
    source_dir = Path(source_dir)
    output_path = Path(output_path)
    validate_source(source_dir)
    manifest = load_agent_manifest(source_dir, agent_manifest)

    files = iter_source_files(source_dir)
    unpacked = total_unpacked_size(files) + len(manifest.encode("utf-8"))
    if unpacked >= max_unpacked_bytes:
        raise PackError(
            f"unpacked size {unpacked} bytes exceeds limit of {max_unpacked_bytes} bytes"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(AGENT_MANIFEST, manifest)
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
