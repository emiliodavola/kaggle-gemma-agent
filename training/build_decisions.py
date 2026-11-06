"""Build decision-point samples from the archived teacher trajectories.

Each sample is a full conversation ending in the assistant's next action, so the
trainer can mask the loss to the final turn:

    system + problem + [thought, tool call, tool result] * k + target action

Three sources are joined, because no single artifact has both sides of a turn:

* ``trace.json``  -- structured ``tool_calls`` (name and arguments), no results
* ``session.log`` -- the results, but arguments are truncated for file tools
* the repository  -- the shipped system prompt and the problem statements

The two trajectory artifacts agree on the number of tool calls in 91 of 100
tasks. The other nine are dropped: a misaligned pair teaches "this result belongs
to this action" when it does not, and a poisoned sample is worse than nine fewer
tasks.

Usage:
    uv run --directory training python build_decisions.py --out dataset/decisions.jsonl
"""

from __future__ import annotations

import argparse
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
RUN = REPO / "runs/20261102T214038Z"
CORPUS = REPO / "data/raw/tasks.jsonl"
SYSTEM = REPO / "submission/prompts/system.md"


def load_problems() -> dict[str, str]:
    problems: dict[str, str] = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            problems[record["instance_id"]] = record["problem_statement"].strip()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=str(RUN))
    parser.add_argument("--out", default=str(REPO / "training/dataset/decisions.jsonl"))
    parser.add_argument("--max-tokens", type=int, default=10240)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import roundtrip_format
    from smoke_qlora import DEFAULT_MODEL
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(pathlib.Path(DEFAULT_MODEL))
    system = SYSTEM.read_text(encoding="utf-8").strip()
    problems = load_problems()
    # Every prompt carries the tool declarations. They are identical across
    # samples, so one measurement is the constant every sample pays.
    tools_overhead = len(
        tokenizer(
            tokenizer.apply_chat_template(
                [{"role": "system", "content": system}],
                tools=roundtrip_format.schema(),
                tokenize=False,
                add_generation_prompt=False,
            ),
            add_special_tokens=False,
        )["input_ids"]
    ) - len(tokenizer(system, add_special_tokens=False)["input_ids"])
    print(f"tools overhead: {tools_overhead} tokens")

    run = pathlib.Path(args.run)
    records = [
        json.loads(line)
        for line in (run / "turns.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        records = records[: args.limit]

    samples: list[dict] = []
    stats = {"tasks": 0, "skipped_align": 0, "skipped_missing": 0, "oversize": 0, "points": 0}

    for record in records:
        task = record["task"]
        problem = problems.get(task)
        if problem is None:
            stats["skipped_missing"] += 1
            continue
        trace = json.loads((run / task / "trace.json").read_text(encoding="utf-8"))
        calls = [call for step in trace["steps"] for call in (step.get("tool_calls") or [])]
        log_calls = [t for t in record["turns"] if t["role"] == "assistant" and t.get("tool")]
        if len(calls) != len(log_calls):
            stats["skipped_align"] += 1
            continue

        stats["tasks"] += 1
        history: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": problem},
        ]
        pending: str | None = None
        call_index = 0

        for turn in record["turns"]:
            role = turn["role"]
            if role == "thought":
                # The thought opens the assistant turn that carries the call.
                pending = turn["text"]
                continue
            if role == "assistant" and turn.get("tool"):
                call = calls[call_index]
                call_index += 1
                target = {
                    "role": "assistant",
                    "content": pending or "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": call["function_name"],
                                "arguments": call.get("arguments") or {},
                            },
                        }
                    ],
                }
                pending = None
                text = tokenizer.apply_chat_template(
                    [*history, target], add_generation_prompt=False, tokenize=False
                )
                if len(text) > args.max_tokens * 4:
                    stats["oversize"] += 1
                else:
                    message = {
                        "task": task,
                        "messages": [*history, target],
                        "target_index": len(history),
                    }
                    tokens = len(tokenizer(text, add_special_tokens=False)["input_ids"])
                    if tokens + tools_overhead <= args.max_tokens:
                        samples.append(message)
                        stats["points"] += 1
                    else:
                        stats["oversize"] += 1
                history = [*history, target]
                continue
            if role in ("tool", "finish"):
                if history and history[-1]["role"] == "assistant" and history[-1].get("tool_calls"):
                    history = [*history, {"role": "tool", "content": turn["text"]}]
                continue

    print(f"tasks used: {stats['tasks']}")
    print(f"skipped (misaligned): {stats['skipped_align']}")
    print(f"skipped (no problem statement): {stats['skipped_missing']}")
    print(f"decision points: {stats['points']}  oversize: {stats['oversize']}")

    if args.dry_run:
        return 0

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(sample, ensure_ascii=False) for sample in samples) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(samples)} samples -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
