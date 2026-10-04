# Feature: host-trial-repair-audit

Closes #45.

## Goal

`--repair-sandbox-deps` puede saltearse en silencio y el run archivado no deja
constancia de si la reparación corrió. Dos fallas concretas:

1. `ensure_trial_wheels` (`scripts/host-trial/run_host_trial.py`) solo mergea
   `wheels-extra/` y resuelve el closure core dentro del bloque `if repair:`
   (linea ~1515). Si `_list_competition_wheels()` falla y se pasa
   `--allow-partial-wheels`, la funcion hace `return` en la linea ~1484, ANTES de
   ese bloque: la reparacion se ignora aunque se haya pedido.
2. `manifest.json` (`harness_runs.archive_run`) y `report.json`/`STATUS`
   (`run_report`) no registran el modo. Un report que lista un modulo que vive en
   `wheels-extra/` no se puede atribuir a "repair off" vs "repair salteado".

Evidencia: `data/raw/wheels-extra/typing_inspection-0.4.4-py3-none-any.whl` esta
staged, `data/raw/wheels/` no lo tiene, y `runs/20261003T051525Z/report.json`
igual lo lista faltante: el merge nunca corrio.

Decisiones tomadas con el usuario:

1. El merge de suplementarios + el closure core corren siempre que
   `repair=True`, sin importar el resultado del listing remoto.
2. El modo se registra de punta a punta: runner -> archiver -> manifest ->
   report/STATUS, como `sandbox_deps_mode` (`faithful` | `repaired` | `null`).
3. No se parchea `swegemma`; el fix es 100% en codigo propio.

## Non-goals

- Re-correr el trial.
- El bug de paths `read_file`/`edit_file` en Windows (tool layer externa).
- Cambiar el default del flag (sigue off = fiel).

## Tasks

- [ ] T1 — Runner: reestructurar `ensure_trial_wheels` para que el early-return
      por listing caido no saltee el bloque de repair (flag local, sin `return`).
- [ ] T2 — Runner: `build_archive_args(..., sandbox_deps_mode)` y `run()` pasan
      el modo; `archive_and_report` lo propaga.
- [ ] T3 — Archiver: `archive_run(..., sandbox_deps_mode=None)` lo guarda en
      `manifest.json`; `_main_archive` acepta `--sandbox-deps-mode`.
- [ ] T4 — Report: `build_report` lee el manifest y expone `sandbox_deps_mode`;
      `render_summary` (STATUS) lo muestra.
- [ ] T5 — Tests: listing caido + `allow_partial` + `repair` igual mergea/core;
      el manifest y el report/STATUS llevan el modo.
- [ ] T6 — `ruff` + `pytest` + `mypy` + `pyright` + coverage en verde.

## Evidence

- Issue: #45. Rama: `fix/host-trial-repair-audit` (desde `main`).
- (a completar con salidas reales: pytest, ruff, coverage, y la linea de STATUS
  con el modo.)
