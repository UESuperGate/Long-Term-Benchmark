"""Mutation checks against new real replay bytes, never synthetic runtime scores."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.runtime_semantics import task10_native_artifacts as artifacts
from scripts.runtime_semantics import task10_repository_evidence as repository

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "experiment_results/runtime_transition_20261020/task10_raw_retention_v1/candidate/accepted/accepted.runtime.json"
CONTRACT = json.loads((ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json").read_text())


class ActualRetainedRuntimeTest(unittest.TestCase):
    def load(self):
        return json.loads(REPORT.read_text())

    def test_all_nine_raw_artifacts_restore_after_original_tree_and_candidate_deleted(self):
        report = self.load()
        self.assertFalse(Path(report["target"]).exists())
        repository.validate_report(report, CONTRACT)
        for row in report["semantic"]["cases"]:
            bundle = row["nativeArtifacts"]
            for name in ("execution", "build", "nativeResult"):
                pair = bundle[name]
                self.assertFalse(Path(pair["original"]["path"]).exists())
                self.assertTrue(artifacts.read_native_artifact(pair))
            native = artifacts.verify_repository_row(row, report)
            self.assertTrue(native["calls"])
            execution = json.loads(artifacts.read_native_artifact(bundle["execution"]))
            self.assertEqual(native["evidence"], execution["rows"][0]["evidence"])

    def test_actual_first_eight_verdict_observation_invariant_mutations_fail_closed(self):
        report = self.load()
        for index in range(8):
            for field, value in (("status", "not_scored"), ("observed", {}), ("invariantChecks", [])):
                row = copy.deepcopy(report["semantic"]["cases"][index])
                row[field] = value
                with self.subTest(case=index, field=field), self.assertRaises(ValueError):
                    artifacts.verify_repository_row(row, report)

    def test_other_actual_native_row_cannot_be_spliced_even_with_valid_container_hashes(self):
        report = self.load()
        row = copy.deepcopy(report["semantic"]["cases"][0])
        row["nativeArtifacts"]["nativeResult"] = report["semantic"]["cases"][1]["nativeArtifacts"]["nativeResult"]
        with self.assertRaises(ValueError):
            artifacts.verify_repository_row(row, report)

    def test_actual_retained_blob_corruption_is_not_replaced_with_formal_summary(self):
        row = self.load()["semantic"]["cases"][0]
        pair = row["nativeArtifacts"]["nativeResult"]
        target = Path(pair["retained"]["path"])
        read = Path.read_bytes
        def corrupt(path):
            data = read(path)
            return data + b"mutation" if path == target else data
        with patch.object(Path, "read_bytes", corrupt), self.assertRaises(ValueError):
            artifacts.read_native_artifact(pair)

    def test_missing_lossless_mapping_remains_unscored_not_hash_only_acceptance(self):
        report = self.load()
        del report["semantic"]["cases"][0]["nativeArtifacts"]
        with self.assertRaisesRegex(ValueError, "nativeArtifacts unavailable"):
            repository.validate_report(report, CONTRACT)


if __name__ == "__main__":
    unittest.main()
