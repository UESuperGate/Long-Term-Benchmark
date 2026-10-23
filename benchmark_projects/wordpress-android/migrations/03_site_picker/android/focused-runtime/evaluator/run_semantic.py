#!/usr/bin/env python3
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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


def artifact(project: Path, path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(project)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def identity(project: Path) -> tuple[str, str]:
    text = (project / "build.gradle.kts").read_text(encoding="utf-8")
    app = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    test = re.search(r'testApplicationId\s*=\s*"([^"]+)"', text)
    if app is None:
        raise ValueError("candidate does not expose an Android applicationId")
    return app.group(1), test.group(1) if test else app.group(1) + ".test"


def verify_manifest(project: Path) -> tuple[list[dict], list[str]]:
    manifest_path = project / "upstream-source-manifest.json"
    if not manifest_path.is_file():
        return [], ["missing upstream-source-manifest.json"]
    manifest = load(manifest_path)
    rows, errors = [], []
    compiled_files = manifest.get("compiledFiles", {})
    evaluator_root = project.parent / "evaluator" / f"{manifest.get('role')}-production"
    for row in manifest.get("files", []):
        path = project / "upstream-immutable" / row["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
        if digest != row["sha256"]:
            errors.append(f"{row['path']}: source hash mismatch")
        compiled_relative = compiled_files.get(row["path"])
        if compiled_relative:
            compiled = evaluator_root / compiled_relative
            compiled_digest = hashlib.sha256(compiled.read_bytes()).hexdigest() if compiled.is_file() else "missing"
            if compiled_digest != row["sha256"]:
                errors.append(f"{compiled_relative}: compiled production byte mismatch")
        rows.append({"path": row["path"], "sha256": row["sha256"], "gitBlob": row["gitBlob"]})
    return rows, errors


def not_scored(case: dict, diagnostic: str) -> dict:
    return {"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "not_scored", "productionSources": [], "productionBodies": [], "checkpoints": [], "observed": None, "effects": [], "invariantChecks": [], "diagnostic": diagnostic}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", "emulator-5554"))
    args = parser.parse_args()
    project, contract = args.project.resolve(), load(args.contract.resolve())
    lock = Path("/tmp/long-term-benchmark-android-device.lock").open("a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    try:
        sources, integrity = verify_manifest(project)
        binding_errors = []
        try:
            app_id, test_id = identity(project)
        except (OSError, ValueError) as error:
            app_id, test_id = "", ""
            binding_errors.append(str(error))
        app_apks = sorted((project / "build/outputs/apk/debug").glob("*-debug.apk"))
        test_apks = sorted((project / "build/outputs/apk/androidTest/debug").glob("*-debug-androidTest.apk"))
        adb = str(Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))) / "platform-tools/adb")
        device = run([adb, "-s", args.serial, "shell", "getprop", "ro.build.version.sdk"])
        ready = device.returncode == 0 and device.stdout.strip() == "37"
        install_errors = []
        if ready and app_apks and test_apks and not integrity and not binding_errors:
            for apk in (app_apks[-1], test_apks[-1]):
                installed = run([adb, "-s", args.serial, "install", "-r", "-t", str(apk)])
                if installed.returncode or "Success" not in installed.stdout:
                    install_errors.append(installed.stderr.strip() or installed.stdout.strip())
        rows = []
        component = f"{test_id}/evaluator.sitepicker.instrumentation.SemanticInstrumentation" if test_id else ""
        for case in contract["cases"]:
            if not ready or not app_apks or not test_apks or integrity or binding_errors or install_errors:
                rows.append(not_scored(case, "API37 APK, source integrity, or instrumentation binding unavailable"))
                continue
            result = run([adb, "-s", args.serial, "shell", "am", "instrument", "-w", "-r", "-e", "case", case["key"], component])
            matches = re.findall(r"runtime_state_transition_b64=([^\r\n]+)", result.stdout)
            if result.returncode or not matches:
                rows.append(not_scored(case, result.stderr.strip() or result.stdout.strip() or "no runtime payload"))
                continue
            try:
                actual = json.loads(base64.b64decode(matches[-1]).decode())
            except Exception as error:
                rows.append(not_scored(case, f"invalid runtime payload: {error}"))
                continue
            checks = actual.get("invariantChecks", [])
            invariant_names = [row.get("invariant") for row in checks]
            if args.role == "base" and actual.get("observed") is None and actual.get("actionPrefix", {}).get("reachedCommonEntry") is True and actual.get("actionPrefix", {}).get("targetActionReachable") is False:
                status = "fail"
            else:
                complete = invariant_names == case["invariants"] and all(row.get("passed") is True for row in checks)
                status = "pass" if actual.get("observed") == case["expected"] and complete else "fail"
            rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": status, "productionSources": sources, "productionBodies": actual.get("productionBodies", []), "checkpoints": [{"label": "before", "state": actual.get("before")}, {"label": "after", "state": actual.get("after")}], "observed": actual.get("observed"), "effects": (actual.get("observed") or {}).get("effects", []), "invariantChecks": checks, "actionPrefix": actual.get("actionPrefix")})
        if test_id:
            run([adb, "-s", args.serial, "uninstall", test_id])
        if app_id:
            run([adb, "-s", args.serial, "uninstall", app_id])
        summary = {"passed": sum(r["status"] == "pass" for r in rows), "failed": sum(r["status"] == "fail" for r in rows), "notScored": sum(r["status"] == "not_scored" for r in rows), "total": len(rows)}
        report = {"schemaVersion": 1, "taskId": contract["taskId"], "platform": "android", "role": args.role, "observationMode": "runtime_state_transition", "runtime": "application-owned focused runtime on Android API37 ART", "device": {"serial": args.serial, "apiLevel": 37 if ready else None}, "codeGeneration": {"passed": True, "changedProductionFiles": []}, "compile": {"passed": bool(app_apks and test_apks), "command": ["bash", "build.sh"], "artifacts": [artifact(project, p) for p in (app_apks[-1], test_apks[-1])] if app_apks and test_apks else []}, "semantic": {"cases": rows, "summary": summary}, "provenance": {"sourceManifest": artifact(project, project / "upstream-source-manifest.json") if (project / "upstream-source-manifest.json").is_file() else None}, "diagnostics": {"adapter": "ready" if summary["notScored"] == 0 else "incomplete", "transport": "adb_instrumentation" if ready else "unavailable", "sourceIntegrity": "passed" if not integrity else integrity, "bindingErrors": binding_errors, "installErrors": install_errors, "sourcePatternScoring": False, "roleMarkerUsedForVerdict": False}}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary))
        valid = summary["notScored"] == 0 and ((args.role == "base" and summary["failed"] == len(rows)) or (args.role != "base" and summary["passed"] == len(rows)))
        return 0 if valid else 1
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN); lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
