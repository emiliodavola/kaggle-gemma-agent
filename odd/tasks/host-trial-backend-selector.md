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

- [x] T1 — Runner: `BACKEND_PRESETS` + `DEFAULT_BACKEND`; `resolve_trial_env`
      resuelve base URL por selector (override explicito gana) y valida el backend.
- [x] T2 — Runner: `parse_env_file` sin cap; error claro en clave activa duplicada.
- [x] T3 — `.env.example`: selector + presets comentados; sin claves activas duplicadas.
- [x] T4 — Docs: runbook §6/§6.1 (selector, presets, precedencia, modelo explicito).
- [x] T5 — Tests: selector, precedencia override, backend desconocido, duplicados,
      parseo completo.
- [x] T6 — `ruff` + `pytest` + `mypy` + `pyright` + coverage + gate en verde.

## Evidence

- Issue: #43. PR: #44.
- Rama: `feat/host-trial-backend-selector` (desde `main`).
- (pendiente) comandos y salidas reales se pegan en el body del PR.
- `parse_env_file` sobre el `.env` real del operador (preset LM Studio
  descomentado debajo del cap viejo) -> `TrialError: duplicate key
  'OPENAI_BASE_URL' in .env (lines 11 and 43)`. `.env.example` -> 3 claves
  activas (`HARNESS_MODEL`, `HARNESS_TRIAL_BACKEND`, `OPENAI_API_KEY`).
- `uv run pytest tests/ -q` -> `161 passed`; ruff/format/mypy/pyright limpios;
  coverage 98%; `pack submission --check` -> 6/6.
- Comandos y salidas completas en el body del PR #44.