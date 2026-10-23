from __future__ import annotations

import unittest
from pathlib import Path

from audit_android_runtime_harness import audit_repository


ROOT = Path(__file__).resolve().parents[4]


class AndroidRuntimeHarnessAuditTest(unittest.TestCase):
    def test_runtime_owner_harnesses_pass(self) -> None:
        result = audit_repository(ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(set(result["tasks"]), {"01_pages_list", "02_unified_support"})

    def test_calibration_is_strict_and_fully_scored(self) -> None:
        result = audit_repository(ROOT)
        for task in result["tasks"].values():
            self.assertEqual(task["detachedViewModels"], 0)
            self.assertEqual(task["directDerivedStateWrites"], 0)
            self.assertEqual(task["sourcePresenceVerdicts"], 0)
            self.assertEqual(set(task["reports"]), {"base", "final"})

    def test_pages_public_owner_runtime_keeps_verdict_outside_adapter(self) -> None:
        runtime = ROOT / (
            "benchmark_projects/wordpress-android/migrations/01_pages_list/android/focused-runtime/"
            "evaluator/public-owner-runtime/evaluator/pages/PagesPublicOwnerRuntimeMain.kt"
        )
        text = runtime.read_text(encoding="utf-8")
        self.assertIn("PagesRuntimeOwnerActivity.open", text)
        self.assertIn("CollectionLeaf.install", text)
        self.assertNotIn('"status" to', text)
        self.assertNotIn("target_absent", text)
        self.assertNotIn("source presence", text)


if __name__ == "__main__":
    unittest.main()
