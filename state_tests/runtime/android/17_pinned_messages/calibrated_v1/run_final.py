#!/usr/bin/env python3
"""Run nine isolated immutable Task17 Android final runtime slices."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = ROOT / "_sources/element-x-android"
TASK = "17_pinned_messages"
COMMIT = "eff868ddf9e1caef8182e55ac59054e81526a68f"
TREE = "0cd8a58632515f8e0f6fb669b02c8b35614d9181"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
sys.path.insert(0, str(ROOT / "scripts/runtime_semantics"))
import android_robolectric
import android_robolectric_dependencies
from android_robolectric_ui_resources import compile_resources


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def configuration(key: str, output: Path) -> tuple[dict, list[dict]]:
    template = ROOT / "experiment_results/runtime_transition_20261019/android_base_followup/task12-presenter/base-v4.config.json"
    config = json.loads(template.read_text())
    prefix = "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/"
    config.update(
        scope=f"task17_final_calibrated_v1_{key}",
        runtimeScope="immutable_final_provider_presenter_factory_action_and_sdk_effect",
        testClass="runtime.FinalRuntimeTest",
        keys=[key],
        entrypoints=[
            prefix + "pinned/list/PinnedMessagesListPresenter.kt",
            prefix + "pinned/DefaultIsPinnedMessagesFeatureEnabled.kt",
        ],
        evaluatorSources=[str(HERE / "FinalRuntimeTest.kt"), str(HERE.parents[1] / "common/Anvil.kt")],
        offlineDependencies=True,
    )
    config["resources"] = [item for item in config["resources"] if item["package"] in (
        "io.element.android.libraries.ui.strings",
        "io.element.android.libraries.designsystem",
        "io.element.android.libraries.matrix.ui",
    )]
    for item in config["resources"]:
        if item["package"] == "io.element.android.libraries.designsystem":
            item["files"] += ["libraries/designsystem/src/main/res/drawable/ic_developer_options.xml"]
    config["dependencies"] = [item for item in config["dependencies"] if item[0] != "io.coil-kt.coil3"]
    for item in config["dependencies"]:
        if item[0] == "androidx.compose.material":
            item[2] = "1.6.8"
        elif item[0] == "androidx.compose.material3":
            item[2] = "1.2.1"
    config["alignedGroups"] += [["androidx.compose.material", "1.6.8"], ["androidx.compose.material3", "1.2.1"]]
    config["dependencyCatalog"]["libraries"] += [
        "coil_compose", "jsoup", "sigpwned_emoji4j", "androidx_constraintlayout_compose",
        "matrix_richtexteditor", "matrix_richtexteditor_compose", "androidx_recyclerview",
    ]
    config["dependencies"].append(["androidx.media3", "media3-common", "1.4.1"])
    config["resources"] += [{
        "package": "io.element.android.features.location.api",
        "files": ["features/location/api/src/main/res/drawable/blurred_map.png", "_evaluator_generated/res/values/location_defaults.xml"],
    }]
    config_path = output.with_suffix(".config.json")
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    return config, [record(template), record(config_path)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--only", choices=[case["key"] for case in json.loads(CONTRACT.read_text())["cases"]])
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Preserve old evidence; choose a new directory: {output_dir}")
    output_dir.mkdir(parents=True)
    cases_dir = output_dir / "cases"
    cases_dir.mkdir()
    contract = json.loads(CONTRACT.read_text())
    resolved = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", f"{COMMIT}^{{commit}}"], text=True).strip()
    tree = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", f"{COMMIT}^{{tree}}"], text=True).strip()
    if (resolved, tree) != (COMMIT, TREE):
        raise RuntimeError("Immutable final identity mismatch")

    defaults = HERE.parent / "empty_ui" / "res/values/location_defaults.xml"
    original_compile = android_robolectric.compile_resources
    original_closure = android_robolectric.closure
    original_prepare = android_robolectric.prepare
    original_seed = android_robolectric_dependencies.seed_repository
    current_output: Path | None = None
    metadata_records: dict[str, dict] = {}

    def resources(candidate, config, work, java_home):
        read_original = candidate.read
        candidate.read = lambda path: defaults.read_bytes() if path == "_evaluator_generated/res/values/location_defaults.xml" else read_original(path)
        try:
            return compile_resources(candidate, config, work, java_home)
        finally:
            candidate.read = read_original

    def seed_metadata(repository):
        original_seed(repository)
        coordinates = [("androidx.compose.material", name, "1.6.8") for name in ("material", "material-ripple", "material-icons-core")]
        coordinates.append(("androidx.compose.material3", "material3", "1.2.1"))
        for group, name, version in coordinates:
            relative = Path(group.replace(".", "/")) / name / version / f"{name}-{version}.jar"
            target = HERE.parent / "empty_ui" / ".dependencies" / relative
            if not target.exists():
                with urllib.request.urlopen("https://dl.google.com/dl/android/maven2/" + relative.as_posix(), timeout=30) as response:
                    data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024 or not data.startswith(b"PK"):
                    raise ValueError("Refusing oversized or non-JAR metadata")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            metadata_records[str(target)] = record(target)
            linked = repository / relative
            if not linked.exists():
                linked.parent.mkdir(parents=True, exist_ok=True)
                linked.symlink_to(target)

    def prepare(config, work):
        environment = original_prepare(config, work)
        assert current_output is not None
        environment["jvmArgs"] += [f"-Druntime.contract.path={CONTRACT}", f"-Druntime.rendered.output={current_output.with_suffix('')}"]
        return environment

    android_robolectric.compile_resources = resources
    android_robolectric.closure = lambda repository, ref, seeds: original_closure(repository, ref, seeds) + [
        "appconfig/src/main/kotlin/io/element/android/appconfig/TimelineConfig.kt",
        "appconfig/src/main/kotlin/io/element/android/appconfig/OnBoardingConfig.kt",
    ]
    android_robolectric.prepare = prepare
    android_robolectric_dependencies.seed_repository = seed_metadata
    rows = []
    raw_reports = []
    started = time.monotonic()
    lock_path = ROOT / "state_tests/runtime/android/.build.lock"
    try:
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            selected = [case for case in contract["cases"] if args.only is None or case["key"] == args.only]
            for case in selected:
                key = case["key"]
                raw = cases_dir / f"{case['caseId']}.raw.json"
                current_output = raw
                _config, packaging = configuration(key, raw)
                result = android_robolectric.run_slice(TASK, "final", SOURCE, HERE, raw.with_suffix(".config.json"), raw, args.timeout)
                result.setdefault("provenance", {})["packagingSources"] = packaging + [record(defaults)]
                raw.write_text(json.dumps(result, indent=2) + "\n")
                raw_reports.append(record(raw))
                observation = next((row for row in result.get("observations", []) if row.get("key") == key), None)
                if observation is None:
                    observation = {"key": key, "status": "not_scored", "reason": result.get("error") or "No runtime observation", "observed": {}, "checkpoints": [], "invariantChecks": []}
                if result.get("runtimeCompile", {}).get("status") != "passed" or result.get("error"):
                    observation["status"] = "not_scored"
                    observation["reason"] = result.get("error") or "Runtime slice did not compile; not a semantic failure."
                row = copy.deepcopy(observation)
                row.update(caseId=case["caseId"], traceDigest=case["traceDigest"], given=case["given"], event=case["event"], expected=case["expected"], runtimeReport=record(raw))
                rows.append(row)
    finally:
        android_robolectric.compile_resources = original_compile
        android_robolectric.closure = original_closure
        android_robolectric.prepare = original_prepare
        android_robolectric_dependencies.seed_repository = original_seed

    counts = {status: sum(row["status"] == status for row in rows) for status in ("pass", "fail", "not_scored")}
    report = {
        "schemaVersion": 2,
        "taskId": TASK,
        "platform": "android",
        "role": "final",
        "candidate": {"commit": COMMIT, "tree": TREE, "source": str(SOURCE)},
        "contract": record(CONTRACT),
        "runtimeDomain": "host_jvm_robolectric_real_production_transition",
        "applicationCompile": {"status": "not_run", "passed": None},
        "runtimeCompile": {"status": "passed" if counts["not_scored"] == 0 else "incomplete", "isolatedSlices": len(rows)},
        "semantic": {"counts": counts, "cases": rows},
        "status": "candidate" if len(rows) == 9 and counts == {"pass": 9, "fail": 0, "not_scored": 0} else "incomplete",
        "durationSeconds": round(time.monotonic() - started, 3),
        "isolation": {"oneRunSlicePerCase": True, "separateCompilerTemporaryDirectoryPerCase": True, "separateJvmPerCase": True, "externalDeviceUsed": False},
        "provenance": {
            "runner": record(Path(__file__)),
            "evaluatorSources": [record(HERE / "FinalRuntimeTest.kt"), record(HERE.parents[1] / "common/Anvil.kt")],
            "rawReports": raw_reports,
            "metadataArtifacts": list(metadata_records.values()),
        },
        "cleanup": {"compilerTemporaryDirectories": "removed by android_robolectric.run_slice", "buildLock": "released"},
        "limitations": ["Host Robolectric production slices, not a full Android application build or device run."],
    }
    output = output_dir / "android_17_pinned_messages_final_calibrated_v1.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(output), "counts": counts, "runtimeCompile": report["runtimeCompile"]}))
    return 0 if report["status"] == "candidate" else 1


if __name__ == "__main__":
    raise SystemExit(main())
