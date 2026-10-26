---
Date: 2026-10-26
Genre: living reference
Status: current
Scope: The protocol a harness change follows: two proposal dimensions, evidence citation, the KEEP_BASE outcome, one retry on rejection, the score-free brief, and the composition step. It contains no proposal itself and changes no harness file.
Source of truth: runs/20261009T122847Z/, docs/proposals/20261006-prompt-hardening.md, odd/tasks/88-delivery-record.md, harness2 core/prompts.py and core/spec.py upstream (read 2026-10-26)
Limits: A rule set, not an experiment: no attribution is claimed for any edit it later governs.
---

# Harness improvement protocol

A harness change is argued from one archived moment, along one dimension, and
ends in one of two outcomes. Before this protocol the argument lived in one
blended document, `docs/proposals/20261006-prompt-hardening.md`
(`Status: implemented in PR #74`), which mixed procedure fixes with domain
fixes and had no way to record "leave it alone", so every review produced edits
and a rejected proposal had nowhere to go.

Run `20261009T122847Z` shows the two kinds in the same 13-task `psf/requests`
batch: `requests_6644` patched one layer while the graded assertion exercised
another, and `requests_7315` spent 22 tool calls over 445.63 s and ended without
`submit_patch`. Those are different defects with different owners, and the
always-on surface that would have to carry a blended fix
(`submission/prompts/system.md`, the `v3` variant, 5 364 characters) is paid on
every turn.

## Dimensions

**R1.** A harness change is proposed along exactly one of two independent
dimensions, and merged by a third.

| Token | Owns | Never owns |
|---|---|---|
| `INV` | procedure: tool choice and order, budget use, turn structure, loop exit, and completion (`submit_patch`) | which layer a fix belongs to |
| `DOM` | the work's understanding: which layer owns a behaviour, how a failing test is read, what a correct fix looks like, how a module/file divergence is resolved | procedure changes, tool policy |
| `COMPOSE` | the merge of the two proposals (rule R6) | either dimension on its own |

Rules:

- One proposal addresses exactly one dimension. A proposal that mixes them is
  split before review.
- A proposal declares its dimension on the **first body line after the header
  block**, as a bare line `Dimension: INV` | `Dimension: DOM` |
  `Dimension: COMPOSE`. It is body text on purpose: the six-field header rule in
  `docs/README.md` stays intact, with no seventh field.
- `INV` and `DOM` for one change are proposed independently and reviewed
  independently.

## Evidence rule

**R2.** Every edit names one citable moment as `(task id, artifact path,
verbatim quote or line range)`.

Allowed artifacts, and nothing else:

- `runs/<run-id>/<task-id>/session.log`
- `runs/<run-id>/<task-id>/trace.json`
- `runs/<run-id>/<task-id>/agent_patch.diff`
- `runs/<run-id>/<task-id>/test_output.log`
- fields read from `runs/<run-id>/report.json`

The quote is at most five consecutive lines, reproduced verbatim. A field read
from `report.json` is cited as `(task id, runs/<run-id>/report.json, <field>)`
with the observed value, never paraphrased.

An edit that cannot name its moment is dropped from the proposal, not weakened
into a preference: an edit without a moment is speculation.

## Outcomes

**R3.** The outcome set is closed and has exactly two members.

- `KEEP_BASE` — no edit. It is a **completed** proposal: the document records
  `Outcome: KEEP_BASE` plus the evidence that argued against an edit.
- `EDIT` — the proposal carries a concrete edit, its moment, and the
  verification the edit must pass.

There is no third outcome, no "partial", and no "investigate later". A proposal
reporting `KEEP_BASE` closes its dimension and its review.

## Retry

**R4.** Exactly one retry follows a rejection.

- The rejection is the human reviewer's; it is never self-assessed.
- The rejected proposal is **discarded whole**: nothing from it is applied
  partially, and no line of it moves into the retry unexamined.
- The retry is a new dated document under `docs/proposals/`. The rejected one
  gains `Status: superseded-by <retry path>` and is never edited.
- The retry quotes the rejection text verbatim inside a fenced block under a
  `## Rejection` heading, and states for each quoted point what changed.
- A second rejection closes the dimension as `KEEP_BASE`. There is no third
  attempt.

## Brief template

**R5.** Fill every slot. The brief describes only the work: the moment, the
observed behaviour, the change, and the check that must pass afterwards.

```text
Moment:    <task id, artifact path, verbatim quote or line range>
Observed:  <what the artifacts show, in one sentence>
Change:    <the exact edit, stated so a reviewer can apply it>
Check:     <the command or observation that must pass after the edit>
```

