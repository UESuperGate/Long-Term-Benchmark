#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from record_visible_android_abi import production_source_digest, production_source_roots


TASKS = {
    "01_pages_list": {
        "instrumentation": "pages-instrumentation",
        "target_include": "org/wordpress/android/ui/pagesrs/**",
        "target_package": "org.wordpress.android.ui.pagesrs",
        "target_path": "org/wordpress/android/ui/pagesrs/",
        "base_only_includes": ["org/wordpress/android/ui/pages/PagesActivity.kt"],
        "additional_production_includes": [],
    },
    "02_unified_support": {
        "instrumentation": "support-instrumentation",
        "target_include": "org/wordpress/android/support/unified/**",
        "target_package": "org.wordpress.android.support.unified",
        "target_path": "org/wordpress/android/support/unified/",
        "base_only_includes": ["org/wordpress/android/support/main/ui/SupportViewModel.kt"],
        "additional_production_includes": [
            "org/wordpress/android/support/common/model/Conversation.kt",
            "org/wordpress/android/support/common/ui/ConversationsSupportViewModel.kt",
        ],
    },
}
FORBIDDEN_NAMES = {
    "transitions.json", "transitions.draft.json", "observer_rules.json", "task.json", "evidence.json"
}
PAGES_OWNER = "org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity"
PAGES_VIEW_MODEL = "org.wordpress.android.ui.pagesrs.PagesRsListViewModel"
LEGACY_PAGES_OWNER = "org.wordpress.android.ui.pages.PagesActivity"
PAGES_PUBLIC_OWNER_METHODS = {
    "open", "refresh", "openSearch", "changeSearchQuery", "closeSearch", "selectAuthor",
    "openPage", "chooseMenuAction", "confirmPendingAction", "performSnackbarAction",
    "renderHierarchy", "renderMenu",
}
SUPPORT_VIEW_MODEL = "org.wordpress.android.support.unified.ui.UnifiedSupportViewModel"
SUPPORT_REPOSITORY = "org.wordpress.android.support.unified.repository.UnifiedSupportRepository"
SUPPORT_CONVERSATION = "org.wordpress.android.support.unified.model.UnifiedConversation"
SUPPORT_DETAIL = "org.wordpress.android.support.unified.ui.UnifiedConversationDetailScreenKt"
LEGACY_SUPPORT_VIEW_MODEL = "org.wordpress.android.support.main.ui.SupportViewModel"
SUPPORT_CANDIDATE_VIEW_MODEL_METHODS = {
    "isSendingReply", "getReplyFormState", "onConversationClick",
    "onCreateNewBotConversationClick", "sendReply", "addReplyAttachments",
    "removeReplyAttachment", "updateReplyMessage", "updateReplyIncludeAppLogs",
    "updateReplyBottomSheetVisibility", "clearReplyForm",
}
SUPPORT_REPOSITORY_METHODS = {
    "init", "loadConversations", "loadConversation",
    "createNewBotConversation", "replyToConversation",
}
SUPPORT_CANDIDATE_MODEL_METHODS = {
    "isBot", "getShowsInlineComposer", "getShowsReplyAction", "isClosed",
}


