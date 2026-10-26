"""Fixed task subsets used to compare two harnesses on the same batch.

A subset is a committed JSON document under ``experiments/subsets/``. It names a
stable list of ``swegemma`` instance ids and records the per-repository counts
that selection produced. The document is the source of truth; the corpus under
``data/raw/tasks.jsonl`` is only used to validate it, so the module keeps working
on a fresh clone where that git-ignored file is absent.

The subset is a *contrast set*, not a resolution-rate estimate: a fixed list is
what makes two runs comparable, and a list chosen for signal is not a random
sample of the 129 public tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SUBSET_DIR = Path("experiments") / "subsets"

#: The exact key set of a subset document. Unknown keys are rejected so the
#: format cannot drift silently between a writer and its readers.
REQUIRED_KEYS: tuple[str, ...] = (
    "schema_version",
    "id",
    "description",
    "selection",
    "task_ids",
    "counts",
)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
#: Repository root resolved from this package's location.
REPO_ROOT = Path(__file__).resolve().parents[2]


class SubsetError(Exception):
    """Raised when a subset cannot be resolved, parsed or validated."""


@dataclass(frozen=True)
class Subset:
    """One validated subset document and the digest of its bytes."""

    id: str
    path: Path
    sha256: str
    task_ids: tuple[str, ...]
    counts: dict[str, int]
    description: str
    selection: str
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON-shaped body, without the path and the digest."""
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "description": self.description,
            "selection": self.selection,
            "task_ids": list(self.task_ids),
            "counts": dict(self.counts),
        }

    def identity(self) -> dict[str, Any]:
        """Return the identity a run records in its manifest."""
        return {
            "id": self.id,
            "sha256": self.sha256,
            "task_ids": list(self.task_ids),
            "counts": dict(self.counts),
        }


def repo_root(root: Path | None = None) -> Path:
    """Return *root*, or the repository root that contains this package."""
    return Path(root) if root is not None else REPO_ROOT


def subset_path(source: str | Path, *, root: Path | None = None) -> Path:
    """Resolve a subset name or path.

    - An absolute path is returned unchanged.
    - A path with a separator is resolved against *root*.
    - A bare name is resolved under ``experiments/subsets/``, gaining ``.json``
      when it has no suffix.
    """
    raw = Path(source)
    if raw.is_absolute():
        return raw
    if len(raw.parts) > 1:
        return repo_root(root) / raw
    name = raw.name if raw.suffix else f"{raw.name}.json"
    return repo_root(root) / SUBSET_DIR / name


