"""Focused tests for fixed task subsets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kaggle_gemma_agent import subsets

TASKS = Path("data/raw/tasks.jsonl")


def _write_subset(
    root: Path,
    body: dict[str, object],
    *,
    name: str = "dev-v1.json",
) -> Path:
    directory = root / "experiments" / "subsets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "1.0",
        "id": "dev-v1",
        "description": "contrast set",
        "selection": "chosen for signal",
        "task_ids": ["a__1", "b__2"],
        "counts": {"org/a": 1, "org/b": 1},
    }
    body.update(overrides)
    return body


def _corpus(path: Path, rows: list[tuple[str, str]]) -> Path:
    path.write_text(
        "\n".join(json.dumps({"instance_id": i, "repo": r}) for i, r in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_committed_dev_v1_is_valid_and_matches_the_corpus() -> None:
    subset = subsets.load_subset("dev-v1")

    assert subset.id == "dev-v1"
    assert len(subset.task_ids) == 11
    assert subset.task_ids == tuple(sorted(subset.task_ids))
    assert subset.counts == {
        "Textualize/rich": 5,
        "encode/httpx": 1,
        "fastapi/fastapi": 2,
        "psf/requests": 3,
    }
    if TASKS.is_file():
        assert subsets.validate_against_corpus(subset, TASKS) == []
    else:
        pytest.skip("data/raw/tasks.jsonl is not present on this checkout")


def test_resolve_bare_name_path_and_absolute(tmp_path: Path) -> None:
    root = tmp_path
    (root / "experiments" / "subsets").mkdir(parents=True)
    assert subsets.subset_path("dev-v1", root=root) == (
        root / "experiments" / "subsets" / "dev-v1.json"
    )
    assert subsets.subset_path("dev-v1.json", root=root) == (
        root / "experiments" / "subsets" / "dev-v1.json"
    )
    assert subsets.subset_path("experiments/subsets/x.json", root=root) == (
        root / "experiments" / "subsets" / "x.json"
    )
    absolute = tmp_path / "elsewhere" / "y.json"
    assert subsets.subset_path(absolute, root=root) == absolute


def test_reject_duplicate_unsorted_and_empty_ids(tmp_path: Path) -> None:
    _write_subset(
        tmp_path,
        _body(task_ids=["b__2", "a__1"], counts={"org/a": 1, "org/b": 1}),
    )
    with pytest.raises(subsets.SubsetError, match="sorted"):
        subsets.load_subset("dev-v1", root=tmp_path)

    _write_subset(
        tmp_path,
        _body(task_ids=["a__1", "a__1"], counts={"org/a": 2}),
    )
    with pytest.raises(subsets.SubsetError, match="duplicate"):
        subsets.load_subset("dev-v1", root=tmp_path)

    _write_subset(tmp_path, _body(task_ids=[], counts={}))
    with pytest.raises(subsets.SubsetError, match="non-empty"):
        subsets.load_subset("dev-v1", root=tmp_path)


def test_reject_unknown_missing_and_mismatched_counts(tmp_path: Path) -> None:
    body = _body()
    body["extra"] = True
    _write_subset(tmp_path, body)
    with pytest.raises(subsets.SubsetError, match="unknown key"):
        subsets.load_subset("dev-v1", root=tmp_path)

    body = _body()
    del body["selection"]
    _write_subset(tmp_path, body)
    with pytest.raises(subsets.SubsetError, match="missing key"):
        subsets.load_subset("dev-v1", root=tmp_path)

    _write_subset(tmp_path, _body(counts={"org/a": 1}))
    with pytest.raises(subsets.SubsetError, match="counts sum"):
        subsets.load_subset("dev-v1", root=tmp_path)


def test_validate_against_corpus_reports_missing_ids_and_counts(tmp_path: Path) -> None:
    tasks = _corpus(tmp_path / "tasks.jsonl", [("a__1", "org/a")])
    subset = subsets.load_subset(
        _write_subset(tmp_path, _body(task_ids=["a__1", "b__2"])),
        root=tmp_path,
    )

    errors = subsets.validate_against_corpus(subset, tasks)

    assert any("absent from the corpus: b__2" in error for error in errors)
    assert any("counts disagree" in error for error in errors)


def test_build_document_sorts_ids_and_computes_counts(tmp_path: Path) -> None:
    tasks = _corpus(
        tmp_path / "tasks.jsonl",
        [("b__2", "org/b"), ("a__1", "org/a"), ("c__3", "org/a")],
    )

    document = subsets.build_document(
        ["c__3", "a__1", "b__2", "a__1"],
        subset_id="dev-v1",
        description="contrast set",
        selection="chosen for signal",
        tasks_path=tasks,
    )

    assert document["task_ids"] == ["a__1", "b__2", "c__3"]
    assert document["counts"] == {"org/a": 2, "org/b": 1}


def test_build_document_rejects_an_unknown_id(tmp_path: Path) -> None:
    tasks = _corpus(tmp_path / "tasks.jsonl", [("a__1", "org/a")])
    with pytest.raises(subsets.SubsetError, match="absent from the corpus"):
        subsets.build_document(
            ["a__1", "missing"],
            subset_id="dev-v1",
            description="x",
            selection="y",
            tasks_path=tasks,
        )


def test_sha256_tracks_the_bytes(tmp_path: Path) -> None:
    path = _write_subset(tmp_path, _body())
    first = subsets.subset_sha256(path)
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert subsets.subset_sha256(path) != first


def test_cli_validate_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tasks = _corpus(tmp_path / "tasks.jsonl", [("a__1", "org/a"), ("b__2", "org/b")])
    _write_subset(tmp_path, _body())

    assert subsets.main(["validate", "dev-v1", "--root", str(tmp_path), "--tasks", str(tasks)]) == 0
    first = capsys.readouterr().out
    assert "dev-v1: 2 tasks" in first

    assert subsets.main(["show", "dev-v1", "--root", str(tmp_path)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["task_ids"] == ["a__1", "b__2"]
