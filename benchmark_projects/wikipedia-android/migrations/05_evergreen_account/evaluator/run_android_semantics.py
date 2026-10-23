#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import re
import subprocess
from pathlib import Path

from score_common import score_case, source_inventory, write_report

ADB = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))) / "platform-tools/adb"
DEVICE = os.environ.get("ANDROID_SERIAL", "emulator-5554")
RUNNER = "org.wikipedia.benchmark.evergreen.native.NativeEvergreenInstrumentation"


def adb(*args: str, timeout: int = 90, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(ADB), "-s", DEVICE, *args], text=True, capture_output=True, timeout=timeout, check=check)


def encoded(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def app_id(project: Path) -> str:
    text = (project / "app/build.gradle.kts").read_text()
    return re.search(r'applicationId\s*=\s*"([^"]+)"', text).group(1)  # type: ignore[union-attr]


def unavailable(case: dict, reason: str) -> dict:
    return {"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
            "status": "not_scored", "observed": {}, "invariantChecks": [],
            "runtimeBoundaryChecks": [], "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    migration = Path(__file__).resolve().parents[1]
    contract = json.loads((migration / "canonical/transitions.json").read_text())
    project = args.project.resolve()
    package = app_id(project)
    app_apk = project / "app/build/outputs/apk/debug/app-debug.apk"
    test_apk = project / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
    rows, episodes = [], []
    runtime = {"device": DEVICE, "apiLevel": None, "transport": "adb instrumentation"}
    with open("/tmp/long-term-benchmark-android-device.lock", "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if not app_apk.is_file() or not test_apk.is_file():
                raise RuntimeError("app or instrumentation APK missing")
            api = int(adb("shell", "getprop", "ro.build.version.sdk").stdout.strip())
            runtime["apiLevel"] = api
            if api != 37:
                raise RuntimeError(f"expected API 37 device, found {api}")
            adb("install", "-r", "-t", str(app_apk), timeout=180)
            adb("install", "-r", "-t", str(test_apk), timeout=180)
            for case in contract["cases"]:
                call = adb("shell", "am", "instrument", "-w", "-e", "caseKey", case["key"],
                           "-e", "given", encoded(case["given"]), "-e", "event", encoded(case["event"]),
                           f"{package}.test/{RUNNER}", check=False)
                if call.returncode or "INSTRUMENTATION_CODE: 0" not in call.stdout:
                    rows.append(unavailable(case, (call.stdout + call.stderr).strip() or "instrumentation failed"))
                    episodes.append({"caseId": case["caseId"], "instrumentation": call.stdout + call.stderr})
                    continue
                raw = adb("exec-out", "run-as", package, "cat", "files/runtime-episode.json").stdout
                episode = json.loads(raw)
                episodes.append({"caseId": case["caseId"], "episode": episode, "instrumentation": call.stdout})
                rows.append(score_case(case, episode))
        except Exception as exc:
            rows = [unavailable(case, str(exc)) for case in contract["cases"]]
        finally:
            adb("uninstall", f"{package}.test", check=False)
            adb("uninstall", package, check=False)
    write_report(args.output.resolve(), contract["taskId"], "android", args.role, rows,
                 source_inventory(project / "app/src/main", (".kt", ".xml")), runtime, episodes)
    return 0 if all(row["status"] != "not_scored" for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
