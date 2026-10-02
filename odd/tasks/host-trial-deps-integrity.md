# Feature: host-trial-deps-integrity

Closes #37.

## Goal

El run `runs/20261001T034308Z` puntuo 0/2 porque los containers (A y B) no
tenian `starlette`/`pydantic` en site-packages, aunque `data/raw/wheels/` (124
wheels) si los contiene. `swegemma` inyecta las deps desde un tar cacheado
(`<temp>/swegemma_sp_cache_v8/sp_base.tar`) **keyed por nombre**, sin hash del
wheel set: un tar construido en un staging parcial (429) envenena todos los runs
posteriores. El handoff (`report.json` + `STATUS`) ademas reporta `DONE` /
`error: null`, asi que la causa (collection error) queda enterrada en
`failure_tail`.

Decisiones tomadas con el usuario:

1. Invalidar el cache de site-packages de swegemma antes de cada eval, para que
   el tar se reconstruya desde el wheel set actual.
2. Si el listing remoto de wheels no esta disponible y hay un set local, **no**
   continuar en silencio: fallar con mensaje accionable. Override explicito
   `--allow-partial-wheels` para el caso offline deliberado.
3. Clasificar la causa de fallo en `run_report` (`collection_error` /
   `test_failure` / `timeout` / `unknown`) y exponerla por tarea y en `STATUS`.
4. Documentar el backend OpenAI-compatible local (llama.cpp / LM Studio) en el
   runbook: el proxy ya soporta cualquier upstream http(s).

## Non-goals

- Parchear `swegemma` (harness externo): el fix durable ahi es keyear el cache
  por hash de contenido.
- El bug de paths `read_file`/`edit_file`/`write_file` en Windows (`C:\workspace\`),
  que vive en la tool layer externa (`adk-eval-core`).
- Re-correr trials o cambiar el modelo por defecto.
- Auto-merge ni push a `main`.

## Tasks

- [x] T1 — Runner: `clear_swegemma_site_packages_cache()` + invocacion antes del
      eval con log de lo removido.
- [x] T2 — Runner: `ensure_trial_wheels` falla rapido si el listing cae y el set
      local no esta verificado; `--allow-partial-wheels` como override.
- [x] T3 — `run_report`: `failure_kind` por tarea + kind en la linea
      `failures` de `STATUS`.
- [x] T4 — Docs: `docs/run-reports.md` (campo + STATUS) y
      `docs/host-trial-runbook.md` (cache, flag, backend local).
- [x] T5 — Tests: cache clear, fail-fast/override, clasificacion y STATUS.
- [x] T6 — `ruff check` + `pytest` + gate de compliance en verde.
- [x] T7 — Preflight de backend (`smoke_test_backend`, tool-aware) en phase 7 con
      `--skip-backend-smoke`; habilita LM Studio / llama.cpp local y falla rapido.

## Evidence

- Branch: `fix/host-trial-deps-integrity` (commits `b3ed390`, `0ff6ce1`).
- `uv run pytest -q` -> `133 passed`.
- `uv run ruff check src/ tests/ scripts/` -> clean.
- `uv run python -m kaggle_gemma_agent.pack submission --check` -> `6/6 points`.
- `run_report.build_report(runs/20261001T034308Z)` -> ambos tasks
  `failure_kind=collection_error`; `STATUS`:
  `failures 2 | kinds collection_error=2 | top: fastapi_15588, fastapi_15661`.
- Comandos y resultados se pegan en el body del PR.

