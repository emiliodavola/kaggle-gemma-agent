SPECIFICATION: GEMMA 4 E4B AUTONOMOUS PYTHON CODING AGENT

Document ID: G4-PY-AGENT-001
Version: 1.0.0
Status: Implementation Specification
Target Model: google/gemma-4-E4B-it
Target Language: Python
Training Strategy: QLoRA / LoRA + Supervised Fine-Tuning + DPO
Execution Environment: Linux / NVIDIA GPU
Primary Objective: Build a reproducible training pipeline and a functional autonomous Python software engineering agent.

1. MISSION AND OBJECTIVE

The implementing AI agent MUST build a complete, reproducible system that transforms the pretrained Gemma 4 E4B IT model into an autonomous Python software engineering agent.

The resulting agent MUST be capable of:

Receiving software engineering tasks expressed in natural language.
Inspecting existing Python repositories.
Understanding project structure and dependencies.
Searching and reading source files.
Identifying bugs and their causes.
Creating and modifying files.
Applying code patches.
Executing terminal commands through controlled tools.
Running automated tests.
Interpreting test failures.
Iteratively correcting implementation errors.
Verifying that changes solve the requested problem.
Producing a final report containing actual execution results.

The system MUST NOT be considered complete merely because the model can generate syntactically correct Python code.

The primary success criterion is the ability to solve real software engineering tasks through tool interaction and execution feedback.

1.1. Fundamental engineering principles

The implementation MUST follow these principles:

Reproducibility over convenience.
Verified execution over generated claims.
Explicit contracts over implicit assumptions.
Dataset quality over dataset quantity.
Tool-use competence over isolated code generation.
Evaluation over subjective judgments.
Failure transparency over fabricated success.
Deterministic preprocessing wherever possible.
Versioned datasets, configurations and model artifacts.

The implementing agent MUST NOT silently invent missing dataset fields, model capabilities, API compatibility or benchmark results.

When an assumption cannot be verified, it MUST be documented as an unresolved dependency.

2. HARDWARE AND ENVIRONMENT
2.1. Target hardware

The initial supported hardware range is:

NVIDIA GPU with 24 GB VRAM.
NVIDIA GPU with 48 GB VRAM.

The implementation MUST detect the actual hardware and adapt batch size and sequence length without changing the semantic training configuration.

The system MUST NOT assume a specific GPU model.

2.2. Required software

Target operating system:

Ubuntu Linux.

Required components:

Python 3.11 or a verified compatible version.
PyTorch.
CUDA-compatible NVIDIA drivers.
Hugging Face Transformers.
Hugging Face Datasets.
TRL.
PEFT.
Accelerate.
BitsAndBytes, when compatible with the selected GPU and CUDA environment.
Safetensors.
Pytest.
Docker.

The implementation MUST pin dependency versions in a lockfile.

The implementing agent MUST verify that the installed versions support the selected Gemma 4 architecture before executing training.

It MUST NOT assume that generic Gemma 3 training examples work unchanged with Gemma 4.

2.3. Hardware validation

Before any dataset download or training operation, implement a hardware validation script.

It MUST report:

GPU model.
Total VRAM.
Available VRAM.
CUDA version.
PyTorch version.
Compute capability.
BF16 support.
Quantization backend availability.
Estimated available training memory.

If the environment is incompatible, the pipeline MUST stop with an explicit error.

3. PROJECT STRUCTURE

The repository MUST use the following structure:

