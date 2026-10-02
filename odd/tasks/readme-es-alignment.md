# Feature: readme-es-alignment

## Goal

`README_ES.md` no existia, y `README.md` estaba desactualizado: el arbol
mostraba `src/` como placeholder cuando ya tiene el packer, los harness runs y
los run reports, y no mencionaba `scripts/`, `tests/`, `.github/`, `odd/` ni
`skill-stack/`. Actualizar `README.md` a la realidad y crear `README_ES.md`
completamente alineado (mismas secciones y contenido).

Decisiones tomadas con el usuario:

1. `README.md` es la fuente de verdad y `README_ES.md` su espejo fiel.
2. Se corrige primero `README.md` (estaba factualmente viejo) y luego se traduce.
3. Espanol neutro/profesional en el README en espanol (sin voseo ni regionalismos).

## Non-goals

- Reescribir `AGENTS.md` (ya cubre las reglas de operacion).
- Documentar cada doc de `docs/` en detalle; el README es un sketch publico.

## Tasks

- [x] T1 — Revisar `README.md` contra el repo real (tracked vs local, `src/`,
      `scripts/`, `tests/`, `.github/`, `odd/`, `skill-stack/`, `submission/`).
- [x] T2 — Corregir `README.md`: quickstart con `pre-commit install`, layout
      real, "What's implemented", compliance gate y CI.
- [x] T3 — Crear `README_ES.md` espejo, espanol neutro.
- [x] T4 — Verificar que cada ruta referenciada exista.

## Evidence

- Branch: `docs/readme-es-alignment`.
- `uv run pytest tests/ -q`, `ruff check` y `pack --check` en el PR body.
- Rutas referenciadas verificadas contra `git ls-files`.
