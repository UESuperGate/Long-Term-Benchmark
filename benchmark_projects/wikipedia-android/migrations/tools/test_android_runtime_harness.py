#!/usr/bin/env python3
from __future__ import annotations

import sys
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[3]
sys.path.insert(0, str(TOOLS))

from audit_android_runtime_harness import audit
from prepare_agent_harness import candidate_production_roots, copy_candidate_production
from run_wikipedia_03_04_agent_eval import generation_audit, production_files


class AndroidRuntimeHarnessAuditTest(unittest.TestCase):
    def test_codegen_audit_distinguishes_candidate_tests_from_production_probe(self) -> None:
        android_paths = [
            "app/src/main/kotlin/org/wikipedia/Feature.kt",
            "app/src/test/kotlin/org/wikipedia/FeatureTest.kt",
            "app/src/androidTest/kotlin/org/wikipedia/FeatureDeviceTest.kt",
        ]
        self.assertEqual(
            ["app/src/main/kotlin/org/wikipedia/Feature.kt"],
            production_files(android_paths, "android"),
        )
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            probe = candidate / "entry/src/main/ets/pages/Probe.ets"
            probe.parent.mkdir(parents=True)
            probe.write_text("export struct Probe {}\n")
            result = generation_audit(candidate, [str(probe.relative_to(candidate))])
            self.assertFalse(result["passed"])
            self.assertIn("evaluator-like generated path", result["issues"][0])

    def test_no_detached_or_evaluator_owned_runtime_semantics(self) -> None:
        self.assertEqual([], audit(ROOT))

    def test_visible_scaffold_changes_no_production_source(self) -> None:
        migrations = ROOT / "benchmark_projects/wikipedia-android/migrations"
        for task_id in ("01_reading_challenge", "02_hybrid_search", "03_explore_feed", "04_reading_lists"):
            migration = migrations / task_id
            with self.subTest(task_id=task_id), tempfile.TemporaryDirectory() as directory:
                candidate = Path(directory) / "candidate"
                shutil.copytree(migration / "android/native/base", candidate)
                before = source_hashes(candidate)
                subprocess.run(
                    [
                        sys.executable,
                        str(TOOLS / "prepare_visible_scaffold.py"),
                        "--task-id", task_id,
                        "--project", str(candidate),
                        "--migration", str(migration),
                    ],
                    check=True,
                )
                self.assertEqual(before, source_hashes(candidate))
                self.assertEqual([], list((candidate / "app/src/main/java").rglob("*.kt")))
                self.assertIn('"src/main/java"', (candidate / "app/build.gradle.kts").read_text())

    def test_hidden_copy_uses_only_visible_production_roots(self) -> None:
        migrations = ROOT / "benchmark_projects/wikipedia-android/migrations"
        expected = {
            "01_reading_challenge": {"PageLoadCompleteActionPrefix.kt", "ReadingChallengePageActionPrefix.kt"},
            "02_hybrid_search": {"SearchResultsViewModel.kt", "HybridSearchPageActionPrefix.kt"},
            "03_explore_feed": {"ExploreActionPrefix.kt"},
            "04_reading_lists": {"SavedActionPrefix.kt"},
        }
        for task_id, required in expected.items():
            migration = migrations / task_id
            with self.subTest(task_id=task_id), tempfile.TemporaryDirectory() as directory:
                candidate = Path(directory) / "candidate"
                target = Path(directory) / "collected"
                shutil.copytree(migration / "android/native/base", candidate)
                subprocess.run(
                    [
                        sys.executable,
                        str(TOOLS / "prepare_visible_scaffold.py"),
                        "--task-id", task_id,
                        "--project", str(candidate),
                        "--migration", str(migration),
                    ],
                    check=True,
                )
                roots = candidate_production_roots(candidate)
                app = (candidate / "app").resolve()
                self.assertTrue(all(app in root.parents for root in roots))
                copy_candidate_production(candidate, target)
                names = [path.name for path in target.rglob("*.kt")]
                self.assertTrue(required.issubset(names))
                self.assertNotIn("PageActivity.kt", names)
                self.assertNotIn("Prefs.kt", names)
                for name in required:
                    self.assertEqual(1, names.count(name))

    def test_new_runtime_controls_and_fail_closed_binding(self) -> None:
        migrations = ROOT / "benchmark_projects/wikipedia-android/migrations"
        for task_id in ("03_explore_feed", "04_reading_lists"):
            migration = migrations / task_id
            with self.subTest(task_id=task_id):
                contract = json_load(migration / "canonical/transitions.json")
                self.assertEqual(10, len(contract["cases"]))
                self.assertEqual(10, len({case["traceDigest"] for case in contract["cases"]}))
                for name, expected in (("android-no-change-control.json", (0, 10, 0)),
                                       ("android-known-final-control.json", (10, 0, 0))):
                    report = json_load(migration / "results" / name)
                    semantic = report["semantic"]
                    self.assertEqual(expected, (semantic["passed"], semantic["failed"], semantic["notScored"]))
                    self.assertEqual("runtime_state_transition", report["observationMode"])
                    self.assertFalse(report["diagnostics"]["sourceObserver"])
                runner = (migration / "evaluator/run_android_semantics.py").read_text()
                self.assertIn('parser.add_argument("--project"', runner)
                production = "\n".join(path.read_text() for path in (migration / "android/native/final/app/src/main/upstream/kotlin").rglob("*.kt"))
                for case in contract["cases"]:
                    self.assertNotIn(case["caseId"], production)
                    self.assertNotIn(case["key"], production)

    def test_new_upstream_snapshots_match_immutable_commits(self) -> None:
        source = ROOT / "_sources/wikipedia-android"
        migrations = ROOT / "benchmark_projects/wikipedia-android/migrations"
        entries = [
            ("03_explore_feed", "40876929c5a84e1a1f968b29184c245582c7ff9a", "base/src/upstream_snapshot/kotlin/org/wikipedia/feed/FeedFragment.kt", "app/src/main/java/org/wikipedia/feed/FeedFragment.kt"),
            ("03_explore_feed", "0c4d8a2e33dda8dface830e7ac90d1e923fe7c6e", "final/src/upstream/kotlin/org/wikipedia/feed/HomeViewModel.kt", "app/src/main/java/org/wikipedia/feed/HomeViewModel.kt"),
            ("04_reading_lists", "8b7427f178b619aeb585fbcbb8a02e5ea0f0b68c", "base/src/upstream_snapshot/kotlin/org/wikipedia/readinglist/ReadingListsFragment.kt", "app/src/main/java/org/wikipedia/readinglist/ReadingListsFragment.kt"),
            ("04_reading_lists", "12d1dd2bffea3db7ead5a69b2025bcbf287fe64d", "final/src/upstream/kotlin/org/wikipedia/readinglist/ReadingListsViewModel.kt", "app/src/main/java/org/wikipedia/readinglist/ReadingListsViewModel.kt"),
        ]
        for task, commit, local, upstream in entries:
            with self.subTest(task=task, upstream=upstream):
                actual = (migrations / task / "android" / local).read_bytes()
                expected = subprocess.check_output(["git", "-C", str(source), "show", f"{commit}:{upstream}"])
                self.assertEqual(expected, actual)


def source_hashes(project: Path) -> dict[str, str]:
    source = project / "app/src/main"
    return {
        str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*")
        if path.is_file() and path.suffix in {".kt", ".java"}
    }


def json_load(path: Path) -> dict:
    import json
    return json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
