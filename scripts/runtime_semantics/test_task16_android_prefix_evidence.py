import copy
import json
from pathlib import Path
import unittest

from scripts.runtime_semantics import task16_android_prefix_evidence as prefix
from scripts.run_runtime_transition_matrix import validate_report


class Task16PrefixEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(prefix.CONTRACT.read_text())
        cls.path = prefix.ROOT / "experiment_results/runtime_transition_20261020/task16_android/common-prefix-sanity-v3/base_evidence/entry.json"
        cls.raw = json.loads(cls.path.read_text())
        cls.rows = prefix.base_rows(cls.contract, cls.raw, cls.path)

    def report(self):
        return {"taskId": prefix.TASK, "platform": "android", "role": "agent",
                "observationMode": "runtime_state_transition", "semantic": {"cases": copy.deepcopy(self.rows)},
                "provenance": {"candidateSource": self.raw["provenance"]["source"]}}

    def test_real_independent_ui_and_production_flow_negative_control_validates(self):
        self.assertEqual([row["status"] for row in self.rows], ["fail"] * 10)
        self.assertEqual(len({row["observed"]["executionId"] for row in self.rows}), 10)
        validate_report(self.report(), self.contract)

    def test_role_labels_do_not_select_the_base_outcome(self):
        for role in ("agent", "base", "final"):
            report = self.report()
            report["role"] = role
            validate_report(report, self.contract)

    def test_unknown_downstream_states_and_invariants_stay_unknown(self):
        for row, spec in zip(self.rows, self.contract["cases"]):
            self.assertEqual(row["invariantChecks"], [])
            self.assertEqual(row["unevaluatedInvariants"], spec["invariants"])
            self.assertEqual(row["unobservedExpectedFields"], list(spec["expected"]))
            self.assertFalse(row["canonicalEventExecuted"])

    def test_each_positive_control_is_required(self):
        for name in ("common_initial", "recovery_positive_control", "recovery_returns_root", "entry_attempt"):
            raw = copy.deepcopy(prefix.rows(self.raw)[0])
            raw["checkpoints"] = [point for point in raw["checkpoints"] if point["name"] != name]
            self.assertFalse(prefix.valid_prefix(raw, self.raw), name)

    def test_fake_canonical_poststate_is_rejected(self):
        report = self.report()
        report["semantic"]["cases"][0]["observed"]["confirmationVisible"] = True
        with self.assertRaisesRegex(ValueError, "differs from runtime bytes"):
            validate_report(report, self.contract)

    def test_reused_execution_is_rejected(self):
        row = self.rows[0]
        used = set()
        prefix.validate_prefix_failure(row, self.report(), used, self.contract)
        with self.assertRaisesRegex(ValueError, "reused"):
            prefix.validate_prefix_failure(row, self.report(), used, self.contract)

    def test_report_hash_mutation_is_rejected(self):
        report = self.report()
        report["semantic"]["cases"][0]["task16PrefixFailure"]["report"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_report(report, self.contract)

    def test_reflection_only_probe_has_no_eligible_prefix_rows(self):
        raw = json.loads((prefix.ROOT /
            "experiment_results/runtime_transition_20261020/task16_android/base-entry-v1.json").read_text())
        rows = prefix.base_rows(self.contract, raw, self.path)
        self.assertEqual({row["status"] for row in rows}, {"not_scored"})
        self.assertTrue(all(row["prefixTransitionExecuted"] is False for row in rows))

    def test_report_outside_audit_root_is_rejected_before_reading(self):
        report = self.report()
        report["semantic"]["cases"][0]["task16PrefixFailure"]["report"]["path"] = "/tmp/unreviewed-task16-report.json"
        with self.assertRaisesRegex(ValueError, "audit root"):
            validate_report(report, self.contract)

    def test_empty_evaluator_manifest_is_rejected(self):
        raw = copy.deepcopy(self.raw)
        raw["provenance"]["evaluatorSources"] = []
        with self.assertRaisesRegex(ValueError, "nonempty reviewed"):
            prefix.validate_evaluator_sources(raw, self.path)

    def test_self_signed_evaluator_hash_is_rejected(self):
        raw = copy.deepcopy(self.raw)
        raw["provenance"]["evaluatorSources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "current reviewed"):
            prefix.validate_evaluator_sources(raw, self.path)

    def test_old_reflection_evaluator_cannot_replace_the_reviewed_runtime_test(self):
        raw = copy.deepcopy(self.raw)
        replacement = prefix.ASSETS / "base_entry/IdentityResetEntryTest.kt"
        raw["provenance"]["evaluatorSources"][0] = prefix.record(replacement)
        with self.assertRaisesRegex(ValueError, "current reviewed"):
            prefix.validate_evaluator_sources(raw, self.path)

    def test_generated_binding_is_derived_only_from_actual_api_shape(self):
        without = prefix.binding_bytes("fun VerifySelfSessionView(state: X, onFinish: () -> Unit) { }")
        with_reset = prefix.binding_bytes("fun VerifySelfSessionView(state: X, onResetKey: () -> Unit, onFinish: () -> Unit) { }")
        self.assertNotIn(b"onResetKey =", without)
        self.assertIn(b"onResetKey = onReset", with_reset)
        with self.assertRaisesRegex(ValueError, "cannot be bound"):
            prefix.binding_bytes("class Unrelated")


if __name__ == "__main__":
    unittest.main()
