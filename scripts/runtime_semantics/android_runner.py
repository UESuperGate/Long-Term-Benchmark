#!/usr/bin/env python3
"""Run evaluator JUnit adapters against unmodified candidate Kotlin source slices.

This is a host domain/Compose-runtime test, not an Android app build or UI test.
Git sources use an isolated index for base + archived patch reconstruction.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
import importlib

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "state_tests/runtime/android"
CACHE = Path.home() / ".gradle/caches/modules-2/files-2.1"
JAVA = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java")
ARCH = "libraries/architecture/src/main/kotlin/io/element/android/libraries/architecture/"
FEATURE = "features/{feature}/impl/src/main/kotlin/io/element/android/features/{package}/impl/"


def cached(group, artifact, version):
    files = sorted((CACHE / group / artifact / version).glob("*/*.jar"))
    if len(files) != 1:
        raise RuntimeError(f"Expected cached {group}:{artifact}:{version}, found {len(files)}")
    return files[0]


def adapter_dependency(group, artifact, version):
    directory = CACHE / group / artifact / version
    files = sorted([*directory.glob("*/*.jar"), *directory.glob("*/*.aar")])
    if len(files) != 1:
        raise RuntimeError(f"Expected one cached dependency {group}:{artifact}:{version}, found {len(files)}")
    return dependency_jar(files[0])


def dependency_jar(path):
    if not path.is_file():
        raise RuntimeError(f"Missing runtime dependency {path}")
    if path.suffix == ".jar":
        return path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    jar = ASSETS / ".dependencies" / f"{path.stem}-{digest[:12]}.jar"
    if not jar.exists():
        with zipfile.ZipFile(path) as archive:
            jar.write_bytes(archive.read("classes.jar"))
    return jar


def toolchain():
    deps = ASSETS / ".dependencies"
    deps.mkdir(exist_ok=True, parents=True)
    jars = []
    for artifact in ("runtime-desktop", "runtime-saveable-desktop"):
        jar = deps / f"{artifact}-1.7.3.jar"
        if not jar.exists():
            url = f"https://repo.maven.apache.org/maven2/org/jetbrains/compose/runtime/{artifact}/1.7.3/{jar.name}"
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read()
            jar.write_bytes(data)
        jars.append(jar)
    specs = [
        ("org.jetbrains.kotlin", "kotlin-stdlib", "2.1.20"),
        ("org.jetbrains.kotlin", "kotlin-reflect", "2.1.20"),
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm", "1.10.2"),
        ("org.jetbrains.kotlinx", "kotlinx-coroutines-test-jvm", "1.10.2"),
        ("org.jetbrains.kotlinx", "kotlinx-collections-immutable-jvm", "0.3.8"),
        ("junit", "junit", "4.13.2"),
        ("org.hamcrest", "hamcrest-core", "1.3"),
        ("com.google.code.gson", "gson", "2.11.0"),
        ("org.jetbrains", "annotations", "23.0.0"),
        ("org.jetbrains.intellij.deps", "trove4j", "1.0.20200330"),
        ("androidx.collection", "collection-jvm", "1.4.4"),
        ("com.freeletics.flowredux", "flowredux-jvm", "1.2.2"),
        ("com.freeletics.flowredux", "compose-jvm", "1.2.2"),
        ("com.freeletics.mad", "state-machine-jvm", "0.24.0"),
        ("com.freeletics.khonshu", "state-machine-jvm", "0.24.0"),
    ]
    jars += [cached(*s) for s in specs]
    compiler = cached("org.jetbrains.kotlin", "kotlin-compiler-embeddable", "2.1.20")
    plugin = cached("org.jetbrains.kotlin", "kotlin-compose-compiler-plugin-embeddable", "2.1.20")
    return jars, compiler, plugin


class Candidate:
    def __init__(self, source, task, role, work):
        self.source = source
        self.env = os.environ.copy()
        self.git_source = not (source / "gradlew").exists()
        self.provenance = {"source": str(source), "role": role, "productionSources": []}
        if self.git_source:
            self.env["GIT_INDEX_FILE"] = str(work / "candidate.index")
            if role == "agent":
                raise ValueError(
                    "Android agent candidates must be supplied as a standalone project directory; "
                    "immutable repository sources are reserved for base/final refs"
                )
            ref = task["android"]["finalCommit" if role == "final" else "baseCommit"]
            self.git("read-tree", ref)
            self.provenance["commit"] = ref
            self.provenance["tree"] = self.git("write-tree").decode().strip()
        elif role == "agent":
            self.provenance.update(
                candidateMode="standalone_directory",
                archivedPatchApplied=False,
                candidateRootSha256=self.directory_digest(),
            )

    def directory_digest(self):
        digest = hashlib.sha256()
        excluded = {".git", ".gradle", "build", ".idea"}
        for path in sorted(self.source.rglob("*")):
            if not path.is_file() or any(part in excluded for part in path.relative_to(self.source).parts):
                continue
            relative = path.relative_to(self.source).as_posix().encode()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            data = path.read_bytes()
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
        return digest.hexdigest()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.source), *args], env=self.env, stderr=subprocess.PIPE)

    def read(self, path):
        data = self.git("show", f":{path}") if self.git_source else (self.source / path).read_bytes()
        self.provenance["productionSources"].append({"path": path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        return data

    def exists(self, path):
        if not self.git_source:
            return (self.source / path).is_file()
        try:
            self.git("cat-file", "-e", f":{path}")
            return True
        except subprocess.CalledProcessError:
            return False


def verify_completeness(case, contract_case, provenance, scoring_exclusion=None):
    """A passing JUnit method is insufficient without the whole canonical observation."""
    if case["status"] == "not_scored":
        return
    missing = []
    mismatches = []
    def compare(expected, actual, prefix=""):
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                mismatches.append({"field": prefix, "expected": expected, "observed": actual})
                return
            for key, value in expected.items():
                path = f"{prefix}.{key}" if prefix else key
                if key not in actual:
                    missing.append(path)
                else:
                    compare(value, actual[key], path)
        elif expected != actual:
            mismatches.append({"field": prefix, "expected": expected, "observed": actual})
    compare(contract_case["expected"], case.get("observed", {}))
    invariants = {v.get("invariant"): v for v in case.get("invariantChecks", [])}
    missing_invariants = [v for v in contract_case.get("invariants", []) if v not in invariants or invariants[v].get("status") not in ("pass", "fail") or "evidence" not in invariants[v]]
    case["coverage"] = {"missingExpectedFields": missing, "missingInvariants": missing_invariants, "mismatches": mismatches}
    if scoring_exclusion:
        case["junitStatus"] = case["status"]
        case["status"] = "not_scored"
        case["scoringExclusion"] = scoring_exclusion
        case["reason"] = scoring_exclusion["reason"]
    elif missing or missing_invariants or len(case.get("checkpoints", [])) < 2 or not provenance.get("productionSources"):
        case["junitStatus"] = case["status"]
        case["status"] = "not_scored"
        case["reason"] = "Incomplete canonical runtime evidence; see coverage."
    elif mismatches or any(v.get("status") == "fail" for v in invariants.values()):
        case["status"] = "fail"
        case["reason"] = case.get("reason") or "Runtime observation differs from canonical contract."


def _load_adapter_config(config_path):
    config = json.loads(config_path.read_text())
    parent = config.pop("extends", None)
    if parent is None:
        return config
    base = _load_adapter_config((config_path.parent / parent).resolve())
    base.update(config)
    return base


def run(task_id, role, source, output, timeout, adapter_config=None):
    start = time.monotonic()
    task = json.loads((ROOT / "benchmark_tasks" / task_id / "task.json").read_text())
    contract = json.loads((ROOT / "benchmark_tasks" / task_id / "transitions.json").read_text())
    result = {
        "schemaVersion": 1, "taskId": task_id, "platform": "android", "role": role,
        "observationMode": "runtime_state_transition",
        "compile": {"passed": None, "status": "not_run", "scope": "android_application", "reason": "Host domain compilation does not establish app build success."},
        "runtimeCompile": {"passed": None, "status": "not_run", "scope": "candidate_production_slice_and_evaluator_adapter"},
        "semantic": {"cases": [{"caseId": c["caseId"], "key": c["key"], "traceDigest": c["traceDigest"], "status": "not_scored", "observed": {}, "checkpoints": [], "invariantChecks": [], "reason": "Runtime adapter not implemented for this contract."} for c in contract["cases"]]},
        "diagnostics": {"adapter": "not_implemented", "device": "not_used", "uiCoverage": False},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".log")
    logs = []
    try:
        config_path = Path(adapter_config).resolve() if adapter_config else ASSETS / task_id / "adapter.json"
        if not config_path.exists():
            return result
        config = _load_adapter_config(config_path)
        jars, compiler, plugin = toolchain()
        with tempfile.TemporaryDirectory(prefix="android-runtime-") as tmp:
            work = Path(tmp)
            candidate = Candidate(source, task, role, work)
            result["provenance"] = candidate.provenance
            result["provenance"]["contractSha256"] = hashlib.sha256((ROOT / "benchmark_tasks" / task_id / "transitions.json").read_bytes()).hexdigest()
            if adapter_config is None:
                for preferred in config.get("preferredAdapters", []):
                    preferred_path = config_path.parent / preferred
                    preferred_config = _load_adapter_config(preferred_path)
                    if all(candidate.exists(path) for path in preferred_config["sources"]):
                        config = preferred_config
                        config_path = preferred_path
                        break
                if not all(candidate.exists(path) for path in config["sources"]):
                    for alternate in config.get("alternatives", []):
                        alternate_path = config_path.parent / alternate
                        alternate_config = _load_adapter_config(alternate_path)
                        if all(candidate.exists(path) for path in alternate_config["sources"]):
                            config = alternate_config
                            config_path = alternate_path
                            break
            result["diagnostics"]["adapterConfiguration"] = str(config_path)
            result["provenance"]["adapterConfigurationSha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest()
            ui_runtime = config.get("runtime") == "robolectric" and config.get("uiRuntime", False)
            if not ui_runtime:
                jars += [adapter_dependency(*dependency) for dependency in config.get("dependencies", [])]
            runtime_options = {}
            excluded_common = set()
            if ui_runtime:
                module_name = f"{__package__}.android_robolectric_dependencies" if __package__ else "android_robolectric_dependencies"
                provider = importlib.import_module(module_name)
                runtime_options = provider.prepare(dict(config, runtimeTimeout=max(1, timeout - (time.monotonic() - start))), work)
                resource_module = f"{__package__}.android_ui_resources" if __package__ else "android_ui_resources"
                resource_provider = importlib.import_module(resource_module)
                resource_jar, resource_inputs = resource_provider.compile_ui_resources(
                    work / "robolectric-classpath.txt", work, JAVA.parent.parent, candidate, config)
                jars = [resource_jar, *runtime_options["jars"]]
                compiler, plugin = runtime_options["compiler"], runtime_options["plugin"]
                excluded_common = set(runtime_options["excludedCommonSources"])
                runtime_options["jvmArgs"] = [*runtime_options["jvmArgs"], "--add-opens=java.base/java.io=ALL-UNNAMED"]
                runtime_options["scope"] = config.get("runtimeScope", "android_production_rendered_compose")
                result["provenance"].update(resourceInputs=resource_inputs, dependencyPom=runtime_options["dependencyPom"],
                                            buildVariantFields=config.get("buildConfig", {}))
                result["diagnostics"]["uiHarness"] = "real_androidx_compose_test_rule"
            elif config.get("runtime") == "robolectric":
                module_name = f"{__package__}.android_robolectric_dependencies" if __package__ else "android_robolectric_dependencies"
                provider = importlib.import_module(module_name)
                foundation = ASSETS / config.get("robolectricFoundation", "08_threads")
                if config.get("robolectricClasspath"):
                    classpath_path = ASSETS / config["robolectricClasspath"]
                    foundation_jars = [dependency_jar(Path(path)) for path in classpath_path.read_text().strip().split(os.pathsep)]
                    result["provenance"]["robolectricClasspathSha256"] = hashlib.sha256(classpath_path.read_bytes()).hexdigest()
                else:
                    foundation_jars = provider.resolve(foundation, JAVA.parent.parent, max(1, timeout - (time.monotonic() - start)))
                jars = foundation_jars + [p for p in jars if not p.name.startswith(("runtime-desktop", "runtime-saveable-desktop")) and p not in foundation_jars]
                compiler = cached("org.jetbrains.kotlin", "kotlin-compiler-embeddable", "2.2.10")
                plugin = cached("org.jetbrains.kotlin", "kotlin-compose-compiler-plugin-embeddable", "2.2.10")
                runtime_options = {"jvmArgs": [*provider.runtime_options(foundation), "--add-opens=java.base/java.io=ALL-UNNAMED"], "executionEnvironment": "host_jvm_robolectric",
                                   "framework": "JUnit4 / Robolectric / real AndroidX Compose and DataStore", "scope": config.get("runtimeScope", "android_production_components")}
                result["diagnostics"]["robolectricFoundation"] = str(foundation)
            paths = config["sources"]
            sources = []
            for index, path in enumerate(paths):
                dest = work / f"{index}_{Path(path).name}"
                dest.write_bytes(candidate.read(path))
                sources.append(dest)
            sources += [path for path in sorted((ASSETS / "common").glob("*.kt")) if path.name not in excluded_common]
            if "evaluatorSources" in config:
                sources += [(config_path.parent / path).resolve() for path in config["evaluatorSources"]]
            else:
                sources += sorted(config_path.parent.glob("*.kt"))
            result["provenance"]["evaluatorSources"] = [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources if p.is_relative_to(ASSETS)]
            if ui_runtime:
                result["provenance"]["evaluatorSources"] += runtime_options["evaluatorSources"]
            cp = os.pathsep.join(map(str, jars))
            compile_cp = cp
            if runtime_options.get("compileOnlyJars"):
                compile_cp = os.pathsep.join(map(str, runtime_options["compileOnlyJars"])) + os.pathsep + cp
            if config.get("androidCompileSdk"):
                android_jar = Path.home() / "Library/Android/sdk/platforms" / f"android-{config['androidCompileSdk']}" / "android.jar"
                if not android_jar.is_file():
                    raise RuntimeError(f"Missing Android compile SDK {android_jar}")
                compile_cp = str(android_jar) + os.pathsep + cp
                result["provenance"]["androidCompileSdk"] = {"path": str(android_jar), "sha256": hashlib.sha256(android_jar.read_bytes()).hexdigest()}
            if config.get("runtime") == "robolectric" and not ui_runtime:
                bridge = ASSETS / config.get("robolectricBridge", "08_threads/robolectric/EvidenceRobolectricRunner.java")
                launcher = bridge.parent / "RobolectricMain.java"
                java_sources = [bridge, launcher]
                classes = work / "classes"
                classes.mkdir(exist_ok=True)
                result["provenance"]["evaluatorSources"] += [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in java_sources]
                proc = subprocess.run([str(JAVA.parent / "javac"), "-cp", cp, "-d", str(classes), *map(str, java_sources)], capture_output=True, text=True,
                                      timeout=max(1, timeout - (time.monotonic() - start)))
                logs.append(proc.stdout + proc.stderr)
                if proc.returncode:
                    raise RuntimeError("Robolectric evidence bridge compilation failed")
                cp = str(classes) + os.pathsep + cp
                compile_cp = str(classes) + os.pathsep + compile_cp
            command = [str(JAVA), "-Xmx1200m", "-cp", str(compiler) + os.pathsep + cp, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect", "-jvm-target", "17", "-classpath", compile_cp, f"-Xplugin={plugin}", *runtime_options.get("compilerArgs", []), "-d", str(work / "classes"), *map(str, sources)]
            result["runtimeCompile"]["command"] = command
            proc = subprocess.run(command, capture_output=True, text=True, timeout=max(1, timeout - (time.monotonic() - start)))
            logs.append(proc.stdout + proc.stderr)
            result["runtimeCompile"].update(passed=proc.returncode == 0, status="passed" if proc.returncode == 0 else "adapter_compile_failed")
            if proc.returncode:
                raise RuntimeError("Candidate production slice / evaluator adapter compilation failed; see log.")
            keys = [c["key"] for c in contract["cases"]]
            main_class = "runtime.foundation.RobolectricMain" if config.get("runtime") == "robolectric" else "runtime.HarnessKt"
            command = [str(JAVA), "-Xmx768m", *runtime_options.get("jvmArgs", []), "-cp", str(work / "classes") + os.pathsep + cp, main_class, config["testClass"], *keys]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=max(1, timeout - (time.monotonic() - start)))
            logs.append(proc.stdout + proc.stderr)
            rows = {}
            for line in proc.stdout.splitlines():
                if line.startswith("RUNTIME_RESULT "):
                    row = json.loads(line.removeprefix("RUNTIME_RESULT "))
                    rows[row["key"]] = row
            for case in result["semantic"]["cases"]:
                if case["key"] in rows:
                    case.update(rows[case["key"]])
                else:
                    case["reason"] = "No JUnit runtime observation returned for case."
                canonical = next(c for c in contract["cases"] if c["key"] == case["key"])
                verify_completeness(case, canonical, candidate.provenance, config.get("scoringExclusions", {}).get(case["key"]))
            result["diagnostics"]["adapter"] = "ready" if proc.returncode == 0 else "runtime_failed"
            result["runtime"] = {"command": command, "exitCode": proc.returncode, "executionEnvironment": "host_jvm", "framework": "JUnit4 with real Compose Recomposer", "scope": "host_domain_presenter", "dependencies": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in jars]}
            for field in ("executionEnvironment", "framework", "scope"):
                if field in runtime_options:
                    result["runtime"][field] = runtime_options[field]
    except (Exception, subprocess.SubprocessError) as exc:
        reason = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, subprocess.CalledProcessError):
            reason += "\n" + exc.stderr.decode(errors="replace")
        logs.append(reason)
        result["diagnostics"].update(adapter="adapter_failed", error=reason)
        for case in result["semantic"]["cases"]:
            if case["status"] == "not_scored":
                case["reason"] = reason
    finally:
        data = "\n".join(logs).encode()
        log_path.write_bytes(data)
        result["diagnostics"]["log"] = {"path": str(log_path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        result["durationSeconds"] = round(time.monotonic() - start, 3)
        output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_with_supplemental(task_id, role, source, output, timeout, adapter_config=None,
                          include_supplemental=True):
    start = time.monotonic()
    ASSETS.mkdir(parents=True, exist_ok=True)
    with (ASSETS / ".build.lock").open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                remaining = timeout - (time.monotonic() - start)
                if remaining <= 0:
                    raise TimeoutError("Android primary build lock exceeded the runtime budget")
                time.sleep(min(0.1, remaining))
        result = run(task_id, role, source, output, max(0, timeout - (time.monotonic() - start)),
                     adapter_config=adapter_config)
    # Supplemental children acquire the same lock themselves.
    module_name = f"{__package__}.android_supplemental" if __package__ else "android_supplemental"
    supplemental = importlib.import_module(module_name)
    if include_supplemental and task_id in supplemental.RECIPES:
        recipes = (supplemental.RECIPES[task_id],) + supplemental.EXTRA_RECIPES.get(task_id, ())
        for directory, _ in recipes:
            remaining = timeout - (time.monotonic() - start)
            if remaining <= 0:
                result["diagnostics"]["supplementalSkipped"] = "Runtime slices exhausted the shared runtime budget."
                break
            try:
                extra = supplemental.run_supplemental(task_id, role, source,
                    output_dir=output.parent / "supplemental" / directory, timeout=remaining, lock_timeout=0,
                    slice_name=directory)
                contract_path = ROOT / "benchmark_tasks" / task_id / "transitions.json"
                result = supplemental.merge_supplemental(result, [extra], json.loads(contract_path.read_text()),
                    contract_sha256=hashlib.sha256(contract_path.read_bytes()).hexdigest())
            except Exception as exc:
                result["diagnostics"].setdefault("supplementalErrors", []).append({
                    "slice": directory, "error": f"{type(exc).__name__}: {exc}"})
    result["durationSeconds"] = round(time.monotonic() - start, 3)
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True)
    p.add_argument("--role", choices=["base", "final", "agent"], required=True)
    p.add_argument("--source", type=Path, default=ROOT / "_sources/element-x-android")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--timeout", type=float, default=180)
    p.add_argument("--adapter-config", type=Path,
                   help="Force one evaluator adapter without preferred/alternate fallback")
    p.add_argument("--no-supplemental", action="store_true")
    args = p.parse_args()
    result = run_with_supplemental(
        args.task, args.role, args.source.resolve(), args.output.resolve(), args.timeout,
        adapter_config=args.adapter_config,
        include_supplemental=not args.no_supplemental,
    )
    print(json.dumps({"taskId": args.task, "role": args.role, "cases": {status: sum(c["status"] == status for c in result["semantic"]["cases"]) for status in ("pass", "fail", "not_scored")}, "output": str(args.output)}))


if __name__ == "__main__":
    main()
