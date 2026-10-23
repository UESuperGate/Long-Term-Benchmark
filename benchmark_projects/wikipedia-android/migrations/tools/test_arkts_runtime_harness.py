#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import inspect
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS = ROOT / "benchmark_projects/wikipedia-android/migrations"
MODULE_PATH = MIGRATIONS / "tools/prepare_agent_harness.py"
SPEC = importlib.util.spec_from_file_location("prepare_agent_harness", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load prepare_agent_harness")
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class ArktsRuntimeHarnessTest(unittest.TestCase):
    def test_wrap_preserves_existing_sync_lifecycle(self) -> None:
        source = """@Entry\n@Component\nstruct Index {\n  aboutToAppear(): void {\n    this.refresh();\n  }\n}\n"""
        patched = HARNESS.wrap_about_to_appear(source, "RuntimeLaunch", "      await runCase();")
        self.assertIn("async aboutToAppear(): Promise<void>", patched)
        self.assertIn("if (RuntimeLaunch.caseKey.length > 0)", patched)
        self.assertIn("await runCase();", patched)
        self.assertIn("} else {\n      this.refresh();", patched)

    def test_wrap_adds_missing_lifecycle(self) -> None:
        source = "@Entry\n@Component\nstruct Index {\n  build() {}\n}\n"
        patched = HARNESS.wrap_about_to_appear(source, "RuntimeLaunch", "      await runCase();")
        self.assertEqual(1, patched.count("aboutToAppear"))
        self.assertIn("async aboutToAppear(): Promise<void>", patched)
        self.assertIn("await runCase();", patched)

    def test_same_common_adapter_prepares_both_untouched_bases(self) -> None:
        self.assertEqual(4, len(inspect.signature(HARNESS.prepare_arkts).parameters))
        fixtures = (
            ("01_reading_challenge", "ReadingRuntimeEpisode.ets", "this.openArticle()"),
            ("02_hybrid_search", "HybridRuntimeEpisode.ets", "this.submitSearch()"),
        )
        for task_id, episode, normal_action in fixtures:
            with self.subTest(task_id=task_id), tempfile.TemporaryDirectory() as directory:
                migration = MIGRATIONS / task_id
                project = Path(directory) / "candidate"
                shutil.copytree(migration / "arkts/base", project)
                hidden = project / ".benchmark-evaluator"
                hidden.mkdir()
                _, binding = HARNESS.prepare_arkts(task_id, project, migration, hidden)
                page = (project / "entry/src/main/ets/pages/Index.ets").read_text()
                self.assertEqual("page_owner_integration_abi_v1", binding)
                self.assertTrue((project / "entry/src/main/ets/.benchmark-evaluator" / episode).is_file())
                self.assertIn("this.createRuntimeOwner()", page)
                self.assertIn(normal_action, page)
                self.assertIn("} else {", page)

    def test_candidate_directory_name_is_not_a_role_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            migration = MIGRATIONS / "01_reading_challenge"
            project = Path(directory) / "base"
            shutil.copytree(migration / "arkts/base", project)
            hidden = project / ".benchmark-evaluator"
            hidden.mkdir()
            _, binding = HARNESS.prepare_arkts("01_reading_challenge", project, migration, hidden)
            self.assertEqual("page_owner_integration_abi_v1", binding)


if __name__ == "__main__":
    unittest.main()
