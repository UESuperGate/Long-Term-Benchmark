#!/usr/bin/env python3
"""Rebuild archived candidates from base plus patch and rerun semantic observers."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_new_tasks_opencode_eval_macos.py"
SPEC = importlib.util.spec_from_file_location("new_tasks_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task", action="append")
    parser.add_argument("--platform", action="append", choices=("android", "arkts"))
    parser.add_argument("--candidate-root", type=Path, default=Path("/tmp/ltb-new-tasks-rescore"))
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    run_root = ROOT / "eval_runs" / args.run_id
    manifest_path = run_root / "eval_manifest.json"
    if not manifest_path.exists():
        manifest_path = run_root / "eval_manifest.partial.json"
    manifest = load(manifest_path)
    selected_tasks = set(args.task or [])
    selected_platforms = set(args.platform or [])
    backup = run_root / "reports_raw"
    backup.mkdir(parents=True, exist_ok=True)
    results = []
    for row in manifest.get("tasks", []):
        task_id = str(row.get("taskId", ""))
        platform = str(row.get("platform", ""))
        if row.get("availability", "available") != "available":
            continue
        if selected_tasks and task_id not in selected_tasks:
            continue
        if selected_platforms and platform not in selected_platforms:
            continue
        patch = run_root / "patches" / f"{platform}_{task_id}.patch"
        report = run_root / "reports" / f"{platform}_{task_id}_agent.json"
        if not patch.exists() or not report.exists():
            raise FileNotFoundError(f"missing durable candidate artifact for {platform}/{task_id}")
        raw = backup / report.name
        if not raw.exists():
            shutil.copy2(report, raw)
        candidate = RUNNER.prepare(task_id, platform, args.candidate_root.resolve())
        subprocess.run(["git", "apply", "--binary", str(patch)], cwd=candidate, check=True)
        build_exit = int(row.get("buildExit", 1))
        build_command = load(raw)["compile"].get("command", "recovered build command")
        if args.rebuild:
            build_exit, build_command = RUNNER.build(
                platform,
                candidate,
                RUNNER.environment(platform, candidate),
                run_root / "logs" / f"{platform}_{task_id}_rebuild.log",
            )
            row["buildExit"] = build_exit
            row["compile"] = "passed" if build_exit == 0 else "failed"
            row["compileRerun"] = {
                "reason": "replace an environment-invalid prior build",
                "command": build_command,
                "passed": build_exit == 0,
            }
        RUNNER.score(
            task_id,
            platform,
            candidate,
            [str(path) for path in row.get("generatedCodeFiles", [])],
            build_exit,
            build_command,
            report,
        )
        scored = load(report)["semantic"]
        results.append({"taskId": task_id, "platform": platform, "passed": scored["passed"], "failed": scored["failed"], "total": scored["total"]})
        RUNNER.clean_candidate(candidate)
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    if args.candidate_root.exists():
        shutil.rmtree(args.candidate_root, ignore_errors=True)
    if args.rebuild:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_root / "rescore_summary.json").write_text(json.dumps({"schemaVersion": 1, "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
