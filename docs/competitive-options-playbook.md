# Playbook de opciones competitivas — `gemma-4-developer-agent`

Documento de trabajo. Cubre **solo lo relacionado con la competencia**: cómo
subir la tasa de resolución. No trata elegibilidad, impuestos ni marco legal.

Se apoya en lo que ya existe en el repo (`submission/`, `scripts/host-trial/`,
`docs/`) y en los hallazgos de `odd/tasks/trial-collect-and-open-items.md`.
Los números de presupuesto y las rutas de archivo son los reales del proyecto.

---

## 0. Restricciones operativas que condicionan cada decisión

| Restricción | Valor | Fuente / dónde tocar |
|---|---|---|
| Modelo base | único y obligatorio: `gemma-4-31b-it-qat-w4a16-ct` (~16–18 GB, INT4 QAT) | `submission/agent.yaml` |
| Contexto máximo | 32.768 tokens (prompt + pensamiento + salida) | `submission/configs/sampling.yaml` |
| Contexto efectivo (compactación) | **~14.336 tokens**: el evaluador compacta antes del techo (ver §10.1) | §10.1 |
| Ventana con LoRA | la caché KV se reduce; menos adaptadores y de rango bajo = más ventana (ver §10.1) | §10.1 |
| Salida máxima | `max_output_tokens: 16384` | `sampling.yaml` |
| Presupuesto de pensamiento | `thinking_budget: 4096` | `sampling.yaml` |
| Tiempo total del agente | **12 h** para todas las tareas (incluye el armado del entorno, excluye la validación) | `eval_config.yaml` (topes por tarea) |
| Por tarea | 100 llamadas / 60 min / 500 turnos; comando 300 s; salida de comando 5.000 caracteres; `read_file` 150 líneas / 10.000 caracteres | `submission/eval_config.yaml` |
| Herramientas | 9: `run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`, `write_file`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph` | `submission/agent.yaml` |
| Entorno de puntuación | offline: sin red, sin instalaciones, sin servidores, sin procesos en segundo plano | restricción del sistema |
| Adaptadores | hasta 8 simultáneos, rango ≤ 128, total < 3 GiB | carpeta `submission/adapters/` |
| Entrega | `submission.zip` con `agent.yaml` en la raíz, config ADK declarativa | `src/kaggle_gemma_agent/pack.py` |
| Envíos | 1 por día, hasta 2 finales | plataforma |
| Set público | 129 tareas (`fastapi`, `rich`, `requests`, `httpx`), con `patch` de referencia | `data/raw/tasks.jsonl` |

**Consecuencia:** el orden de poder es: (1) medir, (2) usar mejor el contexto y las
herramientas, (3) afinar lo que se le pide al modelo, (4) recién al final entrenar.
El contexto (techo 32.768, pero compactación a ~14.336) y las 100 llamadas son el
cuello de botella real, no el conocimiento del modelo.

---

## 1. Regla de oro: medir antes de cambiar

Todo cambio se prueba contra un trial local **antes** de gastar un envío. Sin
línea base no hay forma de saber si una idea suma.

### 1.1 Cómo correr un trial local

```bash
# entorno
uv sync --locked
cp .env.example .env        # completar backend y clave (nunca commitear)

# un run sobre 2 tareas (default: fastapi_15661,fastapi_15588)
uv run python scripts/host-trial/run_host_trial.py run_01 --repair-sandbox-deps

# elegir tareas
HARNESS_TRIAL_TASKS=fastapi_14962,fastapi_15589 \
  uv run python scripts/host-trial/run_host_trial.py run_02 --repair-sandbox-deps

