# Feature: host-trial-wheels-backoff

## Goal

La fase `3b/8` murio en produccion con `429 Too Many Requests` en la primera
de 124 descargas y aborto todo el trial. Endurecer la descarga: reintento,
pausa y resume.

Decisiones tomadas con el usuario:

1. **El 429 puntual se archivo como server-side**, pero el retry queda como
   seguro permanente contra rate limits.
2. **Stdlib solamente**, mismo estilo del runner (sin dependencias nuevas).

## Non-goals

- Mergear sin orden de Emilio (rama local pendiente de decision: PR o drop).

## Tasks

- [x] T1 — `run_cmd_with_retry` (hasta 5 intentos, backoff exponencial,
      honra `Retry-After`) en `run_host_trial.py`.
- [x] T2 — Pausa de 1.5 s entre descargas sucesivas de wheels.
- [x] T3 — Resume por faltantes (remoto menos validos locales); `.whl` de
      0 bytes se trata como faltante. Reemplaza el skip temprano con `any()`
      que dejaba sets parciales para siempre.
- [x] T4 — 6 tests nuevos + 2 adaptados (mock `subprocess`/`time.sleep`,
      sin red).
- [x] T5 — `ruff check` + `pytest -q` en verde (105 passed).
- [ ] T6 — Decision pendiente: abrir PR o borrar rama
      `fix/host-trial-wheels-backoff` (commit `1149276`).

## Evidence

- Rama local: `fix/host-trial-wheels-backoff` (sin push).
- Verificado por Robotina: ruff limpio, 105/105 pytest.
