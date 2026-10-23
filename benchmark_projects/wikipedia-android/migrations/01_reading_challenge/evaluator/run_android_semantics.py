#!/usr/bin/env python3
"""Install the API 37 harness and score device-produced repository episodes."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


DEVICE = os.environ.get("ANDROID_SERIAL", "emulator-5554")
ADB = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))) / "platform-tools/adb"
RUNNER = "org.wikipedia.benchmark.reading.native.NativeReadingInstrumentation"


def contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def application_id(project: Path) -> str:
    text = (project / "app/build.gradle.kts").read_text()
    match = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("applicationId missing from app/build.gradle.kts")
    return match.group(1)


def adb(*parts: str, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(ADB), "-s", DEVICE, *parts], text=True, capture_output=True, timeout=timeout, check=check)


def instrumentation_args(case: dict[str, Any]) -> list[str]:
    given = case["given"]
    prefs = given.get("preferences", {})
    values: dict[str, Any] = {
        "date": given["clockDate"],
        "event": case["event"]["name"],
        "setupRefresh": any(step.get("name") == "refreshChallengeSurface" for step in case.get("setup", [])),
    }
    for key in ("enrolled", "streak", "lastReadDate", "enrollmentDate"):
        if key in prefs:
            values[key] = prefs[key]
    result: list[str] = []
    for key, value in values.items():
        text = "null" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
        result.extend(["-e", key, text])
    return result


def checks(case: dict[str, Any], episode: dict[str, Any]) -> list[dict[str, Any]]:
    before, after, observed = episode["before"], episode["after"], episode["observed"]
    pb, pa = before.get("persistence", {}), after.get("persistence", {})
    state, effects = after.get("state", {}), observed.get("effects", [])
    values = {
        "before_start": [after.get("clockDate") == case["given"]["clockDate"], pb == pa],
        "start_not_enrolled": [state.get("name") == "not_enrolled", pb == pa],
        "enroll": [pa.get("streak") == 0, pa.get("lastReadDate") is None],
        "first_read": [state.get("streak") == 1, effects == ["heartbeat_requested", "widget_update_requested"]],
        "duplicate_same_day": [pa.get("streak") == pb.get("streak"), effects == []],
        "next_day_continues": [state.get("streak") == 2, pa.get("lastReadDate") == after.get("clockDate")],
        "gap_resets": [pa.get("streak") == 0, effects == []],
        "read_after_reset": [pb.get("streak") == 0 and pa.get("streak") == 1, pa.get("streak") != 4],
        "goal_completion": [state.get("name") == "challenge_completed" and state.get("streak") == 25, pa.get("streak") == state.get("streak")],
        "post_end_broken_rejected": [pb == pa, effects == []],
    }[case["key"]]
    return [{
        "invariant": text,
        "passed": values[index],
        "evidence": {"before": before, "after": after, "effects": effects},
    } for index, text in enumerate(case["invariants"])]


def unavailable_rows(contract: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    return [{
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [], "reason": reason,
    } for case in contract["cases"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.project = args.project.resolve()
    migration = Path(__file__).resolve().parents[1]
    contract = json.loads((migration / "canonical/transitions.json").read_text())
    app_apk = args.project / "app/build/outputs/apk/debug/app-debug.apk"
    test_apk = args.project / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
    package = application_id(args.project)
    test_package = f"{package}.test"
    source_roots = ([args.project / "candidate-production"] if args.role == "agent" else
                    [args.project / "app/src/main/upstream/kotlin", args.project / "app/src/main/action/kotlin"] if args.role == "base" else
                    [migration / "android/final/src/upstream"])
    production = sorted(path for root in source_roots for path in root.rglob("*.kt"))
    source_label_root = args.project if args.role == "agent" else migration
    sources = [{"path": str(path.relative_to(source_label_root)), "sha256": sha256(path)} for path in production]
    rows: list[dict[str, Any]] = []
    raw_episodes: list[dict[str, Any]] = []
    error = ""
    device_api = None
    installed = False
    lock_handle = open("/tmp/long-term-benchmark-android-device.lock", "a+")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    if not app_apk.is_file() or not test_apk.is_file():
        error = "native app or instrumentation APK is missing"
    else:
        try:
            device_api = int(adb("shell", "getprop", "ro.build.version.sdk").stdout.strip())
            if device_api != 37:
                raise RuntimeError(f"expected API 37 device, found API {device_api}")
            adb("install", "-r", "-t", str(app_apk), timeout=90)
            adb("install", "-r", "-t", str(test_apk), timeout=90)
            installed = True
            for case in contract["cases"]:
                invocation = ["shell", "am", "instrument", "-w", *instrumentation_args(case), f"{test_package}/{RUNNER}"]
                run = adb(*invocation, timeout=45, check=False)
                if run.returncode != 0 or "INSTRUMENTATION_CODE: -1" not in run.stdout:
                    raw_episodes.append({"caseId": case["caseId"], "instrumentation": run.stdout + run.stderr})
                    rows.append({
                        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                        "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [],
                        "reason": (run.stdout + run.stderr).strip() or "instrumentation failed",
                    })
                    continue
                raw = adb("exec-out", "run-as", package, "cat", "files/runtime-episode.json").stdout
                episode = json.loads(raw)
                raw_episodes.append({"caseId": case["caseId"], "episode": episode, "instrumentation": run.stdout})
                invariant_checks = checks(case, episode)
                runtime_bound = (
                    episode.get("entryOwner") == "ReadingChallengePageActionPrefix"
                    and episode.get("transitionExecuted") is True
                    and episode.get("storageReopened") is True
                    and bool(episode.get("invokedProductionMethods"))
                )
                passed = runtime_bound and contains(episode["observed"], case["expected"]) and all(row["passed"] for row in invariant_checks)
                rows.append({
                    "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                    "status": "pass" if passed else "fail", "productionSources": sources,
                    "entryOwner": episode["entryOwner"],
                    "invokedProductionMethods": episode["invokedProductionMethods"],
                    "checkpoints": [{"label": "before", "state": episode["before"]}, {"label": "after", "state": episode["after"]}],
                    "observed": episode["observed"], "invariantChecks": invariant_checks,
                    "transitionExecuted": episode["transitionExecuted"],
                    "deviceEvidence": {"serial": DEVICE, "apiLevel": device_api, "runner": RUNNER},
                })
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
            error = str(failure)
        finally:
            if installed:
                adb("uninstall", test_package, check=False)
                adb("uninstall", package, check=False)
    if error:
        rows = unavailable_rows(contract, error)
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    lock_handle.close()
    count = lambda status: sum(row["status"] == status for row in rows)
    raw_output = args.output.with_suffix(".raw.json")
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text(json.dumps({"schemaVersion": 1, "taskId": contract["taskId"], "role": args.role, "episodes": raw_episodes}, indent=2) + "\n")
    report = {
        "schemaVersion": 1, "taskId": contract["taskId"], "platform": "android", "role": args.role,
        "observationMode": "runtime_state_transition", "runtime": "api37_android_instrumentation_official_kotlin_slice",
        "codeGeneration": {"passed": None, "changedProductionFiles": []},
        "compile": {"passed": app_apk.is_file() and test_apk.is_file(), "command": ["bash", "{project}/build.sh"],
                    "artifacts": [{"path": str(path.relative_to(args.project)), "sha256": sha256(path)} for path in (app_apk, test_apk) if path.is_file()]},
        "semantic": {"passed": count("pass"), "failed": count("fail"), "notScored": count("not_scored"), "total": len(rows), "cases": rows},
        "diagnostics": {"adapter": "ready" if not error else "unavailable", "transport": "adb_instrumentation", "deviceSerial": DEVICE,
                        "deviceApi": device_api, "runtimeCompile": {"passed": app_apk.is_file() and test_apk.is_file()}, "sourceObserver": False,
                        "jvmProbeRole": "debug_only", "rawEvidence": {"path": raw_output.name, "sha256": sha256(raw_output), "bytes": raw_output.stat().st_size}},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if not error and count("not_scored") == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