The block above and the sentences in this section are **the enforced zone**. The
zone carries no measurement vocabulary: none of the terms that the `grep -Einw`
command recorded under its `## Brief template` verification in issue #93
matches, case-insensitively, as whole words. That command is the normative list,
and it is not repeated here: writing the terms inside the zone would put each of
them inside the scope it governs. The ban covers this section only. Outside it,
this document names run ids and counts as evidence, because the evidence rule
requires them.

## Composition

**R6.** After both dimensions are proposed, one `COMPOSE` proposal merges them.

- It names the `INV` proposal and the `DOM` proposal it merges.
- It states `kept` or `dropped` for each, with the evidence that decided.
- It produces one edit set.
- It may keep either, both, or neither. A `COMPOSE` proposal that keeps nothing
  is a valid `KEEP_BASE`.

## Worked example

Each example is an observation of its moment, not an attribution: no execution
contrast isolates a change, so no verdict from `docs/run-analysis-vocabulary.md`
applies to any row below. This document proposes nothing; the edit slots show the
shape a proposal takes when it cites these artifacts, and nothing is applied
here.

### `DOM` / `EDIT` — `requests_6644`

Moment: `(requests_6644, runs/20261009T122847Z/requests_6644/agent_patch.diff,
lines 6-10)`, with the graded assertion at lines 9-13 of
`runs/20261009T122847Z/requests_6644/test_output.log`:

```text
         # Bare domains aren't valid URLs.
         if not path:
             path = "/"
+        elif path.startswith("//"):
+            path = "/" + path.lstrip("/")
```

```text
        p = requests.Request(method="GET", url="http://127.0.0.1:10000//v:h").prepare()
>       assert "/v:h" == a.request_url(p, {})
E       AssertionError: assert '/v:h' == '//v:h'
E         
E         - //v:h
```

Observed: the delivered patch edits `PreparedRequest.prepare_url` in
`src/requests/models.py`; the failing test calls
`requests.adapters.HTTPAdapter.request_url` and still reports `'//v:h'`, so the
layer that owns the behaviour was never touched.

What an `EDIT` proposal on this moment would carry: a `DOM` rule stating that a
failing test names the module which owns the behaviour and the patch must land
there, and the check that the quoted failing test file passes afterwards.

### `INV` / `EDIT` — `requests_7315`

Moment: `(requests_7315, runs/20261009T122847Z/requests_7315/trace.json, steps
43 and 45)` — two successive agent turns naming the same divergence, each quoted
up to its first sentence with `…` marking the cut — with `tool_calls 22`,
`wall_seconds 445.63` and `patch_path None` from
`runs/20261009T122847Z/report.json`.

```text
43 agent | Okay, I'm seeing a huge discrepancy between what `inspect.getsource(HTTPAdapter.request_url)` returns and what `grep` / `sed` / `read_file` return for the same file on disk. …
45 agent | Okay, I'm seeing a huge discrepancy between what `inspect.getsource(HTTPAdapter.request_url)` returns and what `cat` / `grep` / `read_file` return from the file on disk. …
```

Observed: the same diagnosis is repeated across two turns, the session consumes
22 of 100 calls and 445.63 s of budget, and the run ends with no patch at all.

What an `EDIT` proposal on this moment would carry: a `INV` rule that spends one
call resolving which path the import loaded before diagnosing the mismatch, and
the check that the next archived run of the same task reaches `submit_patch`.

### `KEEP_BASE` — `requests_7505`

Moment: `(requests_7505,
runs/20261009T122847Z/requests_7505/test_output.log, lines 11-15)`, with
`tool_calls 56` and `wall_seconds 1023.23` from
`runs/20261009T122847Z/report.json`, the delivered patch under `src/requests/` in
`runs/20261009T122847Z/requests_7505/agent_patch.diff`, and the recorded
`patch_scope.src_only = 5` batch total in `odd/tasks/88-delivery-record.md`.

```text
      def test_no_content_length(self, httpbin, method):
file /workspace/tests/conftest.py, line 34
  @pytest.fixture
  def httpbin(httpbin):
E       recursive dependency involving fixture 'httpbin' detected
```

Observed: the patch this task delivered is source-only and in scope, and the
archived log is dominated by 197 setup errors from a recursively defined
`httpbin` fixture, not by the graded assertion. The per-task scope is derived by
`run_report._delivery_record` from the patch paths, because `report.json` does not
carry it. One delivery count is not a resolution count: the batch total is five
source-only deliverables out of thirteen tasks, not five solved tasks.

What argues against an edit: the task's artifacts contain no moment for either
dimension that the two moments above do not already cover, and a sandbox fixture
error cannot be attributed to the harness without an execution contrast. A third
edit drawn from this task would be speculation under R2, so the proposal records
`Outcome: KEEP_BASE` with this evidence and closes.
