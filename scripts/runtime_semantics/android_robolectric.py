#!/usr/bin/env python3
"""Real Android runtime foundation for immutable Kotlin transition adapters.

The self-test validates infrastructure, never a canonical semantic score.
Integration API: resolve(adapter, java_home, timeout) supplies real jar paths;
runtime_options(adapter) supplies Robolectric SDK JVM options. The shared runner
remains responsible for candidate loading and scoring.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

if __package__:
    from .android_robolectric_dependencies import prepare, resolve, runtime_options
    from . import android_runner
    from .android_robolectric_resources import compile_resources
    from .android_robolectric_sources import closure
else:
    from android_robolectric_dependencies import prepare, resolve, runtime_options
    import android_runner
    from android_robolectric_resources import compile_resources
    from android_robolectric_sources import closure

ROOT = Path(__file__).resolve().parents[2]
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")


def candidate_dependencies(candidate, config):
    catalog_config = config.get("dependencyCatalog")
    if not catalog_config:
        return config
    data = candidate.read(catalog_config["path"])
    try:
        import tomllib
        catalog = tomllib.loads(data.decode())
    except ImportError:
        catalog = json.loads(subprocess.check_output([
            "/opt/homebrew/bin/python3", "-c",
            "import json,sys,tomllib; json.dump(tomllib.loads(sys.stdin.read()),sys.stdout)",
        ], input=data))
    entries = list(config.get("dependencies", []))
    resolved = {}
    for alias in catalog_config["libraries"]:
        value = catalog["libraries"][alias]
        if isinstance(value, str):
            group, artifact, version = value.split(":")
        else:
            group, artifact = value["module"].split(":")
            version = value["version"]
            if isinstance(version, dict):
                version = catalog["versions"][version["ref"]]
        entries = [entry for entry in entries if entry[:2] != [group, artifact]]
        entries.append([group, artifact, version])
        resolved[alias] = [group, artifact, version]
    candidate.provenance["catalogDependencies"] = resolved
    return dict(config, dependencies=entries)



def run_slice(task_id: str, role: str, source: Path, adapter: Path, configuration: Path, output: Path, timeout: float):
    """Execute a configured immutable production slice without changing shared code."""
    start = time.monotonic()
    config = json.loads(configuration.read_text())
    result = {"scope": config["scope"], "taskId": task_id, "role": role, "canonicalSemanticScore": False, "status": "not_run"}
    logs = []
    try:
        with tempfile.TemporaryDirectory(prefix="android-robolectric-") as directory:
            work = Path(directory)
            task = json.loads((ROOT / "benchmark_tasks" / task_id / "task.json").read_text())
            candidate = android_runner.Candidate(source, task, role, work)
            result["provenance"] = candidate.provenance
            config = candidate_dependencies(candidate, config)
            environment = prepare(dict(config, runtimeTimeout=timeout), work)
            jars = environment["jars"]
            classpath = os.pathsep.join(map(str, jars))
            classes = work / "classes"
            classes.mkdir()
            source_paths = config["sources"]
            if config.get("sourceClosure"):
                if not candidate.git_source:
                    raise ValueError("Source closure requires an immutable candidate tree")
                source_paths = closure(source, candidate.provenance["tree"], config["entrypoints"])
                result["provenance"]["resolvedSourceManifest"] = source_paths
                result["provenance"]["sourceClosureGeneratorSha256"] = hashlib.sha256(
                    Path(__file__).with_name("android_robolectric_sources.py").read_bytes()).hexdigest()
            resource_jar = compile_resources(candidate, config, work, JAVA_HOME)
            if resource_jar:
                jars.append(resource_jar)
                classpath = os.pathsep.join(map(str, jars))
                result["provenance"]["buildVariantFields"] = config.get("buildConfig", {})
            sources = []
            for index, path in enumerate(source_paths):
                destination = work / f"{index}_{Path(path).name}"
                destination.write_bytes(candidate.read(path))
                sources.append(destination)
            evaluator = [configuration.parent / path for path in config["evaluatorSources"]]
            evaluator.append(ROOT / "state_tests/runtime/android/common/Harness.kt")
            result["provenance"]["evaluatorSources"] = [
                {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in evaluator
            ] + environment["evaluatorSources"]
            result["provenance"]["dependencyPom"] = environment["dependencyPom"]
            result["provenance"]["configurationSha256"] = hashlib.sha256(configuration.read_bytes()).hexdigest()
            compiler = environment["compiler"]
            plugin = environment["plugin"]
            runtime_classpath = str(classes) + os.pathsep + classpath
            compile_classpath = os.pathsep.join(map(str, environment["compileOnlyJars"])) + os.pathsep + runtime_classpath
            command = [str(JAVA_HOME / "bin/java"), "-Xmx1200m", "-cp", str(compiler) + os.pathsep + classpath,
                       "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect",
                       "-jvm-target", "17", "-classpath", compile_classpath, f"-Xplugin={plugin}",
                       *environment["compilerArgs"], "-d", str(classes), *map(str, sources + evaluator)]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            logs.append(proc.stdout + proc.stderr)
            result["runtimeCompile"] = {"status": "passed" if proc.returncode == 0 else "failed", "command": command}
            if proc.returncode:
                raise RuntimeError("Immutable Kotlin production slice compilation failed")
            command = [str(JAVA_HOME / "bin/java"), "-Xmx768m", *environment["jvmArgs"],
                       "-cp", runtime_classpath, environment["mainClass"], config["testClass"], *config["keys"]]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            logs.append(proc.stdout + proc.stderr)
            rows = [json.loads(line.removeprefix("RUNTIME_RESULT ")) for line in proc.stdout.splitlines() if line.startswith("RUNTIME_RESULT ")]
            evidence_present = all(len(row.get("checkpoints", [])) >= 2 for row in rows)
            passed = proc.returncode == 0 and len(rows) == len(config["keys"]) and all(row["status"] == "pass" for row in rows) and evidence_present
            result.update(status="passed" if passed else "failed", observations=rows,
                          runtimeCommand=command, dependencies=[{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in jars])
    except Exception as failure:
        result.update(status="failed", error=f"{type(failure).__name__}: {failure}")
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        log = output.with_suffix(".log")
        data = "\n".join(logs).encode()
        log.write_bytes(data)
        result.update(durationSeconds=round(time.monotonic() - start, 3), log={"path": str(log), "sha256": hashlib.sha256(data).hexdigest()})
        output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def self_test(adapter: Path, output: Path, timeout: float):
    start = time.monotonic()
    result = {"scope": "android_runtime_foundation", "canonicalSemanticScore": False, "status": "not_run"}
    logs = []
    try:
        jars = resolve(adapter, JAVA_HOME, timeout)
        classpath = os.pathsep.join(map(str, jars))
        with tempfile.TemporaryDirectory(prefix="android-robolectric-") as directory:
            sources = sorted((adapter / "robolectric").glob("*.java"))
            javac = [str(JAVA_HOME / "bin/javac"), "-cp", classpath, "-d", directory, *map(str, sources)]
            compiler = subprocess.run(javac, capture_output=True, text=True, timeout=timeout)
            logs.append(compiler.stdout + compiler.stderr)
            if compiler.returncode:
                raise RuntimeError("Robolectric foundation Java compilation failed")
            command = [str(JAVA_HOME / "bin/java"), "-Xmx768m", *runtime_options(adapter),
                       "-cp", directory + os.pathsep + classpath,
                       "org.junit.runner.JUnitCore", "runtime.foundation.AndroidTextRuntimeTest"]
            runtime = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            logs.append(runtime.stdout + runtime.stderr)
            result.update(status="passed" if runtime.returncode == 0 else "failed", exitCode=runtime.returncode,
                          runtimeCommand=command, sources=[{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
                          dependencies=[{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in jars])
    except Exception as failure:
        result.update(status="failed", error=f"{type(failure).__name__}: {failure}")
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        log = output.with_suffix(".log")
        data = "\n".join(logs).encode()
        log.write_bytes(data)
        result.update(durationSeconds=round(time.monotonic() - start, 3), log={"path": str(log), "sha256": hashlib.sha256(data).hexdigest()})
        output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--config", type=Path)
    parser.add_argument("--task", default="08_threads")
    parser.add_argument("--role", choices=["base", "final", "agent"], default="final")
    parser.add_argument("--source", type=Path, default=ROOT / "_sources/element-x-android")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assets = ROOT / "state_tests/runtime/android"
    with (assets / ".build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.self_test:
            result = self_test(assets / args.task, args.output.resolve(), args.timeout)
        else:
            result = run_slice(args.task, args.role, args.source.resolve(), assets / args.task,
                               args.config.resolve(), args.output.resolve(), args.timeout)
    print(json.dumps({"status": result["status"], "output": str(args.output), "error": result.get("error")}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
