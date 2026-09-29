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
import re
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

MAX_UNPACKED_BYTES = 3 * 1024**3
AGENT_MANIFEST = "agent.yaml"
EVAL_CONFIG = "eval_config.yaml"
STACK_DIR = "skills"
SKILL_MANIFEST = "SKILL.md"
FORBIDDEN_NAMES = frozenset({"agent.py"})

# Competition contract, traceable to ``AGENTS.md`` and
# ``docs/skill-stack-inventory.md`` section A (see PR #9 compliance table).
REQUIRED_SKILLS = 12
EXPECTED_MODEL = "gemma-4-31b-it-qat-w4a16-ct"
MAX_TOOL_CALLS = 100
MAX_TIME_MINUTES = 60
MAX_TURNS = 500
DYNAMIC_IMPORT_TOKENS = ("importlib", "__import__")
FORBIDDEN_PATTERNS = re.compile(
    r"https?://|socket|urllib|requests\.|pip install|uv add|mcp|subprocess|\bcurl\b|\bwget\b",
    re.IGNORECASE,
)
MODEL_LINE = re.compile(r"^\s*model:\s*(\S+)")
BUDGET_LINE = re.compile(
    r"^\s*(max_tool_calls|max_time_minutes|max_turns|timeout_seconds):\s*(\d+)"
)

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


def _read_text(path: Path) -> str:
    """Return *path* decoded as UTF-8, ignoring undecodable bytes."""
    return path.read_text(encoding="utf-8", errors="ignore")


def _check_declarative(source_dir: Path, files: Sequence[Path], violations: list[str]) -> None:
    """Rule a: declarative ``agent.yaml`` only, no code or dynamic imports."""
    if not (source_dir / AGENT_MANIFEST).is_file():
        violations.append(
            f"{AGENT_MANIFEST}: declarative manifest required at the archive root (rule a)"
        )
    for path in files:
        rel = path.relative_to(source_dir)
        if path.name in FORBIDDEN_NAMES:
            violations.append(f"{rel}: forbidden file in a declarative submission (rule a)")
        if path.suffix in {".py", ".yaml", ".yml"}:
            text = _read_text(path)
            for token in DYNAMIC_IMPORT_TOKENS:
                if token in text:
                    violations.append(f"{rel}: dynamic import '{token}' is not allowed (rule a)")


def _check_skills(source_dir: Path, violations: list[str]) -> None:
    """Rule b: exactly 12 skills, each shipping its own ``SKILL.md``."""
    stack = source_dir / STACK_DIR
    if not stack.is_dir():
        violations.append(f"{STACK_DIR}/: skill stack directory is required (rule b)")
        return
    skill_dirs = sorted(path for path in stack.iterdir() if path.is_dir())
    for skill_dir in skill_dirs:
        if not (skill_dir / SKILL_MANIFEST).is_file():
            violations.append(f"{STACK_DIR}/{skill_dir.name}: missing {SKILL_MANIFEST} (rule b)")
    if len(skill_dirs) != REQUIRED_SKILLS:
        violations.append(
            f"{STACK_DIR}/: expected {REQUIRED_SKILLS} skills, found {len(skill_dirs)} (rule b)"
        )


def _check_model(files: Sequence[Path], violations: list[str]) -> None:
    """Rule c: a single base model id, and the expected one."""
    model_ids: set[str] = set()
    for path in files:
        if path.suffix in {".yaml", ".yml"}:
            for line in _read_text(path).splitlines():
                match = MODEL_LINE.match(line)
                if match:
                    model_ids.add(match.group(1))
    if len(model_ids) != 1:
        found = ", ".join(sorted(model_ids)) or "none"
        violations.append(f"model: expected exactly one base model id, found [{found}] (rule c)")
    elif next(iter(model_ids)) != EXPECTED_MODEL:
        violations.append(
            f"model: expected '{EXPECTED_MODEL}', found '{next(iter(model_ids))}' (rule c)"
        )


def _check_budgets(source_dir: Path, violations: list[str]) -> None:
    """Rule d: per-task budgets declared and within the harness limits."""
    config = source_dir / EVAL_CONFIG
    if not config.is_file():
        violations.append(f"{EVAL_CONFIG}: required to declare per-task budgets (rule d)")
        return
    budget: dict[str, int] = {}
    for line in _read_text(config).splitlines():
        match = BUDGET_LINE.match(line)
        if match:
            budget[match.group(1)] = int(match.group(2))
    limits = (
        ("max_tool_calls", MAX_TOOL_CALLS),
        ("max_time_minutes", MAX_TIME_MINUTES),
        ("max_turns", MAX_TURNS),
    )
    for key, limit in limits:
        if key not in budget:
            violations.append(f"{EVAL_CONFIG}: missing {key} (rule d)")
        elif budget[key] > limit:
            violations.append(f"{EVAL_CONFIG}: {key}={budget[key]} exceeds limit {limit} (rule d)")


def _check_forbidden_strings(
    source_dir: Path, files: Sequence[Path], violations: list[str]
) -> None:
    """Rule e: no network, pip, MCP, or subprocess strings anywhere."""
    for path in files:
        rel = path.relative_to(source_dir)
        matches = FORBIDDEN_PATTERNS.finditer(_read_text(path))
        hits = sorted({match.group(0).lower() for match in matches})
        for hit in hits:
            violations.append(f"{rel}: forbidden string '{hit}' (rule e)")


def _check_size(
    source_dir: Path,
    files: Sequence[Path],
    max_unpacked_bytes: int,
    violations: list[str],
) -> None:
    """Rule f: the packed archive stays below the 3 GiB budget."""
    unpacked = total_unpacked_size(files) + len(load_agent_manifest(source_dir).encode("utf-8"))
    if unpacked >= max_unpacked_bytes:
        violations.append(
            f"submission: unpacked size {unpacked} bytes exceeds limit "
            f"{max_unpacked_bytes} bytes (rule f)"
        )


def check_submission(
    source_dir: Path, *, max_unpacked_bytes: int = MAX_UNPACKED_BYTES
) -> list[str]:
    """Validate the 6-point competition contract and return every violation.

    An empty list means the source tree is compliant. Each violation names the
    offending file and the contract rule (a-f) it breaks, mirroring the PR #9
    compliance table.
    """
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        return [f"{source_dir}: source directory does not exist (rule a)"]
    files = iter_source_files(source_dir)
    violations: list[str] = []
    _check_declarative(source_dir, files, violations)
    _check_skills(source_dir, violations)
    _check_model(files, violations)
    _check_budgets(source_dir, violations)
    _check_forbidden_strings(source_dir, files, violations)
    _check_size(source_dir, files, max_unpacked_bytes, violations)
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the submission packer."""
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-pack",
        description="Build submission.zip from a skill stack.",
    )
    parser.add_argument("source", nargs="?", default=".", type=Path)
    parser.add_argument("-o", "--output", default="submission.zip", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the 6-point submission contract instead of writing an archive",
    )
    args = parser.parse_args(argv)

    if args.check:
        violations = check_submission(args.source)
        if violations:
            for violation in violations:
                print(f"error: {violation}", file=sys.stderr)
            print(
                f"submission contract FAILED ({len(violations)} violation(s))",
                file=sys.stderr,
            )
            return 1
        print("submission contract OK (6/6 points)")
        return 0

    try:
        archive = build_submission(args.source, args.output)
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {archive} ({archive.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
