---
name: python-testing-patterns
description: "Trigger: write or read pytest tests, or reproduce a bug offline. Use the pytest, fixture, and unittest.mock pattern table."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation Contract
Load when writing or reading pytest tests, or when a scratch reproduction is needed.

## Hard Rules
- Use stdlib `unittest.mock` and pytest built-ins only; no installs.
- Tests must be deterministic: no network, no sleeping, no wall-clock coupling.
- Scratch tests live in `/tmp`; never touch task tests or protected files (see `patch-hygiene`).

## Decision Gates
| Need | Pattern |
|---|---|
| isolate a dependency | `unittest.mock.patch` / `MagicMock` |
| shared setup | pytest `fixture` (function scope) |
| expected error | `pytest.raises` |
| parameterised cases | `@pytest.mark.parametrize` |
| filesystem output | `tmp_path` fixture |

## Execution Steps
1. `read_file` the failing test to learn the repo's assertion style.
2. Reproduce in a `/tmp` scratch test importing the library symbol directly.
3. Mock only the true boundary (I/O, clock, randomness), not internal helpers.
4. `run_command python -m pytest /tmp/scratch_test.py -q` to confirm the cause.
5. Translate the fix into library code, never into the test.

## Output Contract
Return the scratch test path and output plus the confirmed cause. Hand off to `systematic-debugging` or `test-driven-development`.