def file_record(project: Path, path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(project)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def inspect_candidate(project: Path) -> None:
    for path in project.rglob("*"):
        if not path.is_file() or ".benchmark-evaluator" in path.parts:
            continue
        if path.name in FORBIDDEN_NAMES:
            raise RuntimeError(f"agent candidate contains evaluator oracle material: {path}")


def candidate_target_sources(project: Path, task_id: str) -> list[Path]:
    target_package = TASKS[task_id]["target_package"]
    target_path = TASKS[task_id]["target_path"]
    package_pattern = re.compile(rf"^\s*package\s+{re.escape(target_package)}(?:\.|\s*$)", re.MULTILINE)
    sources: list[Path] = []
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix not in {".kt", ".java"}:
            continue
        relative = path.relative_to(project)
        if any(part in {".benchmark-evaluator", "build", ".gradle", ".kotlin"} for part in relative.parts):
            continue
        if any(part in {"test", "androidTest"} for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if target_path in f"{relative.as_posix()}/" or package_pattern.search(text):
            sources.append(path)
    return sorted(sources)


def classify_pages_abi(classes: dict[str, dict[str, object]]) -> str:
    owner = classes.get(PAGES_OWNER)
    owner_methods = set(owner.get("publicMethods", [])) if isinstance(owner, dict) else set()
    if PAGES_PUBLIC_OWNER_METHODS <= owner_methods:
        return "candidate_public_owner"
    if PAGES_VIEW_MODEL in classes:
        return "upstream_final"
    if LEGACY_PAGES_OWNER in classes:
        return "legacy_base"
    raise RuntimeError("visible Pages build exposes no supported runtime ABI")


def class_methods(classes: dict[str, dict[str, object]], class_name: str) -> set[str]:
    value = classes.get(class_name)
    return set(value.get("publicMethods", [])) if isinstance(value, dict) else set()


def classify_support_abi(classes: dict[str, dict[str, object]]) -> str:
    view_model = class_methods(classes, SUPPORT_VIEW_MODEL)
    repository = class_methods(classes, SUPPORT_REPOSITORY)
    conversation = class_methods(classes, SUPPORT_CONVERSATION)
    detail = class_methods(classes, SUPPORT_DETAIL)
    if (
        SUPPORT_CANDIDATE_VIEW_MODEL_METHODS <= view_model
        and SUPPORT_REPOSITORY_METHODS <= repository
        and SUPPORT_CANDIDATE_MODEL_METHODS <= conversation
        and "UnifiedConversationDetailScreen" in detail
    ):
        return "candidate-v1"
    if view_model and repository and "UnifiedConversationDetailScreen" in detail:
        return "final"
    if LEGACY_SUPPORT_VIEW_MODEL in classes:
        return "base"
    raise RuntimeError("visible Unified Support build exposes no supported runtime ABI")


def load_visible_abi(project: Path, task_id: str) -> tuple[dict[str, object], str | None]:
    receipt_path = project / ".benchmark-scaffold/visible-abi.json"
    if not receipt_path.is_file():
        raise RuntimeError("visible Android ABI receipt is missing; run the visible build first")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schemaVersion") != 2 or receipt.get("taskId") != task_id:
        raise RuntimeError("visible Android ABI receipt has the wrong schema or task")
    if receipt.get("buildFileSha256") != hashlib.sha256((project / "build.gradle.kts").read_bytes()).hexdigest():
        raise RuntimeError("visible Android ABI receipt does not match build.gradle.kts")
    if receipt.get("productionSourceDigest") != production_source_digest(project, task_id):
        raise RuntimeError("visible Android ABI receipt does not match candidate production sources")
    if receipt.get("productionSourceRoots") != production_source_roots(project, task_id):
        raise RuntimeError("visible Android ABI receipt does not match candidate production roots")
    classes = receipt.get("classes")
    if not isinstance(classes, dict):
        raise RuntimeError("visible Android ABI receipt has no class table")
    profile = classify_pages_abi(classes) if task_id == "01_pages_list" else classify_support_abi(classes)
    return receipt, profile


def copy_stubs(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        # Device harnesses must link Android framework classes from android.jar. Host-only
        # stand-ins would change method descriptors and fail when ART loads the real classes.
        if relative.parts and relative.parts[0] in {"android", "androidx"}:
            continue
        target = destination / "stubs" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def wire_android_manifest(project: Path, task_id: str, owner: str, support_final: bool) -> Path:
    manifest = project / "src/main/AndroidManifest.xml"
    ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
    tree = ET.parse(manifest)
    application = tree.getroot().find("application")
    if application is None:
        raise RuntimeError("agent AndroidManifest.xml has no application element")
    android_name = "{http://schemas.android.com/apk/res/android}name"
    android_exported = "{http://schemas.android.com/apk/res/android}exported"
    owner_names = {
        "org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity",
        "evaluator.pagesbase.PagesBaseOwnerActivity",
        "org.wordpress.android.support.unified.ui.SupportRuntimeOwnerActivity",
        "evaluator.supportbase.SupportBaseOwnerActivity",
    }
    for activity in list(application.findall("activity")):
        if activity.get(android_name) in owner_names:
            application.remove(activity)
    for provider in list(application.findall("provider")):
        if provider.get(android_name) == "evaluator.support.leaf.EvaluatorContentProvider":
            application.remove(provider)
    ET.SubElement(application, "activity", {android_name: owner, android_exported: "false"})
    if task_id == "02_unified_support" and support_final:
        ET.SubElement(application, "provider", {
            android_name: "evaluator.support.leaf.EvaluatorContentProvider",
            "{http://schemas.android.com/apk/res/android}authorities": "org.wordpress.evaluator.support.files",
            android_exported: "false",
        })
    tree.write(manifest, encoding="unicode")
    return manifest


def wire_hidden_source_sets(build: str, extra_roots: list[str]) -> str:
    build = re.sub(
        r'^\s*srcDir\("(?:\.\./evaluator/[^\"]+|\.benchmark-(?:evaluator/(?:main|androidTest)|scaffold/main)|src/main/java)"\)\s*\n',
        "",
        build,
        flags=re.MULTILINE,
    )
    source_anchor = 'srcDir("upstream-immutable/WordPress/src/main/java")'
    if source_anchor not in build:
        raise RuntimeError("agent build.gradle.kts lacks the immutable production source root")
    source_dirs = '\n'.join([
        source_anchor,
        '            srcDir("src/main/java")',
        *(f'            srcDir("{root}")' for root in extra_roots
          if root not in {".", "upstream-immutable/WordPress/src/main/java", "src/main/java"}),
        '            srcDir(".benchmark-evaluator/main")',
    ])
    build = build.replace(source_anchor, source_dirs, 1)

    android_test_apply = re.compile(
        r'(getByName\("androidTest"\)\.kotlin\.apply\s*\{).*?(\n\s*\})',
        re.DOTALL,
    )
    if android_test_apply.search(build):
        build = android_test_apply.sub(
            r'\1\n            srcDir(".benchmark-evaluator/androidTest")\2',
            build,
            count=1,
        )
    else:
        android_test_direct = re.compile(
            r'getByName\("androidTest"\)\.kotlin\.srcDir\("[^\"]+"\)'
        )
        if not android_test_direct.search(build):
            raise RuntimeError("agent build.gradle.kts lacks an Android test Kotlin source set")
        build = android_test_direct.sub(
            'getByName("androidTest").kotlin.srcDir(".benchmark-evaluator/androidTest")',
            build,
            count=1,
        )
    return build


def prepare_android(
    project: Path, migration: Path, task_id: str, hidden: Path
) -> tuple[list[Path], str, list[Path], dict[str, object]]:
    evaluator = migration / "android/focused-runtime/evaluator"
    main = hidden / "main"
    android_test = hidden / "androidTest"
    target_sources = candidate_target_sources(project, task_id)
    receipt, abi_profile = load_visible_abi(project, task_id)
    runtime_role = abi_profile
    if task_id == "01_pages_list":
        runtime_role = {
            "legacy_base": "base",
            "upstream_final": "final",
            "candidate_public_owner": "public-owner",
        }[abi_profile]

    stub_role = "final" if runtime_role in {"final", "public-owner", "candidate-v1"} else "base"
    copy_stubs(evaluator / f"{stub_role}-stubs", main)
    runtime_main = evaluator / f"{runtime_role}-main"
    if runtime_main.is_dir():
        shutil.copytree(runtime_main, main / "runtime-owner", dirs_exist_ok=True)
    shutil.copytree(evaluator / f"{runtime_role}-runtime", android_test, dirs_exist_ok=True)
    shutil.copytree(evaluator / TASKS[task_id]["instrumentation"], android_test, dirs_exist_ok=True)
    owner = (
        PAGES_OWNER if task_id == "01_pages_list" and runtime_role in {"final", "public-owner"}
        else "evaluator.pagesbase.PagesBaseOwnerActivity" if task_id == "01_pages_list"
        else "org.wordpress.android.support.unified.ui.SupportRuntimeOwnerActivity"
        if runtime_role in {"final", "candidate-v1"}
        else "evaluator.supportbase.SupportBaseOwnerActivity"
    )
    manifest = wire_android_manifest(project, task_id, owner, runtime_role in {"final", "candidate-v1"})

    build_path = project / "build.gradle.kts"
    build = build_path.read_text(encoding="utf-8")
    receipt_roots = receipt.get("productionSourceRoots", [])
    if not isinstance(receipt_roots, list) or not all(isinstance(root, str) for root in receipt_roots):
        raise RuntimeError("visible Android ABI receipt has invalid production source roots")
    build = wire_hidden_source_sets(build, receipt_roots)
    source_anchor = 'srcDir("upstream-immutable/WordPress/src/main/java")'
    source_dirs = '\n'.join([
        source_anchor,
        '            srcDir("src/main/java")',
        *(f'            srcDir("{root}")' for root in receipt_roots
          if root not in {".", "upstream-immutable/WordPress/src/main/java", "src/main/java"}),
        '            srcDir(".benchmark-evaluator/main")',
    ])
    target_include = TASKS[task_id]["target_include"]
    required_includes = ["stubs/**", target_include]
    if runtime_main.is_dir():
        required_includes.append("runtime-owner/**")
    if target_sources:
        required_includes.extend(TASKS[task_id]["additional_production_includes"])
        for base_include in TASKS[task_id]["base_only_includes"]:
            build = re.sub(
                rf'^\s*include\("{re.escape(base_include)}"\)\s*\n',
                "",
                build,
                flags=re.MULTILINE,
            )
    additions = "\n".join(f'            include("{value}")' for value in required_includes if f'include("{value}")' not in build)
    if additions:
        build = build.replace(source_dirs, f"{source_dirs}\n{additions}", 1)
    if task_id == "02_unified_support" and runtime_role in {"final", "candidate-v1"}:
        if 'id("org.jetbrains.kotlin.plugin.compose")' not in build:
            build = build.replace(
                'kotlin("android") version "2.1.20"',
                'kotlin("android") version "2.1.20"\n    id("org.jetbrains.kotlin.plugin.compose") version "2.1.20"',
                1,
            )
        build = build.replace(
            'namespace = "org.wordpress.evaluator.support.base"',
            'namespace = "org.wordpress.android"',
            1,
        )
        if "buildFeatures { compose = true }" not in build:
            build = build.replace(
                'sourceSets.getByName("main").manifest.srcFile("src/main/AndroidManifest.xml")',
                'sourceSets.getByName("main").manifest.srcFile("src/main/AndroidManifest.xml")\n'
                '    sourceSets.getByName("main").res.srcDir(".benchmark-evaluator/res")\n'
                '    buildFeatures { compose = true }',
                1,
            )
        dependency_anchor = 'implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")'
        compose_dependencies = "\n".join([
            '    implementation("androidx.activity:activity-compose:1.10.1")',
            '    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.1")',
            '    implementation("androidx.compose.ui:ui:1.7.8")',
            '    implementation("androidx.compose.foundation:foundation:1.7.8")',
            '    implementation("androidx.compose.material3:material3:1.3.2")',
            '    implementation("androidx.compose.material:material-icons-extended:1.7.8")',
        ])
        if 'androidx.activity:activity-compose' not in build:
            build = build.replace(dependency_anchor, dependency_anchor + "\n" + compose_dependencies, 1)
        shutil.copytree(
            migration / "android/focused-runtime/final/src/main/res", hidden / "res", dirs_exist_ok=True
        )
    build_path.write_text(build, encoding="utf-8")
    return [build_path, manifest], runtime_role, target_sources, receipt


def prepare_arkts(project: Path, migration: Path, hidden: Path) -> list[Path]:
    visible_evaluator = project / "entry/src/main/ets/evaluator"
    if visible_evaluator.exists():
        shutil.rmtree(visible_evaluator)
    hidden_source = project / "entry/src/main/ets/.benchmark-evaluator"
    if hidden_source.exists():
        shutil.rmtree(hidden_source)
    hidden_source.mkdir(parents=True)
    shutil.copy2(
        migration / "arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets",
        hidden_source / "SemanticProbe.ets",
    )

    ability_path = project / "entry/src/main/ets/entryability/EntryAbility.ets"
    evaluator_ability = migration / "arkts/final/entry/src/main/ets/entryability/EntryAbility.ets"
    ability = evaluator_ability.read_text(encoding="utf-8")
    visible_import = "../evaluator/SemanticProbe"
    hidden_import = "../.benchmark-evaluator/SemanticProbe"
    if visible_import not in ability:
        raise RuntimeError("evaluator-owned EntryAbility template lacks the semantic probe import")
    ability_path.write_text(ability.replace(visible_import, hidden_import), encoding="utf-8")
    return [ability_path]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("android", "arkts"), required=True)
    parser.add_argument("--task-id", choices=tuple(TASKS), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    args = parser.parse_args()

    project = args.project.resolve()
    migration = args.migration.resolve()
    if project.name in {"base", "final"}:
        raise RuntimeError("refusing to inject a hidden harness into a calibration base/final root")
    inspect_candidate(project)

    hidden = project / ".benchmark-evaluator"
    if hidden.exists():
        shutil.rmtree(hidden)
    hidden.mkdir(parents=True)
    if args.platform == "android":
        wiring_files, runtime_role, target_sources, visible_abi = prepare_android(
            project, migration, args.task_id, hidden
        )
    else:
        wiring_files = prepare_arkts(project, migration, hidden)
        runtime_role = "device_probe"
        target_sources = []
        visible_abi = None

    injected_files = sorted(path for path in hidden.rglob("*") if path.is_file())
    injected_text = "\n".join(path.read_text(encoding="utf-8") for path in injected_files)
    if re.search(r"traceDigest|\bexpected\b|\boracle\b", injected_text):
        raise RuntimeError("hidden harness unexpectedly contains expected/oracle material")
    prepared = {
        "schemaVersion": 1,
        "taskId": args.task_id,
        "platform": args.platform,
        "classification": "evaluator_owned_hidden_probe_and_build_wiring",
        "containsExpectedOracle": False,
        "productionLogicInjected": False,
        "androidRuntimeAdapterSourceSet": "androidTest" if args.platform == "android" else None,
        "androidMainInjection": "controlled_leaves_compilation_stubs_and_optional_compatibility_owner"
        if args.platform == "android" else None,
        "candidateProductionSources": [file_record(project, path) for path in target_sources],
        "deviceRuntimeRequired": "Android API37" if args.platform == "android" else "OpenHarmony API23",
        "injectedFiles": [file_record(project, path) for path in injected_files],
        "wiringFiles": [file_record(project, path) for path in wiring_files],
        "visibleAbiReceipt": file_record(project, project / ".benchmark-scaffold/visible-abi.json")
        if visible_abi is not None else None,
    }
    (hidden / "PREPARED").write_text(json.dumps(prepared, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
