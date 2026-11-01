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

``check_submission`` validates the 6-point competition contract (rules a-f).
``check_harness_surface`` validates the harness surface next to it (rules s1-s3):
every shipped skill is named in the always-on prompt, that prompt stays under
:data:`MAX_ALWAYS_ON_CHARS`, and every ``scripts/<file>.py`` a skill references
is actually shipped. ``check_answer_leak`` adds a third, independent layer: no
shipped file may carry a grader-specific literal such as an instance id, a test
node id, a ``test_*.py`` path or a ``FAIL_TO_PASS``/``PASS_TO_PASS`` marker. The
three layers are independent: the contract keeps its ``6/6`` meaning and its
messages.

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
SYSTEM_PROMPT = "prompts/system.md"
EVAL_CONFIG = "eval_config.yaml"
STACK_DIR = "skills"
SCRIPTS_DIR = "scripts"
SKILL_MANIFEST = "SKILL.md"
FORBIDDEN_NAMES = frozenset({"agent.py"})

# Competition contract, traceable to ``AGENTS.md`` and
# ``docs/skill-stack-inventory.md`` section A (see PR #9 compliance table).
REQUIRED_SKILLS = 12
# The four quantized competition models ("Model Selection, Budget, and Harness
# Rules", read 2026-10-31). A submission declares exactly one of them and every
# agent in it must use that same variant; mixing variants is a violation.
ALLOWED_MODELS = frozenset(
    {
        "gemma-4-31b-it-qat-w4a16-ct",
        "gemma-4-12b-it-qat-w4a16-ct",
        "gemma-4-e4b-it-qat-w4a16-ct",
        "gemma-4-e2b-it-qat-w4a16-ct",
    }
)
#: Starter-kit default, and the model the shipped ``submission/`` used until the
#: 2026-10-31 E4B baseline run. Kept because tests and messages name it.
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

# Harness-surface layer (rules s1-s3), complementary to the 6-point contract.
#
# Per-turn prefix budget. The active prompt is 5 364 chars today; this cap is
# 4.4x that, which keeps the always-on prefix near 6 000 tokens at the common
# 4-chars-per-token heuristic. That prefix is paid on every turn of every task
# (up to 500 turns), so an unbounded prompt is the most expensive regression
# this gate can catch; the twelve skills already have a line budget in
# tests/test_skills.py and this closes the same gap for the always-on text.
MAX_ALWAYS_ON_CHARS = 24_000
# A ``scripts/<file>.py`` path token, and only that: a bare ``scripts/`` prose
# mention, an absolute scratch path such as ``/tmp/scripts/x.py``, a nested
# ``foo/scripts/x.py``, or a module reference never matches.
SCRIPT_REF = re.compile(r"(?<![\w./-])(?:\./)?scripts/([A-Za-z0-9_.-]+\.py)")

# Answer-leak layer (issue #91): literals that encode a grader target into
# shipped content. The tuple order is the within-line emission order.
ANSWER_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:requests|httpx|fastapi|rich|pydantic|django)_\d{3,}\b"),
    re.compile(r"::test_"),
    re.compile(r"\btests?/test_[A-Za-z0-9_]+\.py\b"),
    re.compile(r"\b(?:FAIL_TO_PASS|PASS_TO_PASS)\b"),
)

