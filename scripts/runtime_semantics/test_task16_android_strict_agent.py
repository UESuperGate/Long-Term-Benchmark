#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import json
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task16_android_strict_agent as scorer
import task16_arkts_strict_agent as arkts_scorer


class Task16AndroidStrictAgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(scorer.CONTRACT.read_text())
        root = scorer.ROOT / "experiment_results/runtime_transition_20261020/task16_android/common-prefix-sanity-v3/final_evidence"
        cls.reports = {
            name: json.loads((root / (name + ".json")).read_text())
            for name in ("entry", "primary", "flow", "root", "password", "verification")
        }

    def test_latest_revision5_final_assembly_is_ten_pass(self):
        rows = scorer.assemble_final(self.contract, self.reports)
        self.assertEqual(len(rows), 10)
        self.assertEqual({row["status"] for row in rows}, {"pass"})
        case6 = next(row for row in rows if row["key"] == "handle_failure_recovers")
        self.assertEqual(case6["observed"]["stateSequence"],
                         ["uninitialized", "loading", "failure", "uninitialized", "loading"])

    def test_both_scorers_pin_promoted_canonical_contract_identity_and_hash(self):
        canonical = scorer.ROOT / "benchmark_tasks/16_identity_reset/transitions.json"
        audited = scorer.ROOT / (
            "experiment_results/runtime_transition_20261020/contract_audit/"
            "revision_5_task16/after/transitions.json"
        )
        self.assertEqual(scorer.CONTRACT, canonical)
        self.assertEqual(arkts_scorer.CONTRACT, canonical)
        canonical_bytes = canonical.read_bytes()
        self.assertEqual(hashlib.sha256(canonical_bytes).hexdigest(),
                         hashlib.sha256(audited.read_bytes()).hexdigest())
        active_binding = scorer.ROOT / "migrations/16_identity_reset/arkts/bindings.json"
        audited_binding = scorer.ROOT / (
            "experiment_results/runtime_transition_20261020/contract_audit/"
            "revision_5_task16/after/arkts-bindings.json"
        )
        self.assertEqual(hashlib.sha256(active_binding.read_bytes()).hexdigest(),
                         hashlib.sha256(audited_binding.read_bytes()).hexdigest())
        contract = json.loads(canonical_bytes)
        self.assertEqual(contract["taskId"], "16_identity_reset")
        self.assertEqual(len(contract["cases"]), 10)
        self.assertTrue(all(case["taskId"] == contract["taskId"] for case in contract["cases"]))

    def test_runtime_compile_mutation_becomes_ns_not_semantic_fail(self):
        reports = copy.deepcopy(self.reports)
        reports["flow"]["runtimeCompile"]["status"] = "adapter_compile_failed"
        rows = scorer.assemble_final(self.contract, reports)
        flow_keys = {"confirm_starts_handle", "password_handle_routes", "oidc_handle_routes_and_resets",
                     "handle_failure_recovers", "cancel_cleans_up"}
        self.assertTrue(all(row["status"] == "not_scored" for row in rows if row["key"] in flow_keys))

    def test_reflection_entry_absence_is_never_scored(self):
        root = scorer.ROOT / "experiment_results/runtime_transition_20261020/task16_android/base-entry-v1.json"
        rows = scorer.base_rows(self.contract, json.loads(root.read_text()))
        self.assertEqual([row["status"] for row in rows], ["not_scored"] * 10)

    def test_reflection_positive_entry_is_insufficient_for_final(self):
        reports = copy.deepcopy(self.reports)
        reports["entry"] = json.loads((scorer.ROOT /
            "experiment_results/runtime_transition_20261020/task16_android/final-entry-v1.json").read_text())
        self.assertEqual({row["status"] for row in scorer.assemble_final(self.contract, reports)}, {"not_scored"})

    def test_assembler_preserves_actual_checkpoints_and_production_sources(self):
        for row in scorer.assemble_final(self.contract, self.reports):
            self.assertTrue(row["productionSources"])
            self.assertGreaterEqual(len(row["checkpoints"]), 2)
            for name in row["runtimeSlices"]:
                raw = scorer.row_for(self.reports[name], row["key"])
                self.assertEqual([dict(point, runtimeSlice=name) for point in raw["checkpoints"]],
                                 [point for point in row["checkpoints"] if point["runtimeSlice"] == name])

    def test_missing_slice_checkpoints_cannot_be_hidden_by_other_slice(self):
        reports = copy.deepcopy(self.reports)
        scorer.row_for(reports["password"], "password_submit_calls_handle")["checkpoints"] = []
        row = next(row for row in scorer.assemble_final(self.contract, reports) if row["key"] == "password_submit_calls_handle")
        self.assertEqual(row["status"], "not_scored")

    def test_missing_production_slice_provenance_cannot_be_hidden(self):
        reports = copy.deepcopy(self.reports)
        reports["flow"]["provenance"]["productionSources"] = []
        rows = scorer.assemble_final(self.contract, reports)
        self.assertEqual(next(row for row in rows if row["key"] == "confirm_starts_handle")["status"], "not_scored")

    def test_assembled_final_passes_public_validator(self):
        from scripts.run_runtime_transition_matrix import validate_report
        report = {"taskId": scorer.TASK, "platform": "android", "role": "agent",
                  "observationMode": "runtime_state_transition", "semantic": {"cases": scorer.assemble_final(self.contract, self.reports)}}
        validate_report(report, self.contract)

    def test_complete_formal_report_verifies_after_candidate_cleanup(self):
        path = scorer.ASSETS / "common_prefix/verify.py"
        spec = importlib.util.spec_from_file_location("task16_prefix_independent_verifier_test", path)
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        result = verifier.verify(scorer.ROOT /
            "experiment_results/runtime_transition_20261020/task16_android/common-prefix-sanity-v3/final.json")
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["semantic"], {"passed": 10, "failed": 0, "notScored": 0, "total": 10})

    def test_filesystem_closure_reads_arbitrary_standalone_root(self):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw)
            first = source / "features/a/src/main/kotlin/p/A.kt"
            second = source / "libraries/b/src/main/kotlin/p/B.kt"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text("package p\nimport p.B\nclass A(val b: B)\n")
            second.write_text("package p\nclass B\n")
            self.assertEqual(scorer.filesystem_closure(source, [first.relative_to(source).as_posix()]),
                             [first.relative_to(source).as_posix(), second.relative_to(source).as_posix()])


if __name__ == "__main__":
    unittest.main()