text
gemma4-python-agent/
│
├── README.md
├── SPECIFICATION.md
├── pyproject.toml
├── requirements.lock
├── .env.example
├── .gitignore
│
├── configs/
│   ├── base.yaml
│   ├── dataset.yaml
│   ├── qlora.yaml
│   ├── sft.yaml
│   ├── dpo.yaml
│   ├── evaluation.yaml
│   └── runtime.yaml
│
├── data/
│   ├── raw/
│   ├── intermediate/
│   ├── processed/
│   ├── preferences/
│   └── manifests/
│
├── scripts/
│   ├── validate_environment.py
│   ├── inspect_model.py
│   ├── download_datasets.py
│   ├── inspect_datasets.py
│   ├── filter_datasets.py
│   ├── normalize_trajectories.py
│   ├── deduplicate.py
│   ├── validate_dataset.py
│   ├── create_splits.py
│   ├── train_sft.py
│   ├── generate_preferences.py
│   ├── train_dpo.py
│   ├── evaluate.py
│   └── export_model.py
│
├── src/
│   ├── data/
│   │   ├── loaders.py
│   │   ├── filters.py
│   │   ├── normalizers.py
│   │   ├── deduplication.py
│   │   ├── validators.py
│   │   └── templates.py
│   │
│   ├── training/
│   │   ├── model_loader.py
│   │   ├── quantization.py
│   │   ├── lora.py
│   │   ├── sft.py
│   │   ├── dpo.py
│   │   └── checkpoints.py
│   │
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── context.py
│   │   ├── tool_registry.py
│   │   ├── tool_executor.py
│   │   ├── conversation.py
│   │   └── policies.py
│   │
│   ├── tools/
│   │   ├── terminal.py
│   │   ├── filesystem.py
│   │   ├── search_code.py
│   │   ├── apply_patch.py
│   │   ├── run_tests.py
│   │   └── git.py
│   │
│   ├── evaluation/
│   │   ├── metrics.py
│   │   ├── swebench.py
│   │   ├── functional.py
│   │   ├── tool_use.py
│   │   └── reports.py
│   │
│   └── utils/
│       ├── logging.py
│       ├── hashing.py
│       ├── configuration.py
│       └── reproducibility.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── dataset/
│   ├── training/
│   └── runtime/
│
├── artifacts/
│   ├── checkpoints/
│   ├── adapters/
│   ├── models/
│   └── reports/
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yaml


All modules MUST have explicit responsibilities.

No critical training or data-processing logic may exist exclusively inside notebooks.

4. BASE MODEL

The initial model MUST be:

google/gemma-4-E4B-it

The model loader MUST:

Download or load the exact model revision.
Record its Hugging Face revision identifier.
Inspect the architecture.
Identify supported attention and MLP projection modules.
Inspect the tokenizer.
Inspect the native chat template.
Verify tool-calling support.
Verify PEFT compatibility.
Verify quantization compatibility.
Record the model configuration.

The implementation MUST NOT assume that module names from other Gemma generations are valid.

The implementation MUST discover actual module names before constructing the LoRA configuration.

All training examples MUST use the model's actual native conversation format.

The model MUST NOT be silently replaced with another Gemma variant.

5. DATASET SOURCES

The pipeline MUST support the following Hugging Face datasets.

5.1. Primary dataset: Open-SWE-Traces

Repository:

https://huggingface.co/datasets/nvidia/Open-SWE-Traces

Purpose:

Tool-use learning.
Repository inspection.
Terminal interaction.
Multi-step software engineering.
Bug resolution.
Code modifications.
Long-horizon agent behavior.

The implementation MUST inspect the actual dataset revision and available columns before filtering.

It MUST NOT assume that all versions have identical schemas.

Required processing:

Inspect available configurations and splits.
Inspect all relevant columns.
Identify programming language metadata.
Identify task resolution metadata.
Identify conversation trajectories.
Identify tool calls and tool responses.
Identify patch and repository metadata.
Record missing or malformed records.
Extract Python examples.
Preserve original source identifiers.

Target contribution: 30,000 accepted examples.

This is a target, not a guaranteed available quantity.

5.2. Secondary dataset: SWE-Hero

Repository:

https://huggingface.co/datasets/nvidia/SWE-Hero-openhands-trajectories

Purpose:

Repository-level reasoning.
Issue resolution.
Tool execution.
Multi-file modifications.
Test-driven debugging.

Target contribution: 10,000 accepted examples.

The pipeline MUST inspect the dataset license and associated repository licensing conditions.

5.3. Supplementary dataset: SWE-ZERO

Repository:

https://huggingface.co/datasets/nvidia/SWE-Zero-openhands-trajectories

Purpose:

Additional task diversity.
Software engineering reasoning.
Repository navigation.
Code modification trajectories.

Target contribution: 5,000 accepted examples.

Examples MUST be identified as synthetic or generated where applicable.

