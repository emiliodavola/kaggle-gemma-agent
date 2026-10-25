"""Select which system prompt is materialized into ``prompts/system.md``.

The ADK declarative manifest binds its instruction with a static
``!include prompts/system.md`` and cannot read a YAML variable. This module is
the indirection: ``configs/prompt_variant.yaml`` names a variant, and
:func:`apply_variant` copies that variant over the active prompt so the packed
archive and a local trial see the same text.

``v3`` is the shipped text, so it aliases the active prompt instead of owning a
second file with the same bytes; see issue #90. ``legacy`` and ``v2`` keep their
own files and are copied on demand.

Stdlib only, mirroring :mod:`kaggle_gemma_agent.pack`.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

SELECTOR = Path("configs/prompt_variant.yaml")
ACTIVE_PROMPT = Path("prompts/system.md")
VARIANTS: dict[str, Path] = {
    "legacy": Path("prompts/system.legacy.md"),
    "v2": Path("prompts/system.v2.md"),
    "v3": ACTIVE_PROMPT,
}
VARIANT_LINE = re.compile(r"^\s*variant:\s*(\S+)")


class PromptVariantError(Exception):
    """Raised when the selector is missing, invalid, or a variant is absent."""


def has_selector(source_dir: Path) -> bool:
    """Return whether *source_dir* ships a prompt-variant selector."""
    return (Path(source_dir) / SELECTOR).is_file()


def read_variant(source_dir: Path) -> str:
    """Return the variant selected in *source_dir*.

    Raises :class:`PromptVariantError` when the selector is missing, declares no
    ``variant:`` line, or names a variant outside :data:`VARIANTS`.
    """
    selector = Path(source_dir) / SELECTOR
    if not selector.is_file():
        raise PromptVariantError(f"{SELECTOR}: selector file is required")
    for line in selector.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = VARIANT_LINE.match(line)
        if match:
            name = match.group(1).strip().strip("'\"")
            if name not in VARIANTS:
                allowed = ", ".join(sorted(VARIANTS))
                raise PromptVariantError(
                    f"{SELECTOR}: unknown variant '{name}' (allowed: {allowed})"
                )
            return name
    raise PromptVariantError(f"{SELECTOR}: no 'variant:' line found")


def variant_path(source_dir: Path, name: str) -> Path:
    """Return the prompt file that backs *name* inside *source_dir*."""
    return Path(source_dir) / VARIANTS[name]


def active_prompt_path(source_dir: Path) -> Path:
    """Return the active ``prompts/system.md`` path inside *source_dir*."""
    return Path(source_dir) / ACTIVE_PROMPT


def _path_key(path: Path) -> str:
    """Return a comparison key ignoring relative/absolute form and Windows case."""
    return os.path.normcase(str(Path(path).resolve()))


def _same_file(first: Path, second: Path) -> bool:
    """Return whether *first* and *second* denote the same file.

    ``os.path.samefile`` requires both paths to exist; the resolved-key fallback
    covers a missing active prompt, which callers must handle explicitly.
    """
    try:
        return os.path.samefile(first, second)
    except OSError:
        return _path_key(first) == _path_key(second)


def is_active(source_dir: Path) -> bool:
    """Return whether the active prompt already matches the selected variant."""
    source_dir = Path(source_dir)
    name = read_variant(source_dir)
    variant = variant_path(source_dir, name)
    active = active_prompt_path(source_dir)
    if _same_file(variant, active):
        return active.is_file()
    if not (variant.is_file() and active.is_file()):
        return False
    return variant.read_bytes() == active.read_bytes()


def apply_variant(source_dir: Path) -> tuple[str, Path]:
    """Copy the selected variant over ``prompts/system.md``.

    Returns ``(variant_name, active_path)``. A variant that aliases the active
    prompt is a no-op: it returns without copying, so no
    :class:`shutil.SameFileError` is possible. Raises
    :class:`PromptVariantError` when a copy-backed variant file is absent, or
    when an aliased variant finds no active prompt to stand for it.
    """
    source_dir = Path(source_dir)
    name = read_variant(source_dir)
    variant = variant_path(source_dir, name)
    active = active_prompt_path(source_dir)
    if _same_file(variant, active):
        if not active.is_file():
            raise PromptVariantError(f"{ACTIVE_PROMPT}: active prompt not found")
        return name, active
    if not variant.is_file():
        raise PromptVariantError(f"{VARIANTS[name]}: variant file not found")
    active.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(variant, active)
    return name, active


def duplicate_variants(source_dir: Path) -> list[tuple[str, str]]:
    """Return the variant-name pairs whose prompt bytes are identical.

    Copy-backed variants are always compared with each other. The active prompt
    joins the comparison as ``active`` only while the selector names an alias,
    because it mirrors whichever variant was materialized: comparing it against
    a selected copy-backed variant would match after every ``apply`` and report
    a duplicate that is just the materialized selection.
    """
    source_dir = Path(source_dir)
    active = active_prompt_path(source_dir)
    candidates = [
        (name, variant_path(source_dir, name))
        for name in VARIANTS
        if not _same_file(variant_path(source_dir, name), active)
    ]
    if _same_file(variant_path(source_dir, read_variant(source_dir)), active):
        candidates.append(("active", active))
    candidates.sort()

    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str]] = []
    for name, path in candidates:
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            duplicates.append((seen[digest], name))
        else:
            seen[digest] = name
    return duplicates


def _print_variants() -> None:
    for name, relative in sorted(VARIANTS.items()):
        print(f"{name}\t{relative}")


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the prompt-variant selector."""
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-prompt-variant",
        description="Show or apply the system prompt variant selected by YAML.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=("show", "apply", "list"),
        default="show",
        help="show the selection (default), apply it, or list the variants",
    )
    parser.add_argument("--cwd", default="submission", type=Path, help="submission source root")
    args = parser.parse_args(argv)

    if args.action == "list":
        _print_variants()
        return 0

    try:
        name = read_variant(args.cwd)
    except PromptVariantError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    active = active_prompt_path(args.cwd)
    aliased = _same_file(variant_path(args.cwd, name), active)

    if args.action == "show":
        if aliased:
            if not active.is_file():
                print(
                    f"variant: {name} -> {VARIANTS[name]} | {ACTIVE_PROMPT}: MISSING",
                    file=sys.stderr,
                )
                return 1
            state = "active (no copy needed)"
            print(f"variant: {name} -> {VARIANTS[name]} | {ACTIVE_PROMPT}: {state}")
            return 0
        state = "in sync" if is_active(args.cwd) else "OUT OF SYNC (run 'apply')"
        print(f"variant: {name} -> {VARIANTS[name]} | {ACTIVE_PROMPT}: {state}")
        return 0

    try:
        name, active = apply_variant(args.cwd)
    except PromptVariantError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if aliased:
        print(f"variant '{name}' is already the active prompt ({active})")
    else:
        print(f"applied variant '{name}' to {active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
