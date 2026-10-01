# Feature: trial-collect-and-open-items

## Goal

Tracker de hallazgos del analisis del run_03 (20260930T170701Z,
deepseek-v4.1-flash, 0/2) y de deuda detectada al costado. Nada de esto cambia
el submission; es contexto para decidir proximos pasos.

## Findings (verificados, no opiniones)

- F1 — `fastapi_15588`: el fallo de scoring fue `ModuleNotFoundError:
  starlette` por falta de `data/raw/wheels/` en el trial, NO por el patch
  (toca `fastapi/sse.py`, igual que el gold). Resuelto por
  `host-trial-wheels-staging`.
- F2 — `fastapi_15661`: task inasible sin ver el test. El test escondido
  (307 lineas, 100% nuevo) exige 7 nombres/firmas exactos
  (`RELEASE_NOTES_HEADER`, `BumpType`, `app`, ...) que no aparecen en
  enunciado, hints, git del snapshot ni scripts existentes. El agente
  adivino el archivo correcto (`scripts/prepare_release.py`) con API
  distinta. Ningun agente lo gana sin el test.
- F3 — El agente-proxy (deepseek) usa `run_command` para todo (89 y 70
  llamadas) e ignora `read_file`/`edit_file` + turismo exploratorio
  (`git fsck`, `/root`, `pip download`). Matiz: no es el modelo scored;
  no sobre-optimizar contra el.
- F4 — Papers arXiv revisados (SWE-agent ACI 2405.15793, Meta-Skills
  2609.38143, meta-reasoning 2609.38147, SWE-Gym, SWE-rebench). Propuestas
  concretas aparcadas en `/opt/data/cache/scratch/harness-tool-notes.md`
  (fuera del repo): sacar "una accion por turno", colapsar verificacion a
  2 llamadas, caps de mapping, guardarrailes anti-reintento, recorte
  12→7 skills, `code_analyzer` condicional.

## Open debt

- [ ] D1 — Hook `pre-commit` commiteado con `INSTALL_PYTHON` hardcodeado a
      un venv viejo (`.../kaggle-gemma-4-developer-agent-competition/.venv`).
      Workaround actual: anteponer `.venv/bin` al `PATH`. (Issue sugerido.)
- [ ] D2 — Probar el patch del 15588 contra el test escondido con deps
      reales (PyPI esta en la allowlist del proxy).
- [ ] D3 — Filtrar los 129 tasks por ganabilidad antes de medir resolution
      rate en serio.