They MUST NOT be treated as verified execution trajectories without actual execution evidence.

5.4. Custom synthetic dataset

Target contribution: 5,000 accepted examples.

The system MUST generate controlled Python software engineering tasks.

Required categories:

Bug fixing.
Feature implementation.
Refactoring.
Unit test creation.
Dependency management.
Type checking.
API changes.
Exception handling.
Performance improvements.
Code navigation.
Multi-file changes.
Test failure recovery.

Every synthetic task MUST have:

A unique task ID.
A description.
An initial repository state.
An expected outcome.
A test suite.
A verification procedure.
An execution result.
A provenance record.

Synthetic examples MUST NOT be included as successful trajectories unless their expected outcome is independently verified.

6. DATASET SELECTION AND QUALITY CONTROL
6.1. Target distribution

The initial target dataset is 50,000 accepted trajectories.

Source	Target count	Percentage
Open-SWE-Traces	30,000	60%
SWE-Hero	10,000	20%
SWE-ZERO	5,000	10%
Custom verified tasks	5,000	10%
TOTAL	50,000	100%

These are target counts.

If the required number of valid Python examples cannot be obtained, the pipeline MUST:

Report the actual available count.
Report the reason for the shortfall.
Preserve the source distribution.
Avoid duplicating examples to artificially reach the target.
Stop before training if the minimum quality requirements are not met.

The initial minimum acceptable dataset size is 20,000 unique, valid trajectories.

6.2. Filtering rules

Each dataset MUST be filtered according to the following rules.

Required:

Programming language is Python, when language metadata is available.
Conversation is structurally valid.
Assistant tool calls are parseable.
Tool responses are associated with valid calls.
Task has a meaningful software engineering objective.
Source provenance is available.

For the primary SFT dataset:

Prefer tasks marked resolved.
Prefer tasks with successful test execution.
Prefer complete trajectories.
Prefer trajectories containing actual tool interactions.

The system MUST distinguish:

Verified successful.
Declared successful but unverified.
Failed.
Incomplete.
Unknown.

These categories MUST remain explicit in metadata.

Only verified successful examples SHOULD form the primary SFT dataset.

Unverified examples MAY be included in a separate experiment, with their inclusion documented.

Failed examples MUST NOT be presented as successful demonstrations.

6.3. Deduplication

Deduplication MUST operate at multiple levels:

Exact conversation hash.
Normalized conversation hash.
Task description hash.
Repository and issue identifier.
Patch hash.
Repository-level train/validation/test leakage detection.

The implementation MUST preserve a mapping from each processed record to its original dataset and record ID.

6.4. Licensing

Before downloading and using any dataset:

Inspect its published license.
Inspect source repository licensing where applicable.
Record attribution requirements.
Record redistribution restrictions.
Record any usage limitations.
Produce a machine-readable license manifest.

If a source cannot be used under the intended project conditions, exclude it.

Do not assume that a dataset's license automatically grants redistribution rights over all referenced source repositories.

7. CANONICAL DATA FORMAT

All datasets MUST be converted into one canonical intermediate schema.

Each record MUST contain:

json
{
  "id": "unique-record-id",
  "source": "dataset-name",
  "source_revision": "dataset-revision",
  "source_record_id": "original-id",
  "language": "python",
  "repository": "repository-identifier",
  "task_description": "task description",
  "resolved": true,
  "verification_status": "verified",
  "messages": [],
  "tool_names": [],
  "patch": null,
  "test_results": {},
  "license": "license-identifier",
  "metadata": {}
}


The schema MUST be versioned.

7.1. Message structure

Messages MUST preserve the semantic distinction between:

System messages.
User messages.
Assistant messages.
Assistant tool calls.
Tool responses.

Do not convert tool calls into plain text.

Do not merge tool outputs into assistant messages.

Do not fabricate missing tool results.

7.2. Tool-call normalization

The normalized tool interface MUST use the following tools:

terminal

Arguments:

json
{
  "command": "string",
  "working_directory": "string"
}

read_file

Arguments:

json
{
  "path": "string"
}

write_file

Arguments:

json
{
  "path": "string",
  "content": "string"
}

search_code

Arguments:

