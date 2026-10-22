from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SPEC = importlib.util.spec_from_file_location("task17_verify", HERE / "verify.py")
VERIFY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VERIFY)


class Task17VerifierMutationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        results = ROOT / "experiment_results/runtime_transition_20261020/task17_android"
        cls.base = json.loads((results / "base-candidate-v6/android_17_pinned_messages_base_calibrated_v1.json").read_text())
        cls.final = json.loads((results / "final-candidate-v2/android_17_pinned_messages_final_calibrated_v1.json").read_text())
        cls.navigation = json.loads((results / "final-navigation-v1/android_17_pinned_messages_final_navigation_v1.json").read_text())
        cls.contract = json.loads((ROOT / "benchmark_tasks/17_pinned_messages/transitions.json").read_text())

    def errors(self, base=None, final=None, navigation=None, contract=None):
        active_contract = contract or self.contract
        return (
            VERIFY.validate_documents(base or self.base, final or self.final, active_contract)
            + VERIFY.validate_navigation(navigation or self.navigation, active_contract)
        )

    def test_reviewed_documents_validate(self):
        self.assertEqual([], self.errors())

    def test_base_pass_or_not_scored_is_rejected(self):
        for status in ("pass", "not_scored"):
            base = copy.deepcopy(self.base)
            base["semantic"]["cases"][0]["status"] = status
            self.assertTrue(self.errors(base=base))

    def test_final_fail_or_not_scored_is_rejected(self):
        for status in ("fail", "not_scored"):
            final = copy.deepcopy(self.final)
            final["semantic"]["cases"][0]["status"] = status
            self.assertTrue(self.errors(final=final))

    def test_commit_and_tree_mutations_are_rejected(self):
        for field in ("commit", "tree"):
            base = copy.deepcopy(self.base)
            base["candidate"][field] = "0" * 40
            self.assertTrue(self.errors(base=base))

    def test_contract_hash_mutation_is_rejected(self):
        final = copy.deepcopy(self.final)
        final["contract"]["sha256"] = "0" * 64
        self.assertTrue(self.errors(final=final))

    def test_trace_digest_mutation_is_rejected(self):
        final = copy.deepcopy(self.final)
        final["semantic"]["cases"][2]["traceDigest"] = "0" * 64
        self.assertTrue(self.errors(final=final))

    def test_observed_state_mutation_is_rejected(self):
        final = copy.deepcopy(self.final)
        final["semantic"]["cases"][3]["observed"]["visibleEventIds"] = ["$b", "$a"]
        self.assertTrue(self.errors(final=final))

    def test_missing_invariant_is_rejected(self):
        final = copy.deepcopy(self.final)
        final["semantic"]["cases"][4]["invariantChecks"] = []
        self.assertTrue(self.errors(final=final))

    def test_base_ui_dispatch_mutation_is_rejected(self):
        base = copy.deepcopy(self.base)
        base["semantic"]["cases"][5]["checkpoints"][1]["state"]["uiDispatches"] = 0
        self.assertTrue(self.errors(base=base))

    def test_base_backstack_mutation_is_rejected(self):
        base = copy.deepcopy(self.base)
        base["semantic"]["cases"][6]["checkpoints"][1]["state"]["backstackTarget"] = "PinnedMessages"
        self.assertTrue(self.errors(base=base))

    def test_reused_base_evidence_is_rejected(self):
        base = copy.deepcopy(self.base)
        base["semantic"]["cases"][1]["runtimeEvidence"] = copy.deepcopy(base["semantic"]["cases"][0]["runtimeEvidence"])
        self.assertTrue(self.errors(base=base))

    def test_reused_final_raw_report_is_rejected(self):
        final = copy.deepcopy(self.final)
        final["semantic"]["cases"][1]["runtimeReport"] = copy.deepcopy(final["semantic"]["cases"][0]["runtimeReport"])
        self.assertTrue(self.errors(final=final))

    def test_compile_failure_cannot_be_semantic_fail(self):
        base = copy.deepcopy(self.base)
        base["runtimeCompile"]["status"] = "failed"
        self.assertTrue(self.errors(base=base))

    def test_isolation_mutation_is_rejected(self):
        final = copy.deepcopy(self.final)
        final["isolation"]["separateJvmPerCase"] = False
        self.assertTrue(self.errors(final=final))

    def test_sdk_unpin_boundary_mutation_is_rejected(self):
        final = copy.deepcopy(self.final)
        row = next(item for item in final["semantic"]["cases"] if item["key"] == "unpin_success")
        row["checkpoints"][-1]["state"]["unpinCalls"] = []
        self.assertTrue(self.errors(final=final))

    def test_retry_boundary_mutation_is_rejected(self):
        final = copy.deepcopy(self.final)
        row = next(item for item in final["semantic"]["cases"] if item["key"] == "unpin_failure_recovery")
        row["checkpoints"][-1]["state"]["retryUnpinCalls"] = 1
        self.assertTrue(self.errors(final=final))

    def test_upstream_source_hash_mutation_is_rejected(self):
        source = copy.deepcopy(self.base["provenance"]["productionSources"][0])
        source["sha256"] = "0" * 64
        errors = []
        VERIFY.verify_upstream([source], VERIFY.BASE_TREE, "mutated-base", errors)
        self.assertTrue(errors)

    def test_local_artifact_hash_mutation_is_rejected(self):
        record = copy.deepcopy(self.base["provenance"]["runner"])
        record["sha256"] = "0" * 64
        self.assertFalse(VERIFY.record_matches(record))

    def test_final_navigation_backstack_mutation_is_rejected(self):
        navigation = copy.deepcopy(self.navigation)
        navigation["semantic"]["navigation"]["after"] = "Messages(focusedEventId=null)"
        self.assertTrue(self.errors(navigation=navigation))

    def test_final_navigation_node_build_mutation_is_rejected(self):
        navigation = copy.deepcopy(self.navigation)
        navigation["semantic"]["navigation"]["pinnedNodeBuilds"] = 0
        self.assertTrue(self.errors(navigation=navigation))

    def test_navigation_v2_requires_actual_checkpoints(self):
        navigation = copy.deepcopy(self.navigation)
        semantic = navigation["semantic"]
        semantic["evidenceSchemaVersion"] = 2
        semantic["observed"] = {"backstackTarget": "PinnedMessagesList", "pinnedNodeBuilds": 1}
        semantic["checkpoints"] = [
            {"name": "common_start", "state": {"backstackTarget": "Messages(focusedEventId=null)"}},
            {"name": "post_event", "state": {"backstackTarget": "PinnedMessagesList",
                                                 "uiDispatches": 1, "pinnedNodeBuilds": 1}}]
        self.assertEqual([], self.errors(navigation=navigation))
        semantic["checkpoints"][1]["state"]["backstackTarget"] = "Messages(focusedEventId=null)"
        self.assertTrue(self.errors(navigation=navigation))

    def test_navigation_v2_cannot_use_a_canonical_projection_as_actual_evidence(self):
        navigation = copy.deepcopy(self.navigation)
        navigation["semantic"]["evidenceSchemaVersion"] = 2
        self.assertTrue(self.errors(navigation=navigation))

    def test_navigation_v3_parent_invariant_uses_actual_backstack(self):
        navigation = copy.deepcopy(self.navigation)
        semantic = navigation["semantic"]
        semantic["evidenceSchemaVersion"] = 3
        semantic["observed"] = {"backstackTarget": "PinnedMessagesList", "pinnedNodeBuilds": 1}
        semantic["navigation"].update(beforeKeys=["timeline-key"], afterKeys=["timeline-key", "pinned-key"],
                                       timelineParentRetained=True)
        semantic["checkpoints"] = [
            {"name": "common_start", "state": {"backstackTarget": "Messages(focusedEventId=null)",
                                                  "backstackKeys": ["timeline-key"]}},
            {"name": "post_event", "state": {"backstackTarget": "PinnedMessagesList", "uiDispatches": 1,
                                                 "pinnedNodeBuilds": 1, "backstackKeys": ["timeline-key", "pinned-key"],
                                                 "timelineParentRetained": True}}]
        semantic["invariantChecks"][0]["evidence"] = {
            "beforeKeys": ["timeline-key"], "afterKeys": ["timeline-key", "pinned-key"]}
        self.assertEqual([], self.errors(navigation=navigation))
        changed = copy.deepcopy(navigation)
        changed["semantic"]["navigation"]["afterKeys"] = ["pinned-key"]
        self.assertTrue(self.errors(navigation=changed))
        semantic["invariantChecks"][0]["evidence"] = {"parentFlow": "room_timeline"}
        self.assertTrue(self.errors(navigation=navigation))


if __name__ == "__main__":
    unittest.main()
