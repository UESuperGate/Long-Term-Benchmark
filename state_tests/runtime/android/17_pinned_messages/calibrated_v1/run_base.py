#!/usr/bin/env python3
"""Run Task17 Android base prefixes in isolated Gradle test JVMs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = ROOT / "_sources/element-x-android"
TASK = "17_pinned_messages"
COMMIT = "4ecc9f46b6627f89184d66b758094a7c4a24c258"
TREE = "6c90042e69580acd06c8d669447c90a4a90ec9e8"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
CLASS = "runtime.task17.BasePrefixRuntimeTest"
JAVA_HOME = Path("/opt/homebrew/Cellar/openjdk@17/17.0.18/libexec/openjdk.jdk/Contents/Home")
ANDROID_HOME = Path.home() / "Library/Android/sdk"


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def git(*args: str, text: bool = True):
    return subprocess.check_output(["git", "-C", str(SOURCE), *args], text=text)


def upstream_record(path: str) -> dict:
    data = git("show", f"{TREE}:{path}", text=False)
    return {"path": path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def junit_methods(path: Path) -> dict[str, dict]:
    root = ET.parse(path).getroot()
    return {
        node.attrib["name"]: {
            "classname": node.attrib.get("classname"),
            "time": float(node.attrib.get("time", "0")),
            "failure": node.find("failure") is not None,
            "error": node.find("error") is not None,
            "skipped": node.find("skipped") is not None,
        }
        for node in root.findall(".//testcase")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Preserve prior evidence; choose a new directory: {output}")
    output.mkdir(parents=True)
    evidence_dir = output / "cases"
    evidence_dir.mkdir()
    contract = json.loads(CONTRACT.read_text())
    if git("rev-parse", f"{COMMIT}^{{commit}}").strip() != COMMIT or git("rev-parse", f"{COMMIT}^{{tree}}").strip() != TREE:
        raise RuntimeError("Immutable Android base identity mismatch")

    source_dir = output / "injected-source"
    source_dir.mkdir()
    shutil.copy2(HERE / "BasePrefixRuntimeTest.kt", source_dir / "BasePrefixRuntimeTest.kt")
    command = []
    process_output = ""
    exit_code = 127
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="task17-base-worktree-") as raw:
        worktree = Path(raw) / "element-x-android"
        worktree_env = os.environ.copy()
        worktree_env["GIT_LFS_SKIP_SMUDGE"] = "1"
        subprocess.run(["git", "-C", str(SOURCE), "worktree", "add", "--detach", str(worktree), COMMIT],
                       check=True, env=worktree_env)
        try:
            env = os.environ.copy()
            env.update({
                "JAVA_HOME": str(JAVA_HOME),
                "ANDROID_HOME": str(ANDROID_HOME),
                "ANDROID_SDK_ROOT": str(ANDROID_HOME),
                "TASK17_EVALUATOR_SOURCE": str(source_dir),
                "TASK17_EVIDENCE_DIR": str(evidence_dir),
                "TASK17_LOCAL_MAVEN": str(HERE / ".m2"),
            })
            env["PATH"] = os.pathsep.join([str(JAVA_HOME / "bin"), str(ANDROID_HOME / "platform-tools"), env.get("PATH", "")])
            command = [
                str(worktree / "gradlew"), "-I", str(HERE / "base-init.gradle"),
                ":features:messages:impl:testDebugUnitTest", "--tests", CLASS,
                "--no-daemon", "--no-configuration-cache", "--console=plain", "--max-workers=4",
                "-Pkotlin.compiler.execution.strategy=in-process",
            ]
            try:
                completed = subprocess.run(command, cwd=worktree, env=env, text=True, errors="replace",
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=args.timeout)
                exit_code = completed.returncode
                process_output = completed.stdout
            except subprocess.TimeoutExpired as error:
                exit_code = 124
                value = error.stdout or ""
                process_output = value.decode(errors="replace") if isinstance(value, bytes) else value
                process_output += f"\nTIMEOUT after {args.timeout}s"
            log = output / "gradle.log"
            log.write_text(process_output)
            result_xml = worktree / "features/messages/impl/build/test-results/testDebugUnitTest" / f"TEST-{CLASS}.xml"
            if result_xml.exists():
                shutil.copy2(result_xml, output / "junit.xml")
        finally:
            subprocess.run(["git", "-C", str(SOURCE), "worktree", "remove", "--force", str(worktree)], check=False,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    compile_passed = exit_code == 0 and (output / "junit.xml").exists()
    methods = junit_methods(output / "junit.xml") if (output / "junit.xml").exists() else {}
    rows = []
    for case in contract["cases"]:
        key = case["key"]
        evidence_path = evidence_dir / f"{key}.json"
        method = methods.get(key)
        healthy = (
            compile_passed and method is not None and method["classname"] == CLASS
            and not method["failure"] and not method["error"] and not method["skipped"]
            and evidence_path.is_file()
        )
        if healthy:
            evidence = json.loads(evidence_path.read_text())
            status = "fail"
            reason = evidence["reason"]
        else:
            evidence = {"observed": {}, "checkpoints": [], "invariantChecks": []}
            status = "not_scored"
            reason = "Base production prefix did not execute cleanly; compile/environment/test failures are not semantic failures."
        rows.append({
            "taskId": TASK, "platform": "android", "role": "base",
            "caseId": case["caseId"], "key": key, "traceDigest": case["traceDigest"],
            "given": case["given"], "event": case["event"], "expected": case["expected"],
            "status": status, "reason": reason,
            "observed": evidence.get("observed", {}),
            "checkpoints": evidence.get("checkpoints", []),
            "invariantChecks": evidence.get("invariantChecks", []),
            "runtimeEvidence": record(evidence_path) if evidence_path.is_file() else None,
            "junit": method,
        })
    counts = {status: sum(row["status"] == status for row in rows) for status in ("pass", "fail", "not_scored")}
    production_paths = [
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesFlowNode.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesNode.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/banner/PinnedMessagesBannerView.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/banner/PinnedMessagesBannerState.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/banner/PinnedMessagesBannerItem.kt",
        "libraries/architecture/src/main/kotlin/io/element/android/libraries/architecture/NodeFactories.kt",
    ]
    report = {
        "schemaVersion": 2, "taskId": TASK, "platform": "android", "role": "base",
        "candidate": {"commit": COMMIT, "tree": TREE, "source": str(SOURCE)},
        "contract": record(CONTRACT),
        "runtimeDomain": "robolectric_real_banner_to_appyx_production_flow_prefix",
        "applicationCompile": {"status": "not_run", "passed": None},
        "runtimeCompile": {
            "status": "passed" if compile_passed else "failed", "passed": compile_passed,
            "scope": ":features:messages:impl:testDebugUnitTest", "exitCode": exit_code,
            "isolatedTestJvms": 9 if compile_passed else len(methods), "forkEvery": 1,
        },
        "semantic": {"counts": counts, "cases": rows},
        "status": "candidate" if counts == {"pass": 0, "fail": 9, "not_scored": 0} else "incomplete",
        "durationSeconds": round(time.monotonic() - started, 3),
        "provenance": {
            "runner": record(Path(__file__)), "initScript": record(HERE / "base-init.gradle"),
            "evaluatorSource": record(HERE / "BasePrefixRuntimeTest.kt"),
            "injectedEvaluatorSource": record(source_dir / "BasePrefixRuntimeTest.kt"),
            "gradleLog": record(output / "gradle.log"),
            "junit": record(output / "junit.xml") if (output / "junit.xml").exists() else None,
            "productionSources": [upstream_record(path) for path in production_paths],
        },
        "cleanup": {"temporaryWorktree": "removed", "moduleBuildOutputs": "removed with worktree", "gradleDaemon": "disabled"},
        "limitations": ["Robolectric/module-test runtime; full Android application compilation was not run."],
    }
    report_path = output / "android_17_pinned_messages_base_calibrated_v1.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(report_path), "counts": counts, "runtimeCompile": report["runtimeCompile"]}))
    return 0 if report["status"] == "candidate" else 1


if __name__ == "__main__":
    raise SystemExit(main())
