#!/usr/bin/env python3
"""Run evaluator-owned Android semantic probes against generated candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from semantic_candidate_integrity import audit_candidate
from project_cross_platform_results import project_android


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "state_tests" / "android_observer" / "probes.json"
INIT_SCRIPT = ROOT / "state_tests" / "android_observer" / "init.gradle"
DEFAULT_SOURCE_REPO = ROOT / "_sources" / "element-x-android"
CROSS_PLATFORM_CONTRACT = ROOT / "state_tests" / "canonical" / "cross_platform_contract.json"
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
ANDROID_HOME = Path.home() / "Library" / "Android" / "sdk"


@dataclass(frozen=True)
class TestMethod:
    name: str
    body: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_process(cmd: list[str], cwd: Path, env: dict[str, str], timeout: int) -> tuple[int, str, float]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return completed.returncode, completed.stdout, time.monotonic() - started
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, output + f"\nTIMEOUT after {timeout}s", time.monotonic() - started


def git_show(repo: Path, revision: str, source: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{source}"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"cannot read {revision}:{source}")
    return completed.stdout


def parse_test_methods(source: str, method_pattern: str = "") -> list[TestMethod]:
    matches = list(re.finditer(r"(?m)^\s*(?:public\s+)?fun\s+`([^`]+)`\s*\(", source))
    methods: list[TestMethod] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        name = match.group(1)
        if method_pattern and method_pattern.lower() not in name.lower():
            continue
        methods.append(TestMethod(name=name, body=source[match.start():end]))
    return methods


def normalized_method_body(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def probe_methods(source_repo: Path, task: dict[str, Any], probe: dict[str, Any], source_text: str) -> list[TestMethod]:
    methods = parse_test_methods(source_text, probe.get("methodPattern", ""))
    if not probe.get("deltaOnly"):
        return methods
    try:
        base_source = git_show(source_repo, task["baseTag"], probe["source"])
    except RuntimeError:
        return methods
    base_methods = {
        method.name: normalized_method_body(method.body)
        for method in parse_test_methods(base_source, probe.get("methodPattern", ""))
    }
    return [
        method for method in methods
        if base_methods.get(method.name) != normalized_method_body(method.body)
    ]


def case_id(task_id: str, class_name: str, method_name: str) -> str:
    digest = hashlib.sha256(f"{task_id}\0{class_name}\0{method_name}".encode()).hexdigest()[:12]
    return f"official_{task_id}_{digest}"


def trace_digest(task_id: str, final_tag: str, class_name: str, method: TestMethod) -> str:
    value = "\0".join([task_id, final_tag, class_name, method.name, method.body])
    return hashlib.sha256(value.encode()).hexdigest()


def contract_cases(manifest: dict[str, Any], source_repo: Path, task_filter: set[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for task_id, task in manifest["tasks"].items():
        if task_filter and task_id not in task_filter:
            continue
        for probe in task["probes"]:
            source = git_show(source_repo, task["finalTag"], probe["source"])
            methods = probe_methods(source_repo, task, probe, source)
            for method in methods:
                cases.append({
                    "caseId": case_id(task_id, probe["className"], method.name),
                    "taskId": task_id,
                    "area": probe["area"],
                    "title": method.name,
                    "finalTag": task["finalTag"],
                    "module": probe["module"],
                    "className": probe["className"],
                    "methodName": method.name,
                    "traceDigest": trace_digest(task_id, task["finalTag"], probe["className"], method),
                    "evidenceSource": "official_final_junit_transition",
                })
    return cases


def junit_results(result_root: Path, class_name: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for path in result_root.glob("TEST-*.xml"):
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        for node in root.findall(".//testcase"):
            if node.attrib.get("classname") != class_name:
                continue
            name = node.attrib.get("name", "")
            if node.find("failure") is not None or node.find("error") is not None:
                statuses[name] = "failed"
            elif node.find("skipped") is not None:
                statuses[name] = "not_scored"
            else:
                statuses[name] = "passed"
    return statuses


def environment_failure(output: str) -> bool:
    markers = (
        "SDK location not found",
        "Could not resolve all files",
        "Could not GET",
        "Could not HEAD",
        "Dependency requires at least JVM",
        "No space left on device",
        "Read timed out",
        "Connection reset",
        "TIMEOUT after",
    )
    return any(marker in output for marker in markers)


def observer_env(module: str, source: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "JAVA_HOME": str(JAVA_HOME),
        "ANDROID_HOME": str(ANDROID_HOME),
        "ANDROID_SDK_ROOT": str(ANDROID_HOME),
        "QINGYU_OBSERVER_MODULE": module,
        "QINGYU_OBSERVER_SOURCE": str(source),
    })
    env["PATH"] = os.pathsep.join([str(JAVA_HOME / "bin"), str(ANDROID_HOME / "platform-tools"), env.get("PATH", "")])
    return env


def module_result_root(candidate: Path, module: str) -> Path:
    relative = module.strip(":").replace(":", "/")
    return candidate / relative / "build" / "test-results" / "testDebugUnitTest"


def clean_candidate_outputs(candidate: Path) -> None:
    module_roots = {
        path.parent
        for pattern in ("build.gradle", "build.gradle.kts")
        for path in candidate.rglob(pattern)
    }
    for module_root in sorted(module_roots, key=lambda path: len(path.parts), reverse=True):
        output = module_root / "build"
        if output.exists():
            shutil.rmtree(output)
    for gradle_state in sorted(candidate.rglob(".gradle"), key=lambda path: len(path.parts), reverse=True):
        if gradle_state.is_dir():
            shutil.rmtree(gradle_state)


def run_probe(
    task_id: str,
    task: dict[str, Any],
    probe: dict[str, Any],
    candidate: Path,
    source_repo: Path,
    timeout: int,
) -> dict[str, Any]:
    source_text = git_show(source_repo, task["finalTag"], probe["source"])
    methods = probe_methods(source_repo, task, probe, source_text)
    if not methods:
        return {
            "taskId": task_id,
            "module": probe["module"],
            "className": probe["className"],
            "source": probe["source"],
            "supportSources": probe.get("supportSources", []),
            "exitCode": 0,
            "durationSeconds": 0.0,
            "adapterFailure": False,
            "skippedReason": "no_changed_canonical_methods",
            "outputTail": "",
            "cases": [],
        }
    with tempfile.TemporaryDirectory(prefix=f"qingyu-{task_id}-observer-") as raw:
        source_root = Path(raw) / "src"
        injected_sources = [probe["source"], *probe.get("supportSources", [])]
        for source_path in injected_sources:
            injected_text = source_text if source_path == probe["source"] else git_show(
                source_repo,
                task["finalTag"],
                source_path,
            )
            package_match = re.search(r"(?m)^package\s+([\w.]+)\s*$", injected_text)
            if package_match is None:
                raise RuntimeError(f"missing package declaration in {source_path}")
            package_path = Path(*package_match.group(1).split("."))
            target = source_root / package_path / Path(source_path).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(injected_text, encoding="utf-8")
        result_root = module_result_root(candidate, probe["module"])
        shutil.rmtree(result_root, ignore_errors=True)
        command = [
            str(candidate / "gradlew"),
            "-I", str(INIT_SCRIPT),
            f"{probe['module']}:testDebugUnitTest",
            "--tests", probe["className"],
            "--no-daemon",
            "--no-configuration-cache",
            "--console=plain",
            "--max-workers=4",
            "-Pkotlin.compiler.execution.strategy=in-process",
        ]
        code, output, duration = run_process(command, candidate, observer_env(probe["module"], source_root), timeout)
        observed = junit_results(result_root, probe["className"])
        clean_candidate_outputs(candidate)
    adapter_failed = code != 0 and environment_failure(output)
    rows = []
    for method in methods:
        status = observed.get(method.name)
        if status is None:
            status = "not_scored" if adapter_failed else "failed"
        rows.append({
            "caseId": case_id(task_id, probe["className"], method.name),
            "taskId": task_id,
            "area": probe["area"],
            "title": method.name,
            "className": probe["className"],
            "methodName": method.name,
            "traceDigest": trace_digest(task_id, task["finalTag"], probe["className"], method),
            "semanticStatus": status,
            "evidenceSource": "official_final_junit_transition",
        })
    return {
        "taskId": task_id,
        "module": probe["module"],
        "className": probe["className"],
        "source": probe["source"],
        "supportSources": probe.get("supportSources", []),
        "exitCode": code,
        "durationSeconds": round(duration, 3),
        "adapterFailure": adapter_failed,
        "outputTail": output[-12000:],
        "cases": rows,
    }


def write_contract(cases: list[dict[str, Any]], destination: Path) -> None:
    payload = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "owner": "evaluator",
        "source": "Element X official final JUnit state-transition tests",
        "cases": cases,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "android_external_observer.json")
    parser.add_argument("--cross-platform-output", type=Path)
    parser.add_argument("--contract-output", type=Path, default=ROOT / "state_tests" / "canonical" / "official_transition_contract.json")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-repo", type=Path, default=DEFAULT_SOURCE_REPO)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--contract-only", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task_filter = set(args.task)
    # The canonical contract is shared by all platform adapters. A scoped
    # execution must never truncate that global artifact to its task filter.
    cases = contract_cases(manifest, args.source_repo, set())
    write_contract(cases, args.contract_output)
    if args.contract_only:
        print(json.dumps({"contract": str(args.contract_output), "cases": len(cases)}, ensure_ascii=False))
        return 0
    if args.candidate_root is None:
        parser.error("--candidate-root is required unless --contract-only is used")

    probes = []
    integrity_by_task: dict[str, Any] = {}
    for task_id, task in manifest["tasks"].items():
        if task_filter and task_id not in task_filter:
            continue
        candidate = args.candidate_root / task["candidateDir"]
        integrity = audit_candidate(candidate, "android")
        integrity_by_task[task_id] = integrity
        if not integrity.get("valid", False):
            continue
        for probe in task["probes"]:
            probes.append(run_probe(task_id, task, probe, candidate, args.source_repo, args.timeout))

    rows = [row for probe in probes for row in probe["cases"]]
    counts = {status: sum(row["semanticStatus"] == status for row in rows) for status in ("passed", "failed", "not_scored")}
    report = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "observerOwner": "evaluator",
        "candidateRoot": str(args.candidate_root.resolve()),
        "contract": str(args.contract_output.resolve()),
        "integrity": integrity_by_task,
        "counts": counts | {"total": len(rows)},
        "probes": probes,
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cross_output = args.cross_platform_output or args.output.with_name(f"{args.output.stem}_cross_platform.json")
    cross_contract = json.loads(CROSS_PLATFORM_CONTRACT.read_text(encoding="utf-8"))
    selected_cross_cases = [
        case for case in cross_contract["cases"]
        if not task_filter or case["taskId"] in task_filter
    ]
    cross_rows = project_android(report, {"cases": selected_cross_cases})
    cross_counts = {
        status: sum(row["semanticStatus"] == status for row in cross_rows)
        for status in ("passed", "failed", "not_scored")
    } | {"total": len(cross_rows)}
    cross_report = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "platform": "android",
        "contract": str(CROSS_PLATFORM_CONTRACT.resolve()),
        "sourceReport": str(args.output.resolve()),
        "counts": cross_counts,
        "cases": cross_rows,
    }
    cross_output.parent.mkdir(parents=True, exist_ok=True)
    cross_output.write_text(json.dumps(cross_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "diagnosticCounts": report["counts"],
        "crossPlatformOutput": str(cross_output),
        "benchmarkCounts": cross_counts,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
