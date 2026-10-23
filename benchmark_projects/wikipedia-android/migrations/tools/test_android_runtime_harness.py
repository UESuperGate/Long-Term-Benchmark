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


class AndroidRuntimeHarnessAuditTest(unittest.TestCase):
    def test_no_detached_or_evaluator_owned_runtime_semantics(self) -> None:
        self.assertEqual([], audit(ROOT))

    def test_visible_scaffold_changes_no_production_source(self) -> None:
        migrations = ROOT / "benchmark_projects/wikipedia-android/migrations"
        for task_id in ("01_reading_challenge", "02_hybrid_search"):
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


def source_hashes(project: Path) -> dict[str, str]:
    source = project / "app/src/main"
    return {
        str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*")
        if path.is_file() and path.suffix in {".kt", ".java"}
    }


if __name__ == "__main__":
    unittest.main()
