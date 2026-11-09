# training/artifacts

Training outputs that are never committed. The directory is git-ignored; this
README is the only tracked file.

| Directory | Holds |
|-----------|-------|
| `checkpoints/` | Optimizer and scheduler state for resumable runs. |
| `adapters/` | LoRA adapters produced by a run, before packaging. |
| `models/` | Explicit exports; the packed submission stays under `submission/`. |
| `reports/` | Environment, dataset, training and evaluation reports. |

Every artifact carries its experiment id, base-model revision and dataset
manifest hash; a run never overwrites a previous successful checkpoint.