# leer el resultado
cat runs/<UTC>/STATUS
```

El runner archiva en `runs/<UTC>/` y `report.json` ya distingue fallos de
entorno de fallos del agente (`environment_blocked`, `failure_kind`,
`verdict_source`).

### 1.2 Qué registrar por experimento

- Tasa de resolución (resueltas / medidas).
- Llamadas y minutos por tarea (presupuesto consumido).
- Motivo de fallo (`collection_error`, `test_failure`, `timeout`, sin veredicto).
- Módulos faltantes (para no confundir infraestructura con agente).

### 1.3 Filtrar tareas "ganables" antes de medir en serio

El hallazgo F2 del repo: `fastapi_15661` es **inasible sin el test oculto** (exige
nombres/firmas que no aparecen en el enunciado). Medir la tasa sobre tareas
perdidas de antemano distorsiona. Propuesta:

1. Correr un trial amplio (10–15 tareas).
2. Marcar las que fallan por "API exacta desconocida" sin chance de deducirla.
3. Definir un subconjunto de tareas "ganables" para comparar cambios A/B.

No cambia el puntaje oficial (el set es oculto), pero hace que tus decisiones se
basen en señal, no en ruido. Ojo: hay tareas públicas que **nadie** puede resolver
por bugs del wheelhouse público (dependencias de test faltantes, `VERIFY_X509_STRICT`
en py3.13); ver §10.4.

---

## 2. Palancas sin entrenar (mayor retorno hoy)

### 2.1 Prompt del sistema — `submission/prompts/system.md`

Es la palanca más barata y suele rendir más que un adaptador. Además del texto
actual, considerar:

- **Contrato de salida**: obligar a diagnosticar, editar, verificar y **enviar**,
  con un criterio explícito de "listo".
- **Regla anti-exploración**: prohibir comandos de turismo (`git fsck`, listar
  `/root`, `pip download`) que no acercan al parche.
- **Orden de herramientas**: preferir `edit_file` para editar; `run_command` solo
  para correr tests y comandos acotados.
- **Punto de no retorno**: a X llamadas restantes, dejar de explorar.
- **Formato de respuesta del sub-agente**: exigir rutas y líneas exactas.

Verificación: A/B con el mismo conjunto de tareas; comparar llamadas y resueltas.

### 2.2 Habilidades — `submission/skills/<nombre>/SKILL.md`

Hay 12. Cada una cuesta contexto en cada turno (se cargan como material de
lectura). Auditoría recomendada:

1. Medir largo de cada `SKILL.md` (las muy largas cuestan tokens cada turno).
2. Quitar solapamientos (por ejemplo, `systematic-debugging` vs
   `differential-diagnosis`; `test-driven-development` vs
   `python-testing-patterns`).
3. Asegurar que cada paso use **solo** las 9 herramientas.
4. Que cada una tenga un criterio claro de activación ("Trigger: ...").

Ejemplo de mapeo correcto: `repo-mapping` → `run_command ls` + `read_file`;
`code-graph-navigation` → `get_code_neighbors` / `get_code_subgraph` /
`search_similar_code` con **símbolos, no lenguaje natural**.

### 2.3 Política de herramientas / interfaz agente-herramienta

Menos llamadas, más grandes:

- Preferir una edición amplia y correcta sobre muchas ediciones chicas.
- No releer un archivo sin cambios (ya está en `budget-aware-tool-use`).
- Usar `get_status` (gratis) para controlar el presupuesto.
- Batch de lecturas al inicio; después editar y verificar.

El hallazgo F3 dice que el modelo-proxy abusa de `run_command`. Regla explícita:
"editar con `edit_file`/`write_file`; `run_command` es para tests".

### 2.4 Sub-agente analizador — `submission/sub_agents/code_analyzer.yaml`

Hoy analiza y devuelve un informe de 15 líneas. Ideas:

- Delegar **solo** la localización cuando el repositorio es grande.
- Mantener `skip_summarization: true` para que el informe llegue crudo.
- Limitar su presupuesto (que no se coma llamadas que necesita el agente principal).
- Afinar `prompts/analyzer.md`: pedir rutas+líneas+firma exacta del símbolo.

### 2.5 Contexto y truncado

El enemigo es el corte del bloque de llamada a herramienta por exceder
`max_output_tokens`. Reglas:

- `thinking_budget` bajo (≈4096) y ediciones incrementales.
- Salidas de comando acotadas (`| head`, `-q`).
- No volcar archivos enteros al contexto.
- Cerrar cada turno con una acción concreta, no con un monólogo.

Además, el evaluador **compacta a ~14.336 tokens** y, con LoRA, la caché KV se
reduce (§10.1): planificá una ventana efectiva chica, no 32k.

### 2.6 Parámetros de generación — `submission/configs/sampling.yaml`

```yaml
temperature: 0.2      # subir si el agente se traba; bajar si divaga
top_p: 0.95
max_output_tokens: 16384
thinking_config:
  thinking_budget: 4096   # subir si falla razonamiento; bajar si trunca
  include_thoughts: true
