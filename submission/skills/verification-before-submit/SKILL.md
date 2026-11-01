---
name: verification-before-submit
description: "Trigger: after a fix or before submit_patch; verify the exact change and report evidence."
license: MIT
metadata: {author: emiliodavola, version: "2.0"}
---

## Activation
Load after a fix and immediately before `submit_patch`.

## Rules
- Make no claim without command output; never call a failing or unrun check passed.
- After a relevant source change, rerun the exact reproduction or target test; repeat exploration only with new evidence or a changed hypothesis.
- Use the budget to fix and verify first. Call 40 is a checkpoint, not a stop; continue bounded work and reserve budget for verification and submission.
- At a hard budget stop, submit the best reasoned relevant patch even if checks are red or missing, and report that status truthfully. Do not submit a speculative no-op.
- A syntax or indentation error is a hard stop: the compile gate below is the only accepted proof.
- Keep scratch/junk files out of the diff; respect `patch-hygiene` for protected paths and scope.

## Steps
Run these three commands literally; do not paraphrase them.

1. Scratch gate, before anything else:
   `git status --porcelain | awk '$1=="??"{print $2}' | grep -v / | xargs -r rm -f`
   Then `git status --porcelain | grep '^??'` must list only new modules that belong under the package.
2. Compile gate, and look for `COMPILE_OK`:
   `{ git diff --name-only --diff-filter=ACM; git ls-files --others --exclude-standard; } | grep '\.py$' | xargs -r python3 -m py_compile && echo COMPILE_OK`
   No `COMPILE_OK` means a changed file does not parse: fix it and rerun. A syntax or indentation error is a hard stop.
3. Target test: run the issue's test, or the nearest test file for the changed symbol; capture the pass/fail counts.
4. Read the full diff (`git diff`), check it against the issue and the test, and confirm a repository-package hunk exists.
5. When finished or at a hard stop, call `submit_patch` once as the terminal action; it captures the current diff.

## Output
Return target-test, regression, syntax, and diff-scope check results with real outputs. At a hard stop, include every failed, missing, or unrun check.
