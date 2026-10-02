# kaggle-gemma-agent

Agente desarrollador/de programación para la competencia de Kaggle
**gemma-4-developer-agent** (fecha límite **2026-12-02**). El agente se empaqueta
y se evalúa con el harness `swegemma`; la métrica puntuada es la **Resolution
Rate** sobre un presupuesto por tarea de **60 minutos** y **100 llamadas a
herramientas**.

Modelo base: `gemma-4-31b-it-qat-w4a16-ct`.

## Inicio rápido

```bash
# 1. Crear el entorno desde el lockfile (solo uv).
uv sync

# 2. Instalar los git hooks una vez por checkout.
uv run pre-commit install

# 3. Instalar/verificar la CLI de Kaggle.
uv run kaggle --version

# 4. Configurar las credenciales de Kaggle fuera del repositorio.
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

Documentación de la API de Kaggle: <https://www.kaggle.com/docs/api>. Nunca
subas el token al repositorio.

## Estructura

```plaintext
.
├── AGENTS.md               # guía de operación (uv, git, submission, presupuestos)
├── README.md               # versión en inglés de este archivo
├── README_ES.md            # este archivo
├── docs/                   # notas, contratos, runbook y reportes de la competencia
├── odd/tasks/              # tracker por feature (objetivo, tareas, evidencia)
├── scripts/host-trial/     # runner multiplataforma del host trial
├── skill-stack/            # 12 skills del agente (un SKILL.md cada una)
├── src/kaggle_gemma_agent/ # packer del submission, harness runs, run reports
├── submission/             # manifest del agente, configs, prompts, skills enviadas
├── tests/                  # suite de pytest
├── .github/                # CI, template de PR, formulario de issues
├── pyproject.toml
├── uv.lock
└── skills-lock.json
```

Las rutas solo locales (`data/`, `runs/`, `tmp/`, `.agents/`) están ignoradas
por git.

## Qué está implementado

- **Packer del submission** (`src/kaggle_gemma_agent/pack.py`): arma
  `submission.zip` a partir de `submission/` (el `agent.yaml` declarativo, los
  configs, los prompts, los sub-agentes y las skills enviadas). Solo stdlib y
  offline.
- **Verificación de cumplimiento**: controla los seis puntos del contrato en
  cada PR.
- **Harness runs y reportes** (`harness_runs.py`, `run_report.py`): archivan una
  corrida de `swegemma` y la renderizan; ver `docs/harness-logging-contract.md`
  y `docs/run-reports.md`.
- **Host trial** (`scripts/host-trial/run_host_trial.py`): el host trial de ocho
  fases; ver `docs/host-trial-runbook.md`.
- **Skills**: 12 skills en `skill-stack/`, copiadas a `submission/skills/`.

## Verificación de cumplimiento

Un submission que falla cualquier punto del contrato puntúa **cero**, así que la
verificación es obligatoria y corre en cada PR:

```sh
uv run python -m kaggle_gemma_agent.pack submission --check
```

Controla: `agent.yaml` solo declarativo (**a**); 12 skills, cada una con
`skills/<dir>/SKILL.md` (**b**); un único id de modelo base (**c**);
presupuestos dentro de los límites en `eval_config.yaml` (**d**, 100 llamadas /
60 min / 500 turnos); sin cadenas de red / pip / MCP / subprocess bajo
`submission/` (**e**); y un archivo por debajo de **3 GiB** (**f**).

## Resumen del submission

`submission.zip` contiene:

- `agent.yaml` — manifest requerido del agente.
- Adaptadores LoRA opcionales — como máximo un modelo, tamaño total **< 3 GiB**.

Mantén el archivo mínimo y autocontenido; el harness `swegemma` lo ejecuta bajo
los presupuestos por tarea de arriba.

## Cómo contribuir

Lee [AGENTS.md](AGENTS.md) para las reglas completas: toolchain solo uv, manejo
de la autenticación de Kaggle, contrato del submission, presupuestos del harness,
uso de skills y flujo de git (ramas de feature, PRs con salidas de comandos
reales, Emilio mergea).

La CI (`.github/workflows/ci.yml`) corre `uv run ruff check src/ tests/`, la
verificación de cobertura de pytest (`fail_under = 90`) y el chequeo de
cumplimiento del packer.
