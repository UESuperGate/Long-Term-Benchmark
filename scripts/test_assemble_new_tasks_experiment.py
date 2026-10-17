#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("assemble_new_tasks_experiment.py")
SPEC = importlib.util.spec_from_file_location("assemble_new_tasks_experiment", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SemanticMetricTest(unittest.TestCase):
    def test_not_scored_cases_are_excluded_from_metric_denominator(self) -> None:
        payload = {
            "semantic": {
                "cases": [
                    {"caseId": "pass", "status": "pass"},
                    {"caseId": "fail", "status": "fail"},
                    {"caseId": "missing", "status": "not_scored"},
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text(json.dumps(payload), encoding="utf-8")

            result = MODULE.semantic(report)

        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["notScored"], 1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["expectedTotal"], 3)
        self.assertFalse(result["available"])

    def test_archive_provenance_copies_patches_and_hashes_local_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluation = root / "evaluation"
            calibration = root / "calibration"
            output = root / "output"
            (evaluation / "patches").mkdir(parents=True)
            (evaluation / "logs").mkdir()
            calibration.mkdir()
            output.mkdir()
            (evaluation / "eval_manifest.json").write_text('{"runId":"test"}\n', encoding="utf-8")
            (evaluation / "patches" / "android_task.patch").write_text("patch\n", encoding="utf-8")
            (evaluation / "logs" / "android_task.jsonl").write_text("log\n", encoding="utf-8")
            (calibration / "calibration_summary.json").write_text('{"allPolarityValid":true}\n', encoding="utf-8")

            MODULE.archive_provenance(evaluation, calibration, output)

            index = json.loads((output / "provenance/evidence_index.json").read_text(encoding="utf-8"))
            patch = next(row for row in index["artifacts"] if row["kind"] == "agent_patch")
            log = next(row for row in index["artifacts"] if row["kind"] == "local_run_log")
            self.assertTrue((output / patch["path"]).exists())
            self.assertTrue(patch["published"])
            self.assertFalse(log["published"])
            self.assertEqual(len(patch["sha256"]), 64)
            self.assertEqual(len(log["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
