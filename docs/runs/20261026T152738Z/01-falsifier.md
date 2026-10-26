---
Date: 2026-10-26
Genre: run analysis
Status: current
Scope: The four-rollout falsifier for the `tools/harness2-swegemma` adapter: two tasks against the base submission and against the same tree plus one INV edit. It checks plumbing and signal; it does not measure whether the edit helps.
Source of truth: runs/harness2-falsifier/20261026T152738Z.json, runs/harness2/raw/falsifier-20261026T152738Z__*/task_results.jsonl, runs/harness2/raw/falsifier-20261026T152738Z__*/harness.json (read 2026-10-26)
Limits: Two tasks, one pair each, no randomisation, one local backend; counts and wall times only, no attribution.
---

# swegemma adapter falsifier - `20261026T152738Z`

The versioned adapter in `tools/harness2-swegemma/` was checked against the
falsifier declared before the rollouts: two tasks (`requests_6644`,
`requests_7315`), base tree and base plus one INV edit to
`prompts/system.md`, four serial rollouts. The edit tells the agent to resolve
which file the interpreter loaded before diagnosing a source/disk mismatch.

## Observations

| Task | Tree | Delivered | Resolved | Patch `sha256` | Wall (s) | Tool calls | LLM calls | Patch bytes |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `requests_6644` | base | yes | no | `e48a7479f850...` | 437.61 | 21 | 36 | 499 |
| `requests_6644` | variant | yes | no | `05cf7f697b69...` | 559.37 | 29 | 33 | 376 |
| `requests_7315` | base | yes | yes | `7a94ed25d3cd...` | 581.30 | 31 | 37 | 522 |
| `requests_7315` | variant | yes | yes | `9869b4ab5a0f...` | 3 626.02 | 89 | 107 | 1 222 |

- All four rollouts archived: each raw directory has `summary.json` and one
  `task_results.jsonl` line.
- The two trees have different fingerprints: base `790d06db787e9c35`, variant
  `602f49e9d77bd443`, on both tasks. `execute()` used the tree it was given.
- At least one task differs in `delivered` or `patch_sha256`: all four patches
  differ; `delivered` is `true` on all four.
- Total rollout wall time is 5 204.30 s (86.74 min). Three rollouts took
  7.3-9.7 min; `requests_7315` on the variant took 3 626.02 s (60 min 26 s) and
  consumed 89 of the 100 tool calls and 107 LLM calls. It hit the harness's
  60-minute wall-clock budget.
- `requests_7315` resolved on both trees; `requests_6644` resolved on neither.
  The variant patch is larger on `7315` (1 222 vs 522 bytes) and smaller on
  `6644` (376 vs 499 bytes).

## Assertions

The falsifier's three pre-declared assertions all hold:
`four_archived=true`, `fingerprints_differ=true`, `signal=true`.
Result JSON: `runs/harness2-falsifier/20261026T152738Z.json`.

## What this establishes

- The adapter drives `swegemma` end to end: it materialises the tree, renders
  `models.yaml`, runs one task in Docker, and reads delivery and the pytest
  verdict from the raw results.
- The tree is not ignored: a one-line prompt edit changes the recorded
  fingerprint and the delivered patch on both tasks.
- `k=1` carries a measurable difference on this pair; the full
  Propose-Probe-Compose loop is not obviously blind here.

## What this does not establish

- **No attribution.** The falsifier declared no intended direction and ran one
  pair per task. It is a plumbing check, not an execution contrast for the INV
  edit; no `helped`, `hurt`, `no observed effect` or `confounded` is claimed.
- It is not a rate estimate: two `psf/requests` tasks, not the 11-task
  `dev-v1` subset.
- The 60-minute outlier may be variance in the local 31B backend, the edit, or
  both. One run per cell cannot separate them.
- No answer to whether the INV edit is worth shipping. That needs the declared
  A/B in `docs/dev-experiment-loop.md`, on `dev-v1`, with the direction and the
  component recorded before the runs.

## Next

The falsifier passed, so Level 2 is technically possible. It is not started:
the next decision is whether a full `k=1` sweep (4 rollouts per task plus three
proposer sessions) is worth its cost, and on which domain. The 60-minute
rollout is the first cost warning to carry into that decision.
