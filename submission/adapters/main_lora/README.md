# main_lora

Rank-32 LoRA adapter for the competition-bound autonomous E4B track.

- Base model: `google/gemma-4-E4B-it`, revision `4ecc2ba63bcac23ba4a767fc87025b1450f84c9c` (training). The scorer serves `gemma-4-e4b-it-qat-w4a16-ct`, revision `6cd26aaa2357fb2bad8c51699a7558a4d1a965bb`.
- Corpus: `vishalxyzabc7527/gemma4-swe-agent-sft-harness`, revision `7b3c7d619fa3c2f5d24a33bce5b413dcc48b2680`, config `sft`; 1,197 train / 130 validation after filtering.
- Training: full-conversation SFT, 4-bit NF4, rank 32, alpha 64, 10,240 tokens, manual per-layer checkpointing, int8 embedding table, chunked masked loss; 140 optimizer steps, final logged loss 0.52.
- Preflight: 10.89 GiB peak, 2,827.8 MiB headroom, adapter reload delta 0.0018.
- Size: 279,129,344 bytes; well under the 3 GiB budget.
- The binary is a build artifact. It is uploaded with the Kaggle code dataset and is not committed to git.
- Parity risk: the adapter trains on the unquantized checkpoint and is scored on the QAT one. T10 must prove it loads in vLLM `qat-w4a16`.
