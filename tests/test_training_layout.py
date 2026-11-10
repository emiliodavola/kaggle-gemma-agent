"""The training project adopted the spec layout without touching competition files."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TRAINING = REPO / "training"


def test_configs_exist_and_pin_the_measured_window() -> None:
    configs = TRAINING / "configs"
    for name in ("base", "dataset", "qlora", "sft", "dpo", "evaluation", "runtime"):
        assert (configs / f"{name}.yaml").is_file(), name
    qlora = (configs / "qlora.yaml").read_text(encoding="utf-8")
    assert "max_sequence_length: 10240" in qlora
    assert "manual_gradient_checkpointing: true" in qlora
    assert "int8_embedding_table: true" in qlora
    assert "12288 paginates" in qlora


def test_package_layout_exists() -> None:
    package = TRAINING / "src" / "e4b_training"
    assert (package / "__init__.py").is_file()
    assert (package / "data" / "__init__.py").is_file()
    assert (package / "data" / "audit.py").is_file()
    assert (package / "data" / "canonical.py").is_file()
    assert (package / "data" / "harness_records.py").is_file()
    assert (package / "training" / "__init__.py").is_file()
    assert (package / "training" / "model_inspection.py").is_file()
    assert (package / "evaluation" / "__init__.py").is_file()
    assert (package / "utils" / "paths.py").is_file()
    assert (package / "utils" / "environment.py").is_file()
    assert (TRAINING / "scripts" / "validate_environment.py").is_file()
    assert (TRAINING / "scripts" / "inspect_model.py").is_file()
    assert (TRAINING / "scripts" / "dataset_audit.py").is_file()


def test_deferred_datasets_are_documented() -> None:
    dataset = (TRAINING / "configs" / "dataset.yaml").read_text(encoding="utf-8")
    assert "nvidia/SWE-Hero-openhands-trajectories" in dataset
    assert "nvidia/SWE-Zero-openhands-trajectories" in dataset
    assert "no language column and no resolved column" in dataset
    assert "execution-free" in dataset


def test_dataset_is_harness_native_and_prompt_is_replaced() -> None:
    runtime = (TRAINING / "configs" / "runtime.yaml").read_text(encoding="utf-8")
    assert "dataset_tools:" in runtime
    assert "run_command" in runtime
    assert "submission/prompts/system.md" in runtime
    assert "No tool-name mapping is applied" in runtime
    assert "execute_bash" not in runtime


def test_dataset_audit_is_streamed_and_bounded() -> None:
    dataset = (TRAINING / "configs" / "dataset.yaml").read_text(encoding="utf-8")
    assert "id: vishalxyzabc7527/gemma4-swe-agent-sft-harness" in dataset
    assert "full_download: forbidden" in dataset
    assert "read_mode: streamed-jsonl" in dataset
    assert "local_bytes: 0" in dataset
    assert "rows: 1350" in dataset
    assert "verification_status:\n    VERIFIED: 1350" in dataset
    assert (TRAINING / "src" / "e4b_training" / "data" / "audit.py").is_file()
    assert (TRAINING / "scripts" / "dataset_audit.py").is_file()


def test_training_stays_on_python_312() -> None:
    pyproject = (TRAINING / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12,<3.13"' in pyproject


def test_competition_surface_is_untouched() -> None:
    agent = (REPO / "submission" / "agent.yaml").read_text(encoding="utf-8")
    assert "model: gemma-4-e4b-it-qat-w4a16-ct" in agent
    assert "submit_patch" in agent
    assert (REPO / "submission" / "eval_config.yaml").is_file()
