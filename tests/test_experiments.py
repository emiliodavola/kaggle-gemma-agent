"""Focused tests for declared A/B experiments."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kaggle_gemma_agent import experiments, run_report

DEFAULT_PROVENANCE = {
    "prompt": "p1",
    "skills": "s1",
    "sampling": "sm1",
    "eval_config": "e1",
    "repo_commit": "c1",
}


def _write_subset(root: Path) -> Path:
    path = root / "experiments" / "subsets" / "dev-v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "id": "dev-v1",
                "description": "contrast set",
                "selection": "chosen for signal",
                "task_ids": ["a__1", "b__2"],
                "counts": {"org/a": 1, "org/b": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _start(root: Path, **overrides: object) -> Path:
    subset = _write_subset(root)
    values: dict[str, object] = {
        "experiment_id": "e1",
        "subset": subset,
        "component": "prompt",
        "direction": "helped",
        "change": "add one rule",
        "backend": "lmstudio",
        "model": "gemma",
    }
    values.update(overrides)
    return experiments.start(root, **values)  # type: ignore[arg-type]


def _make_run(
    root: Path,
    run_id: str,
    *,
    subset_sha: str,
    task_ids: tuple[str, ...] = ("a__1", "b__2"),
    resolved: tuple[bool | None, ...] = (True, False),
    failure_kinds: tuple[str | None, ...] = (None, "test_failure"),
    patch_scopes: tuple[str, ...] = ("src_only", "none"),
    submitted: tuple[bool, ...] = (True, False),
    experiment_id: str = "e1",
    backend: str = "lmstudio",
    model: str = "gemma",
    provenance: dict[str, str] | None = None,
) -> Path:
    run_dir = root / "runs" / run_id
    run_dir.mkdir(parents=True)
    budgets = dict(run_report.DEFAULT_BUDGETS)
    tasks = [
        {
            "instance_id": task_id,
            "resolved": resolved[index],
            "failure_kind": failure_kinds[index],
            "delivery": {
                "patch_scope": patch_scopes[index],
                "submitted": submitted[index],
                "patch_files": [],
                "ran_pytest": False,
                "ran_target_test": False,
            },
            "tool_calls": 10,
            "wall_seconds": 60.0,
            "patch_sha256": None,
        }
        for index, task_id in enumerate(task_ids)
    ]
    report = {
        "schema_version": run_report.SCHEMA_VERSION,
        "run_id": run_id,
        "env": {"backend": model},
        "budgets": budgets,
        "tasks": tasks,
    }
    (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    manifest = {
        "experiment": {
            "id": experiment_id,
            "subset": {
                "id": "dev-v1",
                "sha256": subset_sha,
                "task_ids": list(task_ids),
            },
            "backend": backend,
            "model": model,
            "budgets": budgets,
            "task_ids": list(task_ids),
        },
        "provenance": provenance or dict(DEFAULT_PROVENANCE),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def _subset_sha(root: Path) -> str:
    return experiments.load_experiment(root, "e1").data["subset"]["sha256"]


def test_start_writes_the_declaration(tmp_path: Path) -> None:
    path = _start(tmp_path)

    assert path == tmp_path / "experiments" / "e1" / "experiment.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["id"] == "e1"
    assert data["subset"]["id"] == "dev-v1"
    assert data["component"] == "prompt"
    assert data["direction"] == "helped"
    assert data["runs"] == {"base": None, "variant": None}
    assert set(data["provenance"]) == set(DEFAULT_PROVENANCE)


def test_start_refuses_an_existing_declaration(tmp_path: Path) -> None:
    _start(tmp_path)

    with pytest.raises(experiments.ExperimentError, match="already exists"):
        _start(tmp_path)


def test_start_rejects_a_bad_component(tmp_path: Path) -> None:
    with pytest.raises(experiments.ExperimentError, match="component"):
        _start(tmp_path, component="everything")


def test_finish_no_observed_effect_keeps_delivery_descriptive(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha)
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        submitted=(True, True),
        patch_scopes=("src_only", "src_only"),
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2"},
    )

    result = experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)

    assert result["resolution_verdict"] == "no observed effect"
    assert result["delivery_signal"]["submitted"] == 1
    assert result["identity"]["differing_provenance"] == ["prompt"]
    assert (tmp_path / "experiments" / "e1" / "comparison.json").is_file()


def test_finish_helped_when_resolved_increases(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha, resolved=(False, False))
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        resolved=(True, False),
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2"},
    )

    result = experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)

    assert result["resolution_verdict"] == "helped"
    assert "resolved 0 -> 1" in result["resolution_reason"]


def test_finish_hurt_when_resolved_decreases(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha, resolved=(True, True))
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        resolved=(True, False),
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2"},
    )

    result = experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)

    assert result["resolution_verdict"] == "hurt"


def test_finish_refuses_two_differing_components(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha)
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2", "skills": "s2"},
    )

    with pytest.raises(experiments.ExperimentError, match="differing provenance"):
        experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)
    assert not (tmp_path / "experiments" / "e1" / "comparison.json").exists()


def test_finish_refuses_a_different_commit(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha)
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2", "repo_commit": "c2"},
    )

    with pytest.raises(experiments.ExperimentError, match="differing provenance"):
        experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)


def test_finish_refuses_a_different_backend(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha)
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        backend="cloud",
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2"},
    )

    with pytest.raises(experiments.ExperimentError, match="backend differs"):
        experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)


def test_finish_refuses_a_missing_task(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha)
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        task_ids=("a__1",),
        resolved=(True,),
        failure_kinds=(None,),
        patch_scopes=("src_only",),
        submitted=(True,),
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2"},
    )

    with pytest.raises(experiments.ExperimentError, match="task set mismatch"):
        experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)


def test_render_comparison_has_both_sections(tmp_path: Path) -> None:
    _start(tmp_path)
    sha = _subset_sha(tmp_path)
    base = _make_run(tmp_path, "base", subset_sha=sha)
    variant = _make_run(
        tmp_path,
        "variant",
        subset_sha=sha,
        provenance={**DEFAULT_PROVENANCE, "prompt": "p2"},
    )
    result = experiments.finish(tmp_path, experiment_id="e1", base_run=base, variant_run=variant)

    text = experiments.render_comparison(result)

    assert "Delivery signal (descriptive, never a verdict - R8)" in text
    assert "Resolution verdict" in text
    assert "**no observed effect**" in text
    assert "| `a__1` |" in text


def test_cli_start_and_show(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    subset = _write_subset(tmp_path)

    assert (
        experiments.main(
            [
                "--root",
                str(tmp_path),
                "start",
                "--id",
                "e1",
                "--subset",
                str(subset),
                "--component",
                "prompt",
                "--direction",
                "helped",
                "--change",
                "add one rule",
                "--backend",
                "lmstudio",
                "--model",
                "gemma",
            ]
        )
        == 0
    )
    assert "declared e1" in capsys.readouterr().out

    assert experiments.main(["--root", str(tmp_path), "show", "--id", "e1"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "e1"
