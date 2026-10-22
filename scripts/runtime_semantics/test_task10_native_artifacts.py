import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.runtime_semantics import task10_native_artifacts as retained


class NativeArtifactsTest(unittest.TestCase):
    def test_retainer_script_style_import_has_no_repository_root_side_effect(self):
        root = Path(__file__).resolve().parents[2]
        code = ("import sys; " + f"sys.path.insert(0, {str(root / 'scripts')!r}); " +
                "from runtime_semantics import task10_repository_evidence as module; " +
                f"assert {str(root)!r} not in sys.path; " +
                "assert callable(module.attach_child); assert callable(module.read_native_artifact)")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", "-c", code], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def fixture(self, root):
        artifacts = root / "scratch"
        artifacts.mkdir()
        native = {"taskId": "10_media_upload_quality", "role": "agent", "caseId": "case001",
                  "traceDigest": "a"*64, "status": "pass", "observed": {"value": 42},
                  "invariantChecks": [{"description": "unchanged", "passed": True}]}
        native_path = artifacts / "native-result.json"
        native_path.write_bytes(json.dumps(native, indent=3).encode() + b"\n\n")
        build = {"source": "/unchanged/candidate", "task10SourceInventory": {"sha256": "b"*64}}
        build_path = artifacts / "build.json"
        build_path.write_text(json.dumps(build, indent=1))
        execution = {"rows": [native], "buildReport": retained.shared.record(build_path),
                     "rowArtifact": {"local": str(native_path), **{
                         key: value for key, value in retained.shared.record(native_path).items() if key != "path"}}}
        execution_path = artifacts / "device-execution.json"
        execution_path.write_text(json.dumps(execution, indent=4))
        (artifacts / "aa-test.log").write_bytes(b"raw log\r\n\x00opaque\xff")
        row = {**copy.deepcopy(native), "key": "canonical-key", "build": retained.shared.record(build_path),
               "execution": retained.shared.record(execution_path)}
        report = {"semantic": {"cases": [row]}, "provenance": {
            "productionSourceRoot": "/unchanged/candidate", "sourceInventory": {"sha256": "b"*64}}}
        return report, artifacts, native

    def test_roundtrip_keeps_original_record_refs_and_exact_unformatted_bytes_after_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, artifacts, native = self.fixture(root)
            row = report["semantic"]["cases"][0]
            original_refs = copy.deepcopy([row["execution"], row["build"]])
            raw_native = (artifacts / "native-result.json").read_bytes()
            retained.retain_repository_rows(report, artifacts, root / "audit")
            for file in artifacts.iterdir():
                file.unlink()
            self.assertEqual(original_refs, [row["execution"], row["build"]])
            self.assertEqual(raw_native, retained.read_native_artifact(row["nativeArtifacts"]["nativeResult"]))
            self.assertEqual(native, retained.verify_repository_row(row, report))
            self.assertEqual(b"raw log\r\n\x00opaque\xff", retained.read_native_artifact(row["nativeArtifacts"]["commandLogs"][0]))

    def test_changed_original_or_relabelled_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, artifacts, _ = self.fixture(root)
            retained.retain_repository_rows(report, artifacts, root / "audit")
            for field in ("execution", "build"):
                changed = copy.deepcopy(report)
                changed["semantic"]["cases"][0][field]["path"] = "/other/original"
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "references changed"):
                    retained.verify_repository_row(changed["semantic"]["cases"][0], changed)

    def test_compressed_bytes_and_decompressed_original_digest_are_both_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, artifacts, _ = self.fixture(root)
            retained.retain_repository_rows(report, artifacts, root / "audit")
            pair = report["semantic"]["cases"][0]["nativeArtifacts"]["nativeResult"]
            path = Path(pair["retained"]["path"])
            path.write_bytes(gzip.compress(b"fabricated raw", mtime=0))
            with self.assertRaises(ValueError):
                retained.read_native_artifact(pair)
            pair["retained"] = retained.shared.record(path)
            with self.assertRaisesRegex(ValueError, "decompressed original"):
                retained.read_native_artifact(pair)

    def test_semantic_summary_cannot_replace_original_native_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, artifacts, _ = self.fixture(root)
            retained.retain_repository_rows(report, artifacts, root / "audit")
            report["semantic"]["cases"][0]["observed"]["value"] = 1
            with self.assertRaisesRegex(ValueError, "verdict/state/invariants"):
                retained.verify_repository_row(report["semantic"]["cases"][0], report)

    def test_already_deleted_raw_is_not_reconstructed_from_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, artifacts, _ = self.fixture(root)
            (artifacts / "device-execution.json").unlink()
            with self.assertRaises(FileNotFoundError):
                retained.retain_repository_rows(report, artifacts, root / "audit")

    def test_host_controls_keep_whole_original_observer_report_not_fabricated_native_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "scratch"
            artifacts.mkdir()
            layout = artifacts / "before.layout.json"
            layout.write_bytes(b'{ "attributes": { "id": "actual-ui-fixture" } }\n')
            raw = {"caseId": "case001", "traceDigest": "a"*64, "status": "pass", "observed": {"value": 42},
                   "invariantChecks": [{"text": "unchanged", "passed": True}],
                   "checkpoints": [{"name": "actual-before", "layout": retained.shared.record(layout)}]}
            device = artifacts / "device-report.json"
            original_bytes = (json.dumps({"semantic": {"cases": [raw]}}, indent=5) + "\n\n").encode()
            device.write_bytes(original_bytes)
            build = artifacts / "build-report.json"
            build.write_bytes(b'{ "originalBuild": true }\n')
            (artifacts / "command.log").write_bytes(b"hdc original command output\r\n")
            row = copy.deepcopy(raw)
            row["invariantChecks"][0]["description"] = "unchanged"
            report = {"semantic": {"cases": [row]}, "provenance": {
                "deviceReport": retained.shared.record(device), "buildReport": retained.shared.record(build)}}
            retained.retain_device_ui_rows(report, artifacts, root / "audit")
            for file in artifacts.iterdir():
                file.unlink()
            self.assertEqual("host_device_ui_observer", row["nativeArtifacts"]["backend"])
            self.assertEqual(original_bytes, retained.read_native_artifact(row["nativeArtifacts"]["nativeResult"]))
            self.assertEqual(raw, retained.verify_device_ui_row(row, report))
            row["observed"]["value"] = 99
            with self.assertRaisesRegex(ValueError, "observer verdict/state/invariants"):
                retained.verify_device_ui_row(row, report)


if __name__ == "__main__":
    unittest.main()
