import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from scripts.runtime_semantics import task11_android_entry

audit = sys.modules["task11_android_resource_audit"]


class ResourceAuditTest(unittest.TestCase):
    def test_resource_hash_size_and_path_are_persisted_before_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "runtime.json"
            def compile_resources(_candidate, _config, work, _java):
                jar = work / "resources.jar"
                jar.write_bytes(b"actual compiled resource fixture")
                return jar
            def run_slice(*_args):
                with tempfile.TemporaryDirectory() as work:
                    jar = audit.android_robolectric.compile_resources(None, {}, Path(work), None)
                    manifest = output.with_suffix(".resource-artifacts.json")
                    self.assertTrue(jar.exists())
                    recorded = json.loads(manifest.read_text())["binaryArtifacts"][0]
                    self.assertEqual(jar.stat().st_size, recorded["bytes"])
                    self.assertEqual(str(jar.resolve()), recorded["path"])
                return {"runtimeCompile": {"passed": True}}
            with mock.patch.object(audit.android_robolectric, "compile_resources", side_effect=compile_resources), \
                    mock.patch.object(audit.android_robolectric, "run_slice", side_effect=run_slice):
                with audit.record_slice_resources():
                    result = audit.android_robolectric.run_slice("task", "agent", Path(tmp), None, None, output, 100)
            self.assertTrue(result["resourceArtifactAudit"]["binaryArtifactsDeleted"])
            self.assertTrue(result["resourceArtifactAudit"]["hashesRecordedBeforeDelete"])
            self.assertEqual(64, len(result["resourceArtifactAudit"]["binaryArtifacts"][0]["sha256"]))

    def test_failure_restores_both_compiler_hooks(self):
        previous_run = audit.android_robolectric.run_slice
        previous_compile = audit.android_robolectric.compile_resources
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(audit.android_robolectric, "run_slice", side_effect=RuntimeError("failed")):
                with self.assertRaises(RuntimeError), audit.record_slice_resources():
                    audit.android_robolectric.run_slice("task", "agent", None, None, None, Path(tmp)/"out.json", 100)
        self.assertIs(previous_run, audit.android_robolectric.run_slice)
        self.assertIs(previous_compile, audit.android_robolectric.compile_resources)


if __name__ == "__main__":
    unittest.main()
