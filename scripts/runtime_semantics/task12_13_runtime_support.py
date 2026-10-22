#!/usr/bin/env python3
"""Task12/13-only helpers for live source-parameterized strict evaluators."""

from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import time
from typing import Iterable

try:
    from . import task12_13_formal_core as formal
    from .task14_15_formal_core import bounded_file_lock as _bounded_file_lock
except ImportError:
    import task12_13_formal_core as formal
    from task14_15_formal_core import bounded_file_lock as _bounded_file_lock


ROOT = formal.ROOT
ANDROID_FULL_BUILD_LOCK = Path("/tmp/long-term-benchmark-android-full-build.lock")


@contextmanager
def android_full_build_lock(deadline: float):
    with _bounded_file_lock(
            ANDROID_FULL_BUILD_LOCK, deadline,
            "Task12/13 Android full application build lock"):
        yield

ANDROID_REPOSITORY_INIT = """\
beforeSettings { settings ->
    settings.pluginManagement.repositories {
        maven { name = "MavenCentralRepo1"; url = uri("https://repo1.maven.org/maven2") }
        gradlePluginPortal()
        google()
    }
    settings.dependencyResolutionManagement.repositories {
        maven { name = "MavenCentralRepo1"; url = uri("https://repo1.maven.org/maven2") }
        gradlePluginPortal()
        google()
    }
}

gradle.beforeProject { project ->
    if (project.rootProject.name == "ElementX_plugins") {
        project.buildscript.repositories {
            maven { name = "MavenCentralRepo1"; url = uri("https://repo1.maven.org/maven2") }
        }
        project.repositories {
            maven { name = "MavenCentralRepo1"; url = uri("https://repo1.maven.org/maven2") }
        }
    }
}
"""

DEPENDENCY_TRANSPORT_MARKERS = (
    "could not get resource",
    "could not get '",
    "could not head '",
    "sslhandshakeexception",
    "remote host terminated the handshake",
    "connection timed out",
    "connect timed out",
    "unknownhostexception",
    "temporary failure in name resolution",
)

def android_java_home() -> Path:
    configured = os.environ.get("ANDROID_JAVA_HOME")
    candidates = [
        Path(configured) if configured else None,
        Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"),
        Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home"),
        Path(os.environ["JAVA_HOME"]) if os.environ.get("JAVA_HOME") else None,
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "bin/java").is_file() and \
                (candidate / "bin/jlink").is_file():
            return candidate.resolve()
    raise RuntimeError("Android application compile requires a JDK containing java and jlink")


def wait_hdc_connected(*, serial: str, deadline: float, log: Path) -> None:
    hdc = Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc"
    stop = min(deadline, time.monotonic() + 180)
    samples = []
    while time.monotonic() < stop:
        process = subprocess.run([str(hdc), "list", "targets", "-v"], capture_output=True,
                                 text=True, timeout=min(10, remaining(deadline, "HDC readiness")), check=False)
        text = (process.stdout or "") + (process.stderr or "")
        samples.append(text.strip())
        if any(serial in line and "Connected" in line and "Offline" not in line
               for line in text.splitlines()):
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("\n---\n".join(samples) + "\n", encoding="utf-8")
            return
        time.sleep(min(2, remaining(deadline, "HDC readiness wait")))
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n---\n".join(samples) + "\n", encoding="utf-8")
    raise RuntimeError(f"OpenHarmony device {serial} did not become TCP Connected")


@contextmanager
def arkts_device_lock(*, serial: str, deadline: float):
    suffix = hashlib.sha256(serial.encode()).hexdigest()[:16]
    # Every scorer uses one canonical path. macOS TMPDIR points into
    # /var/folders while /tmp points at /private/tmp; treating both as separate
    # locks allowed two runners to drive the same emulator concurrently.
    lock = Path("/tmp") / f"ltb-arkts-device-{suffix}"
    acquired = False
    while not acquired:
        try:
            lock.mkdir()
            acquired = True
        except FileExistsError:
            time.sleep(min(2, remaining(deadline, "OpenHarmony device lock")))
    try:
        yield
    finally:
        if acquired:
            lock.rmdir()


