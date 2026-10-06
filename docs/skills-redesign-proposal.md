# Propuesta: skills del submission hipercompactas

Documento de decisión. No implementado. Escrito para revisar y después decidir.

## 1. Objetivo

Rediseñar las **12 skills del submission** (`submission/skills/<name>/SKILL.md`)
para que sean **hipercompactas y a la vez super descriptivas**, sin romper la
regla b (exactamente 12) ni la regla e (tokens prohibidos).

## 2. Qué son las skills acá (y cuáles NO tocamos)

Hay tres clases de "skill" en el repo. Esta propuesta es solo sobre la primera:

1. **Skills del submission** (`submission/skills/`, 12) → las carga el agente en
   la evaluación, **cada turno**, como contexto read-only. **Es la que
   rediseñamos.**
2. Skills de desarrollo (`.agents/skills/`, 28 probabl) → tooling ML, no se
   envían. Fuera de alcance.
3. Skills de OpenCode (`~/.config/opencode/skills/`) → workflow del agente de
   desarrollo. Fuera de alcance.

## 3. Estado actual (medido)

| | Valor |
|---|---|
| Skills | 12, cada una con **un solo** `SKILL.md` (sin scripts, sin references) |
| Total | **469 líneas / ~19.5 KB ≈ 5.6k tokens** |
| Ventana efectiva | ~14.3k tokens (playbook §10.1) → las skills son **~40% del contexto de trabajo** |
| Caps del `skill-stack-evaluation.md` | ≤60 por skill (techo 80), total ≤650 |
| Realidad | todas ≤54 líneas; el total es 72% del cap → **el problema no es el largo, es el solapamiento** |

### Solapamientos concretos (reglas repetidas en 2+ skills)

| Regla duplicada | Skills |
|---|---|
| "no tocar tests/`conftest.py`/`pytest.ini`" | systematic-debugging, python-testing-patterns, patch-hygiene, verification-before-submit |
| "scratch en `/tmp`, nunca en el repo" | TDD, python-testing-patterns, patch-hygiene, verification-before-submit |
| "`submit_patch`/`get_status` son gratis" | budget-aware-tool-use, issue-localization |
| "correr `run_command` y verificar" | TDD, python-testing-patterns, systematic-debugging, implementation-planning, differential-diagnosis |
| "revisar el diff / scope" | patch-hygiene, verification-before-submit |
| "reproducir una vez" | systematic-debugging, differential-diagnosis |
| búsqueda por símbolo | code-search, code-graph-navigation, repo-mapping, issue-localization |

### Otros hallazgos

- **`skill-stack/` es un espejo stale.** `pack.py` solo empaqueta
  `submission/skills/`. `verification-before-submit` ya divergió (v1.0 en
  `skill-stack/` vs v1.1 en `submission/`). El README (`:67`) afirma que se
  copian, y no es así.
- **Regla e limpia** en las 12 (cero tokens prohibidos).
- **Sin scripts** en ninguna: compactar es puro texto (y evita el bug de
  `run_skill_script`, playbook §10.2).

## 4. Principios de diseño (hypercompacta + descriptiva)

1. **Un dueño por regla.** Cada regla vive en **una** skill; las demás la
   referencian por nombre, no la repiten.
2. **Trigger único y accionable** en la línea `description:` (formato
   `Trigger: <cuándo>`), ≤20 palabras.
3. **≤40 líneas objetivo** por skill (techo 60). Total objetivo **≤350 líneas**
   (hoy 469) → ahorro ~1.4k tokens/turno.
4. **Tool-mapped**: cada paso nombra solo las 9 herramientas; sin MCP, sin red,
   sin procesos.
5. **Una tabla diferenciadora como máximo**, solo si no está en otra skill
   (scoring de DD, decision table de graph, patrones de pytest).
6. **Sin scripts** y sin archivos extra: solo `SKILL.md`.
7. **Descriptiva = pasos ejecutables**, no prosa. Frases cortas, imperativas.

## 5. Propuesta: las 12 skills (mismo nombre, alcance afinado)

| # | Skill | Trigger (una línea) | Dueña de | Tools | Líneas hoy → obj |
|---|---|---|---|---|---|
| 1 | `repo-mapping` | repo desconocido o el fix cruza módulos | orientación inicial | run_command, read_file, get_code_subgraph | 33 → 28 |
| 2 | `code-search` | buscar definiciones, call sites o config keys | búsqueda textual exacta | run_command, read_file | 31 → 24 |
| 3 | `code-graph-navigation` | callers, definiciones, símbolos similares | búsqueda por grafo | get_code_neighbors, search_similar_code, get_code_subgraph, read_file | 40 → 32 |
| 4 | `issue-localization` | issue/traceback → sospechosos | qué y dónde | run_command, search_similar_code, read_file, get_code_neighbors | 42 → 32 |
| 5 | `systematic-debugging` | test o excepción que falla | el loop de debug | run_command, read_file, get_code_neighbors, edit_file | 37 → 30 |
| 6 | `differential-diagnosis` | >1 causa posible y presupuesto corto | scoring de candidatos | run_command | 37 → 26 |
| 7 | `test-driven-development` | agregar/arreglar comportamiento con test | ciclo RED-GREEN-REFACTOR | edit_file, run_command | 34 → 26 |
| 8 | `python-testing-patterns` | escribir/leer pytest, mockear | tabla de patrones | read_file, run_command | 42 → 30 |
| 9 | `implementation-planning` | el cambio supera un edit chico | plan inline ≤7 pasos | run_command, read_file | 32 → 24 |
| 10 | `budget-aware-tool-use` | inicio de tarea o loop improductivo | presupuesto **+ reglas de loop** | submit_patch, get_status | 42 → 34 |
| 11 | `patch-hygiene` | antes del primer edit o scratch | paths + scratch | edit_file, write_file, run_command | 45 → 30 |
| 12 | `verification-before-submit` | antes de `submit_patch` | gate de submit | run_command, submit_patch, get_status | 54 → 34 |
| | **Total** | | | | **469 → 350** |

