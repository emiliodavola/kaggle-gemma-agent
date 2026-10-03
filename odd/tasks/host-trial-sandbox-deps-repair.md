# Feature: host-trial-sandbox-deps-repair

Closes #41.

## Goal

El backend **Docker** del trial local inyecta todos los wheels base (<20 MB) en
site-packages **sin resolver dependencias** (`swegemma/harness/container_setup.py`,
`_ensure_container_site_packages`), y `_deduplicate_wheels` elige la version mas
alta compatible con py3.13. El set oficial trae `pydantic 2.13.4` sin
`typing-inspection`, asi que `import fastapi` falla y pytest muere en collection
en todas las tasks de fastapi (run `runs/20261002T204541Z`: 4/5, `collection_error`).

La imagen **notebook/subprocess** de Kaggle no tiene el problema (trae pydantic
2.12.3 + typing-inspection); ver discusion #744370.

Falta un interruptor para aplicar la reparacion local a demanda, separando un
run **fiel** (set de la competencia tal cual) de uno **reparado** (wheels
suplementarios para que el Docker local se parezca al notebook).

Decisiones tomadas con el usuario:

1. Flag `--repair-sandbox-deps` en `run_host_trial.py`, **default off**.
2. On: mergea `data/raw/wheels-extra/` (override `HARNESS_TRIAL_WHEELS_EXTRA`) y
   descarga de PyPI las deps **core** aun faltantes para el target del container
   (cp313 / manylinux x86_64, `--only-binary=:all: --no-deps`), via
   `uv run --with pip python -m pip download`.
3. Off: no mergea nada; corre el set de la competencia tal cual (fiel).
4. La reparacion toca solo **core**; las deps test/optional (inline_snapshot,
   dirty_equals, ...) quedan como aviso porque el notebook tampoco las trae.
5. Rama y PR aparte del #40 (que ya fue mergeado); PR contra `main`.

## Non-goals

- Cambiar el submission o el sandbox oficial (imposible: offline, `/wheels` read-only).
- Parchear `swegemma`.
- Vendorizar paquetes dentro del patch del agente (pregunta de reglas abierta al host).

## Tasks

- [x] T1 — Runner: `download_missing_wheels(names, dest_dir)` + constantes
      `PIP_DOWNLOAD_CMD` / `PIP_CONTAINER_TARGET`.
- [x] T2 — Runner: `ensure_trial_wheels(..., repair=False)`; gatea el merge de
      suplementarios y, con `repair`, descarga + re-mergea + re-chequea el core.
- [x] T3 — Runner: flag `--repair-sandbox-deps` en `main` y `run`.
- [x] T4 — Tests: off no mergea; on mergea; on descarga y cierra el gap (mock);
      off falla rapido.
- [x] T5 — Docs: runbook §6.2 (fiel vs reparado, flag, link a la discusion).
- [x] T6 — `ruff` + `pytest` + `mypy` + `pyright` + coverage + gate en verde.

## Evidence

- Issue: #41. PR: #42.
- Rama: `feat/host-trial-sandbox-deps-repair` (desde `main`, con #40 ya mergeado).
- `--repair-sandbox-deps` default off; on mergea extras + descarga core faltante.
- Cierre core real (snapshot `fastapi_14962.tgz`): sin extras
  `{annotated-doc, typing-inspection}`; con extras `{}`.
- `uv run pytest tests/ -q` -> `153 passed`; `ruff`/`format`/`mypy`/`pyright`
  limpios; coverage 98%; `pack submission --check` -> 6/6.
- Comandos y salidas completas en el body del PR #42.
