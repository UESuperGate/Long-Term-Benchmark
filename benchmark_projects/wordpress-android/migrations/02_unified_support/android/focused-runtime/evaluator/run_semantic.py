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


BODY_SOURCES = {
    "list_success": ["ConversationsSupportViewModel.kt", "UnifiedSupportRepository.kt", "UnifiedConversation.kt"],
    "list_failure": ["ConversationsSupportViewModel.kt", "UnifiedSupportRepository.kt"],
    "list_retry": ["ConversationsSupportViewModel.kt", "UnifiedSupportRepository.kt"],
    "new_bot_success": ["ConversationsSupportViewModel.kt", "UnifiedSupportViewModel.kt", "UnifiedSupportRepository.kt"],
    "reply_success": ["UnifiedSupportViewModel.kt", "UnifiedSupportRepository.kt", "AttachmentStateValidator.kt", "EncryptedAppLogsUploader.kt", "TempAttachmentsUtil.kt"],
    "offline_reply": ["UnifiedSupportViewModel.kt"],
    "reply_failure": ["UnifiedSupportViewModel.kt", "UnifiedSupportRepository.kt", "TempAttachmentsUtil.kt"],
    "concurrent_guard": ["UnifiedSupportViewModel.kt", "UnifiedSupportRepository.kt"],
    "draft_lifecycle": ["ConversationsSupportViewModel.kt", "UnifiedSupportViewModel.kt", "AttachmentStateValidator.kt", "ConversationReplyFormState.kt"],
    "detail_affordances": ["UnifiedConversationDetailScreen.kt", "UnifiedConversation.kt", "ConversationStatus.kt"],
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_record(project: Path, path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(project)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def verify_sources(project: Path) -> tuple[dict[str, dict], list[str], list[str]]:
    manifest = load(project / "upstream-source-manifest.json")
    root = project / "upstream-immutable"
    indexed: dict[str, dict] = {}
    paths: list[str] = []
    errors: list[str] = []
    for row in manifest["files"]:
        path = root / row["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
        if digest != row["sha256"]:
            errors.append(f"{row['path']}: sha256 mismatch")
        indexed[Path(row["path"]).name] = {
            "path": row["path"], "sha256": row["sha256"], "gitBlob": row["gitBlob"]
        }
        paths.append(row["path"])
    return indexed, errors, paths


def command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


def with_android_device_lock(function):
    def locked() -> int:
        device_lock = Path("/tmp/long-term-benchmark-android-device.lock").open("a+")
        fcntl.flock(device_lock.fileno(), fcntl.LOCK_EX)
        try:
            return function()
        finally:
            fcntl.flock(device_lock.fileno(), fcntl.LOCK_UN)
            device_lock.close()

    return locked


def unavailable(case: dict, diagnostic: str) -> dict:
    return {
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "productionSources": [], "productionBodies": [],
        "checkpoints": [], "observed": None, "effects": [], "invariantChecks": [],
        "diagnostic": diagnostic,
    }


def agent_identity(project: Path) -> tuple[str, str]:
    build = (project / "build.gradle.kts").read_text(encoding="utf-8")
    app_match = re.search(r'applicationId\s*=\s*"([^"]+)"', build)
    test_match = re.search(r'testApplicationId\s*=\s*"([^"]+)"', build)
    if app_match is None:
        raise ValueError("agent build.gradle.kts does not declare applicationId")
    app_id = app_match.group(1)
    return app_id, test_match.group(1) if test_match else f"{app_id}.test"


def agent_production_sources(project: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(project.rglob("*.kt")):
        relative = path.relative_to(project)
        text_path = str(relative)
        if any(part in {".benchmark-evaluator", "build", ".gradle", ".kotlin"} for part in relative.parts):
            continue
        if any(part in {"test", "androidTest"} for part in relative.parts):
            continue
        if "/support/unified/" not in f"/{text_path}":
            continue
        rows.append({"path": text_path, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return rows


@with_android_device_lock
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", "emulator-5554"))
    args = parser.parse_args()
    project = args.project.resolve()
    contract = load(args.contract.resolve())
    sources, integrity_errors, source_paths = verify_sources(project)
    adb = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))) / "platform-tools/adb"
    if args.role == "agent":
        app_id, test_id = agent_identity(project)
    else:
        app_id = "org.wordpress.evaluator.support.base" if args.role == "base" else "org.wordpress.evaluator.support.v269"
        test_id = f"{app_id}.test"
    component = f"{test_id}/evaluator.support.instrumentation.SemanticInstrumentation"
    app_apks = sorted((project / "build/outputs/apk/debug").glob("*-debug.apk"))
    test_apks = sorted((project / "build/outputs/apk/androidTest/debug").glob("*-debug-androidTest.apk"))
    device = command([str(adb), "-s", args.serial, "shell", "getprop", "ro.build.version.sdk"])
    device_ready = device.returncode == 0 and device.stdout.strip() == "37"
    install_errors: list[str] = []
    if device_ready and app_apks and test_apks and not integrity_errors:
        for apk in (app_apks[-1], test_apks[-1]):
            installed = command([str(adb), "-s", args.serial, "install", "-r", "-t", str(apk)])
            if installed.returncode != 0 or "Success" not in installed.stdout:
                install_errors.append(installed.stderr.strip() or installed.stdout.strip())

    rows = []
    candidate_sources = agent_production_sources(project) if args.role == "agent" else []
    for case in contract["cases"]:
        if not device_ready or not app_apks or not test_apks or integrity_errors or install_errors:
            rows.append(unavailable(case, "API37 instrumentation APK unavailable, install failed, or source integrity failed"))
            continue
        run = command([
            str(adb), "-s", args.serial, "shell", "am", "instrument", "-w", "-r",
            "-e", "case", case["key"], component,
        ])
        matches = re.findall(r"runtime_state_transition_b64=([^\r\n]+)", run.stdout)
        if run.returncode != 0 or not matches:
            rows.append(unavailable(case, run.stderr.strip() or run.stdout.strip() or "instrumentation emitted no runtime report"))
            continue
        try:
            actual = json.loads(base64.b64decode(matches[-1]).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as error:
            rows.append(unavailable(case, f"invalid instrumentation payload: {error}"))
            continue
        effects = actual.get("observed", {}).get("effects", []) if isinstance(actual.get("observed"), dict) else []
        checks = actual.get("invariantChecks", [])
        complete = [row.get("invariant") for row in checks] == case["invariants"] and all(
            row.get("passed") is True for row in checks
        )
        status = "pass" if actual.get("observed") == case["expected"] and complete else "fail"
        production_bodies = actual.get("productionBodies", [])
        if args.role == "agent":
            production_sources = (
                [sources["SupportViewModel.kt"]]
                if any(body.startswith("SupportViewModel.") for body in production_bodies)
                else candidate_sources
            )
        else:
            production_sources = (
                [sources["SupportViewModel.kt"]] if args.role == "base"
                else [sources[name] for name in BODY_SOURCES[case["key"]]]
            )
        rows.append({
            "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
            "status": status,
            "productionSources": production_sources,
            "productionBodies": production_bodies,
            "checkpoints": [
                {"label": "before", "state": actual.get("before")},
                {"label": "after", "state": actual.get("after")},
            ],
            "observed": actual.get("observed"), "effects": effects, "invariantChecks": checks,
        })

    command([str(adb), "-s", args.serial, "uninstall", test_id])
    command([str(adb), "-s", args.serial, "uninstall", app_id])
    passed = sum(row["status"] == "pass" for row in rows)
    failed = sum(row["status"] == "fail" for row in rows)
    not_scored = sum(row["status"] == "not_scored" for row in rows)
    report = {
        "schemaVersion": 1, "taskId": contract["taskId"], "platform": "android", "role": args.role,
        "observationMode": "runtime_state_transition",
        "runtime": "application-owned Activity and production runtime observed by instrumentation on Android API37 ART",
        "device": {"serial": args.serial, "apiLevel": 37 if device_ready else None},
        "codeGeneration": {
            "passed": args.role != "agent" or bool(candidate_sources),
            "changedProductionFiles": [row["path"] for row in candidate_sources],
        },
        "compile": {
            "passed": bool(app_apks and test_apks),
            "command": ["bash", "migrations/tools/build_android_agent_harness.sh", "{project}"]
            if args.role == "agent" else ["bash", "build.sh"],
            "artifacts": [artifact_record(project, path) for path in (app_apks[-1], test_apks[-1])]
            if app_apks and test_apks else [],
        },
        "semantic": {"cases": rows, "summary": {"passed": passed, "failed": failed, "notScored": not_scored, "total": len(rows)}},
        "provenance": {
            "sourceManifest": artifact_record(project, project / "upstream-source-manifest.json"),
            "hiddenHarness": artifact_record(project, project / ".benchmark-evaluator/PREPARED")
            if args.role == "agent" else None,
        },
        "diagnostics": {
            "adapter": "ready" if not not_scored else "incomplete",
            "transport": "adb_instrumentation" if device_ready else "unavailable",
            "sourceIntegrity": "passed" if not integrity_errors else integrity_errors,
            "installErrors": install_errors,
            "verdictBasis": "exact_runtime_observation_and_complete_invariants",
            "sourcePresenceUsedForVerdict": False,
            "roleMarkerUsedForVerdict": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["semantic"]["summary"]))
    if args.role == "base":
        polarity_valid = passed == 0 and failed == len(rows)
    elif args.role == "final":
        polarity_valid = passed == len(rows)
    else:
        polarity_valid = not_scored == 0
    return 0 if not not_scored and polarity_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
