HARDWARE PROFILE OVERRIDE — NVIDIA RTX 3090

Specification ID: G4-PY-AGENT-001-HW3090
Target GPU: NVIDIA GeForce RTX 3090
VRAM: 24 GB
GPU Count: 1
Training Mode: Single-GPU QLoRA
Status: Mandatory Hardware Configuration

This document overrides all generic hardware configurations in the main specification.

If any parameter in the main specification conflicts with this hardware profile, this document takes precedence.

1. HARDWARE CONSTRAINTS

The implementation MUST target exactly one NVIDIA RTX 3090 with 24 GB of VRAM.

The implementation MUST NOT assume:

48 GB VRAM.
Multiple GPUs.
NVLink.
CPU offloading as a normal training strategy.
Full BF16 model fine-tuning.
Unlimited context length.

The system MUST detect the GPU before downloading the complete model or datasets.

Required validation:

bash
nvidia-smi


The environment validation script MUST confirm:

GPU name contains RTX 3090.
Total VRAM is approximately 24 GB.
CUDA is available.
PyTorch can access the GPU.
The GPU supports the selected compute dtype.
BitsAndBytes can initialize a 4-bit quantization configuration.

If the hardware does not match this profile, the pipeline MUST stop and request explicit authorization to use another profile.

2. SOFTWARE CONFIGURATION

Recommended environment:

Ubuntu 22.04 or 24.04.
Python 3.11.
NVIDIA proprietary driver compatible with the installed CUDA runtime.
PyTorch CUDA build.
Transformers with verified Gemma 4 support.
PEFT.
TRL.
Accelerate.
BitsAndBytes.
Safetensors.

The RTX 3090 uses NVIDIA Ampere architecture.

The implementation SHOULD use BF16 when the complete software stack supports it.

The implementation MUST test BF16 operations before training.

If BF16 is unavailable or unstable, use FP16 with a compatible gradient-scaling strategy.

Do not silently change precision.

3. MANDATORY QUANTIZATION CONFIGURATION

QLoRA is mandatory for the initial training.

Configuration:

yaml
quantization:
  enabled: true
  load_in_4bit: true

  bnb_4bit_quant_type: nf4
  bnb_4bit_use_double_quant: true

  bnb_4bit_compute_dtype: bfloat16

  device_map: cuda:0

  trust_remote_code: false


The implementation MUST verify that the actual Gemma 4 implementation supports this configuration.

The quantized base model MUST remain frozen.

Only trainable adapter parameters SHOULD receive gradients.

The implementation MUST verify the number of trainable parameters before training.

If the configured quantization backend is incompatible, stop and report the exact incompatibility.

Do not silently load the model in FP32 or BF16 as a fallback.

4. MANDATORY LORA CONFIGURATION

Initial configuration:

yaml
lora:
  r: 32
  lora_alpha: 64
  lora_dropout: 0.05

  bias: none
  task_type: CAUSAL_LM

  target_modules:
    - q_proj
    - k_proj
    - v_proj
    - o_proj


These are candidate projection names.

The implementation MUST inspect the actual Gemma 4 model modules.

If the names are incompatible, the training process MUST stop.

Do not silently skip modules.

The first experiment MUST use attention projections only.

MLP projection adaptation MAY be tested in a separate experiment after the first successful baseline.

5. RTX 3090 MEMORY CONFIGURATION

Mandatory initial configuration:

yaml
memory:
  per_device_train_batch_size: 1

  gradient_accumulation_steps: 8

  gradient_checkpointing: true

  max_sequence_length: 4096

  dataloader_num_workers: 2

  pin_memory: true

  optim: paged_adamw_8bit

  max_grad_norm: 1.0


The implementation MUST NOT increase microbatch size above 1 in the first training run.

The implementation MUST NOT increase sequence length above 4096 in the first training run.

The implementation MUST run a preflight test before starting the complete training process.

The preflight MUST include:

Model loading.
Tokenizer loading.
Quantization verification.
LoRA injection.
One forward pass.
One backward pass.
One optimizer step.
Peak VRAM measurement.
Adapter saving.
Adapter reload.

The preflight MUST fail if the measured peak memory leaves insufficient safety margin for the intended training workload.

Use a minimum 2 GB VRAM safety margin below the actual GPU capacity.

Do not rely exclusively on PyTorch allocated-memory measurements. Also inspect total GPU memory usage through NVIDIA monitoring tools.

6. INITIAL SFT CONFIGURATION

Mandatory first experiment:

