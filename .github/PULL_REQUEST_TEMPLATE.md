## Summary

<!-- One paragraph: what problem this solves and how. -->

## Changes

<!-- Per-area breakdown. Use tables for multi-file changes. -->

| Area | What changed |
|------|-------------|

## Verification

<!-- Copy-paste the actual command output, not placeholders. -->

```
$ uv run pytest tests/ -q
... NNN passed ...

$ uv run ruff check src/ tests/ scripts/
All checks passed!

$ uv run mypy src/ scripts/
Success: no issues found

$ uv run pyright
0 errors, 0 warnings
```

## Files changed

| File | Lines (+/−) | Description |
|------|------------|-------------|

## Design artifacts

<!-- Pick the option that fits this change:
- SDD: link the archive and list the updated specs, e.g.
  Archived at `openspec/changes/archive/<date>-<change>/`
  Specs updated: `openspec/specs/<domain>/spec.md`
- ODD: one-line design note or link, no archive required.
- N/A: one-line reason (e.g. docs-only).
-->

## Checklist

- [ ] `uv run pytest tests/ -q` — all passing
- [ ] `uv run ruff check src/ tests/ scripts/` — clean
- [ ] `uv run ruff format --check src/ tests/` — clean
- [ ] `uv run mypy src/ scripts/` — clean
- [ ] `uv run pyright` — clean (pyright gate, `[tool.pyright]`)
- [ ] New behaviour covered by tests
- [ ] Coverage gate met — `uv run coverage report -m` ≥ 90% (CI enforces `fail_under = 90`)
- [ ] README updated if CLI surface changed
- [ ] README_ES.md updated if a translated README section changed
- [ ] Related issues linked (`Closes #N`)
