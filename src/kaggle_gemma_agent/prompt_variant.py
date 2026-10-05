"""Select which system prompt is materialized into ``prompts/system.md``.

The ADK declarative manifest binds its instruction with a static
``!include prompts/system.md`` and cannot read a YAML variable. This module is
the indirection: ``configs/prompt_variant.yaml`` names a variant, and
:func:`apply_variant` copies that variant over the active prompt so the packed
archive and a local trial see the same text.

Stdlib only, mirroring :mod:`kaggle_gemma_agent.pack`.
"""

from __future__ import annotations

import argparse
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
    "v3": Path("prompts/system.v3.md"),
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


def is_active(source_dir: Path) -> bool:
    """Return whether the active prompt already matches the selected variant."""
    name = read_variant(source_dir)
    variant = variant_path(source_dir, name)
    active = active_prompt_path(source_dir)
    return variant.is_file() and active.is_file() and variant.read_bytes() == active.read_bytes()


def apply_variant(source_dir: Path) -> tuple[str, Path]:
    """Copy the selected variant over ``prompts/system.md``.

    Returns ``(variant_name, active_path)``. Raises
    :class:`PromptVariantError` when the variant file is absent.
    """
    source_dir = Path(source_dir)
    name = read_variant(source_dir)
    variant = variant_path(source_dir, name)
    if not variant.is_file():
        raise PromptVariantError(f"{VARIANTS[name]}: variant file not found")
    active = active_prompt_path(source_dir)
    active.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(variant, active)
    return name, active


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

    if args.action == "show":
        state = "in sync" if is_active(args.cwd) else "OUT OF SYNC (run 'apply')"
        print(f"variant: {name} -> {VARIANTS[name]} | {ACTIVE_PROMPT}: {state}")
        return 0

    try:
        name, active = apply_variant(args.cwd)
    except PromptVariantError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"applied variant '{name}' to {active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
