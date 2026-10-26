---
Date: 2026-10-26
Genre: experience library
Status: current
Scope: The browsable index of cue-keyed lessons in `docs/harness-library/`; it lists entries and their harness identity and does not contain the lessons themselves.
Source of truth: docs/harness-library/*/EXPERIENCE.md, runs/20261009T122847Z/manifest.json (read 2026-10-26)
Limits: A hand-maintained index, not a search: retrieval is browsing this table, and no entry is discoverable except through it.
---

# Harness experience library

One row per lesson. An entry is keyed by the situation that triggers it, so it can
be found from a task that has never seen it before; the `Status` cell is the only
cell an existing row may ever change.

| Entry | Cue | Status | Confidence | Run | Harness |
|-------|-----|--------|------------|-----|---------|
| [module-path-disagrees-with-disk](module-path-disagrees-with-disk/EXPERIENCE.md) | The module the interpreter loaded disagrees with the file on disk: introspection reports one body and a file read… | current | medium | 20261009T122847Z | prompt=960ec773 skills=none commit=337b85773f47 |
