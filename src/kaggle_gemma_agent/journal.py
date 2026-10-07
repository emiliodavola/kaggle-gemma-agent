"""Append-only change journal: a machine JSONL layer plus a rendered human digest.

The journal lives under ``docs/journal`` by default and records the chronological,
cross-cutting log of changes and decisions. Two layers are kept in sync:

* ``events.jsonl`` -- append-only, one JSON object per line, UTF-8, LF terminated.
  It is the source of truth and an existing line is never rewritten.
* ``YYYYMMDD.md`` -- one rendered day file per UTC date. It is regenerable and
  never hand-edited; :func:`render_day` produces it deterministically.

Stdlib only, mirroring :mod:`kaggle_gemma_agent.pack`, so the CLI runs anywhere
in the repository without third-party imports.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TYPES: tuple[str, ...] = (
    "observation",
    "decision",
    "change",
    "measurement",
    "reversal",
    "run_started",
    "run_finished",
    "gate_check",
)
ACTORS: tuple[str, ...] = ("emilio", "robotina", "opencode", "runner", "ci")
STATUSES: tuple[str, ...] = ("open", "applied", "superseded", "reverted")
EVENT_KEYS: tuple[str, ...] = (
    "id",
    "ts",
    "type",
    "actor",
    "what",
    "why",
    "evidence",
    "status",
    "refs",
    "hashes",
    "counts",
)
REF_KEYS: tuple[str, ...] = ("pr", "issue", "commit", "run_id", "docs")

EVENTS_FILE = "events.jsonl"
DAY_SUFFIX = ".md"

PREAMBLE = (
    "Append-only. One entry per change or decision; an entry is never edited. To revise\n"
    "one, add a new entry that supersedes or reverts it, and set the old one's status.\n"
    "Evidence is counts and paths, never causality: without randomisation a batch\n"
    'comparison is "29/48 -> X/48 on a different batch", never "it improved".'
)

_ID_RE = re.compile(r"^J-\d{8}-\d{2,}$")
_DAY_FILE_RE = re.compile(r"^\d{8}\.md$")
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class JournalError(Exception):
    """Raised when an entry or the journal itself cannot be read or written."""


class DuplicateEntryError(JournalError):
    """Raised when an identical type/what/why/status entry is already recorded."""


def repo_root() -> Path:
    """Return the repository root, resolved from this package's location."""
    return Path(__file__).resolve().parents[2]


