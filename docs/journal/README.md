---
Date: 2026-10-07
Genre: journal
Status: current
Scope: Format and rules for the change journal under `docs/journal/`: the machine layer, the human layer, the entry schema, the CLI and the CI guard. Does not cover per-feature tracking.
Source of truth: docs/journal/events.jsonl and src/kaggle_gemma_agent/journal.py (read 2026-10-07)
Limits: A format specification, not a log of entries; the entries themselves are the evidence.
---

# Change journal

The change journal is the chronological, cross-cutting log of changes and
decisions in this repository. It answers "what changed, when, why, and on what
evidence" for the whole project, independent of which feature or directory the
change touched.

## What it is not

- **Not the per-feature tracker** (`odd/tasks/*.md`). That tracker owns the goal,
  decisions, non-goals and checkboxed tasks of one feature; the journal only
  records the dated event and points at the tracker or PR.
- **Not the documentation index** (`docs/README.md`). The index catalogues
  documents by genre and status; the journal is one of those genres, and an
  entry is not a document.
- **Not `engram`.** Engram is agent recall stored outside the repository; the
  journal is versioned, reviewable evidence committed with the change.
- **Not `git log`.** `git log` records the commit graph; the journal records the
  decision and the evidence, including changes that span several commits or no
  commit at all.

## Two layers

- **Machine layer — `docs/journal/events.jsonl`.** Append-only. One JSON object
  per line, UTF-8, LF terminated. This is the source of truth.
- **Human layer — `docs/journal/YYYYMMDD.md`.** The readable digest of one UTC
  date, rendered from `events.jsonl`. It is regenerable and never hand-edited.

## Entry id

`J-YYYYMMDD-NN`, where `NN` is the next free two-digit sequence for that UTC date
(`01`, `02`, ...). Ids are never reused and never renumbered.

## Event schema

Every event is a JSON object with exactly these keys, always present, in this
order:

```json
{"id": "J-20261006-01", "ts": "2026-10-06T19:40:00Z", "type": "change", "actor": "robotina",
 "what": "one line, imperative or past tense, no filler", "why": "the reason, one or two lines",
 "evidence": ["PR #76", "docs/runs/20261006T103737Z/02-successes-vs-failures.md"],
 "status": "applied",
 "refs": {"pr": 76, "issue": 75, "commit": "fd60705", "run_id": null, "docs": ["docs/README.md"]},
 "hashes": null,
 "counts": null}
```

- **`id`** — the entry id (see above).
- **`ts`** — ISO-8601 UTC timestamp, e.g. `2026-10-06T19:40:00Z`.
- **`type`** — one of `observation`, `decision`, `change`, `measurement`,
  `reversal`, `run_started`, `run_finished`, `gate_check`.
- **`actor`** — one of `emilio`, `robotina`, `opencode`, `runner`, `ci`.
- **`what`** — one line, imperative or past tense, no filler.
- **`why`** — the reason, one or two lines.
- **`evidence`** — list of strings: PR/issue refs, paths, commands, counts. May
  be empty.
- **`status`** — one of `open`, `applied`, `superseded`, `reverted`.
- **`refs`** — object with `pr` (int or null), `issue` (int or null), `commit`
  (string or null), `run_id` (string or null) and `docs` (list of paths, may be
  empty).
- **`hashes`** — null, or an object of `name -> sha256` strings, used by the
  runner for `prompt`, `sampling`, `eval_config`, `repo_commit`.
- **`counts`** — null, or an object of `name -> number`, used by the runner for
  `tasks`, `resolved`, `rate` and failure kinds.

Extra keys are not allowed. Keys are always present in the order shown above so
the serialised output is stable.

## Human file format

`docs/journal/YYYYMMDD.md` is rendered from the events of that UTC date:

```markdown
# Change journal — 2026-10-06

Append-only. One entry per change or decision; an entry is never edited. To revise
one, add a new entry that supersedes or reverts it, and set the old one's status.
Evidence is counts and paths, never causality: without randomisation a batch
comparison is "29/48 -> X/48 on a different batch", never "it improved".

## J-20261006-01 — <what>

- **Time:** 19:40Z · **Actor:** robotina · **Type:** change · **Status:** applied
- **Why:** <why>
- **Evidence:** <evidence joined with "; ", or "none recorded">
- **Refs:** PR #76, issue #75, commit fd60705, run 20261006T103737Z, docs/README.md
```