def subset_sha256(path: Path) -> str:
    """Return the hex ``sha256`` of the file bytes."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SubsetError(f"cannot read subset {path}: {exc}") from exc
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    """Return *path* parsed as a JSON object, or raise :class:`SubsetError`."""
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SubsetError(f"cannot read subset {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SubsetError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(loaded, dict):
        raise SubsetError(f"{path}: expected a JSON object")
    return loaded


def _document_errors(data: Mapping[str, Any], path: Path) -> list[str]:
    """Return every structural and semantic problem in a subset document."""
    errors: list[str] = []
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        errors.append(f"{path}: missing key(s) {', '.join(missing)}")
    unknown = sorted(set(data) - set(REQUIRED_KEYS))
    if unknown:
        errors.append(f"{path}: unknown key(s) {', '.join(unknown)}")

    schema = data.get("schema_version")
    if schema != SCHEMA_VERSION:
        errors.append(f"{path}: schema_version is {schema!r}, expected {SCHEMA_VERSION!r}")

    identifier = data.get("id")
    if not isinstance(identifier, str) or not _ID_RE.fullmatch(identifier):
        errors.append(f"{path}: id must match {_ID_RE.pattern}, got {identifier!r}")

    for key in ("description", "selection"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}: {key} must be a non-empty string")

    ids = data.get("task_ids")
    if not isinstance(ids, list) or not ids:
        errors.append(f"{path}: task_ids must be a non-empty list")
        ids = []
    else:
        if any(not isinstance(item, str) or not item.strip() for item in ids):
            errors.append(f"{path}: every task id must be a non-empty string")
        string_ids = [item for item in ids if isinstance(item, str)]
        duplicates = sorted({item for item in string_ids if string_ids.count(item) > 1})
        if duplicates:
            errors.append(f"{path}: duplicate task id(s) {', '.join(duplicates)}")
        if string_ids != sorted(string_ids):
            errors.append(f"{path}: task_ids must be sorted lexicographically")

    counts = data.get("counts")
    if not isinstance(counts, dict) or not counts:
        errors.append(f"{path}: counts must be a non-empty object")
    else:
        for repo, count in counts.items():
            if not isinstance(repo, str) or not repo.strip():
                errors.append(f"{path}: counts keys must be non-empty repository names")
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                errors.append(f"{path}: count for {repo!r} must be a positive integer")
        total = sum(value for value in counts.values() if isinstance(value, int))
        if isinstance(ids, list) and total != len(ids):
            errors.append(f"{path}: counts sum to {total}, task_ids has {len(ids)} entries")

    return errors


def load_subset(source: str | Path, *, root: Path | None = None) -> Subset:
    """Load and structurally validate one subset document."""
    path = subset_path(source, root=root)
    data = _load_object(path)
    errors = _document_errors(data, path)
    if errors:
        raise SubsetError("\n".join(errors))
    counts_raw = data["counts"]
    assert isinstance(counts_raw, dict)
    counts = {str(repo): int(count) for repo, count in counts_raw.items()}
    ids_raw = data["task_ids"]
    assert isinstance(ids_raw, list)
    return Subset(
        id=str(data["id"]),
        path=path,
        sha256=subset_sha256(path),
        task_ids=tuple(str(item) for item in ids_raw),
        counts=counts,
        description=str(data["description"]),
        selection=str(data["selection"]),
        schema_version=str(data["schema_version"]),
    )


def load_corpus_repos(tasks_path: Path) -> dict[str, str]:
    """Return ``instance_id -> repo`` for every line of ``tasks.jsonl``."""
    tasks_path = Path(tasks_path)
    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SubsetError(f"cannot read task corpus {tasks_path}: {exc}") from exc
    found: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SubsetError(f"{tasks_path}:{number}: invalid JSON ({exc})") from exc
        if not isinstance(record, dict):
            raise SubsetError(f"{tasks_path}:{number}: expected a JSON object")
        instance = record.get("instance_id")
        repo = record.get("repo")
        if not isinstance(instance, str) or not instance.strip():
            raise SubsetError(f"{tasks_path}:{number}: instance_id must be a non-empty string")
        if not isinstance(repo, str) or not repo.strip():
            raise SubsetError(f"{tasks_path}:{number}: repo must be a non-empty string")
        found[instance] = repo
    return found


def validate_against_corpus(subset: Subset, tasks_path: Path) -> list[str]:
    """Return the problems that make *subset* disagree with the task corpus."""
    corpus = load_corpus_repos(tasks_path)
    errors: list[str] = []
    missing = sorted(set(subset.task_ids) - set(corpus))
    if missing:
        errors.append(f"{subset.id}: task id(s) absent from the corpus: {', '.join(missing)}")
    computed: dict[str, int] = {}
    for instance in subset.task_ids:
        repo = corpus.get(instance)
        if repo is not None:
            computed[repo] = computed.get(repo, 0) + 1
    if computed != subset.counts:
        errors.append(
            f"{subset.id}: counts disagree with the corpus: recorded {subset.counts}, "
            f"computed {computed}"
        )
    return errors


def build_document(
    task_ids: Sequence[str],
    *,
    subset_id: str,
    description: str,
    selection: str,
    tasks_path: Path,
) -> dict[str, Any]:
    """Build a subset document from ids and the corpus, with computed counts."""
    corpus = load_corpus_repos(tasks_path)
    unique = sorted(set(task_ids))
    missing = sorted(set(unique) - set(corpus))
    if missing:
        raise SubsetError(f"task id(s) absent from the corpus: {', '.join(missing)}")
    counts: dict[str, int] = {}
    for instance in unique:
        repo = corpus[instance]
        counts[repo] = counts.get(repo, 0) + 1
    document = {
        "schema_version": SCHEMA_VERSION,
        "id": subset_id,
        "description": description,
        "selection": selection,
        "task_ids": unique,
        "counts": dict(sorted(counts.items())),
    }
    errors = _document_errors(document, Path(f"<{subset_id}>"))
    if errors:
        raise SubsetError("\n".join(errors))
    return document


def _main_validate(args: argparse.Namespace) -> int:
    try:
        subset = load_subset(args.source, root=args.root)
        errors = validate_against_corpus(subset, args.tasks) if args.tasks else []
    except SubsetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    counts = ", ".join(f"{repo} {count}" for repo, count in sorted(subset.counts.items()))
    print(f"{subset.id}: {len(subset.task_ids)} tasks ({counts}); sha256 {subset.sha256}")
    return 0


def _main_show(args: argparse.Namespace) -> int:
    try:
        subset = load_subset(args.source, root=args.root)
    except SubsetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(subset.as_dict(), indent=2, sort_keys=False))
    return 0


def _main_build(args: argparse.Namespace) -> int:
    try:
        document = build_document(
            args.task,
            subset_id=args.id,
            description=args.description,
            selection=args.selection,
            tasks_path=args.tasks,
        )
    except SubsetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    body = json.dumps(document, indent=2) + "\n"
    if args.output is None:
        print(body, end="")
        return 0
    output = Path(args.output)
    if output.exists() and not args.force:
        print(f"error: {output} already exists (pass --force to overwrite)", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(body, encoding="utf-8")
    print(f"wrote {output}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for subset validation, display and construction."""
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-subsets",
        description="Validate or build a fixed task subset for harness A/B runs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="validate one subset")
    validate_parser.add_argument("source", help="subset name or path")
    validate_parser.add_argument("--root", type=Path, default=None, help="repository root")
    validate_parser.add_argument(
        "--tasks",
        type=Path,
        default=None,
        help="tasks.jsonl to validate ids and counts against (default: data/raw/tasks.jsonl)",
    )
    validate_parser.set_defaults(handler=_main_validate)

    show_parser = sub.add_parser("show", help="print one subset document")
    show_parser.add_argument("source", help="subset name or path")
    show_parser.add_argument("--root", type=Path, default=None, help="repository root")
    show_parser.set_defaults(handler=_main_show)

    build_parser = sub.add_parser("build", help="build a subset document from ids")
    build_parser.add_argument("--id", required=True, help="subset id")
    build_parser.add_argument("--task", action="append", required=True, help="task id (repeatable)")
    build_parser.add_argument("--description", required=True)
    build_parser.add_argument("--selection", required=True)
    build_parser.add_argument("--tasks", type=Path, default=Path("data/raw/tasks.jsonl"))
    build_parser.add_argument("--output", type=Path, default=None)
    build_parser.add_argument("--force", action="store_true")
    build_parser.set_defaults(handler=_main_build)

    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "validate" and args.tasks is None:
        args.tasks = Path("data/raw/tasks.jsonl")
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
