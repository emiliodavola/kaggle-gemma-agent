# Feature: host-trial-tasks-env

## Goal

Los trial tasks estaban hardcodeados (`TASK_IDS` con 2 fastapi). Hacerlos
configurables por `.env` y generalizar la descarga de snapshots para que el
trial sirva para cualquier task, no solo los 2 iniciales.

Decisiones tomadas con el usuario:

1. **Via `.env`, no flag CLI**: `HARNESS_TRIAL_TASKS` (comma-separated),
   con precedencia `environ > .env > default` (mismo patron que el resto de
   claves del trial). Entrada comentada en `.env.example`.
2. **Snapshots derivados de los ids resueltos** (`snapshots/<id>.tgz`),
   en la misma rama/PR (pedido explicito del usuario).

## Non-goals

- Correr mas de 2 tasks por defecto (el default sigue igual; es smoke trial).

## Tasks

- [x] T1 — `HARNESS_TRIAL_TASKS` + `parse_trial_tasks()`/`resolve_trial_tasks()`
      en `run_host_trial.py`, cableado en `resolve_backend_env` y `run_eval`.
- [x] T2 — Entrada comentada en `.env.example` con el default documentado.
- [x] T3 — `snapshot_remote_files(task_ids)`; `fetch_data()` descarga N
      snapshots via `_fetch_competition_file` con skip si existe.
- [x] T4 — 7 + 5 tests (mock subprocess/red).
- [x] T5 — `ruff check` + `pytest -q` en verde (109 passed).
- [ ] T6 — Push + PR contra `main` asignado a Emilio (2 commits:
      `15399e3`, `b7d86f6`). Sin mergear.

## Evidence

- Rama local: `fix/host-trial-tasks-env` (sin push).
- Verificado por Robotina: ruff limpio, 109/109 pytest.
