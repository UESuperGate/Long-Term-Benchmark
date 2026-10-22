import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts.runtime_semantics import task11_android_entry as entry


class Task11EntryTest(unittest.TestCase):
    def test_configuration_uses_real_messages_dependencies_and_unqualified_resources(self):
        candidate = SimpleNamespace(provenance={"tree": "1"*40}, exists=lambda _: True)
        paths = "\n".join([
            "libraries/textcomposer/impl/src/main/res/values/strings.xml",
            "libraries/textcomposer/impl/src/main/res/values-fr/strings.xml",
            "features/messages/impl/src/main/res/values/localazy.xml",
        ])
        with mock.patch.object(entry.android_runner, "Candidate", return_value=candidate), \
                mock.patch.object(entry, "closure", return_value=["actual/MessagesState.kt"]), \
                mock.patch.object(entry.subprocess, "check_output", return_value=paths):
            config = entry.configuration(Path("/arbitrary/source"), "agent")
        self.assertIn("actual/MessagesState.kt", config["sources"])
        self.assertIn(["io.element.android", "wysiwyg", "2.38.3"], config["dependencies"])
        self.assertEqual(9, len(config["resources"]))
        self.assertEqual(["libraries/textcomposer/impl/src/main/res/values/strings.xml"],
                         config["resources"][0]["files"])
        self.assertTrue(any(path.endswith("LocationBuildConfig.kt") for path in config["evaluatorSources"]))
        self.assertEqual(["task11_entry"], config["keys"])

    def test_loaded_state_capability_is_independent_of_explicit_role(self):
        for role in ("base", "final", "agent"):
            for present in (False, True):
                result = {"runtimeCompile": {"status": "passed"},
                          "provenance": {"productionSources": [{"path": "actual.kt", "sha256": "1"*64}]},
                          "observations": [{"status": "pass", "observed": {"fullFeatureEntry": present}}]}
                with self.subTest(role=role, present=present), tempfile.TemporaryDirectory() as tmp:
                    with mock.patch.object(entry, "configuration", return_value={"scope": "fixture"}), \
                            mock.patch.object(entry.android_robolectric, "run_slice", return_value=result):
                        actual = entry.probe(entry.TASK, Path(tmp), role, Path(tmp) / "entry.json", 100)
                        self.assertIs(present, actual["fullFeatureEntry"])

    def test_compiler_error_is_retained_without_a_semantic_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "entry.json"
            output.with_suffix(".log").write_text("actual/MessagesState.kt:3:1: error: missing fixture dependency\n")
            with mock.patch.object(entry, "configuration", return_value={"scope": "fixture"}), \
                    mock.patch.object(entry.android_robolectric, "run_slice", return_value={
                        "runtimeCompile": {"status": "failed"}}):
                with self.assertRaisesRegex(RuntimeError, "no semantic failure assigned.*missing fixture dependency"):
                    entry.probe(entry.TASK, Path(tmp), "agent", output, 100)
            self.assertTrue(output.with_suffix(".log").exists())

    def test_probe_failure_restores_resource_compiler(self):
        previous = entry.android_robolectric.compile_resources
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(entry, "configuration", return_value={"scope": "fixture"}), \
                    mock.patch.object(entry.android_robolectric, "run_slice", side_effect=ValueError("failure")):
                with self.assertRaises(ValueError):
                    entry.probe(entry.TASK, Path(tmp), "agent", Path(tmp) / "entry.json", 100)
        self.assertIs(previous, entry.android_robolectric.compile_resources)


if __name__ == "__main__":
    unittest.main()