def compile_candidate(*, platform: str, source: Path, output: Path, deadline: float,
                      command: str = "") -> dict:
    """Compile the supplied standalone app; semantic runtime compilation remains separate."""
    source = source.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if platform == "arkts":
        try:
            from .task14_15_formal_core import build_arkts_application
        except ImportError:
            from task14_15_formal_core import build_arkts_application
        report = build_arkts_application(
            source=source, output=output / "application-build", deadline=deadline,
            label="task12-13-formal-candidate",
        )
        passed = report.get("passed") is True and report.get("productionUnchanged") is True
        return {
            "passed": passed, "status": "passed" if passed else "failed",
            "scope": "standalone_candidate_application_build",
            "command": "DevEco hvigor assembleHap --mode module --no-daemon --no-parallel",
            "source": str(source),
            "evidence": formal.file_record(output / "application-build/application-build.json"),
        }
    if platform != "android":
        raise ValueError("Application compiler supports only android or arkts")
    argv = shlex.split(command) if command else [
        "./gradlew", ":app:assembleGplayDebug", "--no-daemon", "--stacktrace",
    ]
    repository_init = output / "repository-mirror.init.gradle"
    repository_init.write_text(ANDROID_REPOSITORY_INIT, encoding="utf-8")
    argv.extend(("--init-script", str(repository_init)))
    # The machine's standard Gradle cache is part of the configured Android
    # toolchain.  Keeping GRADLE_USER_HOME inside the disposable candidate tree
    # hides already-resolved plugins and turns an offline build into a false
    # infrastructure failure.  Project-local .gradle/build outputs are still
    # hashed and removed by the formal scorer after every phase.
    android_sdk = Path(os.environ.get("ANDROID_HOME") or
                       os.environ.get("ANDROID_SDK_ROOT") or
                       Path.home() / "Library/Android/sdk").resolve()
    if not (android_sdk / "platforms").is_dir() or not (android_sdk / "build-tools").is_dir():
        raise RuntimeError(f"Configured Android SDK is incomplete: {android_sdk}")
    java_home = android_java_home()
    environment = {
        **os.environ,
        "GRADLE_USER_HOME": str(Path.home() / ".gradle"),
        "ANDROID_HOME": str(android_sdk),
        "ANDROID_SDK_ROOT": str(android_sdk),
        "JAVA_HOME": str(java_home),
        "PATH": str(java_home / "bin") + os.pathsep + os.environ.get("PATH", ""),
    }
    lock_started = time.monotonic()
    with android_full_build_lock(deadline):
        lock_wait_seconds = time.monotonic() - lock_started
        process = subprocess.run(
            argv, cwd=source, env=environment, capture_output=True, text=True,
            timeout=remaining(deadline, "Android standalone candidate application build"), check=False,
        )
    log = output / "application-build.log"
    log_text = (process.stdout or "") + (process.stderr or "")
    log.write_text(log_text, encoding="utf-8")
    apks = sorted((source / "app/build").rglob("*.apk")) if (source / "app/build").is_dir() else []
    passed = process.returncode == 0 and bool(apks)
    dependency_transport_failure = process.returncode != 0 and any(
        marker in log_text.lower() for marker in DEPENDENCY_TRANSPORT_MARKERS)
    lowered_log = log_text.lower()
    toolchain_environment_failure = process.returncode != 0 and (
        "sdk location not found" in lowered_log or
        ("jlink executable" in lowered_log and "does not exist" in lowered_log))
    external_termination = process.returncode in {130, 137, 143, -2, -9, -15}
    not_scored = dependency_transport_failure or toolchain_environment_failure or external_termination
    status = "passed" if passed else "not_scored" if not_scored else "failed"
    classification = ("dependency_transport" if dependency_transport_failure else
                      "toolchain_environment" if toolchain_environment_failure else
                      "external_termination" if external_termination else
                      "application_compile")
    return {
        "passed": True if passed else None if not_scored else False,
        "status": status,
        "classification": classification,
        "scope": "standalone_candidate_application_build", "command": shlex.join(argv),
        "source": str(source), "exitCode": process.returncode,
        "androidSdk": str(android_sdk),
        "javaHome": str(java_home),
        "fullBuildLock": str(ANDROID_FULL_BUILD_LOCK),
        "fullBuildLockWaitSeconds": lock_wait_seconds,
        "log": formal.file_record(log),
        "repositoryConfiguration": formal.file_record(repository_init),
        "artifacts": [formal.file_record(path) for path in apks],
    }


def remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"{phase} exhausted the shared formal-scorer deadline")
    return value


def run(command: list[str], *, deadline: float, phase: str, log: Path,
        cwd: Path = ROOT, environment: dict[str, str] | None = None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=remaining(deadline, phase))
    except (subprocess.TimeoutExpired, TimeoutError) as error:
        # Kill the wrapper and its device/build descendants, not just the wrapper.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        log.write_text((stdout or "") + (stderr or "") +
                       "\nTask12/13 shared monotonic deadline exhausted; process group terminated.\n",
                       encoding="utf-8")
        raise TimeoutError(f"{phase} exhausted the shared formal-scorer deadline; see {log}") from error
    log.write_text((stdout or "") + (stderr or ""), encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"{phase} failed with exit {process.returncode}; see {log}")


