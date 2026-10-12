#!/usr/bin/env python3
"""Regression tests for Android benchmark metric summarization."""

from __future__ import annotations

import unittest

from summarize_android_benchmark import summarize


class AndroidBenchmarkSummaryTest(unittest.TestCase):
    def test_only_three_headline_metrics_and_missing_rows_count_as_no_pass(self) -> None:
        manifest = {
            "runId": "test",
            "tasks": [
                {"id": "task_a", "codeGenerated": True, "buildExit": 0, "agentTimedOut": False},
                {"id": "task_b", "codeGenerated": False, "buildExit": 1, "agentTimedOut": True},
            ],
        }
        report = {
            "results": [
                {
                    "taskId": "task_a",
                    "caseId": "a1",
                    "platform": "android",
                    "targetRole": "agent_result",
                    "semanticStatus": "passed",
                    "strictStatus": "matched",
                },
                {
                    "taskId": "task_a",
                    "caseId": "a2",
                    "platform": "android",
                    "targetRole": "agent_result",
                    "semanticStatus": "failed",
                    "strictStatus": "mismatch",
                },
            ]
        }
        result = summarize(manifest, report, {"task_a": 2, "task_b": 3})
        self.assertEqual(
            set(result["benchmarkMetrics"]),
            {"codeGeneration", "compile", "semanticTestcase"},
        )
        self.assertEqual(result["benchmarkMetrics"]["codeGeneration"]["passed"], 1)
        self.assertEqual(result["benchmarkMetrics"]["compile"]["passed"], 1)
        self.assertEqual(result["benchmarkMetrics"]["semanticTestcase"], {"passed": 1, "total": 5, "rate": 0.2})
        self.assertEqual(result["diagnostics"]["semanticRowsObserved"], 2)
        self.assertEqual(result["diagnostics"]["semanticRowsExpected"], 5)


if __name__ == "__main__":
    unittest.main()
