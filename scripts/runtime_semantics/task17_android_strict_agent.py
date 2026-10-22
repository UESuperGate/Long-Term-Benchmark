#!/usr/bin/env python3
"""Source-parameterized Task17 Android strict agent scorer."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

try:
    from . import android_robolectric, android_robolectric_dependencies
    from .android_robolectric_ui_resources import compile_resources
    from .task16_android_strict_agent import filesystem_closure
    from . import task17_android_entry_evidence as entry_policy
except ImportError:
    import android_robolectric
    import android_robolectric_dependencies
    from android_robolectric_ui_resources import compile_resources
    from task16_android_strict_agent import filesystem_closure
    import task17_android_entry_evidence as entry_policy


ROOT = Path(__file__).resolve().parents[2]
TASK = "17_pinned_messages"
HERE = ROOT / "state_tests/runtime/android/17_pinned_messages/calibrated_v1"
CONTRACT = ROOT / "benchmark_tasks/17_pinned_messages/transitions.json"
JAVA_HOME = Path("/opt/homebrew/Cellar/openjdk@17/17.0.18/libexec/openjdk.jdk/Contents/Home")
ANDROID_HOME = Path.home() / "Library/Android/sdk"
MIN_FREE_BYTES = 8 * 1024**3


@contextmanager
def runtime_lock(path: Path, deadline: float):
    with path.open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(min(0.2, remaining(deadline, "runtime lock")))
        try:
            if shutil.disk_usage(ROOT).free < MIN_FREE_BYTES:
                raise RuntimeError("storage_protection_environment: less than 8 GiB free")
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def retain_sources(source: Path, records: List[dict], evidence: Path) -> dict:
    snapshots = {}
    for item in records:
        path = source / item["path"]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["bytes"]:
            raise RuntimeError("Candidate production source changed during execution")
        target = evidence / "production-sources" / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        snapshots[item["path"]] = record(target)
    return snapshots

def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"{phase} exceeded the formal scorer deadline")
    return value


def counts(rows: List[dict]) -> dict:
    return {status: sum(row.get("status") == status for row in rows)
            for status in ("pass", "fail", "not_scored")}


def final_configuration(key: str, output: Path) -> dict:
    template = ROOT / "experiment_results/runtime_transition_20261019/android_base_followup/task12-presenter/base-v4.config.json"
    config = json.loads(template.read_text())
    prefix = "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/"
    config.update(scope=f"task17_agent_strict_{key}",
                  runtimeScope="candidate_provider_presenter_factory_action_and_sdk_effect",
                  testClass="runtime.FinalRuntimeTest", keys=[key],
                  entrypoints=[prefix + "pinned/list/PinnedMessagesListPresenter.kt",
                               prefix + "pinned/DefaultIsPinnedMessagesFeatureEnabled.kt"],
                  evaluatorSources=[str(HERE / "FinalRuntimeTest.kt"), str(HERE.parents[1] / "common/Anvil.kt")],
                  offlineDependencies=True)
    config["resources"] = [item for item in config["resources"] if item["package"] in (
        "io.element.android.libraries.ui.strings", "io.element.android.libraries.designsystem",
        "io.element.android.libraries.matrix.ui")]
    for item in config["resources"]:
        if item["package"] == "io.element.android.libraries.designsystem":
            item["files"] += ["libraries/designsystem/src/main/res/drawable/ic_developer_options.xml"]
    config["dependencies"] = [item for item in config["dependencies"] if item[0] != "io.coil-kt.coil3"]
    for item in config["dependencies"]:
        if item[0] == "androidx.compose.material":
            item[2] = "1.6.8"
        elif item[0] == "androidx.compose.material3":
            item[2] = "1.2.1"
    config["alignedGroups"] += [["androidx.compose.material", "1.6.8"],
                                ["androidx.compose.material3", "1.2.1"]]
    config["dependencyCatalog"]["libraries"] += [
        "coil_compose", "jsoup", "sigpwned_emoji4j", "androidx_constraintlayout_compose",
        "matrix_richtexteditor", "matrix_richtexteditor_compose", "androidx_recyclerview"]
    config["dependencies"].append(["androidx.media3", "media3-common", "1.4.1"])
    config["resources"] += [{"package": "io.element.android.features.location.api",
                             "files": ["features/location/api/src/main/res/drawable/blurred_map.png",
                                       "_evaluator_generated/res/values/location_defaults.xml"]}]
    return config


def junit_methods(path: Path) -> Dict[str, dict]:
    if not path.is_file():
        return {}
    return {node.attrib.get("name"): {"classname": node.attrib.get("classname"),
                                      "failure": node.find("failure") is not None,
                                      "error": node.find("error") is not None,
                                      "skipped": node.find("skipped") is not None}
            for node in ET.parse(path).getroot().findall(".//testcase")}


def run_final_slices(source: Path, evidence: Path, deadline: float, contract: dict) -> dict:
    defaults = HERE.parent / "empty_ui/res/values/location_defaults.xml"
    original_compile = android_robolectric.compile_resources
    original_closure = android_robolectric.closure
    original_prepare = android_robolectric.prepare
    original_seed = android_robolectric_dependencies.seed_repository
    current_output = None
    metadata = {}

    def resources(candidate, config, work, java_home):
        read_original = candidate.read
        candidate.read = lambda path: defaults.read_bytes() if path == "_evaluator_generated/res/values/location_defaults.xml" else read_original(path)
        try:
            return compile_resources(candidate, config, work, java_home)
        finally:
            candidate.read = read_original

    def seed_metadata(repository):
        original_seed(repository)
        # These old Android POM edges request JARs for AAR-only libraries.
        # Use the real matching AAR bytecode rather than synthetic metadata.
        for group, name, version in (("androidx.annotation", "annotation-experimental", "1.0.0"),
                                     ("androidx.fragment", "fragment", "1.2.5"),
                                     ("androidx.viewpager2", "viewpager2", "1.0.0")):
            relative = Path(group.replace(".", "/")) / name / version / f"{name}-{version}.aar"
            aar = HERE / ".dependencies" / relative
            jar = aar.with_suffix(".jar")
            if not aar.exists():
                with urllib.request.urlopen("https://dl.google.com/dl/android/maven2/" + relative.as_posix(), timeout=30) as response:
                    data = response.read(4 * 1024 * 1024 + 1)
                if len(data) > 4 * 1024 * 1024 or not data.startswith(b"PK"):
                    raise ValueError("Refusing oversized or non-AAR Android dependency")
                aar.parent.mkdir(parents=True, exist_ok=True)
                aar.write_bytes(data)
            if not jar.exists():
                with zipfile.ZipFile(aar) as bundle:
                    jar.write_bytes(bundle.read("classes.jar"))
            for path in (aar, jar):
                metadata[str(path)] = record(path)
                linked = repository / relative.with_suffix(path.suffix)
                if not linked.exists():
                    linked.parent.mkdir(parents=True, exist_ok=True)
                    linked.symlink_to(path)
        coordinates = [("androidx.compose.material", name, "1.6.8") for name in
                       ("material", "material-ripple", "material-icons-core")]
        coordinates.append(("androidx.compose.material3", "material3", "1.2.1"))
        for group, name, version in coordinates:
            relative = Path(group.replace(".", "/")) / name / version / f"{name}-{version}.jar"
            target = HERE.parent / "empty_ui/.dependencies" / relative
            if not target.exists():
                with urllib.request.urlopen("https://dl.google.com/dl/android/maven2/" + relative.as_posix(), timeout=30) as response:
                    data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024 or not data.startswith(b"PK"):
                    raise ValueError("Refusing oversized or non-JAR metadata")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            metadata[str(target)] = record(target)
            linked = repository / relative
            if not linked.exists():
                linked.parent.mkdir(parents=True, exist_ok=True)
                linked.symlink_to(target)

    def prepare(config, work):
        environment = original_prepare(config, work)
        environment["jvmArgs"] += [f"-Druntime.contract.path={CONTRACT}",
                                   f"-Druntime.rendered.output={current_output.with_suffix('')}"]
        return environment

    rows = []
    raw_reports = []
    cases = evidence / "final-cases"
    cases.mkdir()
    android_robolectric.compile_resources = resources
    android_robolectric.closure = lambda repository, ref, seeds: filesystem_closure(source, seeds)
    android_robolectric.prepare = prepare
    android_robolectric_dependencies.seed_repository = seed_metadata
    try:
        for case in contract["cases"]:
            if shutil.disk_usage(ROOT).free < MIN_FREE_BYTES:
                raise RuntimeError("storage_protection_environment: less than 8 GiB free")
            raw = cases / f"{case['caseId']}.raw.json"
            current_output = raw
            config = final_configuration(case["key"], raw)
            try:
                config["sources"] = filesystem_closure(source, config["entrypoints"])
                for path in ("appconfig/src/main/kotlin/io/element/android/appconfig/TimelineConfig.kt",
                             "appconfig/src/main/kotlin/io/element/android/appconfig/OnBoardingConfig.kt"):
                    if (source / path).is_file() and path not in config["sources"]:
                        config["sources"].append(path)
            except (OSError, ValueError) as error:
                rows.append({"caseId": case["caseId"], "key": case["key"],
                             "traceDigest": case["traceDigest"], "status": "not_scored",
                             "reason": f"Runtime slice could not bind candidate: {error}"})
                continue
            config["sourceClosure"] = False
            config_path = raw.with_suffix(".config.json")
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            packaging = [record(ROOT / "experiment_results/runtime_transition_20261019/android_base_followup/task12-presenter/base-v4.config.json"),
                         record(config_path)]
            result = android_robolectric.run_slice(
                TASK, "agent", source, HERE, config_path, raw, remaining(deadline, "Task17 final slice"))
            result.setdefault("provenance", {})["packagingSources"] = packaging + [record(defaults)]
            raw.write_text(json.dumps(result, indent=2) + "\n")
            raw_reports.append(record(raw))
            observation = next((row for row in result.get("observations", [])
                                if row.get("key") == case["key"]), None)
            if observation is None:
                observation = {"key": case["key"], "status": "not_scored",
                               "reason": result.get("error") or "No runtime observation"}
            if result.get("runtimeCompile", {}).get("status") != "passed" or result.get("error"):
                observation["status"] = "not_scored"
                observation["reason"] = result.get("error") or "Runtime slice did not compile."
            row = copy.deepcopy(observation)
            row.update(caseId=case["caseId"], traceDigest=case["traceDigest"],
                       runtimeReport=record(raw),
                       productionSources=result.get("provenance", {}).get("productionSources", []))
            rows.append(row)
    finally:
        android_robolectric.compile_resources = original_compile
        android_robolectric.closure = original_closure
        android_robolectric.prepare = original_prepare
        android_robolectric_dependencies.seed_repository = original_seed
    return {"rows": rows, "rawReports": raw_reports, "metadata": list(metadata.values()),
            "runtimeCompile": all(row["status"] != "not_scored" for row in rows)}


def gradle_environment(evaluator_source: Path, evidence_dir: Path, build_root: Path) -> dict:
    env = os.environ.copy()
    env.update({"JAVA_HOME": str(JAVA_HOME), "ANDROID_HOME": str(ANDROID_HOME),
                "ANDROID_SDK_ROOT": str(ANDROID_HOME), "TASK17_EVALUATOR_SOURCE": str(evaluator_source),
                "TASK17_EVIDENCE_DIR": str(evidence_dir), "TASK17_LOCAL_MAVEN": str(HERE / ".m2"),
                "TASK17_BUILD_ROOT": str(build_root)})
    env["PATH"] = os.pathsep.join([str(JAVA_HOME / "bin"), str(ANDROID_HOME / "platform-tools"), env.get("PATH", "")])
    return env


def run_gradle_probe(source: Path, output: Path, deadline: float, *, kind: str) -> dict:
    is_base = kind == "base"
    class_name = "runtime.task17.BasePrefixRuntimeTest" if is_base else "runtime.task17.FinalNavigationRuntimeTest"
    test_file = HERE / ("BasePrefixRuntimeTest.kt" if is_base else "FinalNavigationRuntimeTest.kt")
    init_file = HERE / ("base-init.gradle" if is_base else "final-navigation-init.gradle")
    injected = output / "injected-source"
    case_dir = output / "cases"
    injected.mkdir(parents=True)
    case_dir.mkdir()
    shutil.copy2(test_file, injected / test_file.name)
    removed_artifacts = []
    production_sources = []
    prefix = "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/"
    paths = [prefix + name for name in (
        "MessagesFlowNode.kt", "MessagesNode.kt", "pinned/banner/PinnedMessagesBannerView.kt",
        "pinned/banner/PinnedMessagesBannerState.kt", "pinned/banner/PinnedMessagesBannerItem.kt")]
    paths.append("libraries/architecture/src/main/kotlin/io/element/android/libraries/architecture/NodeFactories.kt")
    if not is_base:
        paths.append(prefix + "pinned/list/PinnedMessagesListNode.kt")
    for path in paths:
        production_sources.append({**record(source / path), "path": path})
    snapshots = retain_sources(source, production_sources, output)
    with tempfile.TemporaryDirectory(prefix=f"task17-{kind}-gradle-") as raw:
        temporary = Path(raw)
        build_root = temporary / "build"
        project_cache = temporary / "project-cache"
        derived_init = temporary / "strict-init.gradle"
        derived_init.write_text(init_file.read_text() + "\n" +
            "gradle.beforeProject { project ->\n" +
            "  def safeName = project.path.replace(':', '_').replaceAll('[^A-Za-z0-9_.-]', '_')\n" +
            "  project.layout.buildDirectory.set(new File(System.getenv('TASK17_BUILD_ROOT'), safeName))\n" +
            "}\n")
        shutil.copy2(derived_init, output / "derived-init.gradle")
        command = [str(source / "gradlew"), "-I", str(derived_init),
                   "--project-cache-dir", str(project_cache), ":features:messages:impl:testDebugUnitTest",
                   "--tests", class_name, "--no-daemon", "--no-configuration-cache", "--console=plain",
                   "--max-workers=1", "-Pkotlin.compiler.execution.strategy=in-process"]
        try:
            with runtime_lock(Path("/tmp/long-term-benchmark-android-full-build.lock"), deadline):
                with runtime_lock(ROOT / "state_tests/runtime/android/.build.lock", deadline):
                    process = subprocess.run(command, cwd=source,
                                             env=gradle_environment(injected, case_dir, build_root), text=True,
                                             errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             timeout=remaining(deadline, f"Task17 {kind} Gradle probe"), check=False)
            log = process.stdout
        except subprocess.TimeoutExpired as error:
            process = None
            value = error.stdout or ""
            log = value.decode(errors="replace") if isinstance(value, bytes) else value
            log += "\nTIMEOUT"
        candidates = list(temporary.rglob(f"TEST-{class_name}.xml"))
        if len(candidates) == 1:
            shutil.copy2(candidates[0], output / "junit.xml")
        binary_suffixes = {".apk", ".aab", ".aar", ".jar", ".class", ".dex", ".so"}
        for artifact in sorted(path for path in temporary.rglob("*")
                               if path.is_file() and path.suffix.lower() in binary_suffixes):
            removed_artifacts.append({"path": str(artifact.relative_to(temporary)),
                                      "bytes": artifact.stat().st_size,
                                      "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()})
    (output / "gradle.log").write_text(log)
    methods = junit_methods(output / "junit.xml")
    execution = {"kind": kind, "command": command, "candidateSource": str(source),
            "exitCode": None if process is None else process.returncode,
            "runtimeCompile": bool(methods), "methods": methods, "caseDir": str(case_dir),
            "productionSources": production_sources, "productionSourceSnapshots": snapshots,
            "evaluatorSource": record(injected / test_file.name),
            "log": record(output / "gradle.log"),
            "junit": record(output / "junit.xml") if (output / "junit.xml").is_file() else None,
            "cleanup": {"temporaryBuildRemoved": True, "binariesRetained": False,
                        "removedBinaryArtifacts": removed_artifacts,
                        "candidateBuildIntermediatesCreated": False}}
    execution_path = output / "execution.json"
    execution_path.write_text(json.dumps(execution, indent=2) + "\n")
    return {**execution, "execution": record(execution_path)}


def base_probe_rows(probe: dict, contract: dict) -> Optional[List[dict]]:
    expected_class = "runtime.task17.BasePrefixRuntimeTest"
    result = []
    for case in contract["cases"]:
        method = probe["methods"].get(case["key"])
        evidence_path = Path(probe["caseDir"]) / f"{case['key']}.json"
        if not (method and method["classname"] == expected_class and not method["failure"] and
                not method["error"] and not method["skipped"] and evidence_path.is_file()):
            return None
        evidence = json.loads(evidence_path.read_text())
        result.append(entry_policy.entry_row(case, probe, evidence_path, kind="base_prefix"))
    return result


def apply_navigation(rows: List[dict], probe: dict) -> None:
    row = next(item for item in rows if item["key"] == "open_loading")
    method = probe["methods"].get("open_loading_navigation")
    if not method or method.get("classname") != "runtime.task17.FinalNavigationRuntimeTest" or method.get("error") or method.get("skipped"):
        row.update(status="not_scored", reason="Navigation runtime did not compile or execute cleanly.")
        return
    evidence_path = Path(probe["caseDir"]) / "open_loading_navigation.json"
    if not evidence_path.is_file():
        row.update(status="not_scored", reason="Navigation test passed without evaluator evidence.")
    else:
        evidence = json.loads(evidence_path.read_text())
        if method.get("failure") or evidence.get("status") != "pass":
            case = next(item for item in json.loads(CONTRACT.read_text())["cases"] if item["key"] == "open_loading")
            replacement = entry_policy.entry_row(case, probe, evidence_path, kind="navigation_prefix")
            row.clear()
            row.update(replacement)
        row["navigationConjunct"] = {"status": evidence.get("status"), "runtimeEvidence": record(evidence_path)}
        sources = {item["path"]: item for item in row.get("productionSources", [])}
        sources.update({item["path"]: item for item in probe.get("productionSources", [])})
        row["productionSources"] = [sources[path] for path in sorted(sources)]


def score(source: Path, output: Path, deadline: float) -> dict:
    source, output = source.resolve(), output.resolve()
    evidence = output.with_name(output.stem + "_evidence")
    if output.exists() or evidence.exists():
        raise FileExistsError("Refusing existing Task17 output/evidence")
    evidence.mkdir(parents=True)
    contract = json.loads(CONTRACT.read_text())
    rows = []
    runtime_passed = False
    diagnostics = {}
    lock_path = ROOT / "state_tests/runtime/android/.build.lock"
    try:
        with runtime_lock(lock_path, deadline):
            final = run_final_slices(source, evidence, deadline, contract)
        diagnostics["finalSlices"] = {"runtimeCompile": final["runtimeCompile"],
            "rawReports": final["rawReports"], "metadata": final["metadata"],
            "cases": [{key: row.get(key) for key in ("caseId", "status", "reason")} for row in final["rows"]]}
        scored = [row for row in final["rows"] if row["status"] in {"pass", "fail"}]
        if scored:
            rows = final["rows"]
            navigation = run_gradle_probe(source, evidence / "navigation", deadline, kind="navigation")
            apply_navigation(rows, navigation)
            runtime_passed = final["runtimeCompile"] and navigation["runtimeCompile"]
            diagnostics["navigation"] = navigation
        else:
            base = run_gradle_probe(source, evidence / "base-prefix", deadline, kind="base")
            classified = base_probe_rows(base, contract)
            if classified is not None:
                rows = classified
                runtime_passed = True
            else:
                rows = [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                         "status": "not_scored", "reason": "Neither final strict runtime nor base-prefix runtime classified the candidate."}
                        for case in contract["cases"]]
            diagnostics["basePrefix"] = base
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        rows = [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                 "status": "not_scored", "reason": f"{type(error).__name__}: {error}"}
                for case in contract["cases"]]
        diagnostics["error"] = f"{type(error).__name__}: {error}"
    production = {}
    for row in rows:
        for item in row.get("productionSources", []):
            production[item["path"]] = item
    source_records = [production[key] for key in sorted(production)]
    snapshots = retain_sources(source, source_records, evidence)
    publishable = runtime_passed and len(rows) == len(contract["cases"]) and all(
        row["status"] in {"pass", "fail"} for row in rows)
    report = {"schemaVersion": 2, "taskId": TASK, "platform": "android", "role": "agent",
              "observationMode": "runtime_state_transition",
              "runtimeCompile": {"passed": runtime_passed, "status": "passed" if runtime_passed else "failed",
                                 "scope": "nine isolated production slices plus Appyx navigation or base-prefix classification"},
              "semantic": {"cases": rows},
              "provenance": {"candidateMode": "standalone_directory", "candidateSource": str(source),
                             "canonicalContract": record(CONTRACT), "productionSources": source_records,
                             "productionSourceSnapshots": snapshots, "scorer": record(Path(__file__)),
                             "entryPolicy": record(Path(entry_policy.__file__))},
              "diagnostics": {**diagnostics, "adapter": "ready" if publishable else "incomplete",
                              "transport": "host_runtime_completed" if runtime_passed else "failed",
                              "publishableWithoutApplicationCompile": publishable,
                              "applicationCompileOwnedByParentRunner": True,
                              "environmentFailureIsNotSemanticFailure": True,
                              "cleanup": {"temporaryBuildRemoved": True, "binariesRetained": False,
                                          "candidateBuildIntermediatesCreated": False}}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    args = parser.parse_args()
    if args.timeout_seconds != 3600:
        parser.error("formal score timeout must be exactly 3600 seconds")
    report = score(args.source, args.output, time.monotonic() + args.timeout_seconds)
    print(json.dumps({"output": str(args.output), "publishableWithoutApplicationCompile":
                      report["diagnostics"]["publishableWithoutApplicationCompile"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
