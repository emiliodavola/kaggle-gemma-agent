# Feature: host-trial-wheels-staging

## Goal

El trial local (`scripts/host-trial/run_host_trial.py`) corria sin las
dependencias de los repos: los contenedores no tenian `starlette` ni resto de
deps y los tests morian en collection con `ModuleNotFoundError`. La notebook
oficial pasa `wheels_dir=<competencia>/wheels` al Evaluator; el runner nunca
lo descargaba.

Decisiones tomadas con el usuario:

1. **Origen**: `wheels/` son 124 archivos `.whl` (26.5 MiB) dentro de la
   COMPETENCIA `gemma-4-developer-agent`, no un dataset (verificado: no existe
   dataset de wheels; `-f wheels/` da 400, por archivo funciona).
2. **Sin flags inventados**: el wheel real de `swegemma` 0.2.7 no tiene flag
   `--wheels-dir`; `resolve_wheels_dir` auto-descubre `<parent de
   tasks.jsonl>/wheels` = `data/raw/wheels`. La fase solo stagea ahi.
3. **Fase `3b/8`** para no renumerar las 8 fases ni tocar el runbook.

## Non-goals

- Descarga masiva de snapshots (sigue solo fastapi_15661/fastapi_15588;
  ver `host-trial-tasks-env`).
- Reintentos ante 429 (ver `host-trial-wheels-backoff`).

## Tasks

- [x] T1 — Fase `3b/8` en `run_host_trial.py`: lista `wheels/` paginando
      `kaggle competitions files`, descarga cada `.whl` con skip si existe,
      `wheels_dir` en `TrialPaths`.
- [x] T2 — 5 tests en `tests/test_host_trial_runner.py` (mock subprocess,
      sin red).
- [x] T3 — `ruff check` + `pytest -q` en verde (98 passed).
- [x] T4 — PR #21 contra `main`, asignado a Emilio, mergeado por el.
- [x] T5 — Poda de la rama local tras el merge.

## Evidence

- PR: https://github.com/emiliodavola/kaggle-gemma-agent/pull/21
- Commit: `feat(host-trial): stage competition task wheels into data/raw/wheels`
- `ls data/raw/wheels | wc -l` = 124 tras el primer trial con la fase.
