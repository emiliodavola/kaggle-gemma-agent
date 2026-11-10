"""Inspect the base model without loading its weights.

The checkpoint is a single 16 GB ``model.safetensors``. Only its safetensors
header is read, so every parameter name is available without the weights. The
small config, tokenizer and chat-template files are read from the same local
snapshot, and the pinned Hugging Face revision is recorded for provenance.

The module imports only the standard library at import time; ``peft``,
``bitsandbytes`` and ``transformers`` are imported inside their reports so the
inspector stays runnable in a minimal environment.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

from e4b_training.utils.paths import ARTIFACTS_DIR

MODEL_ID = "google/gemma-4-E4B-it"
REVISION = "4ecc2ba63bcac23ba4a767fc87025b1450f84c9c"
CANDIDATES = ("q_proj", "k_proj", "v_proj", "o_proj")
MLP_CANDIDATES = ("gate_proj", "up_proj", "down_proj")
TARGET_REGEX = (
    r".*language_model\.layers\.\d+\.(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj)$"
)
LAYER_PATTERN = re.compile(r"language_model\.layers\.(\d+)\.")
MODULE_PATTERN = re.compile(r"language_model\.layers\.\d+\.((?:self_attn|mlp)\.[^.]+)\.weight$")
TOOL_TOKENS = ("<|tool_call>", "<|tool_response>", "<|tool_call|>", "<|tool_response|>")


def default_model_dir() -> Path:
    return Path.home() / ".cache/kagglehub/models/google/gemma-4/transformers/gemma-4-e4b-it/1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safetensors_keys(path: Path) -> tuple[list[str], int]:
    with path.open("rb") as handle:
        header_length = struct.unpack("<Q", handle.read(8))[0]
        header = json.loads(handle.read(header_length))
    keys = [key for key in header if key != "__metadata__"]
    return keys, header_length


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def discover_modules(keys: list[str]) -> dict[str, Any]:
    layers = sorted({int(match.group(1)) for key in keys if (match := LAYER_PATTERN.search(key))})
    modules = sorted({match.group(1) for key in keys if (match := MODULE_PATTERN.search(key))})
    attention = sorted(
        {module.split(".", 1)[1] for module in modules if module.startswith("self_attn.")}
    )
    mlp = sorted({module.split(".", 1)[1] for module in modules if module.startswith("mlp.")})
    return {"layers": layers, "attention": attention, "mlp": mlp, "modules": modules}


def _peft_report() -> dict[str, Any]:
    try:
        import peft
        from peft import LoraConfig

        LoraConfig(
            r=32,
            lora_alpha=64,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=TARGET_REGEX,
        )
        return {"available": True, "version": peft.__version__, "regex_accepted": True}
    except Exception as error:
        return {"available": False, "error": str(error), "regex_accepted": False}


def _quantization_report() -> dict[str, Any]:
    try:
        import bitsandbytes as bnb
        from transformers import BitsAndBytesConfig

        config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        return {
            "available": True,
            "bitsandbytes": getattr(bnb, "__version__", "unknown"),
            "nf4_config": type(config).__name__,
        }
    except Exception as error:
        return {"available": False, "error": str(error)}


def inspect(model_dir: Path | None = None) -> dict[str, Any]:
    directory = model_dir or default_model_dir()
    config = _read_json(directory / "config.json")
    tokenizer_config = _read_json(directory / "tokenizer_config.json")
    template = _read_text(directory / "chat_template.jinja") or str(
        tokenizer_config.get("chat_template") or ""
    )
    generation = _read_json(directory / "generation_config.json")
    processor = _read_json(directory / "processor_config.json")
    weights = directory / "model.safetensors"
    keys, header_length = _safetensors_keys(weights) if weights.is_file() else ([], 0)

    discovered = discover_modules(keys)
    regex = re.compile(TARGET_REGEX)
    module_names = [key[: -len(".weight")] for key in keys if key.endswith(".weight")]
    matched = [name for name in module_names if regex.match(name)]
    files = {
        name: (directory / name).stat().st_size
        for name in (
            "config.json",
            "tokenizer_config.json",
            "chat_template.jinja",
            "generation_config.json",
            "processor_config.json",
            "model.safetensors",
        )
        if (directory / name).is_file()
    }
    return {
        "schema_version": "1.0",
        "model_id": MODEL_ID,
        "pinned_revision": REVISION,
        "local_dir": str(directory),
        "files": files,
        "config": {
            "model_type": config.get("model_type"),
            "architectures": config.get("architectures"),
            "num_hidden_layers": config.get("num_hidden_layers"),
            "hidden_size": config.get("hidden_size"),
            "vocab_size": config.get("vocab_size"),
            "torch_dtype": config.get("torch_dtype"),
        },
        "discovered": discovered,
        "target_regex": TARGET_REGEX,
        "target_regex_matches": len(matched),
        "candidate_modules_present": {name: name in discovered["attention"] for name in CANDIDATES},
        "mlp_modules_present": {name: name in discovered["mlp"] for name in MLP_CANDIDATES},
        "towers": {
            "vision": any("vision_tower" in key for key in keys),
            "audio": any("audio_tower" in key for key in keys),
        },
        "tool_call_tokens": {token: token in template for token in TOOL_TOKENS},
        "template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
        "tokenizer_config_keys": sorted(tokenizer_config),
        "generation_config": generation,
        "processor_config_keys": sorted(processor),
        "peft": _peft_report(),
        "quantization": _quantization_report(),
        "safetensors_header_bytes": header_length,
        "tensor_count": len(keys),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect the base model without weights.")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=ARTIFACTS_DIR / "reports" / "model_inspection.json",
    )
    args = parser.parse_args(argv)

    report = inspect(args.model_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    candidates = report["candidate_modules_present"]
    print(
        f"layers={len(report['discovered']['layers'])} "
        f"target_matches={report['target_regex_matches']} "
        f"candidates={candidates} mlp={report['mlp_modules_present']} "
        f"tool_tokens={report['tool_call_tokens']}"
    )
    print(f"wrote {args.out}")
    return 0 if all(candidates.values()) and report["target_regex_matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
