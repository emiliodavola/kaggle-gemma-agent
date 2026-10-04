# Feature: run-report-verdicts

Closes #46.

## Goal

El archivador (`src/kaggle_gemma_agent/run_report.py`) marca `unknown` una tarea
que **tiene evidencia de fallo archivada** pero no tiene veredicto explicito ni
JUnit. En `runs/20261003T051525Z` solo 2 de 5 tareas escribieron linea en
`task_results.jsonl`, mientras `fastapi_14962`, `fastapi_15030` y `fastapi_15661`
tienen `test_output.log` con `collection_error`. El report dice
`3 task(s) without verdict` y queda `PARTIAL`, con el rate calculado sobre un
denominador que no distingue "no resuelta" de "no medida".

Ademas, `environment_blocked` solo se prende si el MISMO modulo falta en >= 2
tareas (`run_report.py:702-708`), asi que un gap de un solo modulo
(`typing_inspection` en una tarea, `inline_snapshot` en otra) nunca marca el
entorno, y el report no dice que tarea quedo afectada.

Decisiones tomadas con el usuario:

1. Si no hay veredicto explicito ni JUnit pero el `test_output.log` archivado
   muestra un fallo o un error de coleccion, inferir `resolved=false` con su
   `failure_kind` (ya lo detecta `_classify_failure`).
2. Distinguir el origen del veredicto por tarea (`verdict_source`) y marcar
   `infra_error` cuando falten modulos.
3. Exponer cada modulo faltante con los ids de tarea afectados, y decir cuantas
   de cuantas tareas se midieron.
4. `environment_blocked` pasa a reflejar cualquier gap de modulo (no solo el
   uniforme >= 2), sin inventar veredictos.

## Non-goals

- Cambiar la emision de resultados de `swegemma`.
- Re-correr el trial.
- Inferir `resolved` cuando NO hay ninguna evidencia (eso sigue siendo `unknown`).

## Tasks

- [ ] T1 — `_infer_resolved` (o un helper nuevo) infiere `false` desde la
      evidencia de test cuando no hay veredicto/JUnit.
- [ ] T2 — `_build_task` agrega `verdict_source` y `infra_error`.
- [ ] T3 — `build_report`: `missing_module_tasks` (modulo -> ids) y
      `environment_blocked` para cualquier gap; `status_reasons`/totales dicen
      cuantas tareas se midieron.
- [ ] T4 — Tests nuevos + actualizar los que fijan el comportamiento viejo.
- [ ] T5 — `ruff` + `pytest` + `mypy` + `pyright` + coverage en verde.

## Evidence

- Issue: #46. Rama: `fix/run-report-verdicts` (desde `main`).
- (a completar con salidas reales.)
