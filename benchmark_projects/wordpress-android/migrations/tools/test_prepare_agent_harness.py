from __future__ import annotations

import tempfile
import unittest
import shutil
import hashlib
import json
from pathlib import Path

from prepare_agent_harness import (
    PAGES_PUBLIC_OWNER_METHODS,
    SUPPORT_CANDIDATE_MODEL_METHODS,
    SUPPORT_CANDIDATE_VIEW_MODEL_METHODS,
    SUPPORT_REPOSITORY_METHODS,
    classify_pages_abi,
    classify_support_abi,
    prepare_android,
    prepare_arkts,
)
from record_visible_android_abi import production_source_digest, production_source_roots
from prepare_visible_scaffold import add_support_candidate_scaffold


ROOT = Path(__file__).resolve().parents[4]


class PrepareAndroidAgentHarnessTest(unittest.TestCase):
    def write_abi_receipt(self, project: Path, task_id: str, classes: dict) -> None:
        receipt = {
            "schemaVersion": 2,
            "taskId": task_id,
            "buildFileSha256": hashlib.sha256(project.joinpath("build.gradle.kts").read_bytes()).hexdigest(),
            "productionSourceDigest": production_source_digest(project, task_id),
            "productionSourceRoots": production_source_roots(project, task_id),
            "classes": classes,
        }
        path = project / ".benchmark-scaffold/visible-abi.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt), encoding="utf-8")

    def prepare_base_candidate(self, task_id: str, classes: dict | None = None) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        (project / "src/main").mkdir(parents=True)
        (project / "src/main/AndroidManifest.xml").write_text(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
            '<application android:label="fixture">'
            '<activity android:name="evaluator.pagesbase.PagesBaseOwnerActivity" '
            'android:exported="false" />'
            '</application></manifest>',
            encoding="utf-8",
        )
        project.joinpath("build.gradle.kts").write_text(
            '''plugins { kotlin("android") version "2.1.20" }
kotlin {
    sourceSets {
        getByName("main").kotlin.apply {
            srcDir("upstream-immutable/WordPress/src/main/java")
            srcDir("../evaluator/base-stubs")
            srcDir("../evaluator/base-main")
            srcDir(".benchmark-scaffold/main")
        }
        getByName("androidTest").kotlin.apply {
            srcDir("../evaluator/pages-instrumentation")
            srcDir("../evaluator/base-runtime")
        }
    }
}
dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
}
''',
            encoding="utf-8",
        )
        migration = ROOT / "benchmark_projects/wordpress-android/migrations" / task_id
        if classes is None:
            if task_id == "01_pages_list":
                classes = {
                    "org.wordpress.android.ui.pages.PagesActivity": {"publicMethods": ["onCreate"]}
                }
            else:
                classes = {
                    "org.wordpress.android.support.main.ui.SupportViewModel": {"publicMethods": []}
                }
        self.write_abi_receipt(project, task_id, classes)
        prepare_android(project, migration, task_id, project / ".benchmark-evaluator")
        return project

    def test_hidden_android_test_sources_replace_external_evaluator_roots(self) -> None:
        project = self.prepare_base_candidate("01_pages_list")
        build = project.joinpath("build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('srcDir(".benchmark-evaluator/androidTest")', build)
        self.assertIn('srcDir(".benchmark-evaluator/main")', build)
        self.assertNotIn("../evaluator/", build)
        self.assertNotIn(".benchmark-scaffold/main", build)

    def test_manifest_wiring_is_idempotent(self) -> None:
        project = self.prepare_base_candidate("01_pages_list")
        manifest = project.joinpath("src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertEqual(manifest.count("evaluator.pagesbase.PagesBaseOwnerActivity"), 1)

    def test_device_main_excludes_androidx_host_stubs(self) -> None:
        project = self.prepare_base_candidate("02_unified_support")
        hidden_main = project / ".benchmark-evaluator/main"
        self.assertFalse((hidden_main / "stubs/androidx/lifecycle/Lifecycle.kt").exists())

    def test_pages_abi_classification_uses_compiled_method_table(self) -> None:
        owner = "org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity"
        self.assertEqual(
            classify_pages_abi({owner: {"publicMethods": sorted(PAGES_PUBLIC_OWNER_METHODS)}}),
            "candidate_public_owner",
        )
        self.assertEqual(
            classify_pages_abi({"org.wordpress.android.ui.pagesrs.PagesRsListViewModel": {"publicMethods": []}}),
            "upstream_final",
        )
        self.assertEqual(
            classify_pages_abi({"org.wordpress.android.ui.pages.PagesActivity": {"publicMethods": []}}),
            "legacy_base",
        )

    def test_candidate_public_owner_is_not_redeclared_by_hidden_main(self) -> None:
        project = self.prepare_base_candidate(
            "01_pages_list",
            {
                "org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity": {
                    "publicMethods": sorted(PAGES_PUBLIC_OWNER_METHODS)
                }
            },
        )
        hidden = project / ".benchmark-evaluator"
        self.assertFalse(any(path.name == "PagesRuntimeOwnerActivity.kt" for path in (hidden / "main").rglob("*")))
        self.assertTrue(
            (hidden / "androidTest/evaluator/pages/PagesPublicOwnerRuntimeMain.kt").is_file()
        )
        manifest = project.joinpath("src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertEqual(manifest.count("org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity"), 1)

    def test_support_candidate_v1_uses_compiled_abi_not_source_role_inference(self) -> None:
        classes = {
            "org.wordpress.android.support.unified.ui.UnifiedSupportViewModel": {
                "publicMethods": sorted(SUPPORT_CANDIDATE_VIEW_MODEL_METHODS)
            },
            "org.wordpress.android.support.unified.repository.UnifiedSupportRepository": {
                "publicMethods": sorted(SUPPORT_REPOSITORY_METHODS)
            },
            "org.wordpress.android.support.unified.model.UnifiedConversation": {
                "publicMethods": sorted(SUPPORT_CANDIDATE_MODEL_METHODS)
            },
            "org.wordpress.android.support.unified.ui.UnifiedConversationDetailScreenKt": {
                "publicMethods": ["UnifiedConversationDetailScreen"]
            },
        }
        self.assertEqual(classify_support_abi(classes), "candidate-v1")
        project = self.prepare_base_candidate("02_unified_support", classes)
        hidden = project / ".benchmark-evaluator"
        self.assertTrue((hidden / "androidTest/evaluator/support/SupportRuntimeMain.kt").is_file())
        owner = hidden / (
            "main/runtime-owner/org/wordpress/android/support/unified/ui/SupportRuntimeOwnerActivity.kt"
        )
        self.assertIn("Compatibility owner for the method-level candidate-v1 ABI", owner.read_text())

    def test_unknown_support_abi_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "no supported runtime ABI"):
            classify_support_abi({
                "org.wordpress.android.support.unified.ui.UnifiedSupportViewModel": {
                    "publicMethods": ["sendReply"]
                }
            })

    def test_support_visible_scaffold_is_idempotent_and_excludes_host_framework_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "candidate"
            scaffold = project / ".benchmark-scaffold/main"
            source = project / (
                "WordPress/src/main/java/org/wordpress/android/support/unified/ui/"
                "UnifiedSupportViewModel.kt"
            )
            source.parent.mkdir(parents=True)
            source.write_text(
                "package org.wordpress.android.support.unified.ui\nclass UnifiedSupportViewModel\n",
                encoding="utf-8",
            )
            scaffold.mkdir(parents=True)
            build = '''plugins { kotlin("android") version "2.1.20" }
android {
    namespace = "org.wordpress.evaluator.support.base"
    sourceSets.getByName("main").manifest.srcFile("src/main/AndroidManifest.xml")
}
kotlin { sourceSets { getByName("main").kotlin.apply {
            srcDir("upstream-immutable/WordPress/src/main/java")
            include("org/wordpress/android/support/main/ui/SupportViewModel.kt")
} } }
dependencies { implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1") }
'''
            migration = ROOT / "benchmark_projects/wordpress-android/migrations/02_unified_support"
            once = add_support_candidate_scaffold(project, migration, scaffold, build)
            twice = add_support_candidate_scaffold(project, migration, scaffold, once)
            self.assertEqual(twice.count('id("org.jetbrains.kotlin.plugin.compose")'), 1)
            self.assertEqual(twice.count('srcDir("WordPress/src/main/java")'), 1)
            self.assertEqual(twice.count('implementation("androidx.compose.ui:ui:1.7.8")'), 1)
            self.assertFalse((scaffold / "android/app/Application.kt").exists())
            self.assertFalse((scaffold / "androidx/lifecycle/Lifecycle.kt").exists())
            self.assertTrue((scaffold / "evaluator/support/leaf/EvaluatorLeaf.kt").is_file())

    def test_known_final_uses_compatibility_owner_without_public_owner_collision(self) -> None:
        project = self.prepare_base_candidate(
            "01_pages_list",
            {"org.wordpress.android.ui.pagesrs.PagesRsListViewModel": {"publicMethods": ["initTab"]}},
        )
        hidden = project / ".benchmark-evaluator"
        self.assertTrue(any(path.name == "PagesRuntimeOwnerActivity.kt" for path in (hidden / "main").rglob("*")))
        self.assertTrue((hidden / "androidTest/evaluator/pages/PagesRuntimeMain.kt").is_file())

    def test_stale_visible_abi_receipt_is_rejected(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        (project / "src/main").mkdir(parents=True)
        (project / "src/main/AndroidManifest.xml").write_text(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application /></manifest>',
            encoding="utf-8",
        )
        project.joinpath("build.gradle.kts").write_text(
            'srcDir("upstream-immutable/WordPress/src/main/java")\n'
            'getByName("androidTest").kotlin.srcDir("../evaluator/base-runtime")\n',
            encoding="utf-8",
        )
        self.write_abi_receipt(
            project,
            "01_pages_list",
            {"org.wordpress.android.ui.pages.PagesActivity": {"publicMethods": []}},
        )
        project.joinpath("build.gradle.kts").write_text(
            project.joinpath("build.gradle.kts").read_text() + "// changed\n", encoding="utf-8"
        )
        migration = ROOT / "benchmark_projects/wordpress-android/migrations/01_pages_list"
        with self.assertRaisesRegex(RuntimeError, "does not match build.gradle.kts"):
            prepare_android(project, migration, "01_pages_list", project / ".benchmark-evaluator")

    def test_arkts_untouched_base_receives_the_single_final_adapter(self) -> None:
        for task_id in ("01_pages_list", "02_unified_support"):
            with self.subTest(task_id=task_id), tempfile.TemporaryDirectory() as directory:
                migration = ROOT / "benchmark_projects/wordpress-android/migrations" / task_id
                project = Path(directory) / "candidate"
                shutil.copytree(migration / "arkts/base", project)
                prepare_arkts(project, migration, project / ".benchmark-evaluator")
                injected = project / "entry/src/main/ets/.benchmark-evaluator/SemanticProbe.ets"
                canonical = migration / "arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets"
                self.assertEqual(injected.read_bytes(), canonical.read_bytes())
                ability = project.joinpath("entry/src/main/ets/entryability/EntryAbility.ets").read_text()
                self.assertIn("../.benchmark-evaluator/SemanticProbe", ability)
                self.assertNotIn("../evaluator/SemanticProbe", ability)


if __name__ == "__main__":
    unittest.main()
