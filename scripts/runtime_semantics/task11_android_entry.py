#!/usr/bin/env python3
"""Load Task11's real MessagesState with its complete production dependencies.

This probe only selects the exact harness. It assigns no semantic verdict and
never prepares Rust or builds the Android application.
"""
from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import android_robolectric
import android_runner
from android_robolectric_sources import closure
from android_robolectric_ui_resources import compile_resources
from task10_11_android_strict_common import bound_git_snapshot, patched_candidate, wall_deadline, write_json
from task11_android_resource_audit import record_slice_resources

TASK = "11_room_upgrade_navigation"
TASK_ROOT = ROOT / "state_tests/runtime/android" / TASK


def configuration(source: Path, role: str) -> dict:
    config = json.loads((TASK_ROOT / "rendered/adapter.json").read_text())
    config.update(scope="loaded_production_entry_capability", sourceClosure=False,
                  entrypoints=["features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesState.kt"],
                  testClass="runtime.ProductionEntryProbe", keys=["task11_entry"], scoringExclusions={},
                  evaluatorSources=[str(HERE / "tasks10_11/ProductionEntryProbe.kt"),
                                    str(ROOT / "state_tests/runtime/android/08_threads/robolectric/Anvil.kt"),
                                    str(TASK_ROOT / "messages/LocationBuildConfig.kt")])
    config["alignedGroups"].append(["androidx.collection", "1.5.0"])
    config["dependencies"] += [
        ["androidx.constraintlayout", "constraintlayout-compose", "1.1.1"],
        ["io.element.android", "wysiwyg", "2.38.3"],
        ["io.element.android", "wysiwyg-compose", "2.38.3"],
        ["com.github.matrix-org", "matrix-analytics-events", "0.28.0"],
        ["com.google.dagger", "dagger", "2.57.1"],
        ["com.vanniktech", "blurhash-android", "0.3.0"],
        ["com.google.android.material", "material", "1.12.0"],
        ["androidx.core", "core-splashscreen", "1.0.1"],
        ["dev.zacsweers.anvil", "annotations-jvm", "0.4.1"],
        ["androidx.media3", "media3-common", "1.7.1"],
        ["io.element.android", "emojibase-bindings", "1.4.2"],
        ["com.sigpwned", "emoji4j-core", "16.0.0"],
    ]
    task = json.loads((ROOT / "benchmark_tasks" / TASK / "task.json").read_text())
    with tempfile.TemporaryDirectory(prefix="task11-entry-config-") as tmp:
        candidate = android_runner.Candidate(source, task, role, Path(tmp))
        config["sources"] = closure(source, candidate.provenance["tree"], config["entrypoints"])
        for name in ("TimelineConfig", "LearnMoreConfig", "OnBoardingConfig"):
            path = f"appconfig/src/main/kotlin/io/element/android/appconfig/{name}.kt"
            if candidate.exists(path):
                config["sources"].append(path)
        paths = subprocess.check_output(["git", "-C", str(source), "ls-tree", "-r", "--name-only",
                                         candidate.provenance["tree"]], text=True).splitlines()
        modules = [
            ("libraries/textcomposer/impl", "io.element.android.libraries.textcomposer"),
            ("libraries/matrixui", "io.element.android.libraries.matrix.ui"),
            ("libraries/designsystem", "io.element.android.libraries.designsystem"),
            ("features/messages/impl", "io.element.android.features.messages.impl"),
            ("libraries/ui-strings", "io.element.android.libraries.ui.strings"),
            ("features/poll/api", "io.element.android.features.poll.api"),
            ("features/location/api", "io.element.android.features.location.api"),
            ("libraries/androidutils", "io.element.android.libraries.androidutils"),
        ]
        config["resources"] = [{"package": package, "files": [p for p in paths
            if p.startswith(module + "/src/main/res/") and "-" not in p.split("/res/")[1].split("/")[0]]}
            for module, package in modules]
        config["resources"].append({"package": "io.element.android.x", "files": [
            "app/src/main/res/values/themes.xml", "app/src/main/res/values/colors.xml",
            "app/src/main/res/drawable/transparent.xml"]})
    return config


def probe(task: str, source: Path, role: str, output: Path, timeout: float) -> dict:
    if task != TASK:
        raise ValueError("Task11-only production entry probe")
    started = time.monotonic()
    config = configuration(source, role)
    output.parent.mkdir(parents=True, exist_ok=True)
    config_path = output.with_suffix(".config.json")
    write_json(config_path, config)
    previous = android_robolectric.compile_resources
    try:
        android_robolectric.compile_resources = compile_resources
        with record_slice_resources():
            result = android_robolectric.run_slice(TASK, role, source, output.parent, config_path,
                                                   output, max(0, timeout - (time.monotonic() - started)))
    finally:
        android_robolectric.compile_resources = previous
    rows = result.get("observations", [])
    if result.get("runtimeCompile", {}).get("status") != "passed" or len(rows) != 1 or rows[0].get("status") != "pass":
        log = output.with_suffix(".log")
        errors = [line for line in log.read_text().splitlines() if ": error:" in line][:4] if log.exists() else []
        raise RuntimeError("Task11 production entry did not execute; no semantic failure assigned. " +
                           " | ".join(errors or [str(result.get("error", "see retained runtime log"))]))
    capability = rows[0].get("observed", {}).get("fullFeatureEntry")
    if type(capability) is not bool or not result.get("provenance", {}).get("productionSources"):
        raise RuntimeError("Task11 entry has no actual candidate production evidence")
    return {"fullFeatureEntry": capability, "report": str(output),
            "scope": "loaded production entry selection only; semantic verdict requires real UI prefix"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=3600)
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600:
        raise ValueError("Task11 entry timeout must be in (0, 3600]")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    with wall_deadline(args.timeout), (ROOT / "state_tests/runtime/android/.build.lock").open("a") as cache_lock:
        fcntl.flock(cache_lock, fcntl.LOCK_EX)
        with Path("/tmp/long-term-benchmark-android-full-build.lock").open("a") as global_lock:
            fcntl.flock(global_lock, fcntl.LOCK_EX)
            with bound_git_snapshot(args.source, args.output_dir / "work") as (control, snapshot), \
                    patched_candidate(control, args.source):
                result = probe(TASK, control, args.role, args.output_dir / "entry.json",
                               args.timeout - (time.monotonic() - started))
    write_json(args.output_dir / "selection.json", {**result, "sourceSnapshot": snapshot,
               "elapsedSeconds": round(time.monotonic() - started, 3), "semanticScoringPerformed": False,
               "applicationBuildStarted": False, "rustBuildStarted": False})
    print(json.dumps(result))


if __name__ == "__main__":
    main()
