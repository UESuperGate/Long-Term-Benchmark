#!/usr/bin/env python3
"""Regression tests for the full Android migration inventory generator."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_full_migration_inventory.py"
ANDROID = ROOT / "_sources" / "element-x-android"
SPEC = importlib.util.spec_from_file_location("generate_full_migration_inventory", SCRIPT)
assert SPEC and SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class FullMigrationInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            GENERATOR.run_git(ANDROID, "rev-parse", "--git-dir")
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise unittest.SkipTest("local Element X Android Git object store is unavailable")
        cls.inventories = {
            tag: GENERATOR.build_inventory(ANDROID, tag)
            for tag in ("v26.04.0", "v26.08.4")
        }

    def test_verified_foss_release_closure_sizes(self) -> None:
        expected = {
            "v26.04.0": (252, 187, 188),
            "v26.08.4": (264, 194, 195),
        }
        for tag, (projects, runtime, build) in expected.items():
            with self.subTest(tag=tag):
                graph = self.inventories[tag]["graph"]
                self.assertEqual(graph["gradle_subprojects"], projects)
                self.assertEqual(graph["runtime_closure"], runtime)
                self.assertEqual(graph["build_closure"], build)
                self.assertEqual(len(graph["runtime_module_ids"]), runtime)
                self.assertEqual(len(graph["build_module_ids"]), build)
                self.assertEqual(len(graph["runtime_reachable_from_root"]), runtime)
                self.assertEqual(len(graph["build_reachable_from_root"]), build)
                self.assertFalse(graph["runtime_unreachable"])
                self.assertFalse(graph["build_unreachable"])

    def test_required_modules_have_identity_edges_and_git_evidence(self) -> None:
        for tag, inventory in self.inventories.items():
            with self.subTest(tag=tag):
                modules = inventory["modules"]
                ids = {item["module_id"] for item in modules}
                excluded_ids = {item["module_id"] for item in inventory["excluded_modules"]}
                self.assertIn(":app", ids)
                self.assertIn(":codegen", ids)
                self.assertFalse(inventory["graph"]["dangling_internal_dependencies"])
                self.assertGreater(inventory["graph"]["dependency_edge_count"], 500)
                for module in modules:
                    self.assertEqual(module["module_id"], GENERATOR.module_id(module["source_path"]))
                    self.assertIn(module["classification"], {"runtime_required", "build_required"})
                    self.assertRegex(module["evidence"]["commit"], r"^[0-9a-f]{40}$")
                    self.assertRegex(module["evidence"]["build_file_blob"], r"^[0-9a-f]{40}$")
                    self.assertRegex(module["evidence"]["source_tree_blob"], r"^[0-9a-f]{40}$")
                    for edge in module["dependencies"]:
                        self.assertIn(edge["target"], ids | excluded_ids)
                        self.assertRegex(edge["evidence"]["blob"], r"^[0-9a-f]{40}$")
                        self.assertGreater(edge["evidence"]["line"], 0)

    def test_expected_exclusions_are_explicit(self) -> None:
        inventory = self.inventories["v26.08.4"]
        excluded = {item["module_id"]: item["classification"] for item in inventory["excluded_modules"]}
        self.assertEqual(excluded[":appicon:enterprise"], "enterprise_only")
        self.assertEqual(excluded[":libraries:rustsdk"], "debug_local")
        self.assertEqual(excluded[":features:messages:test"], "test_only")

    def test_migration_map_starts_unmapped_and_preserves_manual_fields(self) -> None:
        inventory = self.inventories["v26.04.0"]
        initial = GENERATOR.merge_migration_map(inventory, None)
        self.assertEqual(initial["required_module_count"], 188)
        self.assertTrue(all(item["disposition"] == "unmapped" for item in initial["mappings"]))

        app = next(item for item in initial["mappings"] if item["source_module"] == "app")
        app.update(
            {
                "disposition": "partial",
                "reason": "manual assessment",
                "target_paths": ["entry/src/main/ets/App.ets"],
                "target_symbols": ["App"],
                "tests": ["tests/app.json"],
                "notes": "keep this",
            }
        )
        regenerated = GENERATOR.merge_migration_map(inventory, initial)
        preserved = next(item for item in regenerated["mappings"] if item["source_module"] == "app")
        self.assertEqual(preserved["disposition"], "partial")
        self.assertEqual(preserved["reason"], "manual assessment")
        self.assertEqual(preserved["target_paths"], ["entry/src/main/ets/App.ets"])
        self.assertEqual(preserved["notes"], "keep this")

    def test_json_round_trip(self) -> None:
        inventory = self.inventories["v26.04.0"]
        migration_map = GENERATOR.merge_migration_map(inventory, None)
        with tempfile.TemporaryDirectory() as directory:
            inventory_path = Path(directory) / "inventory.json"
            map_path = Path(directory) / "map.json"
            GENERATOR.write_json(inventory_path, inventory)
            GENERATOR.write_json(map_path, migration_map)
            self.assertEqual(json.loads(inventory_path.read_text())["graph"]["runtime_closure"], 187)
            self.assertEqual(len(json.loads(map_path.read_text())["mappings"]), 188)


if __name__ == "__main__":
    unittest.main()
