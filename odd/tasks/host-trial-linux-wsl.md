# Feature: host-trial-linux-wsl

Closes #47.

## Goal

El runbook documentaba solo Windows 11 + Docker Desktop, pero el bug de paths de
`read_file`/`edit_file`/`write_file` es **del host**: la tool layer externa
(`adk-eval-core`) arma los paths del container con semantica Windows
(`/workspace/D:\workspace\...` -> `FileReadError 404 localnpipe`). La evaluacion
de Kaggle corre en Linux, donde ese camino es POSIX y no falla. Un trial en
Windows quema tool calls (`fastapi_14962` ~30, `fastapi_15588` ~47) y subestima el
resolution rate. `odd/tasks/host-trial-wheel-closure.md:40-41` ya lo lista como
non-goal.

Decisiones tomadas con el usuario:

1. No se parchea la tool layer externa; se documenta como correr el trial en
   Linux/WSL2, que es la solucion real.
2. El runbook pasa a ser cross-platform (titulo + nota de fase) y suma una
   seccion §1.5 con prerequisitos y pasos exactos.
3. Un trial en Windows queda documentado como **piso pesimista**, no como
   estimacion final.

## Non-goals

- Parchear `adk-eval-core` / `swegemma`.
- Cambios de CI o de codigo.
- Re-correr el trial.

## Tasks

- [x] T1 — Runbook: titulo + intro cross-platform.
- [x] T2 — Runbook: §1.1 apunta a §1.5 para el trial representativo.
- [x] T3 — Runbook: §1.5 (por que, prerequisitos WSL2, pasos, `/mnt/c`).
- [ ] T4 — `pytest` en verde (docs-only) y PR contra `main`.

## Evidence

- Issue: #47. Rama: `docs/host-trial-linux-wsl` (desde `main`).
- (a completar con la salida real de pytest.)
