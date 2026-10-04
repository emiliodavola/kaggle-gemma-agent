# Feature: pre-submit-guard-skill

Closes #48.

## Goal

El skill `verification-before-submit` pedia re-correr el test target, pero un
`SyntaxError` en un archivo que el test no importa se escapaba, y nada rechazaba
archivos scratch en el diff. En `runs/20261003T051525Z`, `fastapi_15588`
submitio un patch que ni parsea (`SyntaxError: unterminated string literal` en
`fastapi/sse.py:37`) y arrastro `fix_sse.py`, `fix_sse_v2.py`,
`reproduce_sse_issue.py`, `test_sse_val.py` (mas variantes con path Windows).

Decisiones tomadas con el usuario:

1. Agregar chequeos deterministas al skill existente (no crear uno nuevo: rule b
   exige exactamente 12 skills).
2. Antes de `submit_patch`: byte-compilar cada `.py` cambiado
   (`python -m py_compile`) y rechazar paths scratch/junk en el diff.
3. Mantener el skill libre de tokens prohibidos por rule e (`subprocess`,
   `socket`, `mcp`, URLs, `pip install`, ...) y sin tocar tests/config.

## Non-goals

- Cambiar el manifest, la lista de tools, o agregar un skill 13.
- Mecanismos con red, instalacion o algo fuera de `run_command`.

## Tasks

- [x] T1 — Skill: Hard Rules + gate de syntax y diff hygiene.
- [x] T2 — Skill: pasos de ejecucion con `git diff --name-only` y
      `python -m py_compile`; bump de version a 1.1.
- [ ] T3 — Gate `pack submission --check` 6/6 + `pytest` + scan de tokens.

## Evidence

- Issue: #48. Rama: `feat/pre-submit-guard-skill` (desde `main`).
- `pack submission --check` -> `submission contract OK (6/6 points)`.
- 12 skills; sin tokens prohibidos en `submission/`.
- (a completar con la salida real de pytest.)