json
{
  "query": "string",
  "path": "string"
}

apply_patch

Arguments:

json
{
  "path": "string",
  "patch": "string"
}

run_tests

Arguments:

json
{
  "command": "string",
  "working_directory": "string"
}


All tool calls MUST be validated against their respective JSON schemas.

Tool responses MUST include their actual execution results.

7.3. Native Gemma format

The final SFT examples MUST be serialized using the actual Gemma 4 chat template.

The implementation MUST:

Inspect the native tokenizer template.
Use the official Transformers integration.
Preserve tool-call boundaries.
Preserve tool names and arguments.
Preserve tool responses.
Preserve assistant turn termination.
Preserve control-flow semantics.

The implementation MUST verify round-trip serialization on representative examples.

It MUST NOT manually approximate special token IDs.

8. TRAINING DATA PARTITIONING

Dataset splitting MUST happen after deduplication.

Splits:

Training: 90%.
Validation: 5%.
Internal test: 5%.

Splitting MUST be grouped by repository identifier.

Where repository identifiers are unavailable, group by the strongest available source/task identity and document the limitation.

No repository or duplicated issue may appear across training and internal evaluation splits.

SWE-bench Verified MUST remain a separate external evaluation resource.

All split manifests MUST be saved and versioned.

9. QLoRA CONFIGURATION

Initial training strategy:

QLoRA with 4-bit NF4 quantization.

Configuration:

yaml
quantization:
  load_in_4bit: true
  quant_type: nf4
  double_quantization: true
  compute_dtype: bfloat16

lora:
  rank: 32
  alpha: 64
  dropout: 0.05
  bias: none
  task_type: CAUSAL_LM

optimizer:
  name: paged_adamw_8bit

memory:
  gradient_checkpointing: true
  max_grad_norm: 1.0


The implementation MUST validate every configuration option against the installed library versions.

9.1. LoRA target modules

Initial candidate modules:

q_proj
k_proj
v_proj
o_proj

The actual target module list MUST be discovered from the loaded model.

If the selected modules do not exist, training MUST stop.

The implementation MUST NOT silently ignore invalid targets.

A separate experiment MAY include compatible MLP projection modules.

Each experiment MUST have a distinct configuration and checkpoint.

9.2. Hardware profiles
Profile A: 24 GB VRAM

Initial settings:

QLoRA 4-bit.
Microbatch size: 1.
Gradient accumulation: 8.
Sequence length: 4096.
Gradient checkpointing: enabled.
BF16 only if supported.
Profile B: 48 GB VRAM

Initial settings:

QLoRA 4-bit or BF16 LoRA.
Microbatch size: 1.
Gradient accumulation: 8.
Sequence length: 4096 initially.
Optional 8192-token experiment after memory validation.

The pipeline MUST run a short preflight training test before full training.

If out-of-memory errors occur, it MUST apply documented memory adjustments without silently changing the model or dataset.

10. SUPERVISED FINE-TUNING

The first training stage MUST use Supervised Fine-Tuning.

Initial configuration:

yaml
sft:
  learning_rate: 0.0001
  epochs: 2

  per_device_train_batch_size: 1
  gradient_accumulation_steps: 8

  max_sequence_length: 4096

  warmup_ratio: 0.03
  scheduler: cosine

  weight_decay: 0.01
  max_grad_norm: 1.0

  precision: bf16
  gradient_checkpointing: true

  logging_steps: 10
  save_steps: 250
  save_total_limit: 3


These values are starting hyperparameters, not guaranteed optimal values.

10.1. Loss masking

The training objective MUST focus on assistant-generated behavior.

The implementation MUST correctly distinguish:

User input.
Assistant output.
Tool-call arguments generated by the assistant.
Tool output generated by the environment.

The loss MUST NOT train the assistant to imitate tool outputs as if they were assistant-generated responses.

Tool-call arguments MUST receive training loss.

Assistant responses following tool results MUST receive training loss.

The implementation MUST verify masking with token-level inspection on representative examples.

10.2. Sequence truncation

Do not blindly truncate conversations from the beginning or end.

If a trajectory exceeds the sequence limit:

