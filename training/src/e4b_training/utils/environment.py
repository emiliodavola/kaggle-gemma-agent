"""Hardware and software report for the training host.

Collects only the facts the pipeline needs before it touches datasets or
weights: GPU identity and memory through ``nvidia-smi``, CUDA and PyTorch,
compute capability, BF16 support, and whether bitsandbytes can build the NF4
configuration. It never loads the model, so it is cheap on a fresh host.

The report is JSON on stdout. Exit code 0 means the host matches the RTX 3090
profile; 1 means at least one compatibility problem is listed in the report.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys


def _nvidia_smi() -> dict:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,driver_version",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "error": str(error)}
    if completed.returncode != 0:
        return {"available": False, "error": completed.stderr.strip()}
    gpus = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        gpus.append(
            {
                "name": parts[0],
                "memory_total_mib": int(float(parts[1])),
                "memory_free_mib": int(float(parts[2])),
                "driver_version": parts[3],
            }
        )
    return {"available": bool(gpus), "gpus": gpus}


def collect() -> dict:
    report = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "nvidia_smi": _nvidia_smi(),
    }
    try:
        import torch
    except Exception as error:
        report["torch"] = {"available": False, "error": str(error)}
        return report

    report["torch"] = {
        "available": True,
        "version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "device_count": torch.cuda.device_count(),
    }
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        report["torch"].update(
            {
                "device_name": properties.name,
                "compute_capability": f"{properties.major}.{properties.minor}",
                "total_memory_gib": round(properties.total_memory / 1024**3, 2),
                "bf16_supported": torch.cuda.is_bf16_supported(),
            }
        )

    try:
        import bitsandbytes as bnb
        from transformers import BitsAndBytesConfig

        config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        report["bitsandbytes"] = {
            "available": True,
            "version": getattr(bnb, "__version__", "unknown"),
            "nf4_config": True,
            "quantization_config": type(config).__name__,
        }
    except Exception as error:
        report["bitsandbytes"] = {"available": False, "error": str(error)}
    return report


def compatibility(report: dict) -> list[str]:
    problems: list[str] = []
    smi = report.get("nvidia_smi", {})
    gpus = smi.get("gpus", []) if smi.get("available") else []
    if not gpus:
        problems.append("nvidia-smi reported no GPU")
    elif "RTX 3090" not in gpus[0]["name"]:
        problems.append(f"GPU is {gpus[0]['name']}, expected an RTX 3090")

    torch_report = report.get("torch", {})
    if not torch_report.get("available"):
        problems.append("PyTorch is not importable")
    elif not torch_report.get("cuda_available"):
        problems.append("PyTorch cannot see CUDA")

    if not report.get("bitsandbytes", {}).get("nf4_config"):
        problems.append("bitsandbytes cannot build the NF4 configuration")
    return problems


def main() -> int:
    report = collect()
    report["compatibility_problems"] = compatibility(report)
    print(json.dumps(report, indent=2))
    return 0 if not report["compatibility_problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