#: Suffixes scanned for leaks; mirrors Harness2 ``_MARKER_SCAN_SUFFIXES`` plus
#: ``.jsonl``. Everything else (model weights, archives, images) is skipped.
_LEAK_SCAN_SUFFIXES: frozenset[str] = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".jsonl",
        ".csv",
        ".tsv",
        ".yaml",
        ".yml",
        ".html",
        ".htm",
        ".log",
        ".py",
        ".js",
        ".sh",
        ".xml",
        ".ini",
        ".toml",
        ".patch",
        ".diff",
        "",
    }
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
    """Rule c: a single base model id, drawn from the permitted set."""
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
        return
    declared = next(iter(model_ids))
    if declared not in ALLOWED_MODELS:
        allowed = ", ".join(sorted(ALLOWED_MODELS))
        violations.append(
            f"model: '{declared}' is not a permitted competition model; "
            f"expected one of [{allowed}] (rule c)"
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


def _always_on_prompt(source_dir: Path, violations: list[str]) -> tuple[Path, str] | None:
    """Return the resolved always-on prompt and its text, or ``None``.

    The manifest injects ``prompts/system.md`` with a static ``!include``, so the
    whole decoded file is the always-on text; nothing is stripped. A missing
    file appends one violation and returns ``None`` so the caller skips rules s1
    and s2.
    """
    prompt_path = Path(source_dir) / SYSTEM_PROMPT
    if not prompt_path.is_file():
        violations.append(
            f"{prompt_path.relative_to(source_dir)}: always-on prompt not found (rules s1/s2)"
        )
        return None
    return prompt_path.relative_to(source_dir), _read_text(prompt_path)


def _check_skill_naming(source_dir: Path, prompt: tuple[Path, str], violations: list[str]) -> None:
    """Rule s1: every shipped skill is named in the always-on text."""
    stack = source_dir / STACK_DIR
    if not stack.is_dir():
        return
    prompt_rel, text = prompt
    for skill_dir in sorted(path for path in stack.iterdir() if path.is_dir()):
        if not (skill_dir / SKILL_MANIFEST).is_file():
            continue
        if skill_dir.name not in text:
            violation_file = Path(STACK_DIR, skill_dir.name, SKILL_MANIFEST)
            violations.append(
                f"{violation_file}: skill '{skill_dir.name}' is not named in {prompt_rel} (rule s1)"
            )


def _check_always_on_size(prompt: tuple[Path, str], violations: list[str]) -> None:
    """Rule s2: the always-on text stays within the per-turn character budget."""
    prompt_rel, text = prompt
    if len(text) > MAX_ALWAYS_ON_CHARS:
        violations.append(
            f"{prompt_rel}: always-on prompt is {len(text)} chars, exceeds "
            f"{MAX_ALWAYS_ON_CHARS} (rule s2)"
        )


def _missing_scripts(source_dir: Path, text: str) -> list[str]:
    """Return the referenced script basenames absent from ``scripts/``, in order."""
    missing: list[str] = []
    seen: set[str] = set()
    for match in SCRIPT_REF.finditer(text):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        if not (source_dir / SCRIPTS_DIR / name).is_file():
            missing.append(name)
    return missing


def _check_script_refs(
    source_dir: Path, prompt: tuple[Path, str] | None, violations: list[str]
) -> None:
    """Rule s3: every referenced ``scripts/<file>.py`` ships in the archive."""
    sources: list[tuple[Path, str]] = []
    if prompt is not None:
        sources.append(prompt)
    stack = source_dir / STACK_DIR
    if stack.is_dir():
        for skill_dir in sorted(path for path in stack.iterdir() if path.is_dir()):
            manifest = skill_dir / SKILL_MANIFEST
            if manifest.is_file():
                sources.append((manifest.relative_to(source_dir), _read_text(manifest)))
    for rel, text in sources:
        for name in _missing_scripts(source_dir, text):
            violations.append(f"{rel}: references missing script '{SCRIPTS_DIR}/{name}' (rule s3)")


def check_harness_surface(source_dir: Path) -> list[str]:
    """Validate the harness surface (rules s1-s3) and return every violation.

    An empty list means the surface is compliant. Rules, in emission order:

    * s1: every ``skills/<name>/SKILL.md`` has ``<name>`` in the always-on text;
    * s2: that text is at most :data:`MAX_ALWAYS_ON_CHARS` characters;
    * s3: every ``scripts/<file>.py`` referenced by a skill body or the always-on
      text exists at ``scripts/<file>.py`` in the source tree.

    The always-on text is ``prompts/system.md``. This function is read-only: it
    never writes.
    """
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        return [f"{source_dir}: source directory does not exist (harness surface)"]
    violations: list[str] = []
    prompt = _always_on_prompt(source_dir, violations)
    if prompt is not None:
        _check_skill_naming(source_dir, prompt, violations)
        _check_always_on_size(prompt, violations)
    _check_script_refs(source_dir, prompt, violations)
    return violations


def check_answer_leak(source_dir: Path) -> list[str]:
    """Reject shipped content that encodes a grader answer (issue #91).

    An empty list means no leak was found. The scan is a literal deny-list over
    the shipped tree: every :data:`ANSWER_LEAK_PATTERNS` match in a file name is
    a violation without a line number, and every match in the content of a file
    whose suffix is in :data:`_LEAK_SCAN_SUFFIXES` is a violation with its
    1-based line number. Violations are emitted in path order, then file name,
    then content: line, pattern order, match position. Duplicate matches for the
    same ``(path, line, literal)`` are reported once.

    This function is read-only and never raises for a missing, unreadable or
    binary file.
    """
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        return [f"{source_dir}: source directory does not exist (answer leak)"]
    violations: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for path in iter_source_files(source_dir):
        rel = path.relative_to(source_dir).as_posix()
        for pattern in ANSWER_LEAK_PATTERNS:
            for match in pattern.finditer(rel):
                key = (rel, "name", match.group(0))
                if key in seen:
                    continue
                seen.add(key)
                violations.append(f"{rel}: answer leak in file name '{match.group(0)}'")
        if path.suffix.lower() not in _LEAK_SCAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in ANSWER_LEAK_PATTERNS:
                for match in pattern.finditer(line):
                    key = (rel, str(line_number), match.group(0))
                    if key in seen:
                        continue
                    seen.add(key)
                    violations.append(f"{rel}:{line_number}: answer leak '{match.group(0)}'")
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
        help=(
            "validate the contract, the harness surface and answer leaks "
            "instead of writing an archive"
        ),
    )
    args = parser.parse_args(argv)

    if args.check:
        contract = check_submission(args.source)
        surface = check_harness_surface(args.source)
        leak = check_answer_leak(args.source)
        for violation in contract:
            print(f"error: {violation}", file=sys.stderr)
        if contract:
            print(
                f"submission contract FAILED ({len(contract)} violation(s))",
                file=sys.stderr,
            )
        else:
            print("submission contract OK (6/6 points)")
        for violation in surface:
            print(f"error: {violation}", file=sys.stderr)
        if surface:
            print(
                f"harness surface FAILED ({len(surface)} violation(s))",
                file=sys.stderr,
            )
        else:
            print("harness surface OK (3 checks)")
        for violation in leak:
            print(f"error: {violation}", file=sys.stderr)
        if leak:
            print(
                f"answer leak FAILED ({len(leak)} violation(s))",
                file=sys.stderr,
            )
        else:
            print(f"answer leak OK ({len(ANSWER_LEAK_PATTERNS)} patterns)")
        return 1 if contract or surface or leak else 0

    try:
        archive = build_submission(args.source, args.output)
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {archive} ({archive.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
