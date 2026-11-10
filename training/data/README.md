# training/data

Local staging for the specification's dataset stages. Contents are git-ignored;
this README is the only tracked file.

| Directory | Holds |
|-----------|-------|
| `raw/` | Unmodified source shards, one directory per dataset and revision. |
| `intermediate/` | Canonical records before filtering, still carrying provenance. |
| `processed/` | Filtered, deduplicated records ready for splitting. |
| `preferences/` | Verified `chosen`/`rejected` pairs; empty while DPO is disabled. |
| `manifests/` | Per-stage counts, hashes, licenses and source revisions. |

The layout is created on demand by the data tasks in
`odd/tasks/autonomous-e4b.md`; it never replaces `training/dataset/`, which is
the existing SFT output directory.
