# Feature: 92-run-vocabulary

Closes #92. Branch `docs/92-run-vocabulary` (stacked on `feat/91-answer-leak`).
Runner: `uv run pytest`. Delivery strategy: chained PR, slice 2 of 2.

The issue body is the specification. This file ties each task to its rules and
records the evidence; it does not restate them.

## Goal

Adopt four standard verdicts - `helped`, `hurt`, `no observed effect`,
`confounded` - for every attribution in a run analysis or proposal, so a claim
about an edit carries its evidence class instead of reading as causality.

## Decisions

- One living reference, `docs/run-analysis-vocabulary.md`, is the single
  definition; `AGENTS.md` and `docs/README.md` only reference it.
- `confounded` is the default whenever no execution contrast isolates the
  declared change; two runs with identical recorded provenance are variance, not
  a contrast.
- Observations carry no verdict; predictions live in a separate
  `## Expected effect` section.
- The worked example (`docs/runs/20261009T122847Z/01-attribution-audit.md`)
  contains no fabricated `helped` / `hurt` / `no observed effect` row, because
  no archived pair of executions isolates one harness change.

## Non-goals

- Re-analysing earlier runs or rewriting `docs/runs/20261006T103737Z/*` or any
  proposal.
- A statistical method beyond plain counts, or a mechanical Markdown lint.
- The `skills` provenance hash (#94) and the two-dimension protocol (#93).
- Changing the journal schema or its causality rule.

## Tasks

- [x] **T1** - `docs/run-analysis-vocabulary.md`: six-field header, the four
      verdicts table, rules R1-R9 and the claim-record format.
- [x] **T2** - `AGENTS.md` `## Documentation`: reference paragraph after the
      genre list, without restating the definitions.
- [x] **T3** - `docs/README.md`: one `## Source of truth` sentence and two index
      rows (the vocabulary and the run analysis).
- [x] **T4** - `docs/runs/20261009T122847Z/01-attribution-audit.md`: the four
      required observation classes, two attribution rows, the exact
      `2/13 -> 1/13 on a different batch` line and the
      `## What this does not establish` section.
- [x] **T5** - No existing run analysis or proposal is modified and no
      `superseded-by` is added.
- [x] **T6** - One `change` journal event for issue #92.

## Evidence

Raw facts checked against the artifacts on 2026-10-26:

```text
$ hunk comparison for requests_7205
hunk_headers_equal: True
hunk_bodies_equal: True

$ runs/20261008T025904Z STATUS
tasks 13 | resolved 2 | rate 0.154 | unknown 0

$ runs/20261009T122847Z STATUS
tasks 13 | resolved 1 | rate 0.077 | unknown 0

$ report.json totals
20261008T025904Z: resolved 2, resolution_rate 0.15384615384615385, unknown 0
20261009T122847Z: resolved 1, resolution_rate 0.07692307692307693, unknown 0

$ per-task status diff
13 identical instance ids; 12 identical statuses; only requests_7315 pass -> fail

$ requests_7315
tool_calls 22; error "Agent completed execution without calling submit_patch."

$ recorded provenance (docs/journal/events.jsonl)
J-20261008-04 and J-20261009-02 have identical prompt, sampling, eval_config
and repo_commit hashes; neither record carries a skills hash (#94)
```

Gates (`pytest`, `ruff`, `journal validate`) are recorded in the pull request.

## Open items

- The `skills` provenance hash is missing from both run records (#94); until it
  exists, a harness change to the skill bytes cannot be ruled out by the record.
