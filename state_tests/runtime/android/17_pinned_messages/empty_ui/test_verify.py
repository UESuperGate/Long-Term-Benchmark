import copy
import json
import unittest

import verify


class EmptyUiEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(verify.REPORT.read_text())
        cls.contract = json.loads(verify.CONTRACT.read_text())

    def setUp(self):
        self.report = copy.deepcopy(self.original)

    def validate(self):
        verify.validate_data(self.report, self.contract)

    def row(self):
        return next(r for r in self.report["semantic"]["cases"] if r["caseId"] == verify.CASE)

    def synchronize_raw(self):
        self.report["observations"][0] = {k: v for k, v in self.row().items() if k not in ("caseId", "traceDigest")}

    def rejected(self):
        with self.assertRaises((ValueError, KeyError, StopIteration)):
            self.validate()

    def test_fixed_archive_artifacts_and_normalization(self):
        result = verify.verify()
        self.assertEqual([r["status"] for r in result["semantic"]["cases"]].count("pass"), 1)

    def test_given_mismatch(self):
        self.row()["checkpoints"][0]["state"]["given"]["listState"] = "empty"
        self.synchronize_raw()
        self.rejected()

    def test_event_mismatch(self):
        self.row()["checkpoints"][0]["state"]["event"]["name"] = "open_pinned_messages"
        self.synchronize_raw()
        self.rejected()

    def test_missing_observed_field(self):
        del self.row()["observed"]["failureVisible"]
        self.synchronize_raw()
        self.rejected()

    def test_unknown_is_not_false(self):
        self.row()["observed"]["failureVisible"] = None
        self.synchronize_raw()
        self.rejected()

    def test_numeric_boolean_rejected(self):
        self.row()["observed"]["failureVisible"] = 0
        self.synchronize_raw()
        self.rejected()

    def test_missing_invariant(self):
        self.row()["invariantChecks"] = []
        self.synchronize_raw()
        self.rejected()

    def test_source_tree_mismatch(self):
        self.report["provenance"]["tree"] = "0" * 40
        self.rejected()

    def test_digest_mismatch(self):
        self.row()["traceDigest"] = "0" * 64
        self.rejected()

    def test_other_case_cannot_reuse_observation(self):
        self.report["semantic"]["cases"][0].update(status="pass", observed=copy.deepcopy(self.row()["observed"]))
        self.rejected()

    def test_different_instance_rejected(self):
        self.row()["checkpoints"][-1]["state"]["identities"]["factory"] += 1
        self.synchronize_raw()
        self.rejected()

    def test_no_actual_factory_output(self):
        self.row()["checkpoints"][-1]["state"]["factoryEmissions"] = []
        self.synchronize_raw()
        self.rejected()

    def test_compile_shim_on_runtime_path(self):
        self.row()["checkpoints"][-1]["state"]["sdkCalls"].append({"port": "runtime.UnexercisedFactory", "method": "replaceWith", "args": []})
        self.synchronize_raw()
        self.rejected()

    def test_legacy_evaluator_source_rejected(self):
        self.report["provenance"]["evaluatorSources"].append({"path": "UnexercisedFactory.kt", "sha256": "0" * 64})
        self.rejected()

    def test_reused_frame_rejected(self):
        self.row()["checkpoints"][-1]["state"]["pixels"] = copy.deepcopy(self.row()["checkpoints"][1]["state"]["pixels"])
        self.synchronize_raw()
        self.rejected()

    def test_missing_rendered_empty(self):
        self.row()["checkpoints"][-1]["state"]["semantics"] = self.row()["checkpoints"][1]["state"]["semantics"]
        self.synchronize_raw()
        self.rejected()

    def test_wrong_contract_hash(self):
        self.report["contractSha256"] = "0" * 64
        self.rejected()

    def test_app_compilation_cannot_be_inferred(self):
        self.report["compile"]["passed"] = True
        self.rejected()


if __name__ == "__main__":
    unittest.main()
