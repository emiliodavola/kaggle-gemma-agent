# Feature: host-trial-smoke-reasoning

Closes #53.

## Goal

El preflight `smoke_test_backend` manda `max_tokens: 16` (`run_host_trial.py:586`).
Un modelo de razonamiento gasta ese presupuesto en el canal de pensamiento y
devuelve `content: ""` con `finish_reason: "length"`, asi que el smoke falla con
un falso *"empty reply"* aunque el endpoint y el modelo esten sanos. Evidencia
real (LM Studio, `gemma-4-31b-it-qat`): `completion_tokens: 16`,
`reasoning_tokens: 13`, `content: ""`, `reasoning_content` no vacio.

El eval real ya tiene margen: `submission/configs/sampling.yaml` define
`max_output_tokens: 16384` y `thinking_budget: 4096`. Solo el sondeo de 16 tokens
esta mal.

Decisiones tomadas con el usuario:

1. Subir el presupuesto del sondeo a un valor que le permita responder a un
   modelo de razonamiento (`SMOKE_MAX_TOKENS = 256`).
2. Aceptar un canal de razonamiento no vacio (`reasoning_content` / `reasoning`)
   como reply usable: el prompt del sondeo pide texto, no un tool call.
3. Un mensaje realmente vacio (sin content, sin tool_calls, sin reasoning) sigue
   fallando.

## Non-goals

- Cambiar el sampling config del submission.
- El bug de paths `read_file`/`edit_file` en Windows.
- Probar tool calling en el smoke (lo ejerce el run).

## Tasks

- [x] T1 — Runner: constante `SMOKE_MAX_TOKENS = 256` y payload del sondeo.
- [x] T2 — Runner: aceptar `reasoning_content`/`reasoning`; devolver
      `"reasoning-only reply"`; el mensaje vacio sigue fallando.
- [x] T3 — Tests: reply solo-razonamiento pasa; el payload usa el presupuesto
      nuevo; el caso vacio sigue fallando.
- [ ] T4 — `ruff` + `pytest` + `mypy` + `pyright` en verde y PR contra `main`.

## Evidence

- Issue: #53. Rama: `fix/host-trial-smoke-reasoning` (desde `main`).
- (a completar con la salida real de pytest.)
