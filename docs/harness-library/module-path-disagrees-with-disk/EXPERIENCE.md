---
Date: 2026-10-26
Genre: experience library
Status: current
Scope: Covers a diagnosis where the module the interpreter loaded disagrees with the file on disk; does not cover environment or fixture failures, which produce errors without a patch to repair.
Source of truth: runs/20261009T122847Z/requests_7315/, runs/20261009T122847Z/report.json, runs/20261009T122847Z/manifest.json (read 2026-10-26)
Limits: No execution contrast and no independent repeat: one task, two effects in the same run, so the repeated diagnosis and the missing delivery are not separable.
---

# module-path-disagrees-with-disk

## Cue

The module the interpreter loaded disagrees with the file on disk: introspection reports one body and a file read reports another.

## Lesson

Before diagnosing the code, resolve which path the import loaded and confirm you are editing that path; then re-run the failing test against that path.

## Evidence

`runs/20261009T122847Z/requests_7315/trace.json` steps 43 and 45 (two successive agent turns naming the discrepancy between `inspect.getsource(HTTPAdapter.request_url)` and `grep`/`sed`/`cat`), plus `runs/20261009T122847Z/requests_7315/agent_patch.diff` (absent: no patch delivered) and `runs/20261009T122847Z/report.json` (`requests_7315` | `tool_calls 22` | `wall_s 445.63` | `patch_path None`). Verdict: `confounded` — the same run also ended without `submit_patch`, so the repeat and the missing delivery are not separable.

## Confidence

`medium` — one artifact, two effects in the same run, no isolation.

## Harness

```text
run: 20261009T122847Z
prompt: 960ec773f9b1394f3238e8ad2827e86f05aed3e8c57dde392a0cf523129af8ee
skills: none (manifest predates the skills hash)
repo_commit: 337b85773f47a203a903086ab43d104eb5ed3ef9-dirty
```

The run id is the manifest's `created_at` value and the run directory name; the
manifest carries no separate `run` field.