def _check_name(item: dict) -> str | None:
    return item.get("description", item.get("invariant", item.get("text")))


def canonical_rows(contract: dict, rows: Iterable[dict], *, role: str,
                   base_entry_failure: bool = False) -> list[dict]:
    by_identity = {}
    for row in rows:
        identity = row.get("caseId") or row.get("key")
        if identity in by_identity:
            raise ValueError(f"Duplicate runtime row: {identity}")
        by_identity[identity] = row
    normalized = []
    for spec in contract["cases"]:
        source = by_identity.get(spec["caseId"], by_identity.get(spec["key"]))
        if source is None:
            raise ValueError(f"Live runtime did not return {spec['caseId']}")
        for field in ("caseId", "key", "traceDigest"):
            if field in source and source[field] != spec[field]:
                raise ValueError(f"Live runtime {field} differs from canonical contract: {spec['caseId']}")
        row = copy.deepcopy(source)
        row.update(caseId=spec["caseId"], key=spec["key"], traceDigest=spec["traceDigest"])
        checks = []
        for item in row.get("invariantChecks", []):
            check = copy.deepcopy(item)
            name = _check_name(check)
            if name is not None:
                check.setdefault("description", name)
            if "passed" not in check and check.get("status") in {"pass", "fail"}:
                check["passed"] = check["status"] == "pass"
            if "status" not in check and isinstance(check.get("passed"), bool):
                check["status"] = "pass" if check["passed"] else "fail"
            checks.append(check)
        row["invariantChecks"] = checks
        row.setdefault("observed", {})
        row.setdefault("checkpoints", [])
        if role == "base" and base_entry_failure and row.get("transitionExecuted") is not True:
            entry = copy.deepcopy(row.get("entryFailureEvidence", {}))
            entry.update(
                canonicalGivenEstablished=True,
                positiveControlCompleted=True,
                evidenceSource="live runtime checkpoints in this report",
            )
            row["entryFailureEvidence"] = entry
            row["transitionExecuted"] = False
            row["status"] = "fail"
        else:
            row["transitionExecuted"] = True
        normalized.append(row)
    return normalized


def strict_report(*, task, platform: str, source: Path, role: str, rows: list[dict],
                  runtime_compile: dict, lineage: dict, runtime_kind: str,
                  transport: str, evidence: dict, output: Path) -> dict:
    inventory = formal.source_inventory(source)
    passed = sum(row.get("status") == "pass" for row in rows)
    failed = sum(row.get("status") == "fail" for row in rows)
    not_scored = len(rows) - passed - failed
    report = {
        "schemaVersion": 2,
        "taskId": task.task_id,
        "platform": platform,
        "role": role,
        "observationMode": "runtime_state_transition",
        "runtimeCompile": {
            **runtime_compile,
            "passed": runtime_compile.get("passed", runtime_compile.get("status") == "passed"),
            "status": "passed" if runtime_compile.get("passed", runtime_compile.get("status") == "passed") else
                      runtime_compile.get("status", "failed"),
            "scope": runtime_compile.get("scope", "strict evaluator packaging and runtime build"),
        },
        "semantic": {
            "total": len(rows), "passed": passed, "failed": failed,
            "notScored": not_scored, "cases": rows,
        },
        "provenance": {
            "candidateMode": "standalone_directory",
            "archivedPatchApplied": False,
            "candidateSource": str(source.resolve()),
            "productionSourceRoot": str(source.resolve()),
            "sourceInventorySha256": inventory["sha256"],
            "productionSources": [item for item in inventory["files"]
                                  if item["path"].endswith((".kt", ".ets"))],
            "runtimeEvidence": evidence,
        },
        "diagnostics": {
            "adapter": "ready" if not_scored == 0 else "failed",
            "transport": transport,
            "strictRuntime": {
                "sourceParameterized": True,
                "actualProductionExecuted": True,
                "sourceObserverUsed": False,
                "fallbackUsed": False,
                "hostTranspilationUsed": False,
                "runtimeKind": runtime_kind,
                "calibratorLineageSha256": lineage["sha256"],
            },
        },
    }
    formal.write(output, report)
    return report


def parse_args(description: str):
    import argparse

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deadline-seconds", type=float, default=3600)
    parser.add_argument("--device-serial", default=os.environ.get("ARKTS_DEVICE_SERIAL", "127.0.0.1:5555"))
    return parser.parse_args()
