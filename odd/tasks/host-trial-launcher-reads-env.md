# Feature: host-trial-launcher-reads-env

## Goal

`serve_local_model.py` leia solo el entorno del proceso, no el `.env` del repo.
Correrlo suelto fallaba con *"no launchable backend"* aunque el `.env` tuviera
`HARNESS_TRIAL_LAUNCH`, porque el `.env` lo lee el runner, no el script.

Decisiones tomadas con el usuario:

1. El script lee `<repo root>/.env` primero y luego el entorno del proceso (gana
   el entorno), igual criterio que el runner.
2. Flag `--env-file <path>` para override.
3. Parser con las mismas reglas que el runner (comentarios, `export`, comillas,
   rechazo de claves duplicadas).

## Non-goals

- Cambiar el comportamiento del runner (ya pasaba el entorno fusionado).

## Tasks

- [x] T1 — `parse_env_file` / `load_env_file` / `merged_env` en el script.
- [x] T2 — `main` usa el entorno fusionado; `--env-file`.
- [x] T3 — Docstring + runbook §6.3.
- [x] T4 — Tests: parser, duplicados, merge, resolucion desde `.env`.
- [x] T5 — `ruff` + `pytest` + `mypy` + `pyright` en verde.

## Evidence

- Rama: `fix/host-trial-launcher-reads-env`.
- `uv run pytest tests/ -q` -> `192 passed`.
- Dry-run sin `--backend`, leyendo el `.env` -> comando de LM Studio correcto.