Entries appear in `ts` order, oldest first. The `Refs` line omits empty parts; if
everything is empty it reads `none`. The human file is never edited by hand: run
the render subcommand instead.

## Rules

1. **Append-only.** An entry is never edited and never deleted. To revise one,
   add a new entry that supersedes or reverts it, and set the old entry's
   `status` to `superseded` or `reverted`.
2. **One entry per change or decision**, written in the same PR as the change.
3. **Evidence is counts and paths, never causality.** Without randomisation a
   batch comparison is `"29/48 -> X/48 on a different batch"`, never
   `"it improved"`. State the observation; do not infer a cause.
4. **Stable, exact schema.** The key set and key order above are fixed. Do not
   add extra keys.
5. **UTC everywhere.** Both `ts` and the day file are in UTC.

## How to add an entry

```sh
uv run python -m kaggle_gemma_agent.journal add \
  --type change \
  --what "Add the change journal" \
  --why "Record cross-cutting changes and their evidence in one place" \
  --actor robotina \
  --evidence "PR #76" \
  --pr 76 --issue 75 --doc docs/README.md
```

- `--actor`, `--status`, `--evidence` (repeatable), `--pr`, `--issue`,
  `--commit`, `--run-id`, `--doc` (repeatable), `--ts` and `--date` are optional.
- `--ts` defaults to now (UTC); `--date` derives from `--ts`.
- `--json` prints the created event instead of just the new id.
- The command appends to `events.jsonl` and re-renders that day's file.
- `add` refuses an identical entry (`type` + `what` + `why` + `status`) added in
  the same run, so a change is never double-logged.

Other subcommands:

- `render [--date YYYY-MM-DD] [--root PATH]` — regenerate a day file from
  `events.jsonl`; idempotent.
- `list [--type T] [--status S] [--since ISO] [--date YYYY-MM-DD] [--root PATH]`
  — print `id | ts | type | status | what`.
- `validate [--root PATH]` — check unique ids, valid enums, parseable `ts`, an
  exact and ordered key set, and that every day file matches a fresh render.

`--root` defaults to `docs/journal`, resolved from the package location, so the
commands work from any directory.

## Worked example

1. A worker changes `submission/prompts/system.md` and writes a new entry:

   ```sh
   uv run python -m kaggle_gemma_agent.journal add \
     --type change \
     --what "Harden the system prompt against premature submits" \
     --why "Run_03 shows submit_patch called before the failing test was read" \
     --actor robotina \
     --evidence "PR #77" "runs/20261006T103737Z/" \
     --pr 77
   ```

2. The command appends the JSON line to `docs/journal/events.jsonl` and writes
   `docs/journal/20261007.md`.
3. CI runs the guard: because the PR touched `submission/` and a path under
   `docs/journal/` also changed, the gate passes.

## How CI enforces it

Every PR must ship its journal entry. The guard
`scripts/check_journal_entry.py` runs `git diff --name-only <base>...<head>` and
fails when the diff touches a **guarded path** and changes nothing under
`docs/journal/`. Guarded paths are:

- `submission/`
- `docs/`
- `scripts/host-trial/`
- `src/kaggle_gemma_agent/harness_runs.py`
- `src/kaggle_gemma_agent/run_report.py`

Run it locally:

```sh
uv run python scripts/check_journal_entry.py --base origin/main --head HEAD
```

The GitHub Actions `journal` job runs it for pull requests only, passing the PR
title and body through environment variables.

### Escape hatch: `[no-journal]`

If the PR title or body contains the token `[no-journal]`, the guard exits 0 and
prints a warning. The escape is not free: it must be justified in the PR body.
Legitimate uses are mechanical changes that carry no decision and no new
evidence: reverting a breakage with a plain `git revert`, a pure typo or link
fix, or a bot commit. It is **not** legitimate for a change that alters agent
behaviour, submission content, prompts, skills or harness runs; those always get
an entry.

## Adding a new actor or type

The enums above are closed. To add a `type` or `actor`, change the schema in
`src/kaggle_gemma_agent/journal.py`, update this document, and record the change
with a `decision` entry. Do not bypass the enum with a free string.
