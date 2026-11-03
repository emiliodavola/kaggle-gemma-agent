"""Run the teacher batch in resumable, quota-aware chunks.

The host-trial runner has no resume and no rate-limit handling on the eval path:
if the API provider closes its quota window mid-run, every remaining task is
recorded as a failure and the run still finishes "successfully". This driver
wraps it with the two things that makes a long batch operable:

- **Resume.** Task ids already present in any ``results/*/task_results.jsonl``
  are skipped, so a chunk that dies can be continued instead of repeated.
- **A watchdog.** When ``--max-api-failures`` consecutive tasks fail with an API
  signature (connection, rate limit, quota), the child is killed and the sandbox
  containers are removed, instead of burning the rest of the split.

Usage:
    uv run python scripts/host-trial/batch_teacher.py --subset ft-train --concurrency 4
    uv run python scripts/host-trial/batch_teacher.py --subset ft-train --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "host-trial" / "run_host_trial.py"
RESULTS = REPO / "results"

#: Substrings that identify a failure caused by the provider, not by the agent.
API_SIGNATURES = (
    "APIConnectionError",
    "RateLimitError",
    "OpenAIException",
    "429",
    "quota",
    "insufficient",
)


def read_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a line still being written
    return rows


def completed_ids(series: str) -> set[str]:
    """Ids that already have a real verdict in this batch series.

    Only directories named ``<series>*`` count, so a historical run of another
    backend cannot mark a task as done, and a row whose failure is an API error
    does not count either: that task never ran and has to be retried.
    """
    done: set[str] = set()
    for path in RESULTS.glob(f"{series}*/task_results.jsonl"):
        for row in read_rows(path):
            task_id = row.get("instance_id")
            if task_id and not is_api_failure(row):
                done.add(task_id)
    return done


def is_api_failure(row: dict) -> bool:
    error = (row.get("error") or "").lower()
    return any(signature.lower() in error for signature in API_SIGNATURES)


def trailing_api_failures(rows: list[dict]) -> int:
    count = 0
    for row in reversed(rows):
        if not is_api_failure(row):
            break
        count += 1
    return count


def cleanup_containers() -> int:
    listing = subprocess.run(
        ["docker", "ps", "--filter", "ancestor=swebench-sandbox:latest", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    ids = [line for line in listing.stdout.split() if line]
    if ids:
        subprocess.run(["docker", "rm", "-f", *ids], capture_output=True, text=True, check=False)
    return len(ids)


def kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
    else:
        subprocess.run(["pkill", "-TERM", "-P", str(pid)], capture_output=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", default="ft-train", help="subset under experiments/subsets/")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-api-failures", type=int, default=3)
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    subset_path = REPO / "experiments" / "subsets" / f"{args.subset}.json"
    split = json.loads(subset_path.read_text(encoding="utf-8"))["task_ids"]
    done = completed_ids(args.subset)
    pending = [task_id for task_id in split if task_id not in done]

    print(
        f"split {args.subset}: {len(split)} tasks | completed: {len(done & set(split))} "
        f"| pending: {len(pending)}"
    )
    if not pending:
        print("nothing to do")
        return 0
    if args.dry_run:
        print("dry run:", ",".join(pending[:5]), "..." if len(pending) > 5 else "")
        return 0

    name = f"{args.subset}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    results_dir = RESULTS / name
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "HARNESS_TRIAL_TASKS": ",".join(pending),
        "HARNESS_TRIAL_BACKEND": os.environ.get("HARNESS_TRIAL_BACKEND", "opencode"),
        "HARNESS_MODEL": os.environ.get("HARNESS_MODEL", "deepseek-v4.1-flash"),
        "HARNESS_TRIAL_LAUNCH": "none",
    }
    argv = [
        sys.executable,
        str(RUNNER),
        name,
        "--repair-sandbox-deps",
        "--concurrency",
        str(args.concurrency),
    ]
    print(f"chunk {name}: {len(pending)} tasks at concurrency {args.concurrency}")

    child = subprocess.Popen(argv, env=env)
    rows_path = results_dir / "task_results.jsonl"
    try:
        while child.poll() is None:
            time.sleep(args.poll_seconds)
            rows = read_rows(rows_path)
            streak = trailing_api_failures(rows)
            if rows:
                resolved = sum(1 for row in rows if row.get("resolved"))
                print(
                    f"  {len(rows)}/{len(pending)} done, {resolved} resolved, "
                    f"api-failure streak {streak}"
                )
            if streak >= args.max_api_failures:
                print(f"ABORT: {streak} consecutive API failures; the provider quota is closed")
                kill_tree(child.pid)
                child.wait(timeout=60)
                removed = cleanup_containers()
                print(f"removed {removed} sandbox container(s); rerun this command to resume")
                return 2
    except KeyboardInterrupt:
        print("interrupted")
        kill_tree(child.pid)
        cleanup_containers()
        return 130

    code = child.wait()
    rows = read_rows(rows_path)
    resolved = sum(1 for row in rows if row.get("resolved"))
    print(f"chunk finished with exit {code}: {resolved}/{len(rows)} resolved")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
