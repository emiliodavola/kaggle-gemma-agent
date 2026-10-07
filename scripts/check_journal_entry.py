"""CI guard: a PR that touches guarded paths must ship a change-journal entry.

The guard diffs ``<base>...<head>`` and fails when the change touches a guarded
path -- ``submission/``, ``docs/``, ``scripts/host-trial/`` or the files
``src/kaggle_gemma_agent/harness_runs.py`` and
``src/kaggle_gemma_agent/run_report.py`` -- while changing nothing under
``docs/journal/``. A pull request may carry the escape token ``[no-journal]`` in
its title or body to bypass the gate with a warning; the token must be justified
in the PR body (see ``docs/journal/README.md``).

Stdlib only and read-only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

GUARDED_PREFIXES = ("submission/", "docs/", "scripts/host-trial/")
GUARDED_FILES = (
    "src/kaggle_gemma_agent/harness_runs.py",
    "src/kaggle_gemma_agent/run_report.py",
)
JOURNAL_PREFIX = "docs/journal/"
DEFAULT_ESCAPE_TOKEN = "[no-journal]"


class GuardError(RuntimeError):
    """Raised when the underlying ``git diff`` cannot be computed."""


def diff_paths(base: str, head: str) -> list[str]:
    """Return the paths changed by ``base...head`` via ``git diff --name-only``."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git diff failed"
        raise GuardError(f"cannot diff {base}...{head}: {message}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def is_guarded(path: str) -> bool:
    """Return whether *path* requires a journal entry when it changes."""
    return path.startswith(GUARDED_PREFIXES) or path in GUARDED_FILES


def _escape_used(args: argparse.Namespace, body: str) -> bool:
    text = f"{args.pr_title or ''}\n{body}"
    return args.no_journal_token in text


def _load_body(path: str | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardError(f"cannot read PR body {path}: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check-journal-entry",
        description="Fail when a PR touches guarded paths without a journal entry.",
    )
    parser.add_argument("--base", required=True, help="base ref of the diff, e.g. origin/main")
    parser.add_argument("--head", required=True, help="head ref of the diff, e.g. HEAD")
    parser.add_argument("--pr-body-file", help="path to a file holding the PR body")
    parser.add_argument("--pr-title", default="", help="the PR title")
    parser.add_argument(
        "--no-journal-token",
        default=DEFAULT_ESCAPE_TOKEN,
        help=f"escape token checked in the PR title/body (default: {DEFAULT_ESCAPE_TOKEN})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the journal guard and return the process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        body = _load_body(args.pr_body_file)
        if _escape_used(args, body):
            print(
                f"journal guard: escape token {args.no_journal_token!r} in the PR title/body.",
                file=sys.stderr,
            )
            print(
                "journal guard: change-journal gate SKIPPED; justify the escape in the PR body.",
                file=sys.stderr,
            )
            return 0
        paths = diff_paths(args.base, args.head)
    except GuardError as exc:
        print(f"journal guard: {exc}", file=sys.stderr)
        return 2

    guarded = sorted(path for path in paths if is_guarded(path))
    journal_changed = any(path.startswith(JOURNAL_PREFIX) for path in paths)
    if guarded and not journal_changed:
        print("journal guard: guarded paths changed without a journal entry.", file=sys.stderr)
        print("Guarded paths changed:", file=sys.stderr)
        for path in guarded:
            print(f"  {path}", file=sys.stderr)
        print(
            "Missing: an entry under docs/journal/ (docs/journal/events.jsonl).",
            file=sys.stderr,
        )
        print(
            "Add one with `uv run python -m kaggle_gemma_agent.journal add ...`, "
            f"or justify the escape in the PR body with {args.no_journal_token}.",
            file=sys.stderr,
        )
        return 1

    print(f"journal guard: OK ({len(guarded)} guarded, {len(paths)} changed paths).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
