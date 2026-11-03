---
Date: 2026-11-03
Genre: run analysis
Status: current
Scope: The 100-task teacher batch of the LoRA SFT (stage S1): what it resolved, what it cost, how the split behaved per repository, and what it means for the dataset. It does not cover training or the adapter.
Source of truth: runs/20261102T214038Z/report.json, runs/20261102T214038Z/STATUS, results/ft-train-20261102T213941Z/, experiments/subsets/ft-train.json, docs/proposals/20261101-lora-sft.md
Limits: One run, one teacher (`deepseek-v4.1-flash`), on a Windows host with a repaired sandbox. The 100 tasks are the training half of the split, so this rate is not an estimate of the hidden test set.
---

# Teacher batch, 100 tasks

Stage S1 of `docs/proposals/20261101-lora-sft.md`: run the open teacher over the
training half of the split and keep what resolves cleanly.

```bash
uv run python scripts/host-trial/batch_teacher.py --subset ft-train --concurrency 4
```

Archived as `runs/20261102T214038Z`.

## Result

| Metric | Value |
|--------|-------|
| Tasks | 100 |
| Resolved | **32 (32.0%)** |
| Tokens | **191,345,568** (~1.9 M per task) |
| Wall clock | 6 h 42 m |
| Tool calls | 5,194 of 10,000 |
| API failures | **0** |
| Length of the longest API-failure streak | 0 |

The estimate before the run was 33% and ~200 M tokens, taken from an 18-task
random sample. The batch landed on 32% and 191 M.

## Per repository

| Repository | Resolved | Total | Rate |
|------------|---------:|------:|-----:|
| `Textualize/rich` | 24 | 37 | **0.65** |
| `psf/requests` | 2 | 10 | 0.20 |
| `fastapi/fastapi` | 6 | 52 | **0.12** |

This is the finding that matters beyond the headline rate. The teacher is strong
on `rich` and weak on `fastapi`, so the dataset it produces is **not
corpus-shaped**: rich supplies three quarters of the accepted trajectories while
fastapi supplies six. An adapter trained on it will see far more rich-shaped
problems than the corpus contains.

## Failures

| Kind | Count |
|------|------:|
| `collection_error` | 28 |
| `test_failure` | 28 |
| `unknown` | 12 |
| `pass` | 32 |

Delivery scope across the 100 submissions: `src_only=95`, `scratch=4`,
`config_only=1`, `corrupted=0`. So the patch hygiene held: 95 of 100 shipped a
clean source-only diff, against 111 of 129 in the E4B baseline.

## What the driver did

`scripts/host-trial/batch_teacher.py` ran the chunk into
`results/ft-train-20261102T213941Z/` and printed progress per task. The watchdog
was armed at three consecutive API failures and never fired: the provider window
held for the whole 6 h 42 m.

Its resume path was wrong on the first attempt and was fixed before the run: it
counted every `results/*/task_results.jsonl` as completed, including the 31B run
of 2026-10-30 that already covered the corpus, and reported `completed: 100 |
pending: 0` before the batch had started. It now filters by batch series and does
not count a task whose failure was an API error, because that task never ran.

## What this gives the dataset

32 resolved tasks, of which the `src_only` filter keeps at most 31 (one resolved
task is the `config_only` submission). That is the ceiling on the dataset:
**~30 trajectories**, against the 33 the proposal assumed.

Its shape is skewed toward `rich`, and its size is small for a fine-tune. Both
facts argue for training the procedure rather than the final patch: a
decision-point sample can reuse the same trajectory many times, while a
patch-level sample spends it once.

## Next step

Build the dataset at the 10240-token window measured in
`docs/proposals/20261102-int8-embedding-table.md` and train. The evaluation is
the 29 held-out tasks; `dev-v1` is the secondary contrast.
