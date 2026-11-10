"""The shipped adapter config must be UTF-8 without a BOM.

vLLM loads ``adapter_config.json`` with ``json.load``, which rejects a UTF-8
BOM. A Windows PowerShell round-trip added one once; this test keeps it out.
"""

from __future__ import annotations

import json
from pathlib import Path

ADAPTER = (
    Path(__file__).resolve().parents[1]
    / "submission"
    / "adapters"
    / "main_lora"
    / "adapter_config.json"
)


def test_adapter_config_has_no_utf8_bom() -> None:
    raw = ADAPTER.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), (
        "adapter_config.json must not start with a UTF-8 BOM"
    )


def test_adapter_config_matches_the_trained_adapter() -> None:
    payload = json.loads(ADAPTER.read_text(encoding="utf-8"))
    assert payload["base_model_name_or_path"] == "google/gemma-4-E4B-it"
    assert payload["r"] == 32
    assert payload["lora_alpha"] == 64
    assert payload["peft_type"] == "LORA"
