# Feature: host-trial-wheels-offline-resume

## Goal

La fase `3b/8` (`ensure_trial_wheels`) aborta cuando `_list_competition_wheels()`
falla por red no disponible o rate limit, incluso si el set local de wheels ya
esta estacionado. Antes de PR #24 la fase saltaba sin tocar la red; ese camino
offline se perdio al hacer que el listing remoto fuera obligatorio.

Decisiones tomadas con el usuario:

1. Mirar primero el set local y despues consultar `_list_competition_wheels()`.
2. Si el listing falla pero hay wheels locales validos, continuar con el set
   local y dejar un warning; si falla y no hay nada local, propagar el error.
3. Un listing exitoso pero vacio sigue siendo error: significa que la
   competencia no tiene `wheels/` para estacionar.
4. De paso, hacer inyectable la pausa entre descargas (nit del review).

## Non-goals

- Cambiar el resume por faltantes de PR #24 (remoto menos validos locales).
- Tocar el retry/backoff ni la deteccion de rate limit (va en el PR del path
  de retry).
- Auto-merge ni push a `main`.

## Tasks

- [x] T1 — `ensure_trial_wheels`: computar `_staged_wheel_names` antes del
      listing y tolerar un `TrialError` del listing cuando hay wheels locales.
- [x] T2 — `sleep` inyectable en `ensure_trial_wheels` y `_fetch_competition_file`.
- [x] T3 — Tests: listing caido con set local, listing caido sin set local,
      forwarding de `sleep`.
- [x] T4 — `ruff check` + `pytest` en verde.

## Evidence

- Branch: `fix/host-trial-wheels-offline-resume`.
- Commands and results are pasted in the PR body.
