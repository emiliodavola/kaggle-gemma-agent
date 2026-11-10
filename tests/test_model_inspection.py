"""T2: inspect the base model without loading its weights."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training" / "src"))

from e4b_training.training.model_inspection import inspect, main

MODULES = (
    "self_attn.q_proj",
    "self_attn.k_proj",
    "self_attn.v_proj",
    "self_attn.o_proj",
    "mlp.gate_proj",
    "mlp.up_proj",
    "mlp.down_proj",
)


def _write_model(directory: Path) -> None:
    tensors: dict[str, dict] = {}
    for layer in range(2):
        for module in MODULES:
            tensors[f"model.language_model.layers.{layer}.{module}.weight"] = {
                "dtype": "BF16",
                "shape": [4, 4],
                "data_offsets": [0, 0],
            }
    tensors["model.vision_tower.patch.weight"] = {
        "dtype": "BF16",
        "shape": [4, 4],
        "data_offsets": [0, 0],
    }
    tensors["model.audio_tower.conv.weight"] = {
        "dtype": "BF16",
        "shape": [4, 4],
        "data_offsets": [0, 0],
    }
    header = json.dumps(tensors).encode("utf-8")
    (directory / "model.safetensors").write_bytes(struct.pack("<Q", len(header)) + header)
    (directory / "config.json").write_text(
        json.dumps(
            {
                "model_type": "gemma4",
                "architectures": ["Gemma4ForConditionalGeneration"],
                "num_hidden_layers": 2,
                "hidden_size": 4,
                "vocab_size": 32,
                "torch_dtype": "bfloat16",
            }
        ),
        encoding="utf-8",
    )
    (directory / "tokenizer_config.json").write_text(
        json.dumps({"chat_template": "<|tool_call>"}), encoding="utf-8"
    )
    (directory / "chat_template.jinja").write_text(
        "<|tool_call> and <|tool_response>", encoding="utf-8"
    )
    (directory / "generation_config.json").write_text("{}", encoding="utf-8")
    (directory / "processor_config.json").write_text("{}", encoding="utf-8")


def test_inspect_discovers_modules(tmp_path: Path) -> None:
    _write_model(tmp_path)
    report = inspect(tmp_path)

    assert report["discovered"]["layers"] == [0, 1]
    assert report["target_regex_matches"] == 14
    assert all(report["candidate_modules_present"].values())
    assert all(report["mlp_modules_present"].values())
    assert report["towers"] == {"vision": True, "audio": True}
    assert report["tool_call_tokens"]["<|tool_call>"] is True
    assert report["tool_call_tokens"]["<|tool_response>"] is True
    assert report["tensor_count"] == 16


def test_main_writes_report(tmp_path: Path) -> None:
    _write_model(tmp_path)
    out = tmp_path / "report.json"
    assert main(["--model-dir", str(tmp_path), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["target_regex_matches"] == 14
