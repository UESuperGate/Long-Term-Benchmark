#!/usr/bin/env python3
"""Build ArkTS ground truth and produce four-way polarity reports for tasks 08-18."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmark_tasks/extraction_catalog.json"
OBSERVER = ROOT / "scripts/run_task_semantic_observer.py"
PARITY = ROOT / "skills/migration-skill/scripts/validate_transition_parity.py"
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def task_ids() -> list[str]:
    return [str(item) for item in load(CATALOG)["acceptedTaskIds"]]


def build_arkts(project: Path, log: Path) -> tuple[bool, str]:
    command = [str(HVIGOR), "assembleHap", "--mode", "module", "-p", "product=default", "-p", "buildMode=debug", "--no-daemon"]
    env = os.environ.copy()
    env["DEVECO_SDK_HOME"] = str(OH_SDK)
    env["PATH"] = os.pathsep.join([str(HVIGOR.parent), "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin", env.get("PATH", "")])
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as output:
        completed = subprocess.run(command, cwd=project, env=env, stdout=output, stderr=subprocess.STDOUT, text=True, check=False)
    return completed.returncode == 0, " ".join(command)


def clean_arkts_outputs(project: Path) -> None:
    for relative in (".hvigor", "entry/build", "build", "oh_modules", "node_modules"):
        shutil.rmtree(project / relative, ignore_errors=True)


def observe(task_id: str, platform: str, role: str, output: Path, compile_passed: bool, compile_command: str) -> None:
    subprocess.run(
        [
            "python3", str(OBSERVER), "--task", task_id, "--platform", platform, "--role", role,
            "--compile-passed", str(compile_passed).lower(), "--compile-command", compile_command, "--output", str(output),
        ],
        cwd=ROOT,
        check=True,
    )


def semantic_counts(report: Path) -> dict[str, int]:
    rows = load(report)["semantic"]["cases"]
    counts = Counter(row["status"] for row in rows)
    return {"passed": counts["pass"], "failed": counts["fail"], "notScored": counts["not_scored"], "total": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"new_tasks_calibration_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument("--task", action="append", choices=task_ids())
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    tasks = args.task or task_ids()
    output_root = ROOT / "verification_reports" / args.run_id
    reports = output_root / "reports"
    logs = output_root / "logs"
    reports.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    summary: dict[str, Any] = {}
    valid = True

    for task_id in tasks:
        task = load(ROOT / "benchmark_tasks" / task_id / "task.json")
        contract = ROOT / "benchmark_tasks" / task_id / "transitions.json"
        parity_report = reports / f"{task_id}_parity.json"
        subprocess.run(
            ["python3", str(PARITY), "--android", str(contract), "--arkts", str(contract), "--output", str(parity_report)],
            cwd=ROOT,
            check=True,
        )
        build_results: dict[str, tuple[bool, str]] = {}
        for role, key in (("base", "basePath"), ("final", "finalPath")):
            project = ROOT / task["arkts"][key]
            if args.skip_build:
                build_results[role] = (True, "build skipped by caller")
            else:
                build_results[role] = build_arkts(project, logs / f"arkts_{task_id}_{role}.log")

        paths = {
            "androidBase": reports / f"android_{task_id}_base.json",
            "androidFinal": reports / f"android_{task_id}_final.json",
            "arktsBase": reports / f"arkts_{task_id}_base.json",
            "arktsFinal": reports / f"arkts_{task_id}_final.json",
        }
        observe(task_id, "android", "base", paths["androidBase"], True, "immutable-tag source adapter")
        observe(task_id, "android", "final", paths["androidFinal"], True, "immutable-tag source adapter")
        observe(task_id, "arkts", "base", paths["arktsBase"], *build_results["base"])
        observe(task_id, "arkts", "final", paths["arktsFinal"], *build_results["final"])
        clean_arkts_outputs(ROOT / task["arkts"]["basePath"])
        clean_arkts_outputs(ROOT / task["arkts"]["finalPath"])
        counts = {name: semantic_counts(path) for name, path in paths.items()}
        total = counts["androidFinal"]["total"]
        task_valid = (
            counts["androidBase"] == {"passed": 0, "failed": total, "notScored": 0, "total": total}
            and counts["androidFinal"] == {"passed": total, "failed": 0, "notScored": 0, "total": total}
            and counts["arktsBase"] == {"passed": 0, "failed": total, "notScored": 0, "total": total}
            and counts["arktsFinal"] == {"passed": total, "failed": 0, "notScored": 0, "total": total}
            and all(result[0] for result in build_results.values())
            and load(parity_report)["valid"]
        )
        valid = valid and task_valid
        summary[task_id] = {"valid": task_valid, "counts": counts, "build": {key: passed for key, (passed, _) in build_results.items()}, "parity": str(parity_report.relative_to(ROOT))}
        print(json.dumps({"taskId": task_id, **summary[task_id]}, ensure_ascii=False), flush=True)

    payload = {
        "schemaVersion": 1,
        "runId": args.run_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "startedAt": started_at.isoformat(),
        "durationSeconds": round(time.monotonic() - started, 3),
        "observationMode": "source_transition_conformance",
        "allPolarityValid": valid,
        "tasks": summary,
    }
    (output_root / "calibration_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
