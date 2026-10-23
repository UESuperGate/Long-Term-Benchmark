#!/usr/bin/env python3
"""Materialize compilation-only WordPress stubs inside a clean agent candidate."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from record_visible_android_abi import production_source_roots


SUPPORT_INCLUDES = (
    "org/wordpress/android/support/unified/**",
    "org/wordpress/android/support/common/model/Conversation.kt",
    "org/wordpress/android/support/common/model/UserInfo.kt",
    "org/wordpress/android/support/common/ui/ConversationsSupportViewModel.kt",
    "dagger/**",
    "javax/**",
    "okhttp3/**",
    "rs/**",
    "uniffi/**",
    "evaluator/support/leaf/**",
    "org/wordpress/android/fluxc/module/**",
    "org/wordpress/android/fluxc/store/**",
    "org/wordpress/android/fluxc/utils/**",
    "org/wordpress/android/modules/**",
    "org/wordpress/android/networking/**",
    "org/wordpress/android/util/**",
)
SUPPORT_COMPOSE_DEPENDENCIES = (
    'implementation("androidx.activity:activity-compose:1.10.1")',
    'implementation("androidx.compose.ui:ui:1.7.8")',
    'implementation("androidx.compose.foundation:foundation:1.7.8")',
    'implementation("androidx.compose.material3:material3:1.3.2")',
)


def copy_device_stubs(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if relative.parts and relative.parts[0] in {"android", "androidx"}:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def add_support_candidate_scaffold(project: Path, migration: Path, scaffold: Path, build: str) -> str:
    roots = production_source_roots(project, "02_unified_support")
    candidate_roots = [root for root in roots if not root.startswith("upstream-immutable/")]
    if not candidate_roots:
        return build

    evaluator = migration / "android/focused-runtime/evaluator"
    shutil.rmtree(scaffold)
    scaffold.mkdir(parents=True)
    copy_device_stubs(evaluator / "final-stubs", scaffold)
    leaf = evaluator / "final-main/evaluator/support/leaf/EvaluatorLeaf.kt"
    leaf_target = scaffold / "evaluator/support/leaf/EvaluatorLeaf.kt"
    leaf_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(leaf, leaf_target)

    if 'id("org.jetbrains.kotlin.plugin.compose")' not in build:
        build = build.replace(
            'kotlin("android") version "2.1.20"',
            'kotlin("android") version "2.1.20"\n'
            '    id("org.jetbrains.kotlin.plugin.compose") version "2.1.20"',
            1,
        )
    build = build.replace(
        'namespace = "org.wordpress.evaluator.support.base"',
        'namespace = "org.wordpress.android"',
        1,
    )
    manifest_anchor = 'sourceSets.getByName("main").manifest.srcFile("src/main/AndroidManifest.xml")'
    if "buildFeatures { compose = true }" not in build:
        build = build.replace(manifest_anchor, manifest_anchor + "\n    buildFeatures { compose = true }", 1)
    source_anchor = 'srcDir("upstream-immutable/WordPress/src/main/java")'
    source_lines = "\n".join(
        f'            srcDir("{root}")' for root in candidate_roots if f'srcDir("{root}")' not in build
    )
    if source_lines:
        build = build.replace(source_anchor, source_anchor + "\n" + source_lines, 1)
    build = re.sub(
        r'^\s*include\("org/wordpress/android/support/main/ui/SupportViewModel\.kt"\)\s*\n',
        "",
        build,
        flags=re.MULTILINE,
    )
    include_lines = "\n".join(
        f'            include("{value}")' for value in SUPPORT_INCLUDES if f'include("{value}")' not in build
    )
    build = build.replace(source_anchor, source_anchor + "\n" + include_lines, 1)
    dependency_anchor = 'implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")'
    dependency_lines = "\n".join(
        f"    {value}" for value in SUPPORT_COMPOSE_DEPENDENCIES if value not in build
    )
    if dependency_lines:
        build = build.replace(dependency_anchor, dependency_anchor + "\n" + dependency_lines, 1)
    return build


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", choices=("01_pages_list", "02_unified_support"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    args = parser.parse_args()

    project = args.project.resolve()
    migration = args.migration.resolve()
    evaluator = migration / "android/focused-runtime/evaluator"
    scaffold = project / ".benchmark-scaffold/main"
    shutil.rmtree(project / ".benchmark-scaffold", ignore_errors=True)
    shutil.copytree(evaluator / "base-stubs", scaffold)

    build_path = project / "build.gradle.kts"
    build = build_path.read_text(encoding="utf-8")
    build = re.sub(r'^\s*srcDir\("\.\./evaluator/base-(?:stubs|runtime)"\)\s*\n', "", build, flags=re.MULTILINE)
    anchor = 'srcDir("upstream-immutable/WordPress/src/main/java")'
    build = build.replace(anchor, anchor + '\n            srcDir(".benchmark-scaffold/main")', 1)
    build = re.sub(r'^\s*include\("evaluator/\*\*"\)\s*\n', "", build, flags=re.MULTILINE)
    build = re.sub(r'^\s*getByName\("androidTest"\)\.kotlin\.srcDir\("[^"]+"\)\s*\n', "", build, flags=re.MULTILINE)
    build = build.replace("jvmToolchain(21)", "jvmToolchain(17)")
    if args.task_id == "02_unified_support":
        build = add_support_candidate_scaffold(project, migration, scaffold, build)
    build_path.write_text(build, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
