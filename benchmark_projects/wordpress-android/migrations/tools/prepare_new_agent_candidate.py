#!/usr/bin/env python3
"""Prepare visible and hidden clean-room harnesses for WordPress tasks 03/04."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


TASKS = {
    "03_site_picker": {
        "baseOwner": "evaluator.sitepickerbase.SitePickerBaseOwnerActivity",
        "finalOwner": "evaluator.sitepicker.SitePickerRuntimeOwnerActivity",
        "profileFiles": (
            "org/wordpress/android/ui/main/ChooseSiteViewHolder.kt",
            "org/wordpress/android/ui/main/SiteViewModel.kt",
        ),
    },
    "04_new_stats": {
        "baseOwner": "evaluator.newstatsbase.NewStatsBaseOwnerActivity",
        "finalOwner": "evaluator.newstats.NewStatsRuntimeOwnerActivity",
        "profileFiles": (
            "org/wordpress/android/ui/newstats/repository/StatsResultCache.kt",
            "org/wordpress/android/ui/newstats/locations/LocationsViewModel.kt",
        ),
    },
}


def copytree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, dirs_exist_ok=True)


def rewrite_sources(build: str, main_roots: list[str], test_roots: list[str]) -> str:
    if "sourceSets.getByName(\"main\")" not in build:
        raise RuntimeError("Android build has no main source set")
    build = re.sub(
        r'sourceSets\.getByName\("main"\)\s*\{.*?\}',
        'sourceSets.getByName("main") {\n'
        '        manifest.srcFile("src/main/AndroidManifest.xml")\n'
        f'        java.srcDirs({", ".join(json.dumps(root) for root in main_roots)})\n'
        '    }',
        build,
        count=1,
        flags=re.DOTALL,
    )
    replacement = (
        'sourceSets.getByName("androidTest") {\n'
        f'        java.srcDirs({", ".join(json.dumps(root) for root in test_roots)})\n'
        '    }'
    ) if test_roots else 'sourceSets.getByName("androidTest") { java.srcDirs(emptyList<String>()) }'
    build = re.sub(
        r'sourceSets\.getByName\("androidTest"\)\s*\{.*?\}',
        replacement,
        build,
        count=1,
        flags=re.DOTALL,
    )
    return build.replace("jvmToolchain(21)", "jvmToolchain(21)")


def set_owner(manifest: Path, owner: str, application_name: str | None = None) -> None:
    ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
    tree = ET.parse(manifest)
    application = tree.getroot().find("application")
    if application is None:
        raise RuntimeError("Android manifest has no application")
    name = "{http://schemas.android.com/apk/res/android}name"
    exported = "{http://schemas.android.com/apk/res/android}exported"
    for activity in list(application.findall("activity")):
        application.remove(activity)
    if application_name is None:
        application.attrib.pop(name, None)
    else:
        application.set(name, application_name)
    ET.SubElement(application, "activity", {name: owner, exported: "false"})
    tree.write(manifest, encoding="unicode")


def prepare_visible(project: Path, migration: Path, task_id: str) -> None:
    evaluator = migration / "android/focused-runtime/evaluator"
    source = project / "src/main/java"
    scaffold = project / ".benchmark-scaffold/main"
    final_stubs = project / ".benchmark-scaffold/final-stubs"
    shutil.rmtree(source, ignore_errors=True)
    shutil.rmtree(project / ".benchmark-scaffold", ignore_errors=True)
    copytree(evaluator / "base-production", source)
    copytree(evaluator / "base-stubs", scaffold)
    copytree(evaluator / "base-main", scaffold)
    copytree(evaluator / "final-stubs", final_stubs)

    final_build = migration / "android/focused-runtime/final/build.gradle.kts"
    build = rewrite_sources(final_build.read_text(encoding="utf-8"), ["src/main/java", ".benchmark-scaffold/main"], [])
    (project / "build.gradle.kts").write_text(build, encoding="utf-8")
    set_owner(project / "src/main/AndroidManifest.xml", TASKS[task_id]["baseOwner"])


def detect_profile(project: Path, task_id: str) -> str:
    source = project / "src/main/java"
    return "final" if all((source / relative).is_file() for relative in TASKS[task_id]["profileFiles"]) else "base"


def prepare_hidden(project: Path, migration: Path, task_id: str) -> str:
    evaluator = migration / "android/focused-runtime/evaluator"
    profile = detect_profile(project, task_id)
    hidden = project / ".benchmark-evaluator"
    shutil.rmtree(hidden, ignore_errors=True)
    main = hidden / "main"
    tests = hidden / "androidTest"
    copytree(evaluator / f"{profile}-stubs", main)
    if task_id == "03_site_picker" and profile == "final":
        for relative in (
            "org/wordpress/android/ui/jetpackoverlay/individualplugin/WPJetpackIndividualPluginHelper.kt",
            "org/wordpress/android/viewmodel/Event.kt",
        ):
            source = evaluator / "base-stubs" / relative
            destination = main / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    copytree(evaluator / f"{profile}-main", main)
    copytree(evaluator / f"{profile}-runtime", tests)
    copytree(evaluator / "instrumentation", tests)

    final_build = migration / "android/focused-runtime/final/build.gradle.kts"
    build = rewrite_sources(final_build.read_text(encoding="utf-8"), ["src/main/java", ".benchmark-evaluator/main"], [".benchmark-evaluator/androidTest"])
    (project / "build.gradle.kts").write_text(build, encoding="utf-8")
    application_name = "org.wordpress.android.WordPress" if task_id == "03_site_picker" and profile == "final" else None
    set_owner(project / "src/main/AndroidManifest.xml", TASKS[task_id][f"{profile}Owner"], application_name)
    prepared = {
        "schemaVersion": 1,
        "taskId": task_id,
        "profile": profile,
        "classification": "evaluator_owned_runtime_adapter",
        "productionLogicInjected": False,
        "containsExpectedOracle": False,
        "runtime": "Android API37 ART",
    }
    (hidden / "PREPARED.json").write_text(json.dumps(prepared, indent=2) + "\n", encoding="utf-8")
    return profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("visible", "hidden"), required=True)
    parser.add_argument("--task-id", choices=tuple(TASKS), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    migration = args.migration.resolve()
    if project.name in {"base", "final"}:
        raise RuntimeError("refusing to prepare a calibration root in place")
    if args.phase == "visible":
        prepare_visible(project, migration, args.task_id)
    else:
        print(prepare_hidden(project, migration, args.task_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
