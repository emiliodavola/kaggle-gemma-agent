# training/ structure

This file maps the G4-PY-AGENT-001 tree onto this repository. It exists because
the specification describes a standalone project while this repository already
owns the competition line; nothing here creates a second top-level project or
touches `submission/`. The source documents live in `training/specs/`.

## Present

| Specification path | Here | Status |
|--------------------|------|--------|
| `configs/` | `training/configs/` | present: seven YAML files reconciled with the measured envelope |
| `scripts/validate_environment.py` | `training/scripts/validate_environment.py` | present: JSON report, non-zero on incompatibility |
| `src/utils/` | `training/src/e4b_training/utils/` | present: roots and host report |
| `data/` | `training/data/` | directories documented; contents git-ignored |
| `artifacts/` | `training/artifacts/` | directories documented; contents git-ignored |

## Migrating (tracked in `odd/tasks/autonomous-e4b.md`)

| Specification path | Current implementation | Task |
|--------------------|------------------------|------|
| `src/data/` | `training/src/e4b_training/data/audit.py`; the flat `parse_session.py` and `build_decisions.py` remain for the harness teacher path | T4-T7 |
| `scripts/dataset_audit.py` | present: streams the harness-native JSONL and writes the census | done |
| `src/training/` | `training/smoke_qlora.py`, `smoke_train.py`, `train_lora.py` | T8 |
| `src/evaluation/` | `training/eval_holdout.py`, `compare_order.py`, `roundtrip_format.py` | T9 |
| `scripts/inspect_model.py` | not implemented | T2 |
| `scripts/download_datasets.py` and the dataset stage | `scripts/dataset_audit.py` streams the source; normalization, filtering, dedup and split are not implemented | T4-T7 |
| `scripts/train_dpo.py` and `src/training/dpo.py` | disabled until 500 verified pairs | T12 |

## Deferred by decision

| Specification path | Why |
|--------------------|-----|
| `src/agent/`, `src/tools/`, `docker/` | the swegemma harness is the runtime inside the competition; a second agent runtime is out of scope |
| `src/evaluation/swebench.py` | SWE-bench is an optional diagnostic, not a shipping gate |
| 50,000-record corpus and 16,384-token context | the competition signal is `ft-holdout`; the measured ceiling is 10240 |

## Rule

The competition surface is byte-identical: `submission/`, `src/kaggle_gemma_agent/`,
`notebooks/`, `tests/` and the harness scripts keep their current behaviour. A
change here is accepted only if `uv run python -m kaggle_gemma_agent.pack
submission --check` stays green.
