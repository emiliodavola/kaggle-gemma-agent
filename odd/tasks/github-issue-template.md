# Feature: github-issue-template

## Goal

El repo no tenia issue template, y los issues #25-#28 (creados a partir del
review de `043f921`) salieron con descripciones pobres. Agregar un template de
issue "super informativo" y reescribir esos cuatro issues con el mismo formato.

Decisiones tomadas con el usuario:

1. Un template GitHub Issue Form (`.yml`) que sirva para bug, regression,
   enhancement, chore y docs via un dropdown `Kind`.
2. Los issues existentes se editan (no se cierran/reabren) con el formato del
   template: kind, area, summary, problema, esperado, repro/evidencia,
   acceptance criteria, scope, constraints, referencias y checklist.
3. Sin `config.yml` por ahora: un solo template, pedido explicito del usuario.

## Non-goals

- Configurar multiples templates o assignees por defecto.
- Tocar codigo del runner (ya resuelto en PR #29 / #30).

## Tasks

- [x] T1 — `.github/ISSUE_TEMPLATE/task.yml` con Issue Form completo.
- [x] T2 — Validar el YAML y la forma del schema.
- [x] T3 — Reescribir #25, #26, #27, #28 con el formato del template.
- [x] T4 — `odd/tasks/github-issue-template.md` (este archivo).
- [x] T5 — Commit en rama `chore/github-issue-template` + PR asignado.

## Evidence

- Branch: `chore/github-issue-template` (PR asignado a emiliodavola).
- Issues reescritos: #25, #26, #27, #28.
- Validacion YAML y suite en el PR body.
