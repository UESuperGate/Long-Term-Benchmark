import json
from pathlib import Path
import tempfile
import unittest

from scripts.runtime_semantics import audit_task11_source_controls as audit


class Task11ControlAuditTest(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((audit.ROOT / "benchmark_tasks" / audit.TASK / "transitions.json").read_text())

    def test_missing_negative_is_not_six_semantic_failures(self):
        result = audit.audit_one(Path("/nonexistent-task11-control"), "android", "base-copy", self.contract)
        self.assertEqual({"passed": 0, "failed": 0, "notScored": 6}, result["semantic"])
        self.assertFalse(result["publicAccepted"])

    def test_new_android_run_is_explicit_and_does_not_repoint_historical_inputs(self):
        original = audit.default_paths()
        current = audit.current_paths(Path("/explicit-current-task11-controls"))
        self.assertEqual(original, audit.default_paths())
        for control in audit.CONTROLS:
            self.assertEqual(Path("/explicit-current-task11-controls") / control / "accepted.runtime.json",
                             current[("android", control)])
            self.assertEqual(original[("arkts", control)], current[("arkts", control)])

    def test_matrix_does_not_promote_android_without_its_runtime_negative(self):
        result = audit.build_audit(audit.default_paths())
        self.assertEqual({"android": False, "arkts": True}, result["fourWayRuntimeControlsClosed"])
        self.assertEqual(3, len(result["copySourceBindings"]))
        self.assertFalse(result["applicationBuildStarted"])

    def test_actual_arkts_agent_controls_keep_opposite_polarities_and_snapshots(self):
        for control, passed in (("base-copy", 0), ("final-copy", 6)):
            result = audit.audit_one(audit.default_paths()[("arkts", control)], "arkts", control, self.contract)
            self.assertEqual(passed, result["semantic"]["passed"])
            self.assertEqual(12, len(result["actualSnapshots"]))
            self.assertTrue(result["publicAccepted"])
            self.assertFalse(result["modelAgentResult"])
            self.assertEqual("not_run", result["applicationCompile"]["status"])

    def test_current_arkts_four_way_matrix_passes_public_and_integrity_validation(self):
        for control in audit.CONTROLS:
            with self.subTest(control=control):
                result = audit.audit_one(audit.default_paths()[("arkts", control)], "arkts", control, self.contract)
                self.assertEqual("accepted", result["status"])
                self.assertTrue(result["publicAccepted"])
                self.assertTrue(result["integrityAccepted"])
                self.assertEqual(12, len(result["actualSnapshots"]))
                self.assertEqual(0, result["semantic"]["notScored"])

    def test_final_copy_cannot_be_relabelled_as_a_negative_control(self):
        original = audit.default_paths()[("arkts", "final-copy")]
        with self.assertRaisesRegex(ValueError, "polarity"):
            audit.audit_one(original, "arkts", "base-copy", self.contract)

    def test_snapshot_mutation_is_rejected_by_actual_validator(self):
        report = json.loads(audit.default_paths()[("arkts", "final-copy")].read_text())
        report["semantic"]["cases"][0]["checkpoints"][0]["state"]["production"] = {}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mutated.json"
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "actual snapshot differs"):
                audit.audit_one(path, "arkts", "final-copy", self.contract)


if __name__ == "__main__":
    unittest.main()
