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

- Mergear o pushear sin orden de Emilio.

## Tasks

- [x] T1 — `run_cmd_with_retry` (hasta 5 intentos, backoff exponencial)
      en `run_host_trial.py`; reintenta solo fallos con marcador de rate
      limit (`429` / `too many requests` / `rate limit`), el resto corta al
      primer intento.
- [x] T2 — Pausa de 1.5 s entre descargas sucesivas de wheels.
- [x] T3 — Resume por faltantes (remoto menos validos locales); `.whl` de
      0 bytes se trata como faltante (`_staged_wheel_names`). Reemplaza el
      skip temprano con `any()` que dejaba sets parciales para siempre.
- [x] T4 — 8 tests nuevos + 1 skip-test reemplazado (mock
      `subprocess`/`time.sleep`, sin red).
- [x] T5 — `ruff check` + `pytest -q` en verde (116 passed).
- [x] T6 — Reimplementado en rama nueva `fix/host-trial-wheels-partial-resume`
      (la rama `fix/host-trial-wheels-backoff` fue podada; no se recupera).
      Sin push/PR hasta que Emilio lo pida.

## Evidence

- Rama local nueva: `fix/host-trial-wheels-partial-resume` (sin push).
- `uv run ruff check scripts/host-trial/run_host_trial.py src/ tests/` limpio.
- `uv run pytest tests/ -q` = 116 passed.
- Diagnostico remoto (obtenido antes de la restriccion de red): el prefijo
  `wheels/` tiene 124 wheels, 56 de ellas `starlette-*.whl`, y
  `_list_competition_wheels()` las devuelve todas; el remoto no es la causa.
