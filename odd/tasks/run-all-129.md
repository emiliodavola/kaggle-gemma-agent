# Run the 129-task corpus

Objective: run the public 129-task dev set and decide between a single contended
session and faithful shards.
Branch: `fix/harness-context-and-loops` (from `main`).
Delivery strategy: `ask-on-risk`; one work unit (notebook run mode plus docs).
Test runner: `uv run pytest -q`; notebook cells are compile-checked; the remote
run is the verification.

## Specs

**S1 — Single-session mode.** `SUBSET = None`, `NUM_SHARDS = None`,
`CONCURRENCY = 4`. The notebook prints an estimate from the observed
16.4 min/task and warns above 7.5 h. The evaluation cell catches a fatal error
and the archive cell keeps whatever partial results exist.

**S2 — Faithful mode.** `NUM_SHARDS = 12`, `CONCURRENCY = 1`; about 11 tasks per
session at the per-task condition. The run label and archive stay unique per
shard.

**S3 — Quota math.** Observed 10.1–16.4 min/task. 129 tasks at concurrency 1 are
22–36 h; at concurrency 4 they are 5.4–8.8 h. The weekly GPU quota is 30 h
(L4x4 consumes 2x); 15.79 h remained on 2026-10-28 (about 7.9 h of L4x4). The
single-session mode is tight; shards need 2–3 weeks.

## Tasks

- [x] T1 (S1) — config, estimate, partial archive; every cell compiles.
- [x] T2 (S2) — shard mode preserved.
- [x] T3 (S3) — docs with the quota math.
- [ ] T4 — remote 129 run (single session or 12 shards).

## Log

**L1 — User request (verbatim):** "bueno quiero poner a ejecutar la notebook pero
no sé si va a completar el ciclo con las 129 pruebas, el único baseline es con
las 129 pruebas, hacé el repaso y decime que tengo que hacer, modificá
localmente y luego commiteá y pusheá"

**L2 — Evidence.** `dev-v1` 11 tasks: 180.1 min. Shard 0: 111.2 min. Quota:
15.79 h GPU remaining. 129 at concurrency 1: 22–36 h; at concurrency 4:
5.4–8.8 h.

**L3 — Decision.** The notebook supports both modes. The recommendation is to
wait for the 31/10 quota refresh, or run 2–3 faithful shards now, rather than a
single 129 session that may be cut. The scored baseline is the submission, not
the 129 public dev set.
