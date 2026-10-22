#!/usr/bin/env python3
import json
import tempfile
import sys
import unittest
from unittest import mock
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task17_android_strict_agent as scorer
import task17_android_entry_evidence as policy


class Task17AndroidStrictAgentTest(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(scorer.CONTRACT.read_text())

    def base_raw(self, key):
        return {"key": key, "status": "fail", "reason": "real clicked prefix stayed on timeline",
                "observed": {"screen": "room_timeline", "pinnedListReachable": False},
                "checkpoints": [
                    {"name": "common_start", "state": {"screen": "room_timeline", "pinnedBannerVisible": True,
                        "viewAllLabel": "View All", "flowClass": "io.element.android.features.messages.impl.MessagesFlowNode",
                        "backstackTarget": "Messages"}},
                    {"name": "post_event", "state": {"event": "open_pinned_messages", "uiDispatches": 1,
                        "backstackTarget": "Messages", "screen": "room_timeline", "pinnedListReachable": False}}]}

    def test_base_prefix_requires_all_nine_clean_runtime_methods(self):
        with tempfile.TemporaryDirectory(dir=scorer.ROOT / "experiment_results") as raw:
            case_dir = Path(raw)
            methods = {}
            for case in self.contract["cases"]:
                methods[case["key"]] = {"classname": "runtime.task17.BasePrefixRuntimeTest",
                                         "failure": False, "error": False, "skipped": False}
                (case_dir / f"{case['key']}.json").write_text(json.dumps(self.base_raw(case["key"])))
            probe = {"methods": methods, "caseDir": str(case_dir), "productionSources": [],
                     "junit": {}, "evaluatorSource": {}, "log": {}, "execution": {}}
            rows = scorer.base_probe_rows(probe, self.contract)
            self.assertEqual([row["status"] for row in rows], ["fail"] * 9)
            self.assertTrue(all(row["observed"] is None and row["invariantChecks"] == [] for row in rows))
            self.assertEqual(len({row["entryFailureEvidence"]["runtimeEvidence"]["path"] for row in rows}), 9)
            methods[self.contract["cases"][0]["key"]]["error"] = True
            self.assertIsNone(scorer.base_probe_rows(probe, self.contract))

    def test_navigation_assertion_without_actual_evidence_is_ns(self):
        base_rows = [{"key": case["key"], "status": "pass"} for case in self.contract["cases"]]
        with tempfile.TemporaryDirectory() as raw:
            probe = {"methods": {"open_loading_navigation": {
                "classname": "runtime.task17.FinalNavigationRuntimeTest", "failure": True,
                "error": False, "skipped": False}}, "caseDir": Path(raw)}
            scorer.apply_navigation(base_rows, probe)
            self.assertEqual(base_rows[0]["status"], "not_scored")
            base_rows[0]["status"] = "pass"
            probe["methods"]["open_loading_navigation"].update(failure=False, error=True)
            scorer.apply_navigation(base_rows, probe)
            self.assertEqual(base_rows[0]["status"], "not_scored")

    def test_final_configuration_is_candidate_source_parameterizable(self):
        config = scorer.final_configuration("filled_list", Path("unused"))
        self.assertEqual(config["keys"], ["filled_list"])
        self.assertTrue(config["entrypoints"])
        self.assertNotIn("commit", config)
        self.assertNotIn("tree", config)

    def test_navigation_failure_requires_actual_failed_target(self):
        raw = self.base_raw("open_loading")
        raw["checkpoints"][0]["state"]["backstackTarget"] = "Messages(focusedEventId=null)"
        raw["checkpoints"][0]["state"]["backstackKeys"] = ["messages-key"]
        raw["checkpoints"][1]["state"].update(backstackTarget="Messages(focusedEventId=null)", pinnedNodeBuilds=0,
                                              backstackKeys=["messages-key"], timelineParentRetained=False)
        raw["navigation"] = {"after": "Messages(focusedEventId=null)", "beforeKeys": ["messages-key"],
                             "afterKeys": ["messages-key"], "timelineParentRetained": False}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "open_loading_navigation.json"
            path.write_text(json.dumps(raw))
            probe = {"caseDir": directory, "methods": {"open_loading_navigation": {
                "classname": "runtime.task17.FinalNavigationRuntimeTest", "failure": True, "error": False,
                "skipped": False}}, "productionSources": [], "junit": {}, "evaluatorSource": {},
                "log": {}, "execution": {}}
            rows = [{"key": "open_loading", "status": "pass", "observed": {"screen": "pinned_messages"}}]
            scorer.apply_navigation(rows, probe)
            self.assertEqual(rows[0]["status"], "fail")
            self.assertIsNone(rows[0]["observed"])
            self.assertEqual(rows[0]["actualCheckpoints"], raw["checkpoints"])
            raw["checkpoints"][1]["state"].update(backstackTarget="PinnedMessagesList", pinnedNodeBuilds=1,
                                                  backstackKeys=["messages-key", "pinned-key"], timelineParentRetained=True)
            with self.assertRaises(ValueError):
                policy.check_actual(raw, "navigation_prefix", "open_loading")

    def test_navigation_parent_loss_has_actual_failure_evidence(self):
        raw = self.base_raw("open_loading")
        raw["checkpoints"][0]["state"].update(backstackTarget="Messages(focusedEventId=null)", backstackKeys=["messages-key"])
        raw["checkpoints"][1]["state"].update(backstackTarget="PinnedMessagesList", pinnedNodeBuilds=1,
                                              backstackKeys=["pinned-key"], timelineParentRetained=False)
        raw["navigation"] = {"after": "PinnedMessagesList", "beforeKeys": ["messages-key"],
                             "afterKeys": ["pinned-key"], "timelineParentRetained": False}
        policy.check_actual(raw, "navigation_prefix", "open_loading")
        raw["checkpoints"][1]["state"]["timelineParentRetained"] = True
        with self.assertRaises(ValueError):
            policy.check_actual(raw, "navigation_prefix", "open_loading")

    def test_final_slices_preserve_actual_production_sources(self):
        spec = self.contract["cases"][0]
        sources = [{"path": "actual.kt", "bytes": 4, "sha256": "runtime-digest"}]
        runtime = {"runtimeCompile": {"status": "passed"}, "provenance": {"productionSources": sources},
                   "observations": [{"key": spec["key"], "status": "pass", "checkpoints": [{}, {}]}]}
        with tempfile.TemporaryDirectory() as raw, \
                mock.patch.object(scorer, "filesystem_closure", return_value=["actual.kt"]), \
                mock.patch.object(scorer.android_robolectric, "run_slice", return_value=runtime):
            result = scorer.run_final_slices(Path(raw), Path(raw), scorer.time.monotonic() + 30, {"cases": [spec]})
            self.assertEqual(result["rows"][0]["productionSources"], sources)

    def test_source_binding_failure_is_not_semantic_failure(self):
        with tempfile.TemporaryDirectory() as raw, \
                mock.patch.object(scorer, "filesystem_closure", side_effect=ValueError("entry absent")):
            result = scorer.run_final_slices(Path(raw), Path(raw), scorer.time.monotonic() + 30, self.contract)
            self.assertTrue(all(row["status"] == "not_scored" for row in result["rows"]))

    def test_prefix_rejects_undispatched_click_and_forged_target(self):
        for field, value in (("uiDispatches", 0), ("backstackTarget", "PinnedMessagesList"),
                             ("pinnedListReachable", True)):
            raw = self.base_raw("open_loading")
            raw["checkpoints"][1]["state"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                policy.check_actual(raw, "base_prefix", "open_loading")

    def test_source_bound_policy_and_mutations(self):
        spec = self.contract["cases"][0]
        with tempfile.TemporaryDirectory(dir=scorer.ROOT / "experiment_results") as directory:
            work = Path(directory)
            raw = work / "open_loading.json"
            raw.write_text(json.dumps(self.base_raw(spec["key"])))
            junit = work / "junit.xml"
            junit.write_text('<testsuite><testcase name="open_loading" classname="runtime.task17.BasePrefixRuntimeTest"/></testsuite>')
            evaluator = work / "BasePrefixRuntimeTest.kt"
            evaluator.write_bytes((scorer.HERE / evaluator.name).read_bytes())
            log = work / "gradle.log"
            log.write_text("runtime completed")
            sources, snapshots = [], {}
            for i, path in enumerate(sorted(policy.REQUIRED)):
                snapshot = work / f"source-{i}.kt"
                snapshot.write_text(f"executed production bytes {i}")
                item = policy.artifact(snapshot)
                sources.append({**item, "path": path})
                snapshots[path] = item
            probe = {"junit": policy.artifact(junit), "log": policy.artifact(log),
                     "evaluatorSource": policy.artifact(evaluator), "productionSources": sources}
            execution = work / "execution.json"
            execution.write_text(json.dumps({**probe, "kind": "base", "candidateSource": str(work),
                                             "command": [str(work / "gradlew")]}))
            probe["execution"] = policy.artifact(execution)
            row = policy.entry_row(spec, probe, raw, kind="base_prefix")
            report = {"taskId": scorer.TASK, "platform": "android", "observationMode": "runtime_state_transition",
                      "provenance": {"productionSources": sources, "productionSourceSnapshots": snapshots,
                                     "candidateSource": str(work)}}
            ids = set()
            policy.validate_entry_failure(row, report, ids, self.contract)
            with self.assertRaises(ValueError):
                policy.validate_entry_failure(row, report, ids, self.contract)
            for field, value in (("observed", {"listState": "failed"}), ("transitionExecuted", True),
                                 ("invariantChecks", [{"status": "pass"}]), ("actualCheckpoints", [])):
                changed = copy.deepcopy(row)
                changed[field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    policy.validate_entry_failure(changed, report, set(), self.contract)
            snapshot.write_text("changed candidate production")
            with self.assertRaises(ValueError):
                policy.validate_entry_failure(row, report, set(), self.contract)


if __name__ == "__main__":
    unittest.main()
