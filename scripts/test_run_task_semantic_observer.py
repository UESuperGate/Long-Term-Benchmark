#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run_task_semantic_observer.py")
SPEC = importlib.util.spec_from_file_location("run_task_semantic_observer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObserverRuleTest(unittest.TestCase):
    def test_strip_comments_preserves_comment_markers_in_strings(self) -> None:
        source = '''
const uri = `file://${targetPath}`; // ns_state_fake
const endpoint = "https://example.test/v1";
/* testcase_fake */
const escaped = "say \\\"// still text\\\"";
'''

        stripped = MODULE.strip_comments(source)

        self.assertIn("file://${targetPath}", stripped)
        self.assertIn("https://example.test/v1", stripped)
        self.assertIn("// still text", stripped)
        self.assertNotIn("ns_state_fake", stripped)
        self.assertNotIn("testcase_fake", stripped)

    def test_option_requires_patterns_and_forbids_markers(self) -> None:
        sources = {"entry/src/main/Feature.ets": "class Feature { save(): void {} }"}
        passed, path = MODULE.match_option(
            {"path": r"Feature\.ets$", "patterns": [r"class Feature", r"save\("], "forbid": [r"caseId"]},
            sources,
        )
        self.assertTrue(passed)
        self.assertEqual(path, "entry/src/main/Feature.ets")

    def test_forbidden_pattern_rejects_option(self) -> None:
        sources = {"Feature.kt": "class Feature { val caseId = \"oracle\" }"}
        passed, _ = MODULE.match_option(
            {"path": r"Feature\.kt$", "patterns": [r"class Feature"], "forbid": [r"caseId"]},
            sources,
        )
        self.assertFalse(passed)

    def test_directory_sources_skips_build_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "entry/src/main/ets").mkdir(parents=True)
            (root / "entry/src/main/ets/Feature.ets").write_text("class Feature {}", encoding="utf-8")
            (root / "entry/src/main/ets/build").mkdir()
            (root / "entry/src/main/ets/build/Generated.ets").write_text("class Generated {}", encoding="utf-8")
            sources = MODULE.directory_sources(root, ["entry/src/main/ets"], {".ets"})
            self.assertEqual(list(sources), ["entry/src/main/ets/Feature.ets"])

    def test_directory_sources_rejects_roots_outside_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "candidate"
            root.mkdir()
            outside = root.parent / "Outside.ets"
            outside.write_text("class Outside {}", encoding="utf-8")

            sources = MODULE.directory_sources(root, ["../Outside.ets"], {".ets"})

            self.assertEqual(sources, {})

    def test_agent_source_roots_include_changed_files_outside_final_layout(self) -> None:
        roots = MODULE.agent_source_roots(
            ["features/legacy/src/main/kotlin"],
            [
                "features/newfeature/src/main/kotlin/NewFeature.kt",
                "../outside/Escape.kt",
                "/tmp/Absolute.kt",
                "README.md",
            ],
            {".kt"},
        )

        self.assertEqual(
            roots,
            [
                "features/legacy/src/main/kotlin",
                "features/newfeature/src/main/kotlin/NewFeature.kt",
            ],
        )


if __name__ == "__main__":
    unittest.main()
