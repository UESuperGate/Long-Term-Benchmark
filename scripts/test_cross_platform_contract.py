import json
import unittest
from pathlib import Path

from generate_cross_platform_contract import canonical_digest, generate
from project_cross_platform_results import combine, project_android, project_arkts


ROOT = Path(__file__).resolve().parents[1]


class CrossPlatformContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bindings = json.loads((ROOT / "state_tests/canonical/cross_platform_bindings.json").read_text(encoding="utf-8"))
        official = json.loads((ROOT / "state_tests/canonical/official_transition_contract.json").read_text(encoding="utf-8"))
        cls.cases = generate(bindings, official)

    def test_contract_has_unique_shared_cases(self):
        expected_count = sum(
            len(task["cases"])
            for task in json.loads(
                (ROOT / "state_tests/canonical/cross_platform_bindings.json").read_text(encoding="utf-8")
            )["tasks"].values()
        )
        self.assertEqual(expected_count, 37)
        self.assertEqual(len(self.cases), expected_count)
        self.assertEqual(len({case["caseId"] for case in self.cases}), expected_count)
        self.assertEqual(len({case["traceDigest"] for case in self.cases}), expected_count)
        self.assertEqual(
            {case["taskId"] for case in self.cases},
            {
                "01_user_status",
                "02_gallery_messages",
                "03_timeline_protection_rich_events",
                "04_live_location",
                "05_link_new_device",
            },
        )

    def test_digest_uses_platform_neutral_semantics(self):
        case = self.cases[0]
        self.assertEqual(case["traceDigest"], canonical_digest(case))
        self.assertNotIn("androidEvidence", {
            "taskId": case["taskId"],
            "key": case["key"],
            "given": case["given"],
            "event": case["event"],
            "expected": case["expected"],
        })

    def test_status_combination_is_conservative(self):
        self.assertEqual(combine(["passed", "passed"]), "passed")
        self.assertEqual(combine(["passed", "failed"]), "failed")
        self.assertEqual(combine(["passed", "not_scored"]), "not_scored")
        self.assertEqual(combine([]), "not_scored")

    def test_android_projection_requires_every_bound_method(self):
        case = self.cases[0]
        source_cases = [
            {
                "taskId": case["taskId"],
                "className": item["className"],
                "methodName": item["methodName"],
                "semanticStatus": "passed",
            }
            for item in case["androidEvidence"]
        ]
        rows = project_android({"cases": source_cases}, {"cases": [case]})
        self.assertEqual(rows[0]["semanticStatus"], "passed")
        source_cases[0]["semanticStatus"] = "failed"
        rows = project_android({"cases": source_cases}, {"cases": [case]})
        self.assertEqual(rows[0]["semanticStatus"], "failed")

    def test_arkts_projection_uses_bound_trace_case(self):
        case = self.cases[0]
        report = {
            "results": [{
                "targetId": "final",
                "targetRole": "groundtruth_final",
                "platform": "arkts",
                "taskId": case["taskId"],
                "caseId": case["arktsEvidence"]["traceCaseId"],
                "semanticStatus": "passed",
            }]
        }
        rows = project_arkts(report, {"cases": [case]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["caseId"], case["caseId"])
        self.assertEqual(rows[0]["traceDigest"], case["traceDigest"])
        self.assertEqual(rows[0]["semanticStatus"], "passed")


if __name__ == "__main__":
    unittest.main()
