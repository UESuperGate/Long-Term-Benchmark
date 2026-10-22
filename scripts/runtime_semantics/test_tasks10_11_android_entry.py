import tempfile
from pathlib import Path
import unittest
from unittest import mock

from scripts.runtime_semantics import tasks10_11_android_entry as entry


class RuntimeEntryTest(unittest.TestCase):
    def test_capability_comes_from_loaded_runtime_not_role(self):
        for task in ("10_media_upload_quality", "11_room_upgrade_navigation"):
            for role in ("base", "final", "agent"):
                for present in (True, False):
                    result = {"runtimeCompile": {"status": "passed"},
                              "observations": [{"status": "pass", "observed": {"fullFeatureEntry": present}}],
                              "provenance": {"productionSources": [{"path": "actual.kt", "sha256": "1"*64}]}}
                    with self.subTest(task=task, role=role, present=present), tempfile.TemporaryDirectory() as tmp:
                        with mock.patch.object(entry.android_robolectric, "run_slice", return_value=result):
                            actual = entry.probe(task, Path(tmp), role, Path(tmp) / "probe.json", 100)
                            self.assertIs(present, actual["fullFeatureEntry"])

    def test_missing_api_compile_error_does_not_become_a_semantic_failure(self):
        for result in ({"runtimeCompile": {"status": "failed"}},
                       {"runtimeCompile": {"status": "passed"}, "observations": [{"status": "fail"}]},
                       {"runtimeCompile": {"status": "passed"}, "observations": []}):
            with tempfile.TemporaryDirectory() as tmp:
                with mock.patch.object(entry.android_robolectric, "run_slice", return_value=result):
                    with self.assertRaisesRegex(RuntimeError, "no semantic failure assigned"):
                        entry.probe("10_media_upload_quality", Path(tmp), "agent", Path(tmp) / "probe.json", 100)

    def test_resource_compiler_is_restored_on_error(self):
        previous = entry.android_robolectric.compile_resources
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(entry.android_robolectric, "run_slice", side_effect=ValueError("test failure")):
                with self.assertRaises(ValueError):
                    entry.probe("11_room_upgrade_navigation", Path(tmp), "agent", Path(tmp) / "probe.json", 100)
        self.assertIs(previous, entry.android_robolectric.compile_resources)


if __name__ == "__main__":
    unittest.main()
