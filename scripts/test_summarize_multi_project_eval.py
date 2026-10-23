from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import summarize_multi_project_eval as subject


class SummarizeMultiProjectEvalTest(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def fixture(self, root: Path, semantic: dict[str, int]) -> tuple[Path, Path]:
        catalog = root / "benchmark_projects/catalog.json"
        self.write_json(catalog, {
            "projects": [{"projectId": "project", "catalog": "project/catalog.json"}],
        })
        self.write_json(catalog.parent / "project/catalog.json", {"acceptedTaskIds": ["task"]})
        for platform in ("android", "arkts"):
            self.write_json(root / f"run/project/task/{platform}-agent.json", {
                "taskId": "task",
                "platform": platform,
                "codeGeneration": {"passed": platform == "android"},
                "compile": {"passed": True},
                "semantic": semantic,
            })
        return root / "run", catalog

    def test_summarizes_both_semantic_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, catalog = self.fixture(root, {
                "summary": {"passed": 4, "failed": 6, "notScored": 0, "total": 10},
            })
            result = subject.summarize(run, catalog)
            self.assertEqual({"passed": 1, "total": 2, "rate": 0.5}, result["metrics"]["codeGeneration"])
            self.assertEqual({"passed": 8, "total": 20, "rate": 0.4}, result["metrics"]["semanticTestcase"])

            for platform in ("android", "arkts"):
                report = run / f"project/task/{platform}-agent.json"
                payload = json.loads(report.read_text())
                payload["semantic"] = {"passed": 7, "failed": 3, "notScored": 0, "total": 10}
                self.write_json(report, payload)
            result = subject.summarize(run, catalog)
            self.assertEqual(14, result["metrics"]["semanticTestcase"]["passed"])

    def test_rejects_unscored_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, catalog = self.fixture(root, {
                "passed": 0, "failed": 9, "notScored": 1, "total": 10,
            })
            with self.assertRaisesRegex(ValueError, "unscored"):
                subject.summarize(run, catalog)

    def test_rejects_missing_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, catalog = self.fixture(root, {
                "passed": 0, "failed": 10, "notScored": 0, "total": 10,
            })
            (run / "project/task/arkts-agent.json").unlink()
            with self.assertRaises(FileNotFoundError):
                subject.summarize(run, catalog)


if __name__ == "__main__":
    unittest.main()