Preserve complete message boundaries.
Preserve valid tool-call/result pairs.
Preserve the original task context whenever possible.
Preserve the final resolution when present.
Never leave an unmatched tool call.
Record the truncation operation.

Long trajectories MUST be handled by a dedicated segmentation strategy.

11. LONG-HORIZON TRAINING

After the first SFT experiment, create a separate long-context experiment.

Initial configuration:

yaml
long_context_sft:
  learning_rate: 0.00003
  epochs: 1
  max_sequence_length: 8192
  per_device_train_batch_size: 1
  gradient_accumulation_steps: 8
  lora_rank: 32


This experiment MUST use validated long trajectories.

The goal is to improve:

Multi-step task execution.
Context retention.
Error recovery.
Tool sequencing.
Multi-file modifications.
Test-driven iteration.

The model's native context capacity MUST NOT be confused with the sequence length used during training.

12. PREFERENCE OPTIMIZATION

After SFT evaluation, implement DPO.

Target:

5,000–10,000 preference pairs.

Each preference record MUST contain:

json
{
  "prompt": [],
  "chosen": [],
  "rejected": [],
  "task_id": "unique-task-id",
  "verification": {
    "chosen_passed": true,
    "rejected_passed": false
  }
}


Preference pairs MUST be based on actual execution evidence or explicitly documented expert judgments.

Do not fabricate negative examples.

Do not assume that a longer trajectory is necessarily better.

12.1. Preference criteria

Prefer trajectories that:

Correctly identify the root cause.
Make minimal relevant changes.
Use tools correctly.
Run appropriate tests.
Correct failures.
Avoid unrelated modifications.
Produce verifiable results.

Reject trajectories that:

Claim success without execution evidence.
Introduce regressions.
Use invalid tools.
Modify unrelated files.
Stop before completing verification.
Produce invalid patches.

DPO MUST be a separate training stage with a separate checkpoint.

12.2. GRPO

GRPO is optional and MUST NOT block the initial release.

It MAY be implemented after SFT and DPO are evaluated.

Any GRPO experiment MUST use isolated execution environments and actual test results.

Reward signals MUST be based on independently verified outcomes.

The model MUST NOT be rewarded simply for claiming that tests passed.

13. AUTONOMOUS AGENT RUNTIME

The final model MUST operate through an agent orchestrator.

13.1. Execution loop

The agent MUST implement the following state machine:

text
RECEIVE_TASK
    |
    v
ANALYZE_TASK
    |
    v
INSPECT_REPOSITORY
    |
    v
PLAN
    |
    v
SELECT_TOOL
    |
    v
EXECUTE_TOOL
    |
    v
OBSERVE_RESULT
    |
    v
UPDATE_CONTEXT
    |
    v
VERIFY
    |
    +---- Failure ----> DIAGNOSE
    |                       |
    |                       v
    |                    CORRECT
    |                       |
    +-----------------------+
    |
    +---- Success -----> FINAL_REPORT


The orchestrator MUST enforce:

Maximum iteration count.
Maximum execution time.
Maximum tool-call count.
Maximum context size.
Maximum output size.
Cancellation support.
13.2. Tool execution

All tools MUST be implemented behind a common interface.

Tool calls MUST be validated before execution.

The execution environment MUST enforce:

Workspace isolation.
Path traversal prevention.
Resource limits.
Process timeouts.
Network restrictions.
Command restrictions.
Explicit working directories.

The agent MUST NOT receive unrestricted access to the host filesystem or host credentials.

13.3. Verification

A task MUST NOT be marked successful unless its verification criteria have been met.

At minimum:

Relevant tests execute.
Test output is captured.
Exit codes are recorded.
Changes are inspected.
The final result is associated with actual evidence.

If tests cannot execute, the agent MUST report the task as unverified.

14. EVALUATION

Evaluation MUST occur before and after every major training stage.

Required benchmarks:

SWE-bench Verified.
SWE-bench Lite.
HumanEval.
MBPP.
Custom Python agent benchmark.

HumanEval and MBPP evaluate code generation.

SWE-bench evaluates repository-level software engineering.

The custom benchmark evaluates autonomous tool use.

14.1. Required metrics

Record:

