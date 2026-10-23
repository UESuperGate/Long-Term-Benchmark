from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

import validate_multi_project_catalog as validator


class MultiProjectCatalogTest(unittest.TestCase):
    def write(self, root: Path, relative: str, value: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_empty_exploration_catalog_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "https://example.test/app.git"
            self.write(root, "catalog.json", {"projects": [{
                "projectId": "app", "source": source, "catalog": "app/catalog.json"
            }]})
            self.write(root, "app/catalog.json", {
                "projectId": "app", "source": source, "status": "exploring",
                "acceptedTaskIds": [], "excludedTaskIds": []
            })
            self.assertEqual([], validator.validate(root))

    def test_accepted_task_requires_immutable_boundary_and_handoffs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "https://example.test/app.git"
            self.write(root, "catalog.json", {"projects": [{
                "projectId": "app", "source": source, "catalog": "app/catalog.json"
            }]})
            self.write(root, "app/catalog.json", {
                "projectId": "app", "source": source, "status": "calibrating",
                "acceptedTaskIds": ["01_feature"], "excludedTaskIds": []
            })
            self.write(root, "app/tasks/01_feature/task.json", {
                "projectId": "app", "taskId": "01_feature",
                "android": {"repository": source, "baseRef": "v1", "baseCommit": "a",
                            "finalRef": "v2", "finalCommit": "b"},
                "handoff": {"requirement": "requirement.md", "evidence": "evidence.json",
                            "transitions": "transitions.json", "observerRules": "observer_rules.json"}
            })
            for name in ("requirement.md", "evidence.json", "observer_rules.json"):
                (root / "app/tasks/01_feature" / name).write_text("{}", encoding="utf-8")
            cases = []
            for index, key in enumerate(("open", "load", "save", "failure", "retry", "complete"), 1):
                case = {
                    "caseId": f"case_{index}", "key": key, "given": {"step": index - 1},
                    "event": {"name": key}, "expected": {"step": index}, "invariants": ["identity preserved"]
                }
                semantic = {name: case[name] for name in ("key", "given", "event", "expected")}
                semantic = {"taskId": "01_feature", **semantic}
                encoded = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
                case["traceDigest"] = hashlib.sha256(encoded.encode()).hexdigest()
                cases.append(case)
            contract = {"taskId": "01_feature", "owner": "evaluator", "cases": cases}
            self.write(root, "app/tasks/01_feature/transitions.json", contract)
            self.write(root, "app/migrations/01_feature/canonical/transitions.json", contract)
            for platform in ("android", "arkts"):
                for role in ("base", "final"):
                    (root / f"app/migrations/01_feature/{platform}/{role}").mkdir(parents=True)
            self.write(root, "app/migrations/01_feature/execution.json", {
                "android": {"baseProject": "android/base", "finalProject": "android/final",
                            "buildCommand": ["build"], "semanticCommand": ["test", "{project}"]},
                "arkts": {"baseProject": "arkts/base", "finalProject": "arkts/final",
                          "buildCommand": ["build"], "semanticCommand": ["test", "{project}"]},
            })
            self.assertEqual([], validator.validate(root))


if __name__ == "__main__":
    unittest.main()
