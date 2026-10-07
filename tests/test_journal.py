"""Tests for the append-only change journal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kaggle_gemma_agent import journal

REPO_ROOT = Path(__file__).resolve().parents[1]
REF_KEYS = ["pr", "issue", "commit", "run_id", "docs"]


def _event(**overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "id": "J-20261006-01",
        "ts": "2026-10-06T19:40:00Z",
        "type": "change",
        "actor": "robotina",
        "what": "do a thing",
        "why": "because",
        "evidence": [],
        "status": "applied",
        "refs": {"pr": None, "issue": None, "commit": None, "run_id": None, "docs": []},
        "hashes": None,
        "counts": None,
    }
    event.update(overrides)
    return event


def _write_events(root: Path, *events: dict[str, Any]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "events.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def _add(root: Path, **overrides: Any) -> str:
    params: dict[str, Any] = {"type": "change", "actor": "robotina", "what": "w", "why": "y"}
    params.update(overrides)
    return journal.append_event(root, **params)


def _events(root: Path) -> list[dict[str, Any]]:
    return journal.read_events(root)


def _problems_text(root: Path) -> str:
    return "\n".join(journal.validate(root))


def test_repo_root_and_default_root() -> None:
    assert journal.repo_root() == REPO_ROOT
    assert journal.default_root() == REPO_ROOT / "docs" / "journal"


def test_append_event_key_set_and_order(tmp_path: Path) -> None:
    _add(tmp_path)

    raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()[0]
    pairs = json.loads(raw, object_pairs_hook=lambda items: items)

    assert [key for key, _ in pairs] == list(journal.EVENT_KEYS)


def test_append_event_refs_key_order_and_values(tmp_path: Path) -> None:
    _add(
        tmp_path,
        refs={
            "pr": 76,
            "issue": 75,
            "commit": "fd60705",
            "run_id": "20261006T103737Z",
            "docs": ["docs/README.md"],
        },
    )

    refs = _events(tmp_path)[0]["refs"]
    assert list(refs.keys()) == REF_KEYS
    assert refs == {
        "pr": 76,
        "issue": 75,
        "commit": "fd60705",
        "run_id": "20261006T103737Z",
        "docs": ["docs/README.md"],
    }


def test_append_event_defaults_empty_refs(tmp_path: Path) -> None:
    _add(tmp_path, refs=None)

    assert _events(tmp_path)[0]["refs"] == {
        "pr": None,
        "issue": None,
        "commit": None,
        "run_id": None,
        "docs": [],
    }


def test_ids_increment_per_date(tmp_path: Path) -> None:
    first = _add(tmp_path, what="first")
    second = _add(tmp_path, what="second")

    assert first.endswith("-01")
    assert second.endswith("-02")
    assert first.startswith("J-")
    assert len(second.rsplit("-", 1)[1]) == 2


def test_ids_reset_on_new_date(tmp_path: Path) -> None:
    first = _add(tmp_path, what="first", ts="2026-10-06T10:00:00Z")
    later = _add(tmp_path, what="later", ts="2026-10-07T10:00:00Z")

    assert first == "J-20261006-01"
    assert later == "J-20261007-01"


def test_append_only_never_rewrites(tmp_path: Path) -> None:
    _add(tmp_path, what="first")
    before = (tmp_path / "events.jsonl").read_bytes()

    _add(tmp_path, what="second")
    after = (tmp_path / "events.jsonl").read_bytes()

    assert after.startswith(before)
    assert len(after) > len(before)


def test_append_creates_missing_root(tmp_path: Path) -> None:
    root = tmp_path / "nested" / "journal"

    _add(root)

    event = _events(root)[0]
    assert (root / "events.jsonl").is_file()
    assert (root / f"{event['ts'][:10].replace('-', '')}.md").is_file()


def test_append_writes_hashes_and_counts(tmp_path: Path) -> None:
    _add(tmp_path, hashes={"prompt": "abc"}, counts={"tasks": 3, "resolved": 2})

    event = _events(tmp_path)[0]
    assert event["hashes"] == {"prompt": "abc"}
    assert event["counts"] == {"tasks": 3, "resolved": 2}


def test_append_leaves_hashes_and_counts_null(tmp_path: Path) -> None:
    _add(tmp_path)

    event = _events(tmp_path)[0]
    assert event["hashes"] is None
    assert event["counts"] is None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("type", "bogus", "invalid type"),
        ("actor", "nobody", "invalid actor"),
        ("status", "done", "invalid status"),
    ],
)
def test_append_rejects_invalid_enum(tmp_path: Path, field: str, value: str, message: str) -> None:
    with pytest.raises(journal.JournalError, match=message):
        _add(tmp_path, **{field: value})


@pytest.mark.parametrize("field", ["what", "why"])
def test_append_rejects_empty_text(tmp_path: Path, field: str) -> None:
    with pytest.raises(journal.JournalError, match="must not be empty"):
        _add(tmp_path, **{field: "   "})


def test_append_rejects_bad_ts(tmp_path: Path) -> None:
    with pytest.raises(journal.JournalError, match="invalid timestamp"):
        _add(tmp_path, ts="not-a-timestamp")


def test_append_rejects_unknown_refs_key(tmp_path: Path) -> None:
    with pytest.raises(journal.JournalError, match="unknown refs key"):
        _add(tmp_path, refs={"pr": 1, "nope": True})


def test_duplicate_suppression_same_run(tmp_path: Path) -> None:
    first = _add(tmp_path, what="same", why="same")

    with pytest.raises(journal.DuplicateEntryError, match=first):
        _add(tmp_path, what="same", why="same")

    assert len(_events(tmp_path)) == 1


def test_duplicate_suppression_is_exact(tmp_path: Path) -> None:
    _add(tmp_path, what="same", status="applied")
    _add(tmp_path, what="same", status="open")
    _add(tmp_path, what="different")

    assert len(_events(tmp_path)) == 3


def test_day_file_render_content(tmp_path: Path) -> None:
    _add(
        tmp_path,
        what="Add the change journal",
        why="Record cross-cutting changes",
        evidence=["PR #76", "docs/README.md"],
        refs={
            "pr": 76,
            "issue": 75,
            "commit": "fd60705",
            "run_id": "R1",
            "docs": ["docs/README.md"],
        },
        ts="2026-10-06T19:40:00Z",
    )

    text = (tmp_path / "20261006.md").read_text(encoding="utf-8")
    assert text.startswith("# Change journal — 2026-10-06\n")
    assert "## J-20261006-01 — Add the change journal" in text
    assert (
        "- **Time:** 19:40Z · **Actor:** robotina · **Type:** change · **Status:** applied" in text
    )
    assert "- **Why:** Record cross-cutting changes" in text
    assert "- **Evidence:** PR #76; docs/README.md" in text
    assert "- **Refs:** PR #76, issue #75, commit fd60705, run R1, docs/README.md" in text


def test_day_file_empty_evidence_and_refs(tmp_path: Path) -> None:
    _add(tmp_path, what="plain", why="plain", ts="2026-10-06T05:00:00Z")

    text = (tmp_path / "20261006.md").read_text(encoding="utf-8")
    assert "- **Evidence:** none recorded" in text
    assert "- **Refs:** none" in text
    assert "- **Time:** 05:00Z" in text


def test_render_is_byte_identical(tmp_path: Path) -> None:
    _add(tmp_path, what="first", ts="2026-10-06T10:00:00Z")
    _add(tmp_path, what="second", ts="2026-10-06T11:00:00Z")
    before = (tmp_path / "20261006.md").read_bytes()

    journal.render_day(tmp_path, "2026-10-06")

    assert (tmp_path / "20261006.md").read_bytes() == before


def test_render_all_dates(tmp_path: Path) -> None:
    _add(tmp_path, what="first", ts="2026-10-06T10:00:00Z")
    _add(tmp_path, what="second", ts="2026-10-07T11:00:00Z")

    paths = journal.render_all(tmp_path)

    assert [path.name for path in paths] == ["20261006.md", "20261007.md"]
    assert all(path.is_file() for path in paths)


def test_render_day_rejects_bad_date(tmp_path: Path) -> None:
    with pytest.raises(journal.JournalError, match="invalid date"):
        journal.render_day(tmp_path, "2026/10/06")


def test_read_events_missing_file(tmp_path: Path) -> None:
    assert journal.read_events(tmp_path) == []


def test_validate_ok(tmp_path: Path) -> None:
    _add(tmp_path, what="first", ts="2026-10-06T10:00:00Z")
    _add(tmp_path, what="second", status="open", ts="2026-10-07T11:00:00Z")

    assert journal.validate(tmp_path) == []


def test_validate_missing_journal_is_ok(tmp_path: Path) -> None:
    assert journal.validate(tmp_path) == []


def test_validate_detects_duplicate_id(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        _event(id="J-20261006-01", what="first"),
        _event(id="J-20261006-01", what="second"),
    )

    assert "duplicate id J-20261006-01" in _problems_text(tmp_path)


def test_validate_detects_invalid_enum(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(type="bogus", actor="nobody", status="done"))

    problems = _problems_text(tmp_path)
    assert "invalid type 'bogus'" in problems
    assert "invalid actor 'nobody'" in problems
    assert "invalid status 'done'" in problems


def test_validate_detects_malformed_key_set(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(extra="nope"))

    problems = _problems_text(tmp_path)
    assert "expected keys" in problems


def test_validate_detects_wrong_key_order(tmp_path: Path) -> None:
    event = _event()
    reordered = dict(reversed(list(event.items())))

    _write_events(tmp_path, reordered)

    assert "expected keys" in _problems_text(tmp_path)


def test_validate_detects_bad_refs_keys(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(refs={"pr": None, "issue": None, "commit": None}))

    assert "refs must have keys" in _problems_text(tmp_path)


def test_validate_detects_bad_hashes_and_counts(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(hashes=["x"], counts=3))

    problems = _problems_text(tmp_path)
    assert "hashes must be null or an object" in problems
    assert "counts must be null or an object" in problems


def test_validate_detects_non_list_evidence(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(evidence="PR #1"))

    assert "evidence must be a list" in _problems_text(tmp_path)


def test_validate_detects_unparseable_ts(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(ts="yesterday"))

    assert "unparseable ts" in _problems_text(tmp_path)


def test_validate_detects_id_date_mismatch(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(id="J-20261005-01", ts="2026-10-06T10:00:00Z"))

    assert "id date 2026-10-05 != ts date 2026-10-06" in _problems_text(tmp_path)


def test_validate_detects_invalid_id_format(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(id="nope"))

    assert "invalid id 'nope'" in _problems_text(tmp_path)


def test_validate_detects_day_file_drift(tmp_path: Path) -> None:
    _add(tmp_path, what="first", ts="2026-10-06T10:00:00Z")
    (tmp_path / "20261006.md").write_text("tampered\n", encoding="utf-8")

    assert "drifted from a fresh render" in _problems_text(tmp_path)


def test_validate_detects_missing_day_file(tmp_path: Path) -> None:
    _write_events(tmp_path, _event())

    assert "missing day file" in _problems_text(tmp_path)


def test_validate_detects_malformed_line(tmp_path: Path) -> None:
    (tmp_path / "events.jsonl").write_text("{not json\n", encoding="utf-8")

    assert "malformed JSON" in _problems_text(tmp_path)
    with pytest.raises(journal.JournalError, match="malformed JSON"):
        journal.read_events(tmp_path)


def test_validate_detects_blank_line(tmp_path: Path) -> None:
    (tmp_path / "events.jsonl").write_text("\n", encoding="utf-8")

    assert "blank line" in _problems_text(tmp_path)


def test_validate_detects_non_object_line(tmp_path: Path) -> None:
    (tmp_path / "events.jsonl").write_text("[1, 2]\n", encoding="utf-8")

    assert "not a JSON object" in _problems_text(tmp_path)


def test_list_events_filters(tmp_path: Path) -> None:
    _add(tmp_path, what="change-a", type="change", ts="2026-10-06T10:00:00Z")
    _add(tmp_path, what="decision-a", type="decision", ts="2026-10-06T11:00:00Z")
    _add(tmp_path, what="decision-b", type="decision", status="open", ts="2026-10-07T11:00:00Z")

    assert [e["what"] for e in journal.list_events(tmp_path, type="decision")] == [
        "decision-a",
        "decision-b",
    ]
    assert [e["what"] for e in journal.list_events(tmp_path, status="open")] == ["decision-b"]
    assert [e["what"] for e in journal.list_events(tmp_path, date="2026-10-06")] == [
        "change-a",
        "decision-a",
    ]
    assert [e["what"] for e in journal.list_events(tmp_path, since="2026-10-06T11:00:00Z")] == [
        "decision-a",
        "decision-b",
    ]
    assert journal.list_events(tmp_path, type="observation") == []


def test_list_events_sorts_oldest_first(tmp_path: Path) -> None:
    _add(tmp_path, what="later", ts="2026-10-06T12:00:00Z")
    _add(tmp_path, what="earlier", ts="2026-10-06T08:00:00Z")

    assert [e["what"] for e in journal.list_events(tmp_path)] == ["earlier", "later"]


def test_list_events_rejects_invalid_facet(tmp_path: Path) -> None:
    _add(tmp_path)

    with pytest.raises(journal.JournalError, match="invalid type"):
        journal.list_events(tmp_path, type="bogus")
    with pytest.raises(journal.JournalError, match="invalid status"):
        journal.list_events(tmp_path, status="bogus")
    with pytest.raises(journal.JournalError, match="invalid date"):
        journal.list_events(tmp_path, date="bogus")
    with pytest.raises(journal.JournalError, match="invalid timestamp"):
        journal.list_events(tmp_path, since="bogus")


def test_cli_add_prints_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(
        [
            "add",
            "--type",
            "change",
            "--what",
            "w",
            "--why",
            "y",
            "--ts",
            "2026-10-06T19:40:00Z",
            "--root",
            str(tmp_path),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.strip() == "J-20261006-01"


def test_cli_add_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(
        [
            "add",
            "--type",
            "change",
            "--what",
            "w",
            "--why",
            "y",
            "--ts",
            "2026-10-06T19:40:00Z",
            "--json",
            "--root",
            str(tmp_path),
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert list(payload.keys()) == list(journal.EVENT_KEYS)
    assert payload["id"] == "J-20261006-01"


def test_cli_add_evidence_docs_and_actor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = journal.main(
        [
            "add",
            "--type",
            "change",
            "--what",
            "w",
            "--why",
            "y",
            "--actor",
            "runner",
            "--evidence",
            "PR #76",
            "docs/README.md",
            "--evidence",
            "second",
            "--doc",
            "a.md",
            "b.md",
            "--pr",
            "76",
            "--issue",
            "75",
            "--commit",
            "fd60705",
            "--run-id",
            "R1",
            "--root",
            str(tmp_path),
        ]
    )

    assert code == 0
    capsys.readouterr()
    event = _events(tmp_path)[0]
    assert event["actor"] == "runner"
    assert event["evidence"] == ["PR #76", "docs/README.md", "second"]
    assert event["refs"]["docs"] == ["a.md", "b.md"]
    assert event["refs"]["pr"] == 76


def test_cli_add_date_matching_ts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(
        [
            "add",
            "--type",
            "change",
            "--what",
            "w",
            "--why",
            "y",
            "--ts",
            "2026-10-06T19:40:00Z",
            "--date",
            "2026-10-06",
            "--root",
            str(tmp_path),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.strip().endswith("-01")


def test_cli_add_date_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(
        [
            "add",
            "--type",
            "change",
            "--what",
            "w",
            "--why",
            "y",
            "--ts",
            "2026-10-06T19:40:00Z",
            "--date",
            "2026-10-07",
            "--root",
            str(tmp_path),
        ]
    )

    assert code == 1
    assert "does not match" in capsys.readouterr().err


def test_cli_add_bad_date(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(
        [
            "add",
            "--type",
            "change",
            "--what",
            "w",
            "--why",
            "y",
            "--ts",
            "2026-10-06T19:40:00Z",
            "--date",
            "2026/10/06",
            "--root",
            str(tmp_path),
        ]
    )

    assert code == 1
    assert "invalid date" in capsys.readouterr().err


def test_cli_add_duplicate_entry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _add(tmp_path, what="w", why="y")

    code = journal.main(
        ["add", "--type", "change", "--what", "w", "--why", "y", "--root", str(tmp_path)]
    )

    assert code == 1
    assert "already recorded" in capsys.readouterr().err


def test_cli_add_invalid_type_is_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        journal.main(
            ["add", "--type", "bogus", "--what", "w", "--why", "y", "--root", str(tmp_path)]
        )


def test_cli_render_date(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _add(tmp_path, what="w", ts="2026-10-06T10:00:00Z")

    code = journal.main(["render", "--date", "2026-10-06", "--root", str(tmp_path)])

    assert code == 0
    assert capsys.readouterr().out.strip().endswith("20261006.md")


def test_cli_render_all(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _add(tmp_path, what="a", ts="2026-10-06T10:00:00Z")
    _add(tmp_path, what="b", ts="2026-10-07T10:00:00Z")

    code = journal.main(["render", "--root", str(tmp_path)])

    assert code == 0
    out = capsys.readouterr().out
    assert "20261006.md" in out
    assert "20261007.md" in out


def test_cli_render_bad_date(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(["render", "--date", "nope", "--root", str(tmp_path)])

    assert code == 1
    assert "invalid date" in capsys.readouterr().err


def test_cli_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _add(tmp_path, what="change-a", type="change")
    _add(tmp_path, what="decision-a", type="decision")

    code = journal.main(["list", "--type", "decision", "--root", str(tmp_path)])

    assert code == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "id | ts | type | status | what"
    assert len(lines) == 2
    assert "decision-a" in lines[1]
    assert "change-a" not in lines[1]


def test_cli_list_bad_since(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(["list", "--since", "nope", "--root", str(tmp_path)])

    assert code == 1
    assert "invalid timestamp" in capsys.readouterr().err


def test_cli_validate_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _add(tmp_path, what="a")
    _add(tmp_path, what="b", status="open")

    code = journal.main(["validate", "--root", str(tmp_path)])

    assert code == 0
    assert capsys.readouterr().out.strip() == "journal OK (2 events)"


def test_cli_validate_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_events(tmp_path, _event(type="bogus"))

    code = journal.main(["validate", "--root", str(tmp_path)])

    assert code == 1
    assert "error:" in capsys.readouterr().err


def test_cli_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        journal.main([])


def test_transition_appends_deterministic_record(tmp_path: Path) -> None:
    target = _add(tmp_path, what="base", ts="2026-10-06T10:00:00Z")

    record = journal.transition(
        tmp_path,
        target,
        to="superseded",
        why="superseded by a later entry",
        evidence=["PR #9"],
        ts="2026-10-06T11:00:00Z",
    )

    assert record == "J-20261006-02"
    event = _events(tmp_path)[-1]
    assert event["what"] == f"Marked {target} as superseded"
    assert event["type"] == "change"
    assert event["why"] == "superseded by a later entry"
    assert event["evidence"] == ["PR #9", target]
    assert event["refs"]["docs"] == []


def test_transition_default_why_is_deterministic(tmp_path: Path) -> None:
    target = _add(tmp_path, what="base", ts="2026-10-06T10:00:00Z")

    journal.transition(tmp_path, target, to="reverted", ts="2026-10-06T11:00:00Z")

    event = _events(tmp_path)[-1]
    assert event["why"] == f"status transition of {target} to reverted"
    assert event["type"] == "reversal"


def test_transition_rewrites_only_status_field(tmp_path: Path) -> None:
    target = _add(tmp_path, what="base", why="because", ts="2026-10-06T10:00:00Z")
    before = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()[0]

    journal.transition(tmp_path, target, to="superseded", ts="2026-10-06T11:00:00Z")

    after = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()[0]
    assert after == before.replace('"status": "applied"', '"status": "superseded"')
    assert [key for key, _ in json.loads(after, object_pairs_hook=lambda items: items)] == list(
        journal.EVENT_KEYS
    )


def test_transition_preserves_line_order_and_count(tmp_path: Path) -> None:
    first = _add(tmp_path, what="first", ts="2026-10-06T08:00:00Z")
    target = _add(tmp_path, what="target", ts="2026-10-06T09:00:00Z")
    last = _add(tmp_path, what="last", ts="2026-10-06T10:00:00Z")

    journal.transition(tmp_path, target, to="superseded", ts="2026-10-06T11:00:00Z")

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["id"] for line in lines] == [
        first,
        target,
        last,
        "J-20261006-04",
    ]


def test_transition_rerenders_target_day_file(tmp_path: Path) -> None:
    target = _add(tmp_path, what="base", ts="2026-10-06T10:00:00Z")

    journal.transition(tmp_path, target, to="reverted", ts="2026-10-07T09:00:00Z")

    old_day = (tmp_path / "20261006.md").read_text(encoding="utf-8")
    assert "**Status:** reverted" in old_day
    new_day = (tmp_path / "20261007.md").read_text(encoding="utf-8")
    assert f"## J-20261007-01 — Marked {target} as reverted" in new_day


def test_transition_same_status_is_noop(tmp_path: Path) -> None:
    target = _add(tmp_path, what="base", status="open", ts="2026-10-06T10:00:00Z")
    before = (tmp_path / "events.jsonl").read_bytes()

    result = journal.transition(tmp_path, target, to="open")

    assert result is None
    assert (tmp_path / "events.jsonl").read_bytes() == before


def test_transition_unknown_id(tmp_path: Path) -> None:
    _add(tmp_path, what="base", ts="2026-10-06T10:00:00Z")

    with pytest.raises(journal.JournalError, match="J-20261006-99"):
        journal.transition(tmp_path, "J-20261006-99", to="superseded")


def test_cli_transition_prints_record_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _add(tmp_path, what="base", ts="2026-10-06T10:00:00Z")

    code = journal.main(
        [
            "transition",
            target,
            "--to",
            "superseded",
            "--ts",
            "2026-10-06T11:00:00Z",
            "--root",
            str(tmp_path),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.strip() == "J-20261006-02"


def test_cli_transition_same_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = _add(tmp_path, what="base", status="open", ts="2026-10-06T10:00:00Z")

    code = journal.main(["transition", target, "--to", "open", "--root", str(tmp_path)])

    assert code == 0
    assert capsys.readouterr().out.strip() == "already open"


def test_cli_transition_unknown_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = journal.main(
        ["transition", "J-20261006-99", "--to", "superseded", "--root", str(tmp_path)]
    )

    assert code == 1
    assert "J-20261006-99" in capsys.readouterr().err


def test_validate_requires_named_superseded(tmp_path: Path) -> None:
    _write_events(tmp_path, _event(id="J-20261006-01", status="superseded"))

    problems = _problems_text(tmp_path)
    assert "J-20261006-01" in problems
    assert "not named in the evidence of a later entry" in problems


def test_validate_accepts_transition_record(tmp_path: Path) -> None:
    target = _add(tmp_path, what="base", ts="2026-10-06T10:00:00Z")

    journal.transition(tmp_path, target, to="reverted", ts="2026-10-06T11:00:00Z")

    assert journal.validate(tmp_path) == []