Pass@1.
Resolved rate.
Test pass rate.
Tool-call validity.
Tool selection accuracy.
Recovery rate.
Regression rate.
Average tool calls per task.
Average execution time.
Token consumption.
Peak VRAM usage.

All evaluation results MUST be stored as machine-readable JSON and human-readable Markdown.

14.2. Baseline comparison

Evaluate the original Gemma 4 E4B IT before training.

Then evaluate:

Base model.
SFT model.
Long-context SFT model.
DPO model.

All models MUST use:

The same evaluation tasks.
The same tool implementations.
The same execution environment.
The same resource limits.
The same success criteria.

This is necessary to measure actual improvement.

14.3. Data leakage prevention

Evaluation tasks MUST NOT overlap with training tasks.

Repository-level overlap MUST be detected.

Public benchmark contamination MUST be documented.

Results MUST distinguish between benchmark tasks that are known to the training pipeline and tasks reserved for independent evaluation.

15. CHECKPOINT AND ARTIFACT MANAGEMENT

Every training run MUST save:

Base model identifier.
Base model revision.
Dataset version.
Dataset manifest.
Training configuration.
Dependency versions.
Random seed.
Training logs.
Validation metrics.
Adapter weights.
Optimizer state when applicable.
Checkpoint metadata.

The system MUST support resuming interrupted training.

The system MUST NOT overwrite previous successful checkpoints.

Every artifact MUST have a unique experiment identifier.

16. REPRODUCIBILITY

The pipeline MUST provide commands to reproduce every stage.

Required commands:

bash
python scripts/validate_environment.py

python scripts/inspect_model.py

python scripts/download_datasets.py

python scripts/inspect_datasets.py

python scripts/filter_datasets.py

python scripts/normalize_trajectories.py

python scripts/deduplicate.py

python scripts/validate_dataset.py

python scripts/create_splits.py

python scripts/train_sft.py

python scripts/evaluate.py

python scripts/generate_preferences.py

python scripts/train_dpo.py

python scripts/export_model.py


Every command MUST:

Have documented arguments.
Support configuration files.
Return meaningful exit codes.
Log failures.
Be safely repeatable where applicable.
Avoid destructive overwrites by default.

The complete pipeline MUST be executable without manual modification of source code between stages.

17. TESTING REQUIREMENTS

The implementing agent MUST create tests for all critical modules.

17.1. Unit tests

Required:

Dataset schema validation.
Message normalization.
Tool-call parsing.
Deduplication.
Split generation.
Loss masking.
LoRA target discovery.
Configuration validation.
Checkpoint metadata.
17.2. Integration tests

Required:

Load base model.
Load tokenizer.
Serialize tool-call conversation.
Deserialize tool-call conversation.
Load processed dataset.
Run one forward pass.
Run one training step.
Save and reload adapter.
Execute one tool call.
Run one Python test suite.
17.3. End-to-end test

The system MUST solve a controlled Python repository task.

The test MUST:

Receive a task.
Inspect the repository.
Identify the relevant source file.
Modify the code.
Execute tests.
Correct failures if necessary.
Produce a final report.
Verify the final repository state.

The test MUST execute in an isolated environment.

18. ACCEPTANCE CRITERIA

The implementation is NOT complete until all required criteria are satisfied.

Infrastructure
Environment validation works.
GPU detection works.
Model loading works.
Dependency versions are pinned.
Model architecture is inspected.
LoRA target modules are validated.
Data
All configured datasets are inspected.
Licenses are documented.
Python filtering works.
Trajectory normalization works.
Tool-call structure is preserved.
Deduplication works.
Repository-level split isolation works.
Dataset manifests are generated.
Dataset validation passes.
Training
QLoRA configuration loads successfully.
Preflight training step succeeds.
SFT training completes.
Validation metrics are generated.
Checkpoint saving works.
Checkpoint resumption works.
Adapter reload works.
DPO training works when preference data is available.
Runtime
Agent orchestrator works.
Tool registry works.
Terminal tool works in isolation.
Filesystem tools work.
Code search works.
Patch application works.
Pytest execution works.
Timeouts are enforced.
Workspace isolation is enforced.
Final reports contain execution evidence.
Evaluation
Base model benchmark is recorded.
SFT benchmark is recorded.
DPO benchmark is recorded when applicable.
Metrics are reproducible.
Evaluation leakage checks pass.
Results are documented.