```

Probar cada cambio por separado y medir.
Aviso (§10.1): `include_thoughts` estaba **desactivando** el razonamiento en vez
de solo ocultarlo; verificá antes de confiar en ese ajuste.

### 2.7 Verificación previa al envío (ya implementada)

El skill `verification-before-submit` ahora corre `python -m py_compile` sobre
los archivos cambiados y rechaza archivos basura del diff. Extensión natural:
que el agente corra **una** vez el test objetivo y pegue la salida antes de
enviar.

### 2.8 Grafos y vectores — usarlos bien

`data/raw/graphs/` (redes de llamadas) y `data/raw/embeddings/` (vectores por
símbolo) respaldan `get_code_neighbors`, `get_code_subgraph` y
`search_similar_code`.

- `search_similar_code` espera **símbolos**, no preguntas: "serialize_response",
  no "¿cómo se serializa?".
- Usar `get_code_neighbors`/`get_code_subgraph` para blast-radius antes de editar.
- Documentar el patrón en `code-graph-navigation` para que el agente lo repita.

### 2.9 Presupuesto por tarea — `submission/eval_config.yaml`

```yaml
evaluation:
  timeout_seconds: 3600
  max_tool_calls: 100
  max_time_minutes: 60
  max_turns: 500
```

La suma de topes debe entrar en las 12 h. Estrategia: dar menos a tareas simples
y reservar margen para las difíciles; no regalar una hora a todas. Las tareas
corren **secuencialmente** y el scorer lee **solo cuatro campos**
(`timeout_seconds`, `max_tool_calls`, `max_time_minutes`, `max_turns`). Pasar las
12 h hoy **da error** (planean cambiarlo a "sin terminar = 0"); poné
`max_time_minutes` moderado como salvavidas (§10.3).

### 2.10 Empaquetado y control de cumplimiento

Antes de cualquier envío:

```bash
uv run python -m kaggle_gemma_agent.pack submission --check   # 6/6
uv run pytest tests/ -q
uv run ruff check src/ tests/ scripts/
ruff format --check src/ tests/ ; uv run mypy src/ scripts/ ; uv run pyright
```

---

## 3. Datos y contexto (sin entrenar)

### 3.1 Qué hay en `data/raw/`

| Carpeta | Contenido | Uso |
|---|---|---|
| `tasks.jsonl` | 129 tareas con `problem_statement`, `patch` (referencia) y `test_patch` (solo entrenamiento) | entender problemas; generar datos de entrenamiento |
| `snapshots/` | 129 `.tgz` del repo en `base_commit` | correr el agente como en la competencia |
| `graphs/` | 127 JSON de grafo de llamadas | alimentar las herramientas de grafo |
| `embeddings/` | 127 `.npz` (256-d por símbolo) | alimentar `search_similar_code` |
| `wheels/` | paquetes offline | dependencias del entorno hermético |

### 3.2 Cómo aprovecharlos sin entrenar

- Construir un mapa de símbolos por repo (a partir de `graphs/`) y volcarlo como
  referencia compacta en un skill, para que el agente no adivine nombres.
- Extraer los parches de referencia (`patch`) y estudiar los patrones de fix por
  repo; convertirlos en reglas de los skills.

### 3.3 Datos externos

La competencia permite datos y herramientas externas si son públicamente
accesibles o "razonables". Para implementación: cualquier dato que uses debe
poder descargarse sin costo por cualquier participante. Documentar la fuente.

---

## 4. Entrenamiento

Solo tiene sentido **después** de un baseline medido. Todo adaptador se empaqueta
en `submission/adapters/<nombre>/` y se referencia con `adapter: <nombre>` en
`agent.yaml` o en un sub-agente.

### 4.0 Formato de datos

Dos fuentes:

1. **Pares directos** (desde el set público): `problem_statement` → `patch` de
   referencia. Es la supervisión más limpia que tenés.
2. **Trayectorias** (de tus trials): pasos del agente hasta un parche que pasa
   los tests. Salen de `runs/<UTC>/<tarea>/trace.json` y `session.log`.

Formato de cada ejemplo: lista de mensajes (usuario/problema, asistente/llamada,
resultado de herramienta, …, parche final), aplicando la plantilla de chat de
Gemma. Guardar como JSONL.

### 4.1 Ajuste supervisado (SFT) con adaptador

Puntos de partida evaluados en `docs/skill-stack-inventory.md`: **TRL**,
**PEFT**, **Unsloth**, **Axolotl**, **LlamaFactory**.

Configuración base de adaptador (ajustar rango y objetivo al tope de 3 GiB):

```python
from peft import LoraConfig
config = LoraConfig(
    r=32, lora_alpha=64, lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    bias="none", task_type="CAUSAL_LM",
)
```

Entrenamiento (esquema):

```python
from trl import SFTTrainer, SFTConfig
trainer = SFTTrainer(
    model=base, tokenizer=tok, train_dataset=ds,
    args=SFTConfig(output_dir="out", num_train_epochs=2,
                   per_device_train_batch_size=1, gradient_accumulation_steps=8,
                   learning_rate=2e-4, max_seq_length=32768),
)
trainer.train()
```

Exportación a la carpeta de adaptador:

```python
model.save_pretrained("submission/adapters/main_lora")   # adapter_model.safetensors
tok.save_pretrained("submission/adapters/main_lora")     # + adapter_config.json
```

Verificar: `rank ≤ 128`, `< 3 GiB`, y que `pack --check` siga en 6/6.
Para probar adaptadores localmente hay que usar **el wheel parcheado del
wheelhouse** (el wheel público de PyPI falla con Gemma4+LoRA, §10.5). Y cada
adaptador consume caché KV: rango bajo y pocos adaptadores (§10.1).

### 4.2 Optimización por preferencias (DPO / KTO / ORPO)

Con pares "parche que pasa" vs "parche que falla" del mismo problema:

```python
from trl import DPOTrainer, DPOConfig
DPOTrainer(model=base, ref_model=ref, args=DPOConfig(...), train_dataset=pairs)
```

Útil cuando el SFT ya aprendió el formato pero el modelo elige mal entre dos
soluciones. KTO tolera datos sin par.

### 4.3 Refuerzo con recompensa verificable (GRPO)

Recompensa = **el parche pasa los tests**. Requiere un entorno de ejecución
paralelo (el mismo sandbox hermético) que aplique el parche y corra `pytest`.

```python
from trl import GRPOTrainer, GRPOConfig
GRPOTrainer(model=base, reward_funcs=[reward_patch_passes], args=GRPOConfig(...))
```

Es la palanca más potente y la más cara: exige orquestar contenedores y es
sensible a la varianza de la recompensa. Se justifica solo con baseline y SFT ya
funcionando.

### 4.4 Destilación

Generar trayectorias exitosas con un modelo más fuerte **fuera** de la
competencia y usarlas como datos de SFT. Baja el costo de conseguir ejemplos
buenos. Habilitado oficialmente, con la salvedad de licencias (§10.6).

### 4.5 Varios adaptadores a la vez (hasta 8)

Un adaptador por rol:

- `main_lora` para el agente principal.
- `analyzer_lora` para el sub-agente de análisis.

En `agent.yaml` / `sub_agents/*.yaml`: `adapter: main_lora`. Mantener el total
< 3 GiB repartiendo rango entre ambos.

### 4.6 Variantes dentro del presupuesto

- **QLoRA** (4-bit + LoRA) para entrenar con menos memoria.
- **DoRA** como alternativa a LoRA.
- Elegir `target_modules` y rango según el tope de tamaño; medir el efecto real,
  no asumir.

### 4.7 Empaquetado del adaptador

- `adapter_config.json` + `adapter_model.safetensors` dentro de
  `submission/adapters/<nombre>/`.
- Sin `.bin`/`.pt`/`.pth` (rechazados).
- Correr `pack --check` para confirmar tamaño y formato.

### 4.8 Infraestructura de entrenamiento

La puntuación usa 4×L4 (96 GB). Para entrenar localmente hace falta una GPU con
memoria suficiente (QLoRA/Unsloth para el modelo de 31B). Documentar la
plataforma y los pasos de reproducción, porque un ganador debe poder reproducir.

### 4.9 Cableado del adaptador

```yaml
# submission/agent.yaml (y/o sub_agents/code_analyzer.yaml)
name: kaggle_gemma_agent
model: gemma-4-31b-it-qat-w4a16-ct
adapter: main_lora      # <-- agrega esta línea cuando exista el adaptador
```

### 4.10 Cómo evaluar un adaptador

1. `pack --check`.
2. Trial local sobre el subconjunto "ganable".
3. Comparar tasa, llamadas y tiempo contra el baseline **sin** adaptador.
4. Si no mejora la tasa, no se envía.

---

## 5. Pista de artículo (opcional, $35.000)

Cierra el **12-nov-2026**. Temas que el organizador pide:

- **Ajuste y optimización**: PEFT y RL para agentes de software.
- **Comprensión de código**: grafo de código, parseo, embeddings.
- **Tareas y benchmarks**: nuevos conjuntos/recursos.
- **Razonamiento sobre grafos**.

Se puede escribir sobre el mismo trabajo de la competencia (usar el dataset de
grafos/embeddings que ellos publicaron suma).

---

## 6. Estrategia de envíos

- Validar **todo** localmente antes de gastar el envío del día.
- 1 envío por día: guardarlo para un cambio medido, no para una corazonada.
- Elegir con cuidado los **2 finales**: el que mejor tasa local tenga, no el
  último que subiste.
- No salir de la zona segura de cumplimiento (formato, topes, adaptadores).

---

## 7. Hoja de ruta sugerida por semanas

| Semana | Foco |
|---|---|
| 1 | Baseline local limpio en WSL/Linux + filtro de tareas ganables (sección 1) |
| 2 | Palancas 2.1–2.6 (prompt, skills, interfaz, contexto, sampling) con A/B |
| 3 | Grafos/embeddings (2.8) + presupuesto por tarea (2.9) + consolidación |
| 4 | Datos de entrenamiento (4.0) + primer SFT (4.1) y evaluación (4.10) |
| 5 | Preferencias (4.2) o RL verificable (4.3) si el SFT mostró techo |
| 6 | Ajuste fino de la mejor combinación; multi-adaptador (4.5) |
| 7 | Envíos finales + artículo (sección 5) si aplica |
| 8 | Reserva para imprevistos |

---

## 8. Registro de experimentos (plantilla)

| Fecha | Cambio | Archivo(s) | Tareas | Resueltas | Llamadas | Nota |
|---|---|---|---|---|---|---|
| | baseline | — | | | | |
| | | | | | | |

Regla: un cambio por experimento; si no se puede aislar, no se puede atribuir.

---

## 9. Orden de implementación recomendado

1. Medición y filtro de tareas (§1).
2. Prompt + skills + interfaz + contexto + sampling (§2.1–2.6).
3. Grafos y presupuesto (§2.8–2.9).
4. SFT (§4.0–4.1, 4.7–4.10).
5. Preferencias o RL (§4.2–4.3).
6. Consolidación, envíos y artículo (§5–6).

---

## 10. Hallazgos del foro de Kaggle y su impacto

**Método y advertencia.** Leí los hilos con la API de Kaggle
(`kaggle competitions topics show <id>`). No pude listar los hosts oficiales (la
API devolvió 403), así que marco como **respuesta oficial** solo la de autores que
hablan en nombre de la organización y ejecutan mantenimiento del evaluador —
principalmente **Ryan Holbrook** (que además publica el notebook oficial) y, en
una respuesta institucional, **Ashley Oldacre**. El resto es de participantes:
útil, pero **no oficial**. No inventé autorías ni citas.

### 10.1 Contexto, compactación y caché KV (corrige la sección 0)

- El techo duro es **32.768** tokens combinados, pero el evaluador **compacta a
  ~14.336** (`token_threshold = 14.336`). El contexto de trabajo real es ~14k. Un
  participante pidió confirmar si el scorer usa 14.336 o 32.768; el staff dijo que
  lo revisaría.
- **Con LoRA activado, la caché KV se reduce.** Se reportó que con un adaptador de
  rango 64 la caché KV bajó a ~7.600 tokens y los prompts de ~14.000 tokens **se
  colgaban**. Respuesta oficial: vLLM ahora ajusta los parámetros de LoRA según lo
  que enviaste; **menos adaptadores y de rango más bajo (o ninguno) dejan más
  memoria para la caché KV**.
- `include_thoughts` estaba **desactivando** el razonamiento en vez de solo
  ocultarlo (reportado sobre `adk_submission 0.2.12`; sin respuesta oficial aún).

Implicancia: planificá una ventana efectiva de ~7–14k tokens, no 32k; y tratá cada
adaptador como un costo de contexto.

### 10.2 Bugs del evaluador y estado

- **Pensamientos descartados entre llamadas** (vLLM ignoraba `reasoning_content`):
  confirmado como bug; arreglado en el wheelhouse actual. **No repuntúan envíos
  viejos.**
- **Resultados de herramientas con doble codificación JSON**: arreglado en el
  wheelhouse del 30-sep; `edit_file` sumó un fallback.
- **`thinking_budget` y `seed` no se enviaban**: arreglado en el wheelhouse
  reciente.
- **Adaptadores borrados en silencio** (vLLM 0.19.1 parcheado): arreglado desde el
  wheelhouse v23.
- **`sample_submission` oficial fallaba**: arreglado.
- **Herramienta no declarada termina la tarea y descarta el parche**: el staff dijo
  que lo implementaría. → Declarar solo las herramientas que usás.
- **Bug con skills + `run_skill_script`** (`file_path` como lista → excepción que
  termina la tarea): reportado. → Cuidado con scripts en skills.
- **Errores de envío tras el 30-sep**: fue una caída de GPU; resuelta.

### 10.3 Presupuesto y ejecución

- Las tareas corren **secuencialmente**.
- El scorer lee **solo cuatro campos** de `eval_config.yaml`: `timeout_seconds`,
  `max_tool_calls`, `max_time_minutes`, `max_turns`; por defecto, sin límite.
- Pasar las 12 h **hoy da error**; planean cambiarlo a "tareas sin terminar = 0".
  El staff recomienda poner `max_time_minutes` moderado como salvavidas.

### 10.4 Tareas públicas rotas (no sobre-optimizar)

- Faltan dependencias de test en el wheelhouse público (`typing_inspection`,
  `inline_snapshot`, `dirty_equals`, `ujson`/`orjson`, `python-multipart`,
  `pytest-httpbin`): el parche de referencia falla en muchas tareas FastAPI/requests.
- Python 3.13 activa `VERIFY_X509_STRICT`, y el certificado de `pytest-httpbin` no
  tiene AKI → los tests https fallan siempre (≈8 tareas de requests).
- Tests version-gated con `skipif` que se saltan en 3.13.
- Hay **desplazamiento de dominio** entre los repos públicos y la evaluación oculta
  (hilo abierto).

Implicancia: la tasa sobre las 129 públicas **no** es comparable con el puntaje
oficial; filtrá las irresolubles (§1.3) y usá el notebook oficial de
getting-started.

### 10.5 Adaptadores y vLLM

- Solo el wheel parcheado del wheelhouse soporta LoRA para Gemma4; el wheel público
  de PyPI falla al arrancar ("does not support LoRA yet"). → Para probar adaptadores
  localmente, usá el wheelhouse de la competencia.
- `discover_adapters` espera la **raíz del submission**, no la carpeta del adaptador.

### 10.6 Destilación

Respuesta institucional (Ashley Oldacre): se pueden usar modelos externos para
destilar **siempre que** se usen según su licencia y que el resultado no entre en
conflicto con las reglas de la competencia. → Habilita el enfoque de §4.4, con la
salvedad de licencias.

### 10.7 Señales de la tabla

`sample_submission` oficial ~0.01; envíos mínimos reportados 0.08–0.12; el techo
público ronda ~0.15. Hay margen.

### 10.8 Hilos de referencia

| Hilo | Tema | Respuesta oficial |
|---|---|---|
| 744354 | Pensamientos descartados entre llamadas | Sí (arreglado) |
| 744331 | Caché KV con LoRA / cuelgues | Sí (ajuste dinámico) |
| 744692 | Umbral de compactación | Sí ("lo reviso") |
| 744794 | Resumen de bugs y estado | Sí |
| 743063 | Concurrencia, `eval_config`, 12 h | Sí |
| 743213 / 743508 | Adaptadores/LoRA, `sample_submission` | Sí |
| 744272 | Resultados de herramienta con doble JSON | Sí |
| 745028 | Herramienta no declarada | Sí (a implementar) |
| 744807 | Errores tras el wheelhouse del 30-sep | Sí (caída de GPU) |
| 742882 | Evaluación local, deps faltantes | Sí |
| 742911 | Grafos/embeddings vacíos | Sí (parcial) |
| 742807 | Destilación desde LLMs externos | Sí (Ashley Oldacre) |
| 743973 | Parches de referencia fallan offline | No (participantes) |
| 743186 | Infra para SFT/RL | No (participante) |
| 745059 | `include_thoughts` desactiva el razonamiento | No |
| 745774 | El agente repite el mismo comando | No |
| 745796 | Desplazamiento de dominio | No |