## 6. Mapa de propiedad (quién conserva qué)

- **`patch-hygiene`** es la dueña única de: lista de archivos prohibidos
  (`tests/`, `conftest.py`, `pytest.ini`), scratch en `/tmp`, `git add -N`,
  `git status`/`diff --stat`. Las demás **la referencian**.
- **`verification-before-submit`** es la dueña del **gate**: correr el test
  target, `py_compile` de los `.py` cambiados, rechazar junk, y recién
  `submit_patch`. No repite la lista de prohibidos (la referencia).
- **`budget-aware-tool-use`** es la dueña de: reservar ≥15 llamadas, batch de
  lecturas, parar tras 2 intentos fallidos, always-submit, y **las reglas de
  loop** (nuevas, ver §7).
- **`systematic-debugging`** dueña del loop reproduce→isolate→root-cause→fix;
  **`differential-diagnosis`** conserva solo el scoring
  likelihood×severity/cost y "cuándo hay >1 causa".
- **`test-driven-development`** dueña del ciclo; **`python-testing-patterns`**
  conserva solo la tabla de patrones offline.
- **`code-search` / `code-graph-navigation` / `repo-mapping`**: texto vs grafo
  vs orientación, con un único fallback declarado (graph vacío → code-search).

## 7. Contenido nuevo (lo que aprendimos)

Se agrega, **dentro de `budget-aware-tool-use`** (su trigger ya dice "loop
improductivo"), basado en `odd/tasks/host-trial-trace-metrics.md` y el hilo
#745774:

- **Read loop**: si dos comandos de solo-lectura seguidos no aportan info nueva,
  dejá de buscar; editá o submité.
- **Edit loop**: un edit por hipótesis; si el repro no cambia, revertí y
  re-diagnosticá; nunca apiles edits.

No se crean skills nuevas: el presupuesto de 12 es fijo y estas reglas encajan
en la dueña natural.

## 8. Cómo medir la mejora

1. **Costo**: líneas y bytes totales antes/después (`trace_metrics` no; un
   conteo directo). Objetivo: ≤350 líneas.
2. **Solapamiento**: contar reglas duplicadas antes/después (objetivo: 0).
3. **Trigger**: cada skill tiene `Trigger:` accionable y distinto.
4. **Cumplimiento**: `pack --check` 6/6 y cero tokens prohibidos.
5. (Opcional, sin A/B) correr `trace_metrics.py` sobre un run con el set nuevo y
   comparar formas de loop contra el baseline.

## 9. Riesgos y no-goals

- **Regla b**: deben quedar exactamente 12 directorios. No se crean ni eliminan.
- **Regla e**: todo texto nuevo debe evitar `http(s)://|socket|urllib|requests.|
  pip install|uv add|mcp|subprocess|curl|wget`.
- **`skill-stack/`**: decidir si se re-sincroniza o se elimina (hoy es un espejo
  stale que engaña). Recomendación: **eliminarlo** y dejar `submission/skills/`
  como única fuente, actualizando el README.
- **`run_skill_script`**: no agregar scripts (bug conocido).
- **No-goals**: no cambiar el prompt (v3 ya está), no tocar el harness, no
  agregar skills nuevas, no medir A/B.

## 10. Plan de implementación (si se aprueba)

- **Fase 1 (dedupe)**: quitar las reglas duplicadas y agregar referencias
  cruzadas. Sin cambiar el sentido. → PR con tests de conteo/regla-e.
- **Fase 2 (afinar triggers)**: reescribir cada `description:` a
  `Trigger: <cuándo>` ≤20 palabras.
- **Fase 3 (reglas de loop)** en `budget-aware-tool-use`.
- **Fase 4 (limpieza)**: eliminar `skill-stack/` o re-sincronizar + README.
- Cada fase: `pack --check` 6/6, conteo de líneas, y evidencia real en el PR.

## 11. Decisión pendiente

- ¿Vamos con el rediseño completo (fases 1–4) o solo dedupe + triggers (1–2)?
- ¿`skill-stack/` se elimina o se re-sincroniza?
- ¿Este doc queda en `docs/` (versionado) o se descarta tras decidir?
