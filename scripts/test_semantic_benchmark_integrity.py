#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from semantic_candidate_integrity import audit_candidate
from state_test_public_contract import render_public_contract


ROOT = Path(__file__).resolve().parents[1]


class PublicContractTest(unittest.TestCase):
    def test_oracle_outputs_are_removed_but_inputs_remain(self) -> None:
        source = """cases:
  - id: sample
    given_state:
      mode: closed
    expect_ui:
      visible: [entry]
    transitions:
      - event: open
        to_state:
          mode: open
        expect_ui:
          visible: [dialog]
    parity_assertions:
      - both show dialog
"""
        public = render_public_contract(source)
        self.assertIn("given_state:", public)
        self.assertIn("- event: open", public)
        self.assertNotIn("expect_ui", public)
        self.assertNotIn("to_state", public)
        self.assertNotIn("parity_assertions", public)
        self.assertNotIn("visible: [dialog]", public)

    def test_all_public_contracts_hide_evaluator_outputs(self) -> None:
        for path in sorted((ROOT / "state_tests").glob("elementx-state-test*.yaml")):
            public = render_public_contract(path.read_text(encoding="utf-8-sig"))
            for token in ("expect_ui:", "to_state:", "runtime_oracle:", "parity_assertions:"):
                self.assertNotIn(token, public, f"{path.name}: {token}")

    def test_platform_neutral_traces_cover_all_cases_once(self) -> None:
        cases = []
        for path in sorted((ROOT / "state_tests" / "traces").glob("*.trace.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data["platformNeutral"])
            cases.extend(data["cases"])
        self.assertEqual(len(cases), 150)
        self.assertEqual(len({case["caseId"] for case in cases}), 150)
        self.assertTrue(all(len(case["traceDigest"]) == 64 for case in cases))
        self.assertTrue(all(phase["stateConstraintYaml"] for case in cases for phase in case["phases"]))


class CandidateIntegrityTest(unittest.TestCase):
    def init_candidate(self, root: Path) -> None:
        source = root / "features/foo/src/main/kotlin/Foo.kt"
        source.parent.mkdir(parents=True)
        source.write_text("class Foo\n", encoding="utf-8")
        scaffold = root / "app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt"
        scaffold.parent.mkdir(parents=True)
        scaffold.write_text("object StateTestScenario\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "baseline"],
            cwd=root,
            check=True,
        )

    def test_normal_production_change_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            self.init_candidate(root)
            (root / "features/foo/src/main/kotlin/Foo.kt").write_text("class Foo { fun open() = true }\n", encoding="utf-8")
            self.assertTrue(audit_candidate(root, "android")["valid"])

    def test_modified_scaffold_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            self.init_candidate(root)
            scenario = root / "app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt"
            scenario.write_text('object StateTestScenario { val semanticFacts = listOf("visible:entry") }\n', encoding="utf-8")
            result = audit_candidate(root, "android")
            self.assertFalse(result["valid"])
            self.assertEqual(result["status"], "candidate_oracle_detected")


if __name__ == "__main__":
    unittest.main()
