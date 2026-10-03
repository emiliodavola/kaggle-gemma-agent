# Feature: host-trial-backend-selector

Closes #43.

## Goal

El `.env` reusa los nombres de las claves activas (`OPENAI_BASE_URL`,
`HARNESS_MODEL`) en los presets de backend, asi que colisionan: debajo del cap de
20 lineas se ignoran en silencio, y sin el cap un preset pisaria a la clave
activa. En un run real el operador queria LM Studio y el runner uso el cloud de
opencode.ai.

Decisiones tomadas con el usuario:

1. Un selector `HARNESS_TRIAL_BACKEND` (`opencode` default, `dmr`, `lmstudio`,
   `llamacpp`) resuelve la base URL desde una tabla de presets en codigo; asi
   ninguna clave se repite.
2. `OPENAI_BASE_URL` queda como override explicito opcional (gana si esta seteado).
3. `HARNESS_MODEL` sigue explicito (cada server expone su propio id).
4. `parse_env_file` lee el `.env` **completo** (sin cap de 20) y falla con
   `TrialError` nombrando clave + numeros de linea si hay una clave activa duplicada.
5. Backend desconocido -> fail-fast listando los valores validos.

## Non-goals

- Cambiar el submission o el sandbox.
- El flag `--repair-sandbox-deps` (issue #41, ya mergeado).
- El bug de paths `read_file`/`edit_file` en Windows (tool layer externa).

## Tasks

- [ ] T1 — Runner: `BACKEND_PRESETS` + `DEFAULT_BACKEND`; `resolve_trial_env`
      resuelve base URL por selector (override explicito gana) y valida el backend.
- [ ] T2 — Runner: `parse_env_file` sin cap; error claro en clave activa duplicada.
- [ ] T3 — `.env.example`: selector + presets comentados; sin claves activas duplicadas.
- [ ] T4 — Docs: runbook §6/§6.1 (selector, presets, precedencia, modelo explicito).
- [ ] T5 — Tests: selector, precedencia override, backend desconocido, duplicados,
      parseo completo.
- [ ] T6 — `ruff` + `pytest` + `mypy` + `pyright` + coverage + gate en verde.

## Evidence

- Issue: #43. PR: (pendiente).
- (pendiente) comandos y salidas reales se pegan en el body del PR.
