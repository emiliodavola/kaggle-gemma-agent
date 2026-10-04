# Feature: host-trial-local-model-launcher

## Goal

Los servidores locales (LM Studio, llama.cpp) suelen correr en el **host
Windows**, mientras que el runner corre en **WSL**. Hacia falta un script aparte
que arranque el modelo con el contexto correcto y que el runner pueda llamar.

Decisiones tomadas con el usuario:

1. Script aparte (`scripts/host-trial/serve_local_model.py`), invocado por el
   runner; no meter el lanzamiento dentro del runner.
2. Contexto por defecto **26214** (limitado por VRAM de la RTX 3090; el techo de
   la competencia es 32768).
3. El script resuelve la interop WSL -> Windows (binarios `.exe`), porque los
   servidores viven en Windows.
4. llama.cpp: el script arma los flags verificados en la doc oficial. LM Studio:
   `lms server start` + `lms load ... --context-length ...`.

## Non-goals

- Empaquetar el modelo o el `.gguf` en el submission.
- Hardcodear rutas de modelo.
- Gestionar el ciclo de vida de llama.cpp en Windows (parada manual).

## Tasks

- [x] T1 — Script: builders puros de comandos para lmstudio y llamacpp.
- [x] T2 — Script: deteccion de WSL y sufijo `.exe`; arranque detached.
- [x] T3 — Script: `start` / `stop` / `status`, `--dry-run`, espera de `/v1/models`.
- [x] T4 — Runner: `--launch-model` / `--keep-model` y `HARNESS_TRIAL_LAUNCH`.
- [x] T5 — Docs: `.env.example` + runbook §6.3.
- [x] T6 — Tests: builders, resolucion de backend/contexto/puerto, espera de endpoint.
- [x] T7 — `ruff` + `pytest` + `mypy` + `pyright` + `pack --check` en verde.

## Evidence

- Rama: `feat/host-trial-local-model-launcher`.
- `uv run pytest tests/ -q` -> `187 passed`.
- (a completar con la salida real del PR.)
