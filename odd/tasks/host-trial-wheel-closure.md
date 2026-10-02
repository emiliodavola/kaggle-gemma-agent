# Feature: host-trial-wheel-closure

Closes #39.

## Goal

El run `runs/20261002T204541Z` puntuo 0/5 porque el set oficial de
`wheels/` de la competencia es **incompleto por dependencias**: trae
`pydantic-2.13.4` (que declara `Requires-Dist: typing-inspection>=0.4.2`) pero
no el wheel `typing-inspection`. Confirmado contra Kaggle: 124 wheels, sin
`typing-inspection` ni `inline-snapshot`. El harness instala con
`pip install --no-index --find-links=/wheels --no-deps -e /workspace` y streamea
site-packages pre-horneados desde el set, asi que `import fastapi` explota en
collection y **ninguna task puede pasar**, sin importar el parche.

`ensure_trial_wheels` hoy valida solo **nombres de archivo** contra el listado
remoto (124/124 -> `skip (complete)`), no el cierre de dependencias.

Un cierre naive sobre todo el wheelhouse es inviable: es una union de wheels de
varios repos y da 9 falsos positivos (`blinker`, `h11`, `attrs`, `py`, `toml`,
`pathspec`, `trove-classifiers`, `shellingham`, `annotated-doc`). La raiz
correcta es el repo de la task, replicando el descubrimiento de
`data/raw/sandbox/setup.py` (`collect_from_pyproject` +
`collect_from_requirements_files`).

Decisiones tomadas con el usuario:

1. Cierre anclado al snapshot de la task (`pyproject.toml` + `requirements*.txt`)
   resuelto contra el METADATA de los wheels stageados; fail-fast antes del eval.
2. Wheels suplementarios en `data/raw/wheels-extra/` (override
   `HARNESS_TRIAL_WHEELS_EXTRA`) mergeados a `data/raw/wheels/`.
3. `--allow-incomplete-wheels` para el caso offline/known-gap.
4. `run_report`/`STATUS` marcan un fallo de entorno uniforme (mismo modulo
   faltante en >= 2 tasks) para no confundirlo con performance del agente.

## Non-goals

- Auto-download desde PyPI (solo dir suplementario + docs).
- Parchear `swegemma` (harness externo).
- El bug de paths `read_file`/`edit_file`/`write_file` en Windows (tool layer
  externa `adk-eval-core`; no afecta el scoring de Kaggle, que corre en Linux).

## Tasks

- [x] T1 — Runner: `canonicalize_distribution_name`, `read_wheel_metadata`,
      `_wheel_filename_info`, `_version_sort_key`, `select_wheels` (espeja
      `deduplicate_wheels` de `sandbox/setup.py`).
- [x] T2 — Runner: `read_repo_requirements(snapshot)` -> `RepoRequirements(core,
      optional)` (tar + `tomllib` + requirements, espeja el discovery del harness).
- [x] T3 — Runner: `wheel_dependency_closure(wheels_dir, roots)` -> provistos /
      faltantes (incluye roots ausentes; nombre faltante -> quien lo requiere).
- [x] T4 — Runner: `merge_supplemental_wheels` + `TrialPaths.wheels_extra_dir` +
      env `HARNESS_TRIAL_WHEELS_EXTRA` + flag `--allow-incomplete-wheels`.
- [x] T5 — Runner: cablear el cierre en `ensure_trial_wheels` (gate duro en
      `core`, aviso en `optional`) y pasar los snapshots desde `run()`.
- [x] T6 — `run_report`: `missing_modules` por task + `environment_blocked` +
      razon y linea de `STATUS`.
- [x] T7 — Docs: `docs/host-trial-runbook.md` §6.2, `docs/run-reports.md`,
      `.env.example`.
- [x] T8 — Tests: cierre (wheels fixture + snapshot fixture), root ausente,
      core-vs-optional, merge, override, deteccion de entorno.
- [x] T9 — Evidencia real: cierre contra `data/raw/snapshots/fastapi_14962.tgz` +
      `data/raw/wheels`; stageo de los wheels core faltantes y re-verificacion.
- [x] T10 — `ruff check` + `pytest -q` + gate de compliance en verde.

## Evidence

- Issue: #39.
- PR: #40.
- Rama: `fix/host-trial-wheel-closure`.
- Cierre core real (snapshot `fastapi_14962.tgz` + `data/raw/wheels`, 124 wheels):
  `core MISSING: {'annotated-doc': ('the task repo',), 'typing-inspection':
  ('pydantic', 'the task repo')}`; `h11` solo en optional (aviso).
- Tras stagear `typing-inspection-0.4.4` + `annotated_doc-0.0.5` en
  `data/raw/wheels-extra/`: `core MISSING (with extras): {}`.
- `run_report` sobre `runs/20261002T204541Z` (rebuild):
  `environment_blocked=True`, `missing_modules=['typing_inspection']`,
  `STATUS: failures 5 | kinds collection_error=5 | env missing: typing_inspection`.
- `uv run pytest tests/ -q` -> `147 passed`; `ruff check src/ tests/ scripts/` ->
  `All checks passed!`; `pack submission --check` -> `6/6 points`.
- Comandos y salidas completas en el body del PR.
