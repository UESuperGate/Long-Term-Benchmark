#!/usr/bin/env python3
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "experiment_results/runtime_transition_20261020/task16_arkts_revision5"
SPEC = importlib.util.spec_from_file_location("task16_revision5_verifier", Path(__file__).with_name("verify_Task16Revision5_device.py"))
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)
CASE006 = VERIFIER.CASE006
VerificationError = VERIFIER.VerificationError
load_inputs = VERIFIER.load_inputs
verify_documents = VERIFIER.verify_documents


class Task16Revision5VerifierMutations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = load_inputs(
            ROOT,
            RESULT / "base-build-v9/build-report.json",
            RESULT / "final-build-v9/build-report.json",
            RESULT / "base-device-v9/device-execution.json",
            RESULT / "final-device-v9/device-execution.json",
        )
        verify_documents(cls.clean, check_workspace=False)

    @staticmethod
    def rows(inputs, role, case_id):
        report = inputs["documents"][f"{role}_device"]
        semantic = next(item for item in report["semantic"]["cases"] if item["caseId"] == case_id)
        return semantic, inputs["raw_rows"][role][case_id]

    def assert_rejected(self, mutate, message):
        inputs = copy.deepcopy(self.clean)
        mutate(inputs)
        with self.assertRaisesRegex(VerificationError, message):
            verify_documents(inputs, check_workspace=False)

    def test_rejects_semantic_and_provenance_mutations(self):
        final_first = self.clean["documents"]["contract"]["cases"][0]["caseId"]
        base_first = final_first

        def both(role, case_id, change):
            def mutate(inputs):
                for row in self.rows(inputs, role, case_id):
                    change(row)
            return mutate

        mutations = [
            (both("final", final_first, lambda row: row.__setitem__("status", "fail")),
             "unexpected status"),
            (both("final", final_first, lambda row: row.__setitem__("traceDigest", "0" * 64)),
             "identity/digest mismatch"),
            (both("final", final_first, lambda row: row["nativeBridge"]["capabilities"]["execution"].__setitem__("nonce", "0" * 32)),
             "backend/nonce mismatch"),
            (both("final", final_first, lambda row: row["missingObservations"].append("mutated")),
             "runtime observation is incomplete"),
            (both("final", CASE006, lambda row: row["observed"]["stateSequence"].__setitem__(2, "success")),
             "exact failure-cleanup-retry observation changed"),
            (both("final", CASE006, lambda row: row["evidence"][0]["nativePageTransition"]["actions"].pop(2)),
             "physical failure/retry action sequence changed"),
            (both("final", CASE006, lambda row: next(item for item in row["checkpoints"]
                  if item["label"] == "task16_ui_stable_after_cleanup")["state"]["presenter"].__setitem__("handleState", "failure")),
             "stable cleanup checkpoint is invalid"),
            (both("final", "ir_state_005_oidc_handle_routes_and_resets", lambda row: next(item for item in
                  next(point for point in row["checkpoints"] if point["label"] == "task16_ui_after_event")["state"]["controls"]
                  if item["name"] == "oidcWebview").__setitem__("visible", False)),
             "real WebView/URL controls not observed"),
            (both("final", "ir_state_010_cancel_cleans_up", lambda row: next(item for item in row["checkpoints"]
                  if item["label"] == "task16_ui_after_event")["state"]["presenter"]["cleanupHistory"].remove("node_destroy")),
             "cleanup reasons missing"),
            (both("base", base_first, lambda row: row["evidence"][0]["nativePageTransition"]["basePositiveControl"].__setitem__(
                  "enabledBackupThroughActualUi", False)),
             "positive control or feature absence missing"),
            (both("final", final_first, lambda row: row["evidence"][0]["nativePageTransition"]["productionSources"][0].__setitem__(
                  "sha256", "f" * 64)),
             "production source provenance mismatch"),
            (lambda inputs: inputs["documents"]["final_device"]["cleanup"].__setitem__("lockReleased", False),
             "device cleanup incomplete"),
            (lambda inputs: inputs["documents"]["final_build"]["compile"].__setitem__("passed", False),
             "app or ohosTest compile did not pass"),
            (lambda inputs: inputs["documents"]["audit"]["activeCanonicalAfter"].__setitem__("sha256", "a" * 64),
             "active canonical audit hash mismatch"),
            (lambda inputs: inputs["documents"]["final_build"]["evaluatorInstall"]["fixtures"][0].__setitem__("sha256", "b" * 64),
             "evaluator fixtures differ"),
        ]
        for index, (mutate, message) in enumerate(mutations, start=1):
            with self.subTest(mutation=index, expected=message):
                self.assert_rejected(mutate, message)


if __name__ == "__main__":
    unittest.main()
