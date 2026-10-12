#!/usr/bin/env python3
"""Calibrate evaluator-owned probes against official Android base/final tags."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_android_external_observer.py"
DEFAULT_MANIFEST = ROOT / "state_tests" / "android_observer" / "probes.json"
DEFAULT_REPO = ROOT / "_sources" / "element-x-android"


def run_one(repo: Path, task_id: str, task: dict, role: str, timeout: int) -> dict:
    tag = task["baseTag"] if role == "base" else task["finalTag"]
    with tempfile.TemporaryDirectory(prefix=f"qingyu-calibrate-{task_id}-{role}-") as raw:
        root = Path(raw)
        worktree = root / "worktree"
        candidates = root / "candidates"
        candidates.mkdir()
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), tag],
            cwd=repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            check=False,
        )
        if add.returncode:
            return {"taskId": task_id, "role": role, "tag": tag, "status": "worktree_failed", "output": add.stdout[-4000:]}
        try:
            (candidates / task["candidateDir"]).symlink_to(worktree, target_is_directory=True)
            output = root / "observer.json"
            command = [
                "python3", str(RUNNER),
                "--candidate-root", str(candidates),
                "--task", task_id,
                "--output", str(output),
                "--timeout", str(timeout),
            ]
            completed = subprocess.run(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                check=False,
            )
            if not output.is_file():
                return {
                    "taskId": task_id,
                    "role": role,
                    "tag": tag,
                    "status": "runner_failed",
                    "exitCode": completed.returncode,
                    "output": completed.stdout[-8000:],
                }
            report = json.loads(output.read_text(encoding="utf-8"))
            counts = report["counts"]
            total = counts["total"]
            polarity_valid = (
                counts["not_scored"] == 0
                and ((role == "base" and counts["passed"] == 0 and counts["failed"] == total)
                     or (role == "groundtruth_final" and counts["passed"] == total and counts["failed"] == 0))
            )
            return {
                "taskId": task_id,
                "role": role,
                "tag": tag,
                "status": "complete",
                "polarityValid": polarity_valid,
                "counts": counts,
                "probes": [
                    {
                        "module": probe["module"],
                        "className": probe["className"],
                        "exitCode": probe["exitCode"],
                        "adapterFailure": probe["adapterFailure"],
                        "durationSeconds": probe["durationSeconds"],
                        "outputTail": probe["outputTail"] if probe["exitCode"] else "",
                    }
                    for probe in report["probes"]
                ],
            }
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            shutil.rmtree(worktree, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--output", type=Path, default=ROOT / "verification_reports" / "android_external_observer_calibration.json")
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--role", choices=("base", "groundtruth_final", "both"), default="both")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task_filter = set(args.task)
    roles = ("base", "groundtruth_final") if args.role == "both" else (args.role,)
    rows = []
    for task_id, task in manifest["tasks"].items():
        if task_filter and task_id not in task_filter:
            continue
        for role in roles:
            row = run_one(args.source_repo, task_id, task, role, args.timeout)
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)

    report = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "observerOwner": "evaluator",
        "rows": rows,
        "allPolarityValid": bool(rows) and all(row.get("polarityValid", False) for row in rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["allPolarityValid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