A completed training run MUST NOT be represented as a successful autonomous agent until the end-to-end acceptance test passes.

19. IMPLEMENTATION PHASES

The implementing agent MUST work in the following order.

Phase 1: Environment and architecture validation

Deliverables:

Environment validator.
Model inspector.
Dependency lockfile.
Hardware report.
Architecture compatibility report.

Do not start dataset processing until this phase passes.

Phase 2: Dataset ingestion

Deliverables:

Dataset download scripts.
Dataset inspection reports.
License manifest.
Source revision manifest.
Phase 3: Dataset engineering

Deliverables:

Normalization pipeline.
Filtering pipeline.
Deduplication pipeline.
Repository-level split generator.
Dataset validation report.

Do not start training until all dataset integrity checks pass.

Phase 4: QLoRA SFT

Deliverables:

Training configuration.
Training implementation.
Preflight report.
Checkpoints.
Validation report.
Phase 5: Agent runtime

Deliverables:

Orchestrator.
Tool registry.
Tool implementations.
Docker execution environment.
End-to-end tests.
Phase 6: Evaluation

Deliverables:

Baseline benchmark.
SFT benchmark.
Regression report.
Error analysis.
Performance comparison.
Phase 7: DPO

Deliverables:

Preference dataset.
Preference validation.
DPO training implementation.
DPO checkpoint.
Comparative evaluation.
Phase 8: Final packaging

Deliverables:

Exported adapter.
Runtime configuration.
Reproduction instructions.
Final technical report.
Model card.
Known limitations.
20. IMPLEMENTING AGENT EXECUTION RULES

The implementing AI agent MUST follow these rules throughout the project.

Do not skip phases.
Do not claim that a script works without executing it.
Do not claim that training succeeded without inspecting the training logs.
Do not claim that a dataset was downloaded without verifying its files.
Do not assume dataset schemas.
Do not fabricate dataset statistics.
Do not silently replace incompatible libraries.
Do not silently change training hyperparameters.
Do not silently reduce dataset size.
Do not use evaluation data for training.
Do not treat synthetic trajectories as verified unless executed.
Do not claim a task is solved without verification evidence.
Do not leave critical functions as TODO placeholders.
Do not produce pseudocode in place of required executable modules.
Do not overwrite existing artifacts.
Do not expose credentials or secrets in logs.
Do not execute untrusted repository code outside an isolated sandbox.

If a technical incompatibility is discovered:

Stop the affected operation.
Identify the exact failure.
Record the affected component.
Propose the smallest compatible correction.
Implement the correction only after documenting it.
Add a regression test.
Resume from the last verified stage.

Every phase MUST end with a report containing:

Implemented components.
Files created or modified.
Commands executed.
Tests executed.
Actual results.
Known failures.
Remaining work.
Evidence supporting completion.
21. FINAL DELIVERABLE

The final deliverable MUST be a complete repository containing:

Dataset ingestion pipeline.
Dataset normalization pipeline.
Dataset validation pipeline.
QLoRA training pipeline.
SFT checkpoints.
DPO pipeline.
Preference dataset.
Autonomous Python agent runtime.
Tool implementations.
Isolated execution environment.
Evaluation framework.
Benchmark reports.
Reproduction documentation.
Model card.
Final acceptance report.

The final report MUST clearly distinguish:

Implemented and tested.
Implemented but not fully tested.
Not implemented.
Blocked by external dependencies.
Failed acceptance criteria.

The project MUST NOT be declared complete if any mandatory acceptance criterion remains unverified.

22. DEFINITION OF SUCCESS

The final system succeeds when Gemma 4 E4B IT, after adaptation, can autonomously receive a Python software engineering task, inspect an existing repository, reason about its structure, modify relevant files, execute tests, recover from failures and provide a final report backed by actual execution evidence.

The objective is not to build a chatbot that writes Python.

The objective is to build a reproducible, tool-using, test-driven autonomous Python software engineering agent.

END OF SPECIFICATION