# Feature: host-trial-retry-output-hardening

## Goal

Endurecer `run_cmd_with_retry` (path de descarga de wheels) a partir de tres
hallazgos del review de `043f921`:

1. La deteccion de rate limit miraba `stderr or stdout`, asi que un marcador
   `429` en stdout se perdia cuando stderr traia cualquier otro texto.
2. El marcador desnudo `"429"` daba falsos positivos con montos u offsets que
   contenian `429` (p. ej. `429 KB`), reintentando fallos deterministas 5 veces
   (~30 s de backoff).
3. El progreso de descarga (`tqdm` escribe en stderr) se capturaba y se
   descartaba, asi que la fase parecia colgada entre archivos.

Decisiones tomadas con el usuario:

1. Combinar ambos streams para detectar el rate limit.
2. Acotar los marcadores a frases de rate limit reales (`too many requests`,
   `rate limit`, `429 client error`), sin el `429` desnudo.
3. Reenviar stderr en exito para no perder el progreso.

## Non-goals

- Cambiar el orden local/remoto del staging (va en el PR de offline resume).
- Inventar un parser de progreso; solo reenviar el stream.

## Tasks

- [x] T1 — `RATE_LIMIT_MARKERS` sin `"429"` desnudo.
- [x] T2 — `run_cmd_with_retry`: `detail` combinando stderr + stdout.
- [x] T3 — `run_cmd_with_retry`: reenviar stderr en exito.
- [x] T4 — Tests: marcador en stdout con stderr presente, `429 KB` no matchea,
      stderr en exito.
- [x] T5 — `ruff` + `pytest` en verde.

## Evidence

- Branch: `fix/host-trial-retry-output-hardening`.
- Commands and results are pasted in the PR body.
