import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
if __package__:
    from . import android_runner as runner
    from . import android_supplemental as supplemental
    from .android_runner import verify_completeness
else:
    import android_runner as runner
    import android_supplemental as supplemental
    from android_runner import verify_completeness


class CompletenessTest(unittest.TestCase):
    def row(self):
        return {"status": "pass", "observed": {"state": "done", "payload": {"id": "a"}},
                "checkpoints": [{"state": "before"}, {"state": "after"}],
                "invariantChecks": [{"invariant": "single request", "status": "pass", "evidence": {"calls": 1}}]}

    def verify(self, row):
        verify_completeness(row, {"expected": {"state": "done", "payload": {"id": "a"}}, "invariants": ["single request"]}, {"productionSources": [{"sha256": "source"}]})
        return row["status"]

    def test_junit_success_without_expected_field_is_not_scored(self):
        row = self.row()
        del row["observed"]["payload"]["id"]
        self.assertEqual("not_scored", self.verify(row))

    def test_invariant_with_similar_name_is_not_coverage(self):
        row = self.row()
        row["invariantChecks"][0]["invariant"] = "some request"
        self.assertEqual("not_scored", self.verify(row))

    def test_observed_absence_is_semantic_mismatch(self):
        row = self.row()
        row["observed"]["payload"] = None
        self.assertEqual("fail", self.verify(row))

    def test_runtime_adapter_failure_stays_not_scored(self):
        row = self.row()
        row["status"] = "not_scored"
        self.assertEqual("not_scored", self.verify(row))

    def test_complete_runtime_evidence_passes(self):
        self.assertEqual("pass", self.verify(self.row()))

    def test_single_checkpoint_cannot_score(self):
        row = self.row()
        row["checkpoints"].pop()
        self.assertEqual("not_scored", self.verify(row))

    def test_exclusion_preserves_literal_mismatch(self):
        row = self.row()
        row["status"] = "fail"
        row["observed"]["state"] = "unknown"
        exclusion = {"classification": "contract_calibration_defect", "reason": "Ambiguous observation surface."}
        verify_completeness(row, {"expected": {"state": "resolving"}}, {"productionSources": ["source"]}, exclusion)
        self.assertEqual("not_scored", row["status"])
        self.assertEqual("fail", row["junitStatus"])
        self.assertEqual("unknown", row["coverage"]["mismatches"][0]["observed"])
        self.assertEqual(exclusion, row["scoringExclusion"])

    def test_exclusion_prevents_scripted_boundary_success(self):
        row = self.row()
        verify_completeness(row, {"expected": row["observed"]}, {"productionSources": ["source"]},
                            {"classification": "untested_production_boundary", "reason": "Scripted repository."})
        self.assertEqual("not_scored", row["status"])
        self.assertEqual("pass", row["junitStatus"])
        self.assertEqual([], row["coverage"]["mismatches"])

    def test_early_assertion_keeps_detected_mismatch_as_diagnostic(self):
        row = self.row()
        row["status"] = "fail"
        row["observed"]["state"] = "wrong"
        row["invariantChecks"] = []
        self.assertEqual("not_scored", self.verify(row))
        self.assertEqual("fail", row["junitStatus"])
        self.assertEqual("wrong", row["coverage"]["mismatches"][0]["observed"])
        self.assertEqual(["single request"], row["coverage"]["missingInvariants"])


class IntegrationTest(unittest.TestCase):
    def test_binding_failure_retains_canonical_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = root / "benchmark_tasks/test"
            assets = root / "assets"
            task.mkdir(parents=True)
            (assets / "test").mkdir(parents=True)
            (task / "task.json").write_text("{}")
            contract = b'{"cases": []}'
            (task / "transitions.json").write_bytes(contract)
            (assets / "test/adapter.json").write_text('{"sources": ["missing.kt"]}')
            candidate = MagicMock(provenance={"tree": "immutable"})
            candidate.exists.return_value = False
            candidate.read.side_effect = FileNotFoundError("missing production entrypoint")
            with patch.object(runner, "ROOT", root), patch.object(runner, "ASSETS", assets), \
                    patch.object(runner, "toolchain", return_value=([], None, None)), \
                    patch.object(runner, "Candidate", return_value=candidate):
                result = runner.run("test", "base", root, root / "report.json", 30)
            self.assertEqual(hashlib.sha256(contract).hexdigest(), result["provenance"]["contractSha256"])
            self.assertEqual("adapter_failed", result["diagnostics"]["adapter"])
            self.assertIsNone(result["compile"]["passed"])

    def test_supplement_runs_after_lock_with_remaining_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = root / "benchmark_tasks/12_report_room"
            task.mkdir(parents=True)
            (task / "transitions.json").write_text('{"taskId": "12_report_room", "cases": []}')
            primary = {"diagnostics": {}, "semantic": {"cases": []}, "compile": {"passed": None}}

            def child(*args, **kwargs):
                with (root / "assets/.build.lock").open("a") as lock:
                    runner.fcntl.flock(lock, runner.fcntl.LOCK_EX | runner.fcntl.LOCK_NB)
                self.assertEqual(7, kwargs["timeout"])
                self.assertEqual(0, kwargs["lock_timeout"])
                return {"probe": True}

            with patch.object(runner, "ROOT", root), patch.object(runner, "ASSETS", root / "assets"), \
                    patch.object(runner, "run", return_value=primary) as run_primary, \
                    patch.object(runner.time, "monotonic", side_effect=[10, 11, 13, 15]), \
                    patch.object(supplemental, "run_supplemental", side_effect=child), \
                    patch.object(supplemental, "merge_supplemental", return_value=primary) as merge:
                result = runner.run_with_supplemental("12_report_room", "final", root, root / "report.json", 10)
            self.assertEqual(9, run_primary.call_args.args[-1])
            self.assertEqual(5, result["durationSeconds"])
            merge.assert_called_once()
            self.assertEqual(result, json.loads((root / "report.json").read_text()))

    def test_exhausted_primary_does_not_start_supplement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = {"diagnostics": {}, "semantic": {"cases": []}}
            with patch.object(runner, "ASSETS", root), patch.object(runner, "run", return_value=primary), \
                    patch.object(runner.time, "monotonic", side_effect=[10, 11, 21, 22]), \
                    patch.object(supplemental, "run_supplemental") as child:
                result = runner.run_with_supplemental("12_report_room", "final", root, root / "report.json", 10)
            child.assert_not_called()
            self.assertIn("supplementalSkipped", result["diagnostics"])


if __name__ == "__main__":
    unittest.main()
