#!/usr/bin/env python3
"""Validate rendered Compose UI infrastructure, never score canonical cases."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

if __package__:
    from .android_runner import ASSETS, JAVA
    from .android_robolectric_dependencies import prepare
    from .android_ui_resources import compile_ui_resources
else:
    from android_runner import ASSETS, JAVA
    from android_robolectric_dependencies import prepare
    from android_ui_resources import compile_ui_resources


def run(output, timeout):
    config_path = ASSETS / "common/ui/foundation.json"
    config = json.loads(config_path.read_text())
    result = {"canonicalSemanticScore": False, "scope": config["scope"], "status": "not_run"}
    logs = []
    try:
        with tempfile.TemporaryDirectory(prefix="android-ui-") as temporary:
            work = Path(temporary)
            environment = prepare(dict(config, runtimeTimeout=timeout), work)
            resources, provenance = compile_ui_resources(work / "robolectric-classpath.txt", work, JAVA.parent.parent)
            jars = [resources, *environment["jars"]]
            result["resourceInputs"] = provenance
            classes = work / "classes"
            classes.mkdir()
            classpath = os.pathsep.join(map(str, jars))
            sources = [config_path.parent / path for path in config["evaluatorSources"]] + [ASSETS / "common/Harness.kt"]
            result["sources"] = [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]
            compile_cp = os.pathsep.join(map(str, environment["compileOnlyJars"])) + os.pathsep + classpath
            command = [str(JAVA), "-Xmx1200m", "-cp", str(environment["compiler"]) + os.pathsep + classpath,
                       "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect", "-jvm-target", "17",
                       "-classpath", compile_cp, f"-Xplugin={environment['plugin']}", *environment["compilerArgs"],
                       "-d", str(classes), *map(str, sources)]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            logs.append(proc.stdout + proc.stderr)
            result["runtimeCompile"] = {"passed": proc.returncode == 0}
            if proc.returncode:
                raise RuntimeError("UI probe compilation failed")
            command = [str(JAVA), "-Xmx768m", *environment["jvmArgs"], "--add-opens=java.base/java.io=ALL-UNNAMED",
                       "-cp", str(classes) + os.pathsep + classpath, environment["mainClass"], config["testClass"], *config["keys"]]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            logs.append(proc.stdout + proc.stderr)
            rows = [json.loads(line.removeprefix("RUNTIME_RESULT ")) for line in proc.stdout.splitlines() if line.startswith("RUNTIME_RESULT ")]
            result.update(observations=rows, runtimeCommand=command, executionEnvironment="host_jvm_robolectric_rendered_compose")
            result["status"] = "passed" if proc.returncode == 0 and len(rows) == len(config["keys"]) and all(row["status"] == "pass" for row in rows) else "failed"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        if isinstance(error, subprocess.CalledProcessError):
            logs.append(error.stdout or "")
            logs.append(error.stderr or "")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".log").write_text("\n".join(logs))
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    with (ASSETS / ".build.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = run(args.output.resolve(), args.timeout)
    print(json.dumps({"status": result["status"], "error": result.get("error"), "output": str(args.output)}))
