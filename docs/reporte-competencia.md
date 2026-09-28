# Gemma 4 Developer Agent — Reporte de investigación

Competencia: `gemma-4-developer-agent` (Google, sponsor Google LLC).
Estado de cuenta: reglas aceptadas, `userHasEntered=True`.

## 1. ¿Qué hay que construir?

Post-entrenar / configurar **Gemma 4** como **agente autónomo de software engineering**: navega repos Python reales, diagnostica bugs/feature requests y genera patches que pasan tests. La tesis del sponsor: los agentes top dependen de modelos comerciales con internet; acá hay que lograr un agente capaz **offline, sobre un único modelo local** (`gemma-4-31b-it-qat-w4a16-ct`).

Hay dos competencias hermanas:
- **Esta** (`gemma-4-developer-agent`): predicción/agente, USD 65.000.
- **Paper track** (`gemma-4-developer-agent-paper`): documentar el enfoque (tuning/RL, code-graphs, benchmarks, graph reasoning), USD 35.000, deadline 12-nov-2026. Opcional pero suma y da visibilidad (workshop estilo NeurIPS de Google).

## 2. Formato de submission

Un zip (`submission.zip`) con config **declarativa YAML** en raíz — nada de `agent.py`:

```
submission.zip
├── agent.yaml                  # REQUERIDO (o agent.yml / root_agent.yaml/.yml, uno solo)
├── eval_config.yaml            # opcional: presupuestos por tarea
├── configs/sampling.yaml       # opcional, vía !include
├── prompts/*.md                # system.md, analyzer.md, vía !include
├── sub_agents/*.yaml           # sub-agentes o AgentTools
├── adapters/<nombre>/          # LoRAs PEFT: adapter_config.json + adapter_model.safetensors
└── skills/<skill>/SKILL.md     # skills ADK con frontmatter name:
```

Reglas duras:
- Solo YAML declarativo (`compile_submission`, sin `importlib`, sin imports dinámicos).
- Sin `..`, sin symlinks fuera del root, sin pickle (`.bin/.pt/.pth` rechazados; solo `.safetensors`).
- Tamaño total descomprimido **< 3 GiB** incluyendo adapters.
- Límites de envío: **1 submission por día**, hasta **2 finalistas** para juzgar. Hoy: 0 envíos usados, queda 1 hoy.

## 3. Métrica y evaluación

- Estilo **SWE-bench**: por cada issue se aplica tu patch al repo en `base_commit`, se aplica el `test_patch` oficial y se corre `pytest` hermético.
- Tarea resuelta ⇔ `exit_code == 0` **y** JUnit XML válido con `passed > 0`, `failures == 0`, `errors == 0`, todos los tests requeridos (FAIL_TO_PASS + PASS_TO_PASS) en passed sin skips.
- Score global = **Resolution Rate** = resueltas / totales, en [0.0, 1.0].
- Ciclo en dos fases aisladas: **Container A** (tu agente trabaja en `/workspace`, snapshot sin historia futura, offline) → extracción del patch (`git add -N . && git diff`) → **Container B** (verificación limpia: resetea tests/configs tocados por tu patch, aplica `test_patch`, corre pytest).
- Límite de agente: **12 horas** para todas las tareas (incluye setup, excluye validación). `eval_config.yaml` permite topes por tarea.
- ¡Ojo!: si tu agente modifica tests o configs (`conftest.py`, `pytest.ini`, `pyproject.toml`, etc.), el harness los **revierte** antes de verificar. Hay que arreglar el código de la librería, no los tests.
- ¡Ojo 2!: scripts scratch dentro de `/workspace` (ej. `repro.py`) **entran en el diff**. Usar `/tmp` o borrarlos antes de `submit_patch()`.

## 4. Harness, modelo y presupuesto

- Hardware de scoring: **4× NVIDIA L4 (96 GB VRAM)**. vLLM con `tensor_parallel_size=4`, `gpu_memory_utilization=0.80`, `max_model_len=32768`, `enable_lora=True`, `max_loras=8`, `max_lora_rank=128`.
- **Un solo modelo base por submission, obligatorio**: `gemma-4-31b-it-qat-w4a16-ct` (variante QAT INT4, ~16–18 GB). Todos los agentes/subagentes deben declararlo.
- LoRAs: un agente puede usar distinto adapter (`adapter: main_lora`), hasta 8 simultáneos, rank ≤ 128. Presupuesto: rank 16 ≈ 110–220 MB (entran ~8), rank 32 ≈ 220–450 MB (6–8), rank 64 ≈ 450–900 MB (3–6), rank 128 ≈ 0.9–1.8 GB (1–3).
- Contexto: **32.768 tokens** techo (prompt + thinking + salida). Defaults: `max_output_tokens` 16.384, `thinking_budget` 4.096. Para vLLM conviene `include_thoughts: true + thinking_budget` en vez de `thinking_level`.
- Presupuestos por defecto (Stage 1 `inference.py`): 60 min por sesión (el setup del container **no** descuenta), 100 tool calls, 500 turnos, comando individual 300 s, salida truncada a 5.000 chars, `read_file` a 150 líneas / 10.000 chars.
- 9 herramientas: `run_command`, `submit_patch` (gratis, cierra la sesión al terminar el turno), `get_status` (gratis), `read_file`, `edit_file` (motor resiliente 3 niveles: exacto/flexible/regex), `write_file`, `get_code_neighbors`, `search_similar_code` (ojo: sin servidor de embeddings vivo — pasar **símbolos**, no lenguaje natural), `get_code_subgraph`.
- Anti-truncado: si el pensamiento + tool call supera `max_output_tokens`, el tag `<|tool_call|>` se corta y el harness manda nudges (máx 3). Edits chicos e incrementales, `thinking_budget` ~4096.

