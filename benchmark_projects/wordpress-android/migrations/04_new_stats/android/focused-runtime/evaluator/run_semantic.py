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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(project: Path, path: Path) -> dict:
    return {
        "path": str(path.relative_to(project)),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def identity(project: Path) -> tuple[str, str]:
    build_file = project / "build.gradle.kts"
    if not build_file.is_file():
        raise ValueError("candidate does not expose build.gradle.kts")
    text = build_file.read_text(encoding="utf-8")
    app = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    test = re.search(r'testApplicationId\s*=\s*"([^"]+)"', text)
    if app is None:
        raise ValueError("candidate does not expose an Android applicationId")
    return app.group(1), test.group(1) if test else app.group(1) + ".test"


def verify_manifest(project: Path, evaluator: Path) -> tuple[list[dict], list[str]]:
    manifest_path = project / "upstream-source-manifest.json"
    if not manifest_path.is_file():
        return [], ["missing upstream-source-manifest.json"]
    try:
        manifest = load(manifest_path)
    except (OSError, ValueError) as error:
        return [], [f"invalid upstream-source-manifest.json: {error}"]
    role = manifest.get("role")
    if role not in ("base", "final"):
        return [], ["source manifest role is not base or final"]
    compiled_files = manifest.get("compiledFiles")
    if not isinstance(compiled_files, dict) or not compiled_files:
        return [], ["source manifest has no compiledFiles binding"]
    production_root = evaluator / f"{role}-production"
    rows: list[dict] = []
    errors: list[str] = []
    for row in manifest.get("files", []):
        relative = row.get("path")
        expected = row.get("sha256")
        immutable = project / "upstream-immutable" / str(relative)
        actual = digest(immutable) if immutable.is_file() else "missing"
        if actual != expected:
            errors.append(f"{relative}: immutable source hash mismatch")
        compiled_relative = compiled_files.get(relative)
        if compiled_relative is None:
            errors.append(f"{relative}: no compiled production binding")
        else:
            compiled = production_root / compiled_relative
            compiled_digest = digest(compiled) if compiled.is_file() else "missing"
            if compiled_digest != expected:
                errors.append(f"{compiled_relative}: compiled production byte mismatch")
        rows.append({
            "path": relative,
            "sha256": expected,
            "gitBlob": row.get("gitBlob"),
            "compiledPath": compiled_relative,
        })
    if not rows:
        errors.append("source manifest has no immutable source rows")
    return rows, errors


def not_scored(case: dict, diagnostic: str) -> dict:
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
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", "emulator-5554"))
    args = parser.parse_args()

    project = args.project.resolve()
    contract_path = args.contract.resolve()
    output = args.output.resolve()
    evaluator = Path(__file__).resolve().parent
    contract = load(contract_path)
    lock = Path("/tmp/long-term-benchmark-android-device.lock").open("a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    try:
        sources, integrity = verify_manifest(project, evaluator)
        binding_errors: list[str] = []
        try:
            app_id, test_id = identity(project)
        except (OSError, ValueError) as error:
            app_id, test_id = "", ""
            binding_errors.append(str(error))

        app_apks = sorted((project / "build/outputs/apk/debug").glob("*-debug.apk"))
        test_apks = sorted((project / "build/outputs/apk/androidTest/debug").glob("*-debug-androidTest.apk"))
        sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
        adb = str(sdk / "platform-tools/adb")
        device = run([adb, "-s", args.serial, "shell", "getprop", "ro.build.version.sdk"])
        ready = device.returncode == 0 and device.stdout.strip() == "37"
        install_errors: list[str] = []
        prerequisites = ready and bool(app_apks) and bool(test_apks) and not integrity and not binding_errors
        if prerequisites:
            for apk in (app_apks[-1], test_apks[-1]):
                installed = run([adb, "-s", args.serial, "install", "-r", "-t", str(apk)])
                if installed.returncode or "Success" not in installed.stdout:
                    install_errors.append(installed.stderr.strip() or installed.stdout.strip())

        rows = []
        component = (
            f"{test_id}/evaluator.newstats.instrumentation.SemanticInstrumentation"
            if test_id else ""
        )
        unavailable = "API37 APK, source integrity, or instrumentation binding unavailable"
        for case in contract["cases"]:
            if not prerequisites or install_errors:
                rows.append(not_scored(case, unavailable))
                continue
            result = run([
                adb, "-s", args.serial, "shell", "am", "instrument", "-w", "-r",
                "-e", "case", case["key"], component,
            ])
            matches = re.findall(r"runtime_state_transition_b64=([^\r\n]+)", result.stdout)
            if result.returncode or not matches:
                diagnostic = result.stderr.strip() or result.stdout.strip() or "no runtime payload"
                rows.append(not_scored(case, diagnostic))
                continue
            try:
                actual = json.loads(base64.b64decode(matches[-1]).decode("utf-8"))
            except Exception as error:
                rows.append(not_scored(case, f"invalid runtime payload: {error}"))
                continue

            checks = actual.get("invariantChecks", [])
            invariant_names = [check.get("invariant") for check in checks]
            prefix = actual.get("actionPrefix", {})
            if (
                args.role == "base"
                and actual.get("observed") is None
                and prefix.get("reachedCommonEntry") is True
                and prefix.get("targetActionReachable") is False
            ):
                status = "fail"
            else:
                complete = (
                    invariant_names == case["invariants"]
                    and all(check.get("passed") is True for check in checks)
                )
                status = "pass" if actual.get("observed") == case["expected"] and complete else "fail"
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
                "actionPrefix": prefix or None,
            })

        if test_id:
            run([adb, "-s", args.serial, "uninstall", test_id])
        if app_id:
            run([adb, "-s", args.serial, "uninstall", app_id])

        summary = {
            "passed": sum(row["status"] == "pass" for row in rows),
            "failed": sum(row["status"] == "fail" for row in rows),
            "notScored": sum(row["status"] == "not_scored" for row in rows),
            "total": len(rows),
        }
        compile_passed = bool(app_apks and test_apks) and not integrity and not binding_errors
        report = {
            "schemaVersion": 1,
            "taskId": contract["taskId"],
            "platform": "android",
            "role": args.role,
            "observationMode": "runtime_state_transition",
            "runtime": "application-owned focused runtime on Android API37 ART",
            "device": {"serial": args.serial, "apiLevel": 37 if ready else None},
            "codeGeneration": {"passed": True, "changedProductionFiles": []},
            "compile": {
                "passed": compile_passed,
                "command": ["bash", "build.sh"],
                "artifacts": [artifact(project, path) for path in (app_apks[-1], test_apks[-1])]
                if app_apks and test_apks else [],
            },
            "semantic": {"cases": rows, "summary": summary},
            "provenance": {
                "contractSha256": digest(contract_path),
                "sourceManifest": artifact(project, project / "upstream-source-manifest.json")
                if (project / "upstream-source-manifest.json").is_file() else None,
            },
            "diagnostics": {
                "adapter": "ready" if summary["notScored"] == 0 else "incomplete",
                "transport": "adb_instrumentation" if ready else "unavailable",
                "sourceIntegrity": "passed" if not integrity else integrity,
                "bindingErrors": binding_errors,
                "installErrors": install_errors,
                "sourcePatternScoring": False,
                "roleMarkerUsedForVerdict": False,
                "arbitraryCandidateDirectory": True,
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary))
        valid = summary["notScored"] == 0 and (
            (args.role == "base" and summary["failed"] == len(rows))
            or (args.role != "base" and summary["passed"] == len(rows))
        )
        return 0 if valid else 1
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
