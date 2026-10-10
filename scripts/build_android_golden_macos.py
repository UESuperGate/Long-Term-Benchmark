#!/usr/bin/env python3
"""Build and archive the ten debug-instrumented Android golden APKs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = Path.home() / "Library" / "Android" / "sdk"
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
MIRROR_INIT = ROOT / "scripts" / "android_maven_mirror.init.gradle"
MATRIX = ROOT / "verification_reports" / "state_dynamic" / "state_dynamic_target_matrix.json"
APK_NAME = "app-gplay-arm64-v8a-debug.apk"
APKSIGNER = SDK_ROOT / "build-tools" / "37.0.0" / "apksigner"


def env() -> dict[str, str]:
    value = os.environ.copy()
    value.update(
        {
            "ANDROID_HOME": str(SDK_ROOT),
            "ANDROID_SDK_ROOT": str(SDK_ROOT),
            "JAVA_HOME": str(JAVA_HOME),
        }
    )
    value["PATH"] = os.pathsep.join([str(JAVA_HOME / "bin"), str(SDK_ROOT / "platform-tools"), value.get("PATH", "")])
    value["GRADLE_OPTS"] = " ".join(
        filter(
            None,
            [
                value.get("GRADLE_OPTS", ""),
                "-Dorg.gradle.internal.http.connectionTimeout=30000",
                "-Dorg.gradle.internal.http.socketTimeout=30000",
                "-Djava.net.useSystemProxies=false",
                "-Dhttp.nonProxyHosts=maven.aliyun.com|maven-central.storage-download.googleapis.com",
                "-Dhttps.nonProxyHosts=maven.aliyun.com|maven-central.storage-download.googleapis.com",
                "-Dhttp.proxyHost=127.0.0.1",
                "-Dhttp.proxyPort=7898",
                "-Dhttps.proxyHost=127.0.0.1",
                "-Dhttps.proxyPort=7898",
            ],
        )
    )
    return value


def run_logged(command: list[str], cwd: Path, environment: dict[str, str], log: Path, timeout: int) -> int:
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            stream.write(f"TIMEOUT after {timeout}s\n")
            return 124


def find_apk(worktree: Path) -> Path | None:
    preferred_paths = [
        worktree / "app" / "build" / "outputs" / "apk" / "gplay" / "debug" / APK_NAME,
        worktree / "app" / "build" / "intermediates" / "apk" / "gplay" / "debug" / APK_NAME,
    ]
    for preferred in preferred_paths:
        if preferred.exists():
            return preferred
    matches = sorted(worktree.glob("app/build/**/apk/**/*.apk"), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def is_installable_apk(path: Path) -> bool:
    if not path.exists():
        return False
    return subprocess.run(
        [str(APKSIGNER), "verify", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def clean_build_outputs(project: Path) -> None:
    module_roots = {path.parent for pattern in ("build.gradle", "build.gradle.kts") for path in project.rglob(pattern)}
    for module_root in sorted(module_roots, key=lambda path: len(path.parts), reverse=True):
        output = module_root / "build"
        if output.exists():
            shutil.rmtree(output)


def configure_arm64_only(project: Path) -> None:
    build_file = project / "app" / "build.gradle.kts"
    text = build_file.read_text(encoding="utf-8")
    text = text.replace(
        'abiFilters += listOf("armeabi-v7a", "x86", "arm64-v8a", "x86_64")',
        'abiFilters += listOf("arm64-v8a")',
    )
    text = text.replace(
        'include("armeabi-v7a", "x86", "arm64-v8a", "x86_64")',
        'include("arm64-v8a")',
    )
    text = text.replace("isEnable = !buildingAppBundle", "isEnable = false")
    text = text.replace('include("arm64-v8a")', "// ABI splits are disabled for the arm64 benchmark build.")
    text = text.replace("isUniversalApk = true", "isUniversalApk = false")
    build_file.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    artifact_root = run_root / "android_golden_apks"
    log_root = run_root / "golden_build_logs"
    artifact_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    matrix = json.loads(MATRIX.read_text(encoding="utf-8-sig"))
    targets = [
        target
        for target in matrix["targets"]
        if target["platform"] == "android"
        and target.get("isGroundTruth")
        and (not args.task or target["taskId"] in set(args.task))
    ]
    results: list[dict[str, object]] = []
    environment = env()
    for index, target in enumerate(targets, start=1):
        worktree = Path(target["worktree"])
        label = f"{target['taskId']}_{target['targetRole']}"
        log = log_root / f"{label}.log"
        destination = artifact_root / target["taskId"] / target["targetRole"] / APK_NAME
        if is_installable_apk(destination):
            results.append(
                {
                    "targetId": target["targetId"],
                    "tag": target["tag"],
                    "worktree": str(worktree),
                    "buildExit": 0,
                    "durationSeconds": 0,
                    "apk": str(destination),
                    "log": str(log),
                    "skippedExisting": True,
                }
            )
            print(f"[golden {index}/{len(targets)}] {label} skipped (artifact exists)", flush=True)
            continue
        destination.unlink(missing_ok=True)
        print(f"[golden {index}/{len(targets)}] {label}", flush=True)
        configure_arm64_only(worktree)
        started = time.monotonic()
        exit_code = run_logged(
            [
                "./gradlew",
                ":app:assembleGplayDebug",
                "--no-daemon",
                "--max-workers=8",
                "--no-configuration-cache",
                "--init-script",
                str(MIRROR_INIT),
            ],
            worktree,
            environment,
            log,
            args.timeout,
        )
        source_apk = find_apk(worktree)
        if exit_code == 0 and source_apk and is_installable_apk(source_apk):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_apk, destination)
        if args.clean and is_installable_apk(destination):
            clean_build_outputs(worktree)
        results.append(
            {
                "targetId": target["targetId"],
                "tag": target["tag"],
                "worktree": str(worktree),
                "buildExit": exit_code,
                "durationSeconds": round(time.monotonic() - started, 3),
                "apk": str(destination) if destination.exists() else "",
                "log": str(log),
            }
        )
        print(f"[golden result] {label} build={exit_code} apk={is_installable_apk(destination)}", flush=True)

    manifest = {
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "artifactRoot": str(artifact_root),
        "javaHome": str(JAVA_HOME),
        "androidSdkRoot": str(SDK_ROOT),
        "targets": results,
    }
    output = run_root / "golden_build_manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[manifest] {output}")
    return 0 if all(item["buildExit"] == 0 and item["apk"] and is_installable_apk(Path(str(item["apk"]))) for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
