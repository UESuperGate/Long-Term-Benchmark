#!/usr/bin/env python3
"""Score a prepared WordPress agent candidate on Android API 37.

The preparation step injects evaluator-owned runtime sources after generation. This
scorer never inspects source text for behavior and never changes verdicts by role.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


DEVICE_LOCK = Path("/tmp/long-term-benchmark-android-device.lock")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(project: Path, path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(project)),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


def identity(project: Path) -> tuple[str, str]:
    text = (project / "build.gradle.kts").read_text(encoding="utf-8")
    app = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    test = re.search(r'testApplicationId\s*=\s*"([^"]+)"', text)
    if app is None:
        raise ValueError("candidate does not expose an Android applicationId")
    return app.group(1), test.group(1) if test else app.group(1) + ".test"


def production_sources(project: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = project / "src/main/java"
    if not root.is_dir():
        return rows
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".kt", ".java"}:
            rows.append(artifact(project, path))
    return rows


def not_scored(case: dict[str, Any], diagnostic: str) -> dict[str, Any]:
    return {
        "caseId": case["caseId"],
        "key": case["key"],
        "traceDigest": case["traceDigest"],
        "status": "not_scored",
        "productionSources": [],
        "productionBodies": [],
        "checkpoints": [],
        "observed": None,
        "effects": [],
        "invariantChecks": [],
        "diagnostic": diagnostic,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", choices=("03_site_picker", "04_new_stats"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", "emulator-5554"))
    args = parser.parse_args()

    project = args.project.resolve()
    contract_path = args.contract.resolve()
    output = args.output.resolve()
    contract = load(contract_path)
    app_apks = sorted((project / "build/outputs/apk/debug").glob("*-debug.apk"))
    test_apks = sorted((project / "build/outputs/apk/androidTest/debug").glob("*-debug-androidTest.apk"))
    sources = production_sources(project)
    binding_errors: list[str] = []
    try:
        app_id, test_id = identity(project)
    except (OSError, ValueError) as error:
        app_id, test_id = "", ""
        binding_errors.append(str(error))

    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    adb = str(sdk / "platform-tools/adb")
    lock = DEVICE_LOCK.open("a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    try:
        device = run([adb, "-s", args.serial, "shell", "getprop", "ro.build.version.sdk"])
        ready = device.returncode == 0 and device.stdout.strip() == "37"
        install_errors: list[str] = []
        prerequisites = ready and bool(app_apks) and bool(test_apks) and not binding_errors and bool(sources)
        if prerequisites:
            for apk in (app_apks[-1], test_apks[-1]):
                installed = run([adb, "-s", args.serial, "install", "-r", "-t", str(apk)])
                if installed.returncode or "Success" not in installed.stdout:
                    install_errors.append(installed.stderr.strip() or installed.stdout.strip())

        owner = "sitepicker" if args.task_id == "03_site_picker" else "newstats"
        component = f"{test_id}/evaluator.{owner}.instrumentation.SemanticInstrumentation" if test_id else ""
        rows: list[dict[str, Any]] = []
        for case in contract["cases"]:
            if not prerequisites or install_errors:
                rows.append(not_scored(case, "API37 APK, candidate source, install, or instrumentation binding unavailable"))
                continue
            result = run([
                adb, "-s", args.serial, "shell", "am", "instrument", "-w", "-r",
                "-e", "case", case["key"], component,
            ])
            matches = re.findall(r"runtime_state_transition_b64=([^\r\n]+)", result.stdout)
            if result.returncode or not matches:
                rows.append(not_scored(case, result.stderr.strip() or result.stdout.strip() or "no runtime payload"))
                continue
            try:
                actual = json.loads(base64.b64decode(matches[-1]).decode("utf-8"))
            except Exception as error:  # runtime payload is untrusted diagnostic data
                rows.append(not_scored(case, f"invalid runtime payload: {error}"))
                continue
            checks = actual.get("invariantChecks", [])
            complete = (
                [check.get("invariant") for check in checks] == case.get("invariants", [])
                and all(check.get("passed") is True for check in checks)
            )
            status = "pass" if actual.get("observed") == case.get("expected") and complete else "fail"
            rows.append({
                "caseId": case["caseId"],
                "key": case["key"],
                "traceDigest": case["traceDigest"],
                "status": status,
                "productionSources": sources,
                "productionBodies": actual.get("productionBodies", []),
                "checkpoints": [
                    {"label": "given/before", "state": actual.get("before")},
                    {"label": "event/after", "state": actual.get("after")},
                ],
                "observed": actual.get("observed"),
                "effects": (actual.get("observed") or {}).get("effects", []),
                "invariantChecks": checks,
                "actionPrefix": actual.get("actionPrefix"),
            })

        if test_id:
            run([adb, "-s", args.serial, "uninstall", test_id])
        if app_id:
            run([adb, "-s", args.serial, "uninstall", app_id])
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()

    summary = {
        "passed": sum(row["status"] == "pass" for row in rows),
        "failed": sum(row["status"] == "fail" for row in rows),
        "notScored": sum(row["status"] == "not_scored" for row in rows),
        "total": len(rows),
    }
    report = {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "platform": "android",
        "role": "agent",
        "observationMode": "runtime_state_transition",
        "runtime": "candidate production methods on Android API37 ART",
        "device": {"serial": args.serial, "apiLevel": 37 if ready else None},
        "semantic": {"cases": rows, "summary": summary},
        "provenance": {"contractSha256": digest(contract_path), "productionSources": sources},
        "diagnostics": {
            "adapter": "ready" if summary["notScored"] == 0 else "incomplete",
            "transport": "adb_instrumentation" if ready else "unavailable",
            "bindingErrors": binding_errors,
            "installErrors": install_errors,
            "sourcePatternScoring": False,
            "roleMarkerUsedForVerdict": False,
            "arbitraryCandidateDirectory": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if summary["notScored"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
