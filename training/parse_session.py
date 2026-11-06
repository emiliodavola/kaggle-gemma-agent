"""Parse the harness session log into structured turns.

The archived ``trace.json`` keeps the agent's actions but not the tool
observations, and a decision-point sample without observations teaches the model
to act blind. ``session.log`` is the only artifact that carries both, so this
module turns its rendered text into turns:

    {"role": "system"|"user"|"assistant"|"tool", "text": ..., "tool": ...}

The log is line-oriented and every event starts with ``[  12.3s]``; continuation
lines carry no timestamp and belong to the previous event. ANSI colour is the
only decoration and it is stripped first.

Usage:
    uv run --directory training python parse_session.py runs/<run-id>
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
EVENT = re.compile(r"^\s*\[\s*[\d.]+s\]\s*(.*)$")

# The renderer prefixes each event with a glyph; the mapping is by glyph rather
# than by position because the log interleaves families.
MARKERS = {
    "\U0001f4cb": "system",  # clipboard: system prompt
    "\U0001f9d1": "user",  # person: problem statement
    "\U0001f464": "user",
    "\U0001f4ad": "thought",  # thought balloon
    "\U0001f4ac": "thought",  # speech balloon: a message with no call
    "\U0001f527": "tool_call",  # wrench
    "\u2192": "tool_output",  # arrow
    "\u274c": "error",  # cross mark
    "\U0001f3af": "user",  # dart: task prompt
    "\U0001f916": "tool_call",  # robot: submit_patch
    "\U0001f4d6": "tool_call",  # open book: read_file
    "\u270f": "tool_call",  # pencil: edit_file
    "\u2705": "finish",  # check mark
    "\U0001f3c1": "finish",  # chequered flag
}

# Multi-line arguments arrive as "run_command (10 lines) cd ..."; the count is
# renderer bookkeeping, not part of the command.
LINE_COUNT = re.compile(r"^\w+ \(\d+ lines\)\s*")


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


def split_events(text: str) -> list[str]:
    """Split into events: a timestamped header plus its continuation lines."""
    events: list[str] = []
    for line in strip_ansi(text).splitlines():
        match = EVENT.match(line)
        if match:
            events.append(match.group(1).rstrip())
        elif events and line.strip():
            events[-1] += " " + line.strip()
    return events


def classify(event: str) -> str:
    for glyph, kind in MARKERS.items():
        if event.startswith(glyph):
            return kind
    return "unknown"


def parse(path: Path) -> dict:
    events = split_events(path.read_text(encoding="utf-8", errors="replace"))
    turns: list[dict] = []
    unknown: list[str] = []
    pending: dict | None = None

    for event in events:
        kind = classify(event)
        body = event[1:].strip() if kind != "unknown" else event
        if kind == "unknown":
            unknown.append(event[:60])
            continue
        if kind == "tool_call":
            body = LINE_COUNT.sub(lambda m: m.group(0).split(" (")[0] + " ", body)
            name, _, command = body.partition(" ")
            pending = {"role": "assistant", "tool": name.strip(), "text": command.strip()}
            turns.append(pending)
            continue
        if kind in ("tool_output", "error"):
            text = body
            if turns and turns[-1]["role"] == "assistant" and turns[-1].get("tool"):
                turns[-1].setdefault("result", "")
                turns[-1]["result"] += ("\n" if turns[-1]["result"] else "") + text
            else:
                turns.append({"role": "tool", "text": text})
            continue
        if kind == "thought":
            body = re.sub(r"^\(\d+ chars\)\s*", "", body).strip().strip('"')
            turns.append({"role": "thought", "text": body})
            continue
        turns.append({"role": kind, "text": body})

    return {"turns": turns, "unknown": unknown}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="run directory holding <task>/session.log")
    parser.add_argument("--out", default=None)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    run = Path(args.run)
    logs = sorted(run.glob("*/session.log"))
    if args.limit:
        logs = logs[: args.limit]
    if not logs:
        raise SystemExit(f"no session.log under {run}")

    records = []
    for log in logs:
        parsed = parse(log)
        turns = parsed["turns"]
        counts: dict[str, int] = {}
        for turn in turns:
            counts[turn["role"]] = counts.get(turn["role"], 0) + 1
        records.append(
            {
                "task": log.parent.name,
                "counts": counts,
                "unknown": parsed["unknown"][:3],
                "turns": turns,
            }
        )

    out = Path(args.out) if args.out else run / "turns.jsonl"
    out.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    totals: dict[str, int] = {}
    for record in records:
        for role, count in record["counts"].items():
            totals[role] = totals.get(role, 0) + count
    print(f"tasks: {len(records)} -> {out}")
    print("turns by role:", dict(sorted(totals.items())))
    with_output = sum(1 for r in records if any(t.get("result") for t in r["turns"]))
    print(f"tasks with at least one tool result: {with_output}/{len(records)}")
    unknown = [u for r in records for u in r["unknown"]]
    if unknown:
        print("unclassified samples:", unknown[:5])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