## 5. Datos disponibles

Entrenamiento público (en scoring se reemplaza por test set oculto con mismo pipeline):
- **129 tareas** en `tasks.jsonl`: repos `fastapi/fastapi`, `Textualize/rich`, `psf/requests`, `encode/httpx`. Campos: `instance_id`, `repo`, `base_commit`, `problem_statement`, `hints_text`, `patch` (referencia, solo train), `test_patch` (solo train), `created_at`.
- `snapshots/`: 129 `.tgz` del repo en `base_commit`, sin historia futura.
- `graphs/`: 256 JSON (129 por tarea + hardlinks por commit) — AST/grafos de llamadas NetworkX para `get_code_neighbors`/`get_code_subgraph`.
- `embeddings/`: 256 `.npz` (vectores 256-d por símbolo) para `search_similar_code`.
- `wheels/`: 124 wheels offline (fastapi, starlette, pydantic, requests, rich, httpx, pytest...) montadas en `/wheels` — el sandbox es **air-gapped** (`network_mode=none`), 4 GiB RAM, 2 vCPUs.
- `docker/`: `Dockerfile.sandbox` (base python:3.13-slim + git + pytest) y `Dockerfile.public` (+ cache de wheels públicas). Shims `imp.py`/`telnetlib.py` para compatibilidad.
- `HARNESS_README.md` (49 KB, 671 líneas): referencia técnica completa del stack `swegemma` + `adk-submission` + `adk-eval-core`.

## 6. Timeline (todo 11:59 PM UTC)

- 23-sep-2026: inicio.
- 12-nov-2026: deadline paper track (opcional).
- 25-nov-2026: **entry deadline** (aceptar reglas) y **team merger deadline**.
- 2-dic-2026: **final submission deadline**.

## 7. Premios

Total USD 100.000. Esta competencia USD 65.000: 1° 37.000 / 2° 18.000 / 3° 10.000. Paper track USD 35.000. Ganadores ceden licencia open source (Apache 2.0) del submission.

## 8. Reglas que importan

- Equipos de hasta 5; mergers permiten hasta el tope de envíos acumulados.
- Elegibilidad estándar Kaggle (18+, sin sanciones/export-control).
- Datos: uso comercial permitido bajo Apache 2.0, pero no redistribuir a no participantes.

## 9. Riesgos y próximos pasos

Riesgos:
1. Ventana corta y 1 envío/día → cada submission cuenta; validar local con `swegemma eval` antes.
2. Contexto 32k + truncado de tool calls → prompts compactos, sub-agente analizador (`AgentTool`, `skip_summarization`) para no quemar la ventana del coder.
3. `search_similar_code` offline por clave de símbolo → no sirve con preguntas en lenguaje natural.
4. Leaderboard actual bajo (top ~0.15): hay margen, pero el test set oculto puede ser más duro.

Próximos pasos propuestos:
1. Descargar dataset completo (`tasks.jsonl` + snapshots + graphs) y contar tamaño.
2. Armar baseline mínimo: `agent.yaml` con un LlmAgent coder + analyzer como AgentTool, sin LoRA, y correr `swegemma eval --task-ids` en 2–3 tareas fastapi.
3. Medir resolución local y consumo (tool calls, tiempo) → definir `eval_config.yaml`.
4. Recién después: prompt engineering serio y, si hace falta, LoRA rank 16–32 en el coder.

## 10. Verificación (salidas reales de esta sesión)

- `kaggle competitions list --search gemma-4-developer-agent` → detecta ambas, main con deadline 2026-12-02, 65.000 USD, 502 equipos, `userHasEntered True`.
- `competitions files` → `HARNESS_README.md` (49.356 B) + `docker/` (4 archivos) + cientos de `embeddings/*.npz` (~4–6 MB c/u).
- `competitions pages` → 9 páginas: data-description, Description, Evaluation, rules, abstract, Timeline, foundational-rules, Prizes, Model Selection Budget and Harness Rules.
- `competitions pages list --content --page-name <p>` (con `config set competition`) → contenido completo de las 9 (total ~52 KB).
- `competitions leaderboard --show` → top Makus 0.15 (26-sep-2026).
- `competitions submission-limits` → 0 envíos hoy y lifetime, queda 1 hoy.
- Downloads OK: `HARNESS_README.md`, `Dockerfile.public/sandbox`, `imp.py` (telnetlib.py de 23 KB quedó pendiente, es solo shim).
