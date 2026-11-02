"""Build the SFT dataset from the teacher runs that resolved cleanly.

Stage S2 of ``docs/proposals/20261101-lora-sft.md``.

Two facts shape the sample format:

- A training step fits 2048 tokens (measured, see ``smoke_qlora.py``) and a
  teacher trajectory sends ~17k prompt tokens per turn after a couple of tool
  calls. A whole trajectory cannot be a sample at this context.
- 48 of the E4B's 119 failures were ``AssertionError``: the patch parsed and was
  wrong. So the first sample format is the one that teaches the fix: the harness
  system prompt, the problem statement, and the reference-quality patch the
  teacher produced.

Only tasks that resolved **and** delivered a ``src_only`` patch become samples.
A task that resolved with scratch files teaches the wrong hygiene.

Usage:
    uv run --directory training python build_dataset.py \
        --run runs/20261102T004141Z/report.json:results/pilot20 \
        --run runs/20261101T213823Z/report.json:results/pilot_01
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = Path.home() / ".cache/kagglehub/models/google/gemma-4/transformers/gemma-4-e4b-it/1"


def parse_run(value: str) -> tuple[Path, Path]:
    """Split ``report.json:results-dir`` into its two paths."""
    report, _, results = value.partition(":")
    if not results:
        raise SystemExit(f"--run needs <report.json>:<results-dir>, got {value!r}")
    report_path, results_dir = Path(report), Path(results)
    # Paths are given relative to the repository root, but this script runs with
    # the training project as its working directory.
    if not report_path.is_absolute():
        report_path = REPO / report_path
    if not results_dir.is_absolute():
        results_dir = REPO / results_dir
    return report_path, results_dir


def load_corpus(tasks_file: Path) -> dict[str, dict]:
    corpus = {}
    for line in tasks_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            corpus[record["instance_id"]] = record
    return corpus


def accepted(report: dict) -> list[dict]:
    """Tasks that resolved and whose patch touched only source files."""
    out = []
    for task in report.get("tasks", []):
        delivery = task.get("delivery") or {}
        if task.get("resolved") and delivery.get("patch_scope") == "src_only":
            out.append(task)
    return out


def count_tokens(tokenizer, messages: list[dict]) -> int:
    """Tokens of the rendered conversation.

    ``apply_chat_template(..., tokenize=True)`` returns a ``BatchEncoding`` on
    this multimodal tokenizer, so ``len()`` would report the number of keys. The
    template already emits ``<bos>``, hence ``add_special_tokens=False``.
    """
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def build_sample(tokenizer, system: str, record: dict, patch: str, max_tokens: int) -> dict | None:
    """One sample, or ``None`` when it cannot be made to fit.

    The patch is never truncated: a cut diff teaches a broken fix. The hints go
    first, then the problem statement.
    """
    problem = record["problem_statement"].strip()
    hints = (record.get("hints_text") or "").strip()

    def compose(problem_text: str, hints_text: str) -> list[dict]:
        user = f"Repository: {record['repo']}\n\n{problem_text}"
        if hints_text:
            user += f"\n\nHints:\n{hints_text}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": patch},
        ]

    messages = compose(problem, hints)
    tokens = count_tokens(tokenizer, messages)
    if tokens > max_tokens and hints:
        hints = ""
        messages = compose(problem, "")
        tokens = count_tokens(tokenizer, messages)
    if tokens > max_tokens:
        excess = tokens - max_tokens
        keep = max(200, len(problem) - excess * 4)
        problem = problem[:keep]
        messages = compose(problem, "")
        tokens = count_tokens(tokenizer, messages)
    if tokens > max_tokens:
        return None

    return {
        "instance_id": record["instance_id"],
        "repo": record["repo"],
        "tokens": tokens,
        "messages": messages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, help="<report.json>:<results-dir>")
    parser.add_argument("--tasks", default=str(REPO / "data/raw/tasks.jsonl"))
    parser.add_argument("--system", default=str(REPO / "submission/prompts/system.md"))
    parser.add_argument("--out", default=str(REPO / "training/dataset/train.jsonl"))
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    system = Path(args.system).read_text(encoding="utf-8")
    corpus = load_corpus(Path(args.tasks))

    seen: set[str] = set()
    samples: list[dict] = []
    rejected: list[tuple[str, str]] = []

    for spec in args.run:
        report_path, results_dir = parse_run(spec)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for task in accepted(report):
            task_id = task["instance_id"]
            if task_id in seen:
                continue
            seen.add(task_id)
            patch_path = results_dir / "patches" / f"{task_id}.patch"
            if not patch_path.is_file():
                rejected.append((task_id, "patch file missing"))
                continue
            record = corpus.get(task_id)
            if record is None:
                rejected.append((task_id, "not in tasks.jsonl"))
                continue
            sample = build_sample(
                tokenizer, system, record, patch_path.read_text(encoding="utf-8"), args.max_tokens
            )
            if sample is None:
                rejected.append((task_id, f"over {args.max_tokens} tokens"))
                continue
            samples.append(sample)

    samples.sort(key=lambda row: row["tokens"])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")

    tokens = [sample["tokens"] for sample in samples]
    print(f"samples: {len(samples)} -> {out_path}")
    if tokens:
        print(
            f"tokens  : min {min(tokens)} | max {max(tokens)} | mean {sum(tokens) // len(tokens)}"
        )
    print(f"accepted tasks before filtering: {len(seen)}")
    if rejected:
        print("rejected:")
        for task_id, reason in sorted(rejected):
            print(f"  {task_id:<20} {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