def default_root() -> Path:
    """Return ``<repo_root>/docs/journal``."""
    return repo_root() / "docs" / "journal"


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise JournalError("invalid timestamp: empty value")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise JournalError(f"invalid timestamp: {value!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _normalize_ts(value: str) -> str:
    return _parse_ts(value).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_date(value: str) -> str:
    return _parse_ts(value).date().isoformat()


def _require_date(value: str) -> None:
    if _DAY_RE.match(value) is None:
        raise JournalError(f"invalid date: {value!r} (expected YYYY-MM-DD)")


def _require_choice(name: str, value: str, allowed: Sequence[str]) -> None:
    if value not in allowed:
        raise JournalError(f"invalid {name}: {value!r} (allowed: {', '.join(allowed)})")


def _normalize_refs(refs: Mapping[str, Any] | None) -> dict[str, Any]:
    source = refs or {}
    extra = [key for key in source if key not in REF_KEYS]
    if extra:
        raise JournalError(f"unknown refs key(s): {', '.join(sorted(extra))}")
    docs = source.get("docs") or []
    return {
        "pr": source.get("pr"),
        "issue": source.get("issue"),
        "commit": source.get("commit"),
        "run_id": source.get("run_id"),
        "docs": [str(path) for path in docs],
    }


def read_events(root: Path) -> list[dict[str, Any]]:
    """Return every event in ``<root>/events.jsonl`` in file order.

    A missing file is treated as an empty journal. A blank or malformed line
    raises :class:`JournalError` naming the offending line number.
    """
    path = Path(root) / EVENTS_FILE
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise JournalError(f"{EVENTS_FILE}:{number}: blank line is not a valid event")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalError(f"{EVENTS_FILE}:{number}: malformed JSON ({exc.msg})") from exc
        if not isinstance(event, dict):
            raise JournalError(f"{EVENTS_FILE}:{number}: event is not a JSON object")
        events.append(event)
    return events


def _entry_id(events: Sequence[Mapping[str, Any]], date: str) -> str:
    compact = date.replace("-", "")
    prefix = f"J-{compact}-"
    used: list[int] = []
    for event in events:
        identifier = event.get("id")
        if isinstance(identifier, str) and identifier.startswith(prefix):
            suffix = identifier[len(prefix) :]
            if suffix.isdigit():
                used.append(int(suffix))
    return f"{prefix}{max(used, default=0) + 1:02d}"


def _duplicate_id(
    events: Sequence[Mapping[str, Any]], type: str, what: str, why: str, status: str
) -> str | None:
    for event in events:
        if (
            event.get("type"),
            event.get("what"),
            event.get("why"),
            event.get("status"),
        ) == (type, what, why, status):
            identifier = event.get("id")
            return identifier if isinstance(identifier, str) else "unknown"
    return None


def _append_line(path: Path, event: Mapping[str, Any]) -> None:
    line = json.dumps(event, ensure_ascii=False)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def _event_sort_key(event: Mapping[str, Any]) -> tuple[datetime, str]:
    return (_parse_ts(str(event["ts"])), str(event.get("id", "")))


def _render_refs(refs: Mapping[str, Any] | None) -> str:
    if not refs:
        return "none"
    parts: list[str] = []
    if refs.get("pr") is not None:
        parts.append(f"PR #{refs['pr']}")
    if refs.get("issue") is not None:
        parts.append(f"issue #{refs['issue']}")
    if refs.get("commit"):
        parts.append(f"commit {refs['commit']}")
    if refs.get("run_id"):
        parts.append(f"run {refs['run_id']}")
    parts.extend(str(path) for path in (refs.get("docs") or []))
    return ", ".join(parts) if parts else "none"


def _day_text(events: Sequence[Mapping[str, Any]], date: str) -> str:
    lines = [f"# Change journal — {date}", "", PREAMBLE, ""]
    for event in events:
        moment = _parse_ts(str(event["ts"]))
        evidence = event["evidence"]
        rendered = "; ".join(str(item) for item in evidence) if evidence else "none recorded"
        lines.append(f"## {event['id']} — {event['what']}")
        lines.append("")
        lines.append(
            f"- **Time:** {moment.strftime('%H:%MZ')} · **Actor:** {event['actor']}"
            f" · **Type:** {event['type']} · **Status:** {event['status']}"
        )
        lines.append(f"- **Why:** {event['why']}")
        lines.append(f"- **Evidence:** {rendered}")
        lines.append(f"- **Refs:** {_render_refs(event['refs'])}")
        lines.append("")
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


def render_day(root: Path, date: str) -> Path:
    """Render ``<root>/YYYYMMDD.md`` from the events of *date* and return its path."""
    _require_date(date)
    root = Path(root)
    events = [event for event in read_events(root) if _event_date(str(event["ts"])) == date]
    events.sort(key=_event_sort_key)
    path = root / f"{date.replace('-', '')}{DAY_SUFFIX}"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(_day_text(events, date))
    return path


def render_all(root: Path) -> list[Path]:
    """Render one day file per UTC date present in the journal, oldest first."""
    root = Path(root)
    dates = sorted({_event_date(str(event["ts"])) for event in read_events(root)})
    return [render_day(root, date) for date in dates]


def append_event(
    root: Path,
    *,
    type: str,
    actor: str,
    what: str,
    why: str,
    evidence: Sequence[str] = (),
    status: str = "applied",
    refs: Mapping[str, Any] | None = None,
    hashes: Mapping[str, str] | None = None,
    counts: Mapping[str, Any] | None = None,
    ts: str | None = None,
) -> str:
    """Append one event to the journal and return its new id.

    Writes the JSONL line and re-renders the day file derived from *ts*.
    Raises :class:`DuplicateEntryError` when an entry with the same
    ``type``/``what``/``why``/``status`` already exists, and
    :class:`JournalError` for an invalid enum, empty text, or bad timestamp.
    """
    root = Path(root)
    _require_choice("type", type, TYPES)
    _require_choice("actor", actor, ACTORS)
    _require_choice("status", status, STATUSES)
    if not what.strip():
        raise JournalError("what must not be empty")
    if not why.strip():
        raise JournalError("why must not be empty")

    resolved_ts = _normalize_ts(ts) if ts is not None else _now_utc()
    date = resolved_ts[:10]
    events = read_events(root)
    duplicate = _duplicate_id(events, type, what, why, status)
    if duplicate is not None:
        raise DuplicateEntryError(f"identical entry already recorded as {duplicate}")

    event: dict[str, Any] = {
        "id": _entry_id(events, date),
        "ts": resolved_ts,
        "type": type,
        "actor": actor,
        "what": what,
        "why": why,
        "evidence": [str(item) for item in evidence],
        "status": status,
        "refs": _normalize_refs(refs),
        "hashes": None if hashes is None else dict(hashes),
        "counts": None if counts is None else dict(counts),
    }
    root.mkdir(parents=True, exist_ok=True)
    _append_line(root / EVENTS_FILE, event)
    render_day(root, date)
    identifier = event["id"]
    return identifier if isinstance(identifier, str) else str(identifier)


def transition(
    root: Path,
    identifier: str,
    *,
    to: str,
    why: str | None = None,
    evidence: Sequence[str] = (),
    actor: str = "opencode",
    ts: str | None = None,
) -> str | None:
    """Record a status transition, rewriting only the target entry's status.

    Appends a record entry whose ``what`` is ``Marked <id> as <status>`` and whose
    evidence names the target id, then rewrites only the ``status`` field of the
    target entry's line. Both affected day files are re-rendered. Returns the new
    record entry id, or ``None`` when *identifier* already has status *to* (in
    which case nothing is written). Raises :class:`JournalError` for an unknown
    id or an invalid status/actor.
    """
    root = Path(root)
    _require_choice("status", to, STATUSES)
    _require_choice("actor", actor, ACTORS)
    events = read_events(root)
    position: int | None = None
    target: Mapping[str, Any] | None = None
    for index, event in enumerate(events):
        if event.get("id") == identifier:
            position = index
            target = event
            break
    if position is None or target is None:
        raise JournalError(f"entry not found: {identifier}")

    current = str(target["status"])
    if current == to:
        return None

    default_why = f"status transition of {identifier} to {to}"
    resolved_why = why.strip() if why is not None and why.strip() else default_why
    record_id = append_event(
        root,
        type="reversal" if to == "reverted" else "change",
        actor=actor,
        what=f"Marked {identifier} as {to}",
        why=resolved_why,
        evidence=[*evidence, identifier],
        ts=ts,
    )
    record_event = _read_event(root, record_id)
    record_date = _event_date(str(record_event["ts"]))
    target_date = _event_date(str(target["ts"]))

    path = root / EVENTS_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    rewritten = dict(target)
    rewritten["status"] = to
    lines[position] = json.dumps(rewritten, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    render_day(root, target_date)
    if record_date != target_date:
        render_day(root, record_date)
    return record_id


def list_events(
    root: Path,
    *,
    type: str | None = None,
    status: str | None = None,
    since: str | None = None,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Return journal events, oldest first, filtered by the given facets."""
    events = read_events(root)
    if type is not None:
        _require_choice("type", type, TYPES)
        events = [event for event in events if event.get("type") == type]
    if status is not None:
        _require_choice("status", status, STATUSES)
        events = [event for event in events if event.get("status") == status]
    if since is not None:
        threshold = _parse_ts(since)
        events = [event for event in events if _parse_ts(str(event["ts"])) >= threshold]
    if date is not None:
        _require_date(date)
        events = [event for event in events if _event_date(str(event["ts"])) == date]
    return sorted(events, key=_event_sort_key)


def validate(root: Path) -> list[str]:
    """Return every schema or day-file violation of the journal at *root*.

    An empty list means the journal is valid. Checks cover unique ids, valid
    enums, parseable timestamps, the exact and ordered key set, and that every
    day file matches a fresh render.
    """
    root = Path(root)
    problems: list[str] = []
    try:
        events = read_events(root)
    except JournalError as exc:
        return [str(exc)]

    seen: set[str] = set()
    dated: dict[str, list[dict[str, Any]]] = {}
    for index, event in enumerate(events, start=1):
        keys = list(event.keys())
        if tuple(keys) != EVENT_KEYS:
            expected = "|".join(EVENT_KEYS)
            problems.append(f"event {index}: expected keys [{expected}], got [{'|'.join(keys)}]")
            continue

        identifier = event["id"]
        if not isinstance(identifier, str) or _ID_RE.match(identifier) is None:
            problems.append(f"event {index}: invalid id {identifier!r}")
        elif identifier in seen:
            problems.append(f"event {index}: duplicate id {identifier}")
        else:
            seen.add(identifier)

        if event["type"] not in TYPES:
            problems.append(f"event {index}: invalid type {event['type']!r}")
        if event["actor"] not in ACTORS:
            problems.append(f"event {index}: invalid actor {event['actor']!r}")
        if event["status"] not in STATUSES:
            problems.append(f"event {index}: invalid status {event['status']!r}")
        if not isinstance(event["evidence"], list):
            problems.append(f"event {index}: evidence must be a list")
        if event["hashes"] is not None and not isinstance(event["hashes"], dict):
            problems.append(f"event {index}: hashes must be null or an object")
        if event["counts"] is not None and not isinstance(event["counts"], dict):
            problems.append(f"event {index}: counts must be null or an object")
        refs = event["refs"]
        if not isinstance(refs, dict) or tuple(refs.keys()) != REF_KEYS:
            problems.append(f"event {index}: refs must have keys [{'|'.join(REF_KEYS)}] in order")

        try:
            event_date = _event_date(str(event["ts"]))
        except JournalError:
            problems.append(f"event {index}: unparseable ts {event['ts']!r}")
            continue
        if isinstance(identifier, str) and _ID_RE.match(identifier):
            id_date = f"{identifier[2:6]}-{identifier[6:8]}-{identifier[8:10]}"
            if id_date != event_date:
                problems.append(
                    f"event {index} ({identifier}): id date {id_date} != ts date {event_date}"
                )
        dated.setdefault(event_date, []).append(event)

    for position, event in enumerate(events):
        status = event.get("status")
        if status not in ("superseded", "reverted"):
            continue
        identifier = event.get("id")
        later_named = any(
            isinstance(other.get("evidence"), list) and identifier in other["evidence"]
            for other in events[position + 1 :]
        )
        if not later_named:
            problems.append(
                f"event {position + 1} ({identifier}): status {status} is not named "
                "in the evidence of a later entry"
            )

    existing_dates = (
        {
            f"{path.stem[0:4]}-{path.stem[4:6]}-{path.stem[6:8]}"
            for path in root.glob("*.md")
            if _DAY_FILE_RE.match(path.name)
        }
        if root.is_dir()
        else set()
    )
    for date in sorted(set(dated) | existing_dates):
        expected = _day_text(sorted(dated.get(date, []), key=_event_sort_key), date)
        path = root / f"{date.replace('-', '')}{DAY_SUFFIX}"
        if not path.is_file():
            problems.append(f"{path.name}: missing day file (expected a fresh render)")
            continue
        if path.read_text(encoding="utf-8") != expected:
            problems.append(f"{path.name}: day file drifted from a fresh render")
    return problems


def _read_event(root: Path, identifier: str) -> dict[str, Any]:
    for event in read_events(root):
        if event.get("id") == identifier:
            return event
    raise JournalError(f"entry not found after write: {identifier}")


def _resolve_root(value: Path | None) -> Path:
    return Path(value) if value is not None else default_root()


def _cmd_add(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    evidence = [item for group in args.evidence for item in group]
    docs = [item for group in args.doc for item in group]
    refs = {
        "pr": args.pr,
        "issue": args.issue,
        "commit": args.commit,
        "run_id": args.run_id,
        "docs": docs,
    }
    if args.date is not None:
        try:
            _require_date(args.date)
            resolved_ts = _normalize_ts(args.ts) if args.ts is not None else _now_utc()
        except JournalError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if args.date != resolved_ts[:10]:
            print(
                f"error: --date {args.date} does not match ts date {resolved_ts[:10]}",
                file=sys.stderr,
            )
            return 1
    try:
        identifier = append_event(
            root,
            type=args.type,
            actor=args.actor,
            what=args.what,
            why=args.why,
            evidence=evidence,
            status=args.status,
            refs=refs,
            ts=args.ts,
        )
    except JournalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(_read_event(root, identifier), ensure_ascii=False))
    else:
        print(identifier)
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    try:
        if args.date is not None:
            print(render_day(root, args.date))
        else:
            for path in render_all(root):
                print(path)
    except JournalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    try:
        events = list_events(
            root, type=args.type, status=args.status, since=args.since, date=args.date
        )
    except JournalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("id | ts | type | status | what")
    for event in events:
        print(
            f"{event['id']} | {event['ts']} | {event['type']} | {event['status']} | {event['what']}"
        )
    return 0


def _cmd_transition(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    evidence = [item for group in args.evidence for item in group]
    try:
        identifier = transition(
            root,
            args.id,
            to=args.to,
            why=args.why,
            evidence=evidence,
            actor=args.actor,
            ts=args.ts,
        )
    except JournalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if identifier is None:
        print(f"already {args.to}")
    else:
        print(identifier)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    problems = validate(root)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    print(f"journal OK ({len(read_events(root))} events)")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaggle-gemma-agent-journal",
        description="Append, render, list and validate the change journal.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="append an entry and re-render its day file")
    add.add_argument("--type", required=True, choices=TYPES)
    add.add_argument("--what", required=True)
    add.add_argument("--why", required=True)
    add.add_argument("--actor", default="opencode", choices=ACTORS)
    add.add_argument("--status", default="applied", choices=STATUSES)
    add.add_argument("--evidence", action="append", nargs="+", default=[])
    add.add_argument("--pr", type=int)
    add.add_argument("--issue", type=int)
    add.add_argument("--commit")
    add.add_argument("--run-id")
    add.add_argument("--doc", action="append", nargs="+", default=[])
    add.add_argument("--ts")
    add.add_argument("--date")
    add.add_argument("--json", action="store_true", dest="as_json")
    add.add_argument("--root", type=Path)

    render = subparsers.add_parser("render", help="regenerate a day file from events.jsonl")
    render.add_argument("--date")
    render.add_argument("--root", type=Path)

    move = subparsers.add_parser(
        "transition", help="record a status transition and rewrite the target status"
    )
    move.add_argument("id")
    move.add_argument("--to", required=True, choices=STATUSES)
    move.add_argument("--why")
    move.add_argument("--evidence", action="append", nargs="+", default=[])
    move.add_argument("--actor", default="opencode", choices=ACTORS)
    move.add_argument("--ts")
    move.add_argument("--root", type=Path)

    listing = subparsers.add_parser("list", help="print a compact event table")
    listing.add_argument("--type", choices=TYPES)
    listing.add_argument("--status", choices=STATUSES)
    listing.add_argument("--since")
    listing.add_argument("--date")
    listing.add_argument("--root", type=Path)

    check = subparsers.add_parser("validate", help="check the journal schema and renders")
    check.add_argument("--root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for the change journal."""
    args = _build_parser().parse_args(argv)
    if args.command == "add":
        return _cmd_add(args)
    if args.command == "render":
        return _cmd_render(args)
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "transition":
        return _cmd_transition(args)
    return _cmd_validate(args)


if __name__ == "__main__":
    raise SystemExit(main())
