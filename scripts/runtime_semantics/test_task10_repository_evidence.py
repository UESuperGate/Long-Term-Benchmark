import copy
import json
from pathlib import Path
import unittest

from scripts import run_runtime_transition_matrix as public
from scripts.runtime_semantics import task10_repository_evidence as binding
from scripts.runtime_semantics import task10_repository_prefix_policy as policy

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "experiment_results/runtime_transition_20261020/task10_fresh_m3_binding_v2/candidate-prefix-review-v3-importfix/review.runtime.json"
CONTRACT = json.loads((ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json").read_text())


class ActualRepositoryEvidenceTest(unittest.TestCase):
    def load(self):
        return json.loads(DRAFT.read_text())

    def test_actual_device_prefix_is_bound_to_source_runtime_artifacts_and_unreached_given(self):
        report = self.load()
        row = report["semantic"]["cases"][-1]
        policy.validate_entry_failure(row, report, set(), contract=CONTRACT)
        self.assertFalse(row["transitionExecuted"])
        self.assertIsNone(row["observed"])
        self.assertEqual([], row["invariantChecks"])
        self.assertEqual((6, 3, 0), tuple(report["semantic"][name] for name in ("passed", "failed", "notScored")))

    def test_public_validation_is_never_bypassed_while_policy_route_is_pending(self):
        report = self.load()
        # Public prefix acceptance cannot recover deleted per-case native inputs.
        with self.assertRaisesRegex(ValueError, "nativeArtifacts unavailable"):
            binding.validate_report(report, CONTRACT)

    def test_actual_snapshot_and_verdict_mutations_are_rejected(self):
        for mutate in (lambda report: report["semantic"]["cases"][0]["checkpoints"][0]["state"]["production"]["view"].update(caption="invented"),
                       lambda report: report["semantic"]["cases"][0]["observed"].update(sendState="failure"),
                       lambda report: report["provenance"]["productionSources"][0].update(sha256="0"*64)):
            report = self.load()
            mutate(report)
            with self.assertRaises(ValueError):
                binding.validate_report(report, CONTRACT)

    def test_prepared_prefix_cannot_be_relabelled_or_rebound_to_another_source(self):
        original = self.load()
        for mutation in ("role", "source"):
            report = copy.deepcopy(original)
            if mutation == "role":
                report["role"] = "base"
            else:
                report["provenance"]["sourceInventory"]["sha256"] = "0"*64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                policy.validate_entry_failure(report["semantic"]["cases"][-1], report, set(), contract=CONTRACT)

    def test_actual_nonce_window_and_result_marker_bindings_reject_mutations(self):
        proof = self.load()["semantic"]["cases"][-1]["entryFailureEvidence"]
        native = json.loads(policy.evidence.read_record(proof["nativeRow"]))
        execution = json.loads(policy.evidence.read_record(proof["executionSummary"]))
        policy.verify_native_prefix(native, execution)
        mutations = {
            "different_native_nonce": lambda n, e: n["nativeBridge"]["capabilities"]["execution"].update(nonce="0"*32),
            "different_process_nonce": lambda n, e: e["rowArtifact"]["processLogMarker"].update(executionNonce="0"*32),
            "both_windows_missing": lambda n, e: [p["state"].pop("windowId") for p in n["checkpoints"]],
            "both_windows_non_numeric": lambda n, e: [p["state"].update(windowId="615") for p in n["checkpoints"]],
            "missing_row_artifact": lambda n, e: e.pop("rowArtifact"),
            "different_row_filename": lambda n, e: e["rowArtifact"].update(remote="/data/local/tmp/stale.json"),
            "different_marker_case": lambda n, e: e["rowArtifact"]["processLogMarker"].update(caseId="other"),
            "different_marker_bytes": lambda n, e: e["rowArtifact"]["processLogMarker"].update(bytes=1),
        }
        for name, mutate in mutations.items():
            n, e = copy.deepcopy(native), copy.deepcopy(execution)
            mutate(n, e)
            with self.subTest(mutation=name), self.assertRaises(ValueError):
                policy.verify_native_prefix(n, e)


if __name__ == "__main__":
    unittest.main()