yaml
sft:
  learning_rate: 0.0001

  num_train_epochs: 2

  per_device_train_batch_size: 1

  gradient_accumulation_steps: 8

  max_length: 4096

  warmup_ratio: 0.03

  lr_scheduler_type: cosine

  weight_decay: 0.01

  max_grad_norm: 1.0

  bf16: true
  fp16: false

  gradient_checkpointing: true

  logging_steps: 10

  save_steps: 250

  save_total_limit: 3

  optim: paged_adamw_8bit


If BF16 validation fails, the implementing agent MUST stop and request approval to use FP16.

The first successful training run MUST establish a baseline before experimenting with different ranks, learning rates or sequence lengths.

7. SEQUENCE LENGTH POLICY

The RTX 3090 training profile MUST use the following sequence-length progression:

Experiment	Maximum sequence length	Status
Initial SFT	4,096	Mandatory
Long-context SFT	8,192	Conditional
Extended context	16,384	Not part of initial release

The 8,192-token experiment MAY proceed only if:

The 4,096-token training completes.
Peak VRAM is measured.
A dedicated 8,192-token preflight succeeds.
The minimum 2 GB safety margin is maintained.

If the 8,192-token preflight fails, retain 4,096 tokens.

The implementation MUST NOT attempt 16,384-token training during the initial project.

8. BATCH SIZE AND GRADIENT ACCUMULATION

Initial configuration:

Microbatch: 1.
Gradient accumulation: 8.
Effective batch size: 8 sequences per optimizer update, assuming a single GPU and no additional distributed accumulation.

The implementation MUST distinguish between:

Microbatch size.
Gradient accumulation.
Effective batch size.
Number of optimizer updates.

Training reports MUST include all four values.

9. MEMORY MONITORING

Every training run MUST record:

GPU total memory.
GPU free memory.
GPU allocated memory.
GPU reserved memory.
Peak allocated memory.
Peak reserved memory.
GPU utilization.
Temperature.
Training throughput.

The monitoring system MUST detect CUDA out-of-memory errors.

On OOM:

Stop the current training process cleanly.
Save the last valid checkpoint if possible.
Record the failing batch and sequence length.
Record peak VRAM usage.
Generate a failure report.
Do not automatically restart with modified hyperparameters.

A new configuration requires an explicit experiment ID.

10. TRAINING EXPERIMENT ORDER

The RTX 3090 MUST follow this experiment order:

Experiment 1 — Hardware preflight
Load quantized Gemma 4.
Inject LoRA.
Execute forward and backward passes.
Save and reload adapter.

Acceptance criterion: successful execution with at least 2 GB memory headroom.

Experiment 2 — Baseline QLoRA SFT
4-bit NF4.
LoRA rank 32.
Sequence length 4096.
Microbatch 1.
Gradient accumulation 8.
Two epochs.

Acceptance criterion: completed training and valid checkpoint.

Experiment 3 — Evaluation

Evaluate the trained adapter against the base model.

Acceptance criterion: complete benchmark report with actual execution results.

Experiment 4 — Optional long-context SFT
Sequence length 8192.
Same hardware.
Dedicated preflight.

Acceptance criterion: successful preflight and completed training.

Experiment 5 — DPO

Use the SFT adapter as the starting point.

Run a separate memory preflight.

Do not assume that SFT memory requirements and DPO memory requirements are identical.

Experiment 6 — Final model export

Export the adapter and configuration.

Merge the adapter with the base model only if the selected quantization and PEFT workflow supports the operation.

Do not perform an unsupported merge directly into a quantized model.

11. RTX 3090 ACCEPTANCE CRITERIA

The hardware implementation is accepted only if:

RTX 3090 is detected correctly.
CUDA initialization succeeds.
BF16 support is verified or FP16 fallback is explicitly approved.
NF4 quantization initializes.
Gemma 4 loads successfully.
LoRA modules are correctly attached.
Trainable parameters are reported.
One forward pass succeeds.
One backward pass succeeds.
One optimizer step succeeds.
Adapter saving succeeds.
Adapter reload succeeds.
Peak VRAM is recorded.
Minimum 2 GB memory headroom is verified.
Initial SFT completes.
Checkpoints are recoverable.

No training result may be declared successful if any mandatory criterion remains unverified.

12. FINAL HARDWARE POLICY

The RTX 3090 is the only supported GPU in the initial deployment specification.

All initial training experiments MUST use:

Single GPU.
4-bit NF4 QLoRA.
LoRA rank 32.
Microbatch 1.
Gradient accumulation 8.
Sequence length 4096.
Gradient checkpointing.
Verified BF16 or explicitly approved FP16.
Paged AdamW 8-bit when supported.

The implementation MUST prioritize a stable and reproducible 4,096-token training pipeline over aggressive memory optimization or experimental context expansion.

END OF RTX 3090 HARDWARE OVERRIDE