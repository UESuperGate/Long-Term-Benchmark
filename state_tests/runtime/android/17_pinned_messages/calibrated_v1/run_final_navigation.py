#!/usr/bin/env python3
"""Run the Task17 final banner-to-pinned-list production navigation probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = ROOT / "_sources/element-x-android"
TASK = "17_pinned_messages"
COMMIT = "eff868ddf9e1caef8182e55ac59054e81526a68f"
TREE = "0cd8a58632515f8e0f6fb669b02c8b35614d9181"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
CLASS = "runtime.task17.FinalNavigationRuntimeTest"
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
    if git("rev-parse", f"{COMMIT}^{{commit}}").strip() != COMMIT or git("rev-parse", f"{COMMIT}^{{tree}}").strip() != TREE:
        raise RuntimeError("Immutable Android final identity mismatch")

    source_dir = output / "injected-source"
    source_dir.mkdir()
    shutil.copy2(HERE / "FinalNavigationRuntimeTest.kt", source_dir / "FinalNavigationRuntimeTest.kt")
    process_output = ""
    exit_code = 127
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="task17-final-navigation-") as raw:
        worktree = Path(raw) / "element-x-android"
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        subprocess.run(["git", "-C", str(SOURCE), "worktree", "add", "--detach", str(worktree), COMMIT], check=True, env=env)
        try:
            env.update({
                "JAVA_HOME": str(JAVA_HOME), "ANDROID_HOME": str(ANDROID_HOME), "ANDROID_SDK_ROOT": str(ANDROID_HOME),
                "TASK17_EVALUATOR_SOURCE": str(source_dir), "TASK17_EVIDENCE_DIR": str(evidence_dir),
                "TASK17_LOCAL_MAVEN": str(HERE / ".m2"),
            })
            env["PATH"] = os.pathsep.join([str(JAVA_HOME / "bin"), str(ANDROID_HOME / "platform-tools"), env.get("PATH", "")])
            command = [
                str(worktree / "gradlew"), "-I", str(HERE / "final-navigation-init.gradle"),
                ":features:messages:impl:testDebugUnitTest", "--tests", CLASS,
                "--no-daemon", "--no-configuration-cache", "--console=plain", "--max-workers=4",
                "-Pkotlin.compiler.execution.strategy=in-process",
            ]
            try:
                completed = subprocess.run(command, cwd=worktree, env=env, text=True, errors="replace", stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, timeout=args.timeout)
                exit_code = completed.returncode
                process_output = completed.stdout
            except subprocess.TimeoutExpired as error:
                exit_code = 124
                value = error.stdout or ""
                process_output = value.decode(errors="replace") if isinstance(value, bytes) else value
                process_output += f"\nTIMEOUT after {args.timeout}s"
            (output / "gradle.log").write_text(process_output)
            result_xml = worktree / "features/messages/impl/build/test-results/testDebugUnitTest" / f"TEST-{CLASS}.xml"
            if result_xml.exists():
                shutil.copy2(result_xml, output / "junit.xml")
        finally:
            subprocess.run(["git", "-C", str(SOURCE), "worktree", "remove", "--force", str(worktree)], check=False,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    evidence_path = evidence_dir / "open_loading_navigation.json"
    junit_path = output / "junit.xml"
    method = None
    if junit_path.is_file():
        node = next(iter(ET.parse(junit_path).getroot().findall(".//testcase")), None)
        if node is not None:
            method = {
                "name": node.attrib.get("name"), "classname": node.attrib.get("classname"),
                "failure": node.find("failure") is not None, "error": node.find("error") is not None,
                "skipped": node.find("skipped") is not None,
            }
    healthy = (
        exit_code == 0 and evidence_path.is_file() and method is not None
        and method["name"] == "open_loading_navigation" and method["classname"] == CLASS
        and not method["failure"] and not method["error"] and not method["skipped"]
    )
    evidence = json.loads(evidence_path.read_text()) if evidence_path.is_file() else None
    production_paths = [
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesFlowNode.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesNode.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/banner/PinnedMessagesBannerView.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/list/PinnedMessagesListNode.kt",
        "libraries/architecture/src/main/kotlin/io/element/android/libraries/architecture/NodeFactories.kt",
    ]
    report = {
        "schemaVersion": 1, "taskId": TASK, "platform": "android", "role": "final",
        "probe": "open_loading_navigation_conjunct",
        "candidate": {"commit": COMMIT, "tree": TREE, "source": str(SOURCE)},
        "contract": record(CONTRACT),
        "runtimeCompile": {
            "status": "passed" if healthy else "failed", "passed": healthy,
            "scope": ":features:messages:impl:testDebugUnitTest", "exitCode": exit_code,
            "isolatedTestJvms": 1, "forkEvery": 1,
        },
        "semantic": evidence if healthy else {"key": "open_loading", "status": "not_scored"},
        "status": "candidate" if healthy else "incomplete",
        "junit": method,
        "durationSeconds": round(time.monotonic() - started, 3),
        "provenance": {
            "runner": record(Path(__file__)), "initScript": record(HERE / "final-navigation-init.gradle"),
            "evaluatorSource": record(HERE / "FinalNavigationRuntimeTest.kt"),
            "injectedEvaluatorSource": record(source_dir / "FinalNavigationRuntimeTest.kt"),
            "gradleLog": record(output / "gradle.log"), "junit": record(junit_path) if junit_path.is_file() else None,
            "runtimeEvidence": record(evidence_path) if evidence_path.is_file() else None,
            "productionSources": [upstream_record(path) for path in production_paths],
        },
        "cleanup": {"temporaryWorktree": "removed", "moduleBuildOutputs": "removed with worktree", "gradleDaemon": "disabled"},
    }
    report_path = output / "android_17_pinned_messages_final_navigation_v1.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(report_path), "status": report["status"], "runtimeCompile": report["runtimeCompile"]}))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
