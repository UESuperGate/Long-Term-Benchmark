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
from typing import Any

MIGRATION = Path(__file__).resolve().parents[2]
CONTRACT = MIGRATION / "canonical/transitions.json"


def run(argv: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(project: Path, path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(project)), "bytes": path.stat().st_size, "sha256": sha256(path)}


def source_inventory(project: Path) -> list[dict[str, Any]]:
    root = project / "src/main"
    return [
        {"path": str(path.relative_to(project)), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(root.rglob("*")) if path.is_file()
    ]


def identity(project: Path) -> tuple[str, str]:
    text = (project / "build.gradle.kts").read_text(encoding="utf-8")
    app = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    test = re.search(r'testApplicationId\s*=\s*"([^"]+)"', text)
    if app is None or test is None:
        raise RuntimeError("candidate package identities are unavailable")
    return app.group(1), test.group(1)


def exact_observation(case: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected = case["expected"]
    if observed.get("state") != expected.get("state") or observed.get("effects") != expected.get("effects", []):
        return False
    names = {effect.get("name") for effect in observed.get("effects", [])}
    return all(name not in names for name in expected.get("absentEffects", []))


def not_scored(case: dict[str, Any], diagnostic: str) -> dict[str, Any]:
    return {
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "observed": None, "invariantChecks": [], "diagnostic": diagnostic,
    }


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "step"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent", "control"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", "emulator-5554"))
    args = parser.parse_args()
    project = args.project.resolve()
    output = args.output.resolve()
    raw_dir = (args.raw_dir or output.parent / "raw" / output.stem).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    adb = str(sdk / "platform-tools/adb")
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    app_apk: Path | None = None
    test_apk: Path | None = None
    app_id = test_id = ""
    setup_error = ""
    api_level: int | None = None
    installed = False
    raw_sequence = 0

    def run_recorded(label: str, argv: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
        nonlocal raw_sequence
        raw_sequence += 1
        result = run(argv, timeout=timeout)
        path = raw_dir / f"{raw_sequence:02d}-{safe_name(label)}.json"
        record = {
            "schemaVersion": 1,
            "label": label,
            "command": argv,
            "returnCode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return result

    lock = Path("/tmp/long-term-benchmark-android-device.lock").open("a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    try:
        try:
            sources = source_inventory(project)
            app_id, test_id = identity(project)
            app_apks = sorted((project / "build/outputs/apk/debug").glob("*-debug.apk"))
            test_apks = sorted((project / "build/outputs/apk/androidTest/debug").glob("*-debug-androidTest.apk"))
            if len(app_apks) != 1 or len(test_apks) != 1:
                raise RuntimeError("expected one application APK and one instrumentation APK")
            app_apk, test_apk = app_apks[0], test_apks[0]
            api = run_recorded("device-api-level", [adb, "-s", args.serial, "shell", "getprop", "ro.build.version.sdk"])
            if api.returncode != 0 or api.stdout.strip() != "37":
                raise RuntimeError(f"expected Android API37 device, observed {api.stdout.strip()!r}")
            api_level = 37
            for apk in (app_apk, test_apk):
                result = run_recorded(f"install-{apk.name}", [adb, "-s", args.serial, "install", "-r", "-t", str(apk)])
                if result.returncode or "Success" not in result.stdout:
                    raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "APK install failed")
            installed = True
            component = f"{test_id}/evaluator.domains.SemanticInstrumentation"
            for case in contract["cases"]:
                encoded = base64.urlsafe_b64encode(json.dumps(case, separators=(",", ":")).encode()).decode().rstrip("=")
                result = run_recorded(f"case-{case['caseId']}-{case['key']}", [
                    adb, "-s", args.serial, "shell", "am", "instrument", "-w", "-r",
                    "-e", "case_b64", encoded, component,
                ])
                matches = re.findall(r"runtime_state_transition_b64=([^\r\n]+)", result.stdout)
                if result.returncode or not matches:
                    rows.append(not_scored(case, result.stderr.strip() or result.stdout.strip() or "runtime payload unavailable"))
                    continue
                try:
                    episode = json.loads(base64.b64decode(matches[-1]).decode())
                except Exception as error:
                    rows.append(not_scored(case, f"invalid runtime payload: {error}"))
                    continue
                checks = episode.get("invariantChecks", [])
                names = [check.get("invariant") for check in checks]
                boundary = [
                    episode.get("given") == case.get("given"),
                    episode.get("event") == case.get("event"),
                    episode.get("commonEntryObserved") is True,
                    episode.get("runtimeEvidence", {}).get("storeSource") == "DomainActivity.DomainPageOwner",
                    episode.get("runtimeEvidence", {}).get("evaluatorStoreWrites") == 0,
                    episode.get("runtimeEvidence", {}).get("detachedControllers") == 0,
                    episode.get("transitionExecuted") is True and episode.get("earlyExit") is False,
                ]
                passed = (
                    exact_observation(case, episode.get("observed", {}))
                    and names == case["invariants"]
                    and all(check.get("passed") is True for check in checks)
                    and all(boundary)
                )
                rows.append({
                    "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                    "status": "pass" if passed else "fail", "productionSources": sources,
                    "productionBodies": episode.get("invokedProductionMethods", []),
                    "checkpoints": [
                        {"label": "given/before", "state": episode.get("before")},
                        {"label": "event/after", "state": episode.get("after")},
                    ],
                    "observed": episode.get("observed"),
                    "effects": episode.get("observed", {}).get("effects", []),
                    "invariantChecks": checks,
                    "runtimeBoundaryChecks": boundary,
                    "runtimeEvidence": episode.get("runtimeEvidence"),
                })
        except Exception as error:
            setup_error = str(error)
            rows = [not_scored(case, setup_error) for case in contract["cases"]]
    finally:
        if installed:
            run_recorded(f"uninstall-{test_id}", [adb, "-s", args.serial, "uninstall", test_id])
            run_recorded(f"uninstall-{app_id}", [adb, "-s", args.serial, "uninstall", app_id])
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()

    summary = {
        "passed": sum(row["status"] == "pass" for row in rows),
        "failed": sum(row["status"] == "fail" for row in rows),
        "notScored": sum(row["status"] == "not_scored" for row in rows),
        "total": len(rows),
    }
    artifacts = [artifact(project, path) for path in (app_apk, test_apk) if path is not None]
    report = {
        "schemaVersion": 2, "taskId": contract["taskId"], "platform": "android", "role": args.role,
        "observationMode": "runtime_state_transition",
        "runtime": "Android API37 DomainActivity page-owner instrumentation",
        "device": {"serial": args.serial, "apiLevel": api_level},
        "codeGeneration": {"passed": bool(sources), "changedProductionFiles": sources},
        "compile": {"passed": len(artifacts) == 2, "command": ["bash", "build.sh"], "artifacts": artifacts},
        "semantic": {"summary": summary, "cases": rows},
        "diagnostics": {
            "adapter": "ready" if not setup_error else "unavailable",
            "transport": "adb_instrumentation" if api_level == 37 else "unavailable",
            "productionEntryExecuted": installed,
            "sourceObserver": False,
            "roleAffectsVerdict": False,
            "setupError": setup_error or None,
        },
        "provenance": {
            "contractSha256": sha256(CONTRACT),
            "rawDirectory": str(raw_dir),
            "rawRecords": [
                {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in sorted(raw_dir.glob("*.json"))
            ],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if summary["notScored"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
