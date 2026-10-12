#!/usr/bin/env python3
"""Focused regression tests for strict state-phase scoring."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from run_snapshot_state_matrix import Runner, score_case, tree_selector_facts


class StateMatrixScoringTest(unittest.TestCase):
    def test_layout_nodes_produce_independent_selector_facts(self) -> None:
        layout = {
            "attributes": {},
            "children": [
                {
                    "attributes": {
                        "id": "open_editor",
                        "key": "open_editor",
                        "visible": "true",
                        "enabled": "true",
                        "text": "Open",
                    },
                    "children": [],
                },
                {
                    "attributes": {
                        "id": "status_value",
                        "key": "status_value",
                        "visible": "true",
                        "enabled": "true",
                        "text": "Away",
                    },
                    "children": [],
                },
            ],
        }
        selectors = {
            "visible": ["open_editor"],
            "hidden": ["error_banner"],
            "enabled": ["open_editor"],
            "disabled": [],
            "properties": {"status_value": "Away"},
        }
        facts = tree_selector_facts(json.dumps(layout), selectors)
        self.assertEqual(
            facts,
            {
                "visible:open_editor",
                "hidden:error_banner",
                "enabled:open_editor",
                "property:status_value=Away",
            },
        )

    def test_strict_mode_requires_transition_phase_evidence(self) -> None:
        case = {
            "selectors": {"visible": ["entry"]},
            "expectedInitialFacts": ["visible:entry"],
            "transitionSelectors": [
                {
                    "ordinal": 1,
                    "event": "open",
                    "visible": ["dialog"],
                    "hidden": [],
                    "enabled": [],
                    "disabled": [],
                    "properties": {},
                }
            ],
        }
        capture = {
            "initial": {
                "readyObserved": True,
                "status": "captured",
                "layoutText": "",
                "snapshot": {
                    "semanticFacts": [
                        "visible:entry",
                        "transition:1:open",
                        "transition:1:visible:dialog",
                    ]
                },
            },
            "transitions": [],
        }
        strict = score_case(capture, "pass", case, "strict")
        compatible = score_case(capture, "pass", case, "compatible")
        self.assertEqual(strict["observedPolarity"], "fail")
        self.assertEqual(compatible["observedPolarity"], "pass")

    def test_strict_mode_accepts_acknowledged_transition_state(self) -> None:
        case = {
            "selectors": {"visible": ["entry"]},
            "expectedInitialFacts": ["visible:entry"],
            "transitionSelectors": [
                {
                    "ordinal": 1,
                    "event": "open",
                    "visible": ["dialog"],
                    "hidden": [],
                    "enabled": [],
                    "disabled": [],
                    "properties": {},
                }
            ],
        }
        capture = {
            "initial": {
                "readyObserved": True,
                "status": "captured",
                "layoutText": "",
                "snapshot": {"semanticFacts": ["visible:entry"]},
            },
            "transitions": [
                {
                    "readyObserved": True,
                    "status": "captured",
                    "layoutText": "",
                    "snapshot": {"lastEvent": "open#1", "semanticFacts": ["visible:dialog"]},
                    "eventLaunchExit": 0,
                }
            ],
        }
        result = score_case(capture, "pass", case, "strict")
        self.assertEqual(result["observedPolarity"], "pass")
        self.assertEqual(result["missingFacts"], [])

    def test_transport_snapshot_with_empty_facts_is_semantic_failure(self) -> None:
        case = {
            "selectors": {"visible": ["entry"]},
            "expectedInitialFacts": ["visible:entry"],
            "transitionSelectors": [],
        }
        capture = {
            "initial": {
                "readyObserved": True,
                "status": "captured",
                "layoutText": "",
                "snapshot": {"caseId": "case-1", "ready": True, "semanticFacts": []},
            },
            "transitions": [],
        }

        result = score_case(capture, "pass", case, "strict")

        self.assertEqual(result["semanticStatus"], "failed")
        self.assertEqual(result["strictStatus"], "mismatch")
        self.assertEqual(result["missingFacts"], ["visible:entry"])

    def test_strict_mode_rejects_candidate_prefixed_transition_facts(self) -> None:
        case = {
            "selectors": {"visible": ["entry"]},
            "expectedInitialFacts": ["visible:entry"],
            "expectedFacts": ["visible:entry", "transition:1:open", "transition:1:visible:dialog"],
            "transitionSelectors": [{
                "ordinal": 1,
                "event": "open",
                "visible": ["dialog"],
                "hidden": [],
                "enabled": [],
                "disabled": [],
                "properties": {},
            }],
        }
        capture = {
            "integrity": {"valid": True},
            "evidencePolicy": "trusted_external_observer",
            "initial": {"readyObserved": True, "status": "captured", "layoutText": "", "snapshot": {"semanticFacts": ["visible:entry"]}},
            "transitions": [{
                "readyObserved": True,
                "status": "captured",
                "layoutText": "",
                "snapshot": {"lastEvent": "open", "semanticFacts": ["transition:1:visible:dialog"]},
            }],
        }
        result = score_case(capture, "pass", case, "strict")
        self.assertEqual(result["observedPolarity"], "fail")
        self.assertIn("transition:1:visible:dialog", result["missingFacts"])

    def test_contradictory_snapshot_fails(self) -> None:
        case = {
            "selectors": {"visible": ["entry"]},
            "expectedInitialFacts": ["visible:entry"],
            "expectedFacts": ["visible:entry"],
            "transitionSelectors": [],
        }
        capture = {
            "integrity": {"valid": True},
            "evidencePolicy": "trusted_external_observer",
            "initial": {
                "readyObserved": True,
                "status": "captured",
                "layoutText": "",
                "snapshot": {"semanticFacts": ["visible:entry", "hidden:entry"]},
            },
            "transitions": [],
        }
        result = score_case(capture, "pass", case, "strict")
        self.assertEqual(result["semanticStatus"], "failed")
        self.assertEqual(result["reason"], "contradictory_semantic_facts")

    def test_ui_tree_policy_ignores_self_reported_snapshot_facts(self) -> None:
        case = {
            "selectors": {"visible": ["entry"]},
            "expectedInitialFacts": ["visible:entry"],
            "expectedFacts": ["visible:entry"],
            "transitionSelectors": [],
        }
        capture = {
            "integrity": {"valid": True},
            "evidencePolicy": "ui_tree_only",
            "initial": {
                "readyObserved": True,
                "status": "captured",
                "layoutText": "{}",
                "snapshot": {"semanticFacts": ["visible:entry"]},
            },
            "transitions": [],
        }
        result = score_case(capture, "pass", case, "strict")
        self.assertEqual(result["observedPolarity"], "fail")

    def test_android_phase_query_url_encodes_state_event(self) -> None:
        runner = Runner({"targets": [], "caseTargets": []}, Path("unused"), android_serial="emulator-5556")
        calls: list[list[str]] = []

        def fake_adb(args: list[str], timeout: int = 60) -> tuple[int, str]:
            calls.append(args)
            return 0, 'Row: 0 snapshot={"caseId":"case-1","lastEvent":"open panel","semanticFacts":[]}'

        runner.adb = fake_adb  # type: ignore[method-assign]
        with tempfile.TemporaryDirectory() as directory:
            phase = runner.capture_android_provider_phase(
                {"package": "io.element.android.x.debug"},
                "case-1",
                "transition_1",
                Path(directory),
                "open panel",
            )

        self.assertTrue(phase["readyObserved"])
        self.assertIn("stateEvent=open+panel", calls[0][-1])

    def test_android_initial_query_retries_once_after_cold_start_failure(self) -> None:
        runner = Runner(
            {"targets": [], "caseTargets": []},
            Path("unused"),
            android_serial="emulator-5556",
            poll_interval=0,
        )
        calls = 0

        def fake_adb(args: list[str], timeout: int = 60) -> tuple[int, str]:
            nonlocal calls
            calls += 1
            if calls == 1:
                return 1, "Error while accessing provider"
            return 0, 'Row: 0 snapshot={"caseId":"case-1","semanticFacts":[]}'

        runner.adb = fake_adb  # type: ignore[method-assign]
        with tempfile.TemporaryDirectory() as directory:
            phase = runner.capture_android_provider_phase(
                {"package": "io.element.android.x.debug"},
                "case-1",
                "initial",
                Path(directory),
            )

        self.assertTrue(phase["readyObserved"])
        self.assertEqual(phase["queryAttempts"], 2)

    def test_external_observer_requires_matching_trace_digest(self) -> None:
        runner = Runner({"targets": [], "caseTargets": []}, Path("unused"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_dir = root / "case-1"
            case_dir.mkdir()
            bundle = case_dir / "capture.json"
            bundle.write_text(
                json.dumps({
                    "observerOwner": "evaluator",
                    "caseId": "case-1",
                    "traceDigest": "wrong",
                    "capture": {"initial": {"readyObserved": True}},
                }),
                encoding="utf-8",
            )
            capture, detail = runner.external_observer_capture(
                {"externalObservationDir": str(root)},
                "case-1",
                {"traceDigest": "expected"},
            )
            self.assertEqual(detail["status"], "external_capture_invalid")
            self.assertEqual(capture["initial"]["status"], "external_capture_invalid")

            payload = json.loads(bundle.read_text(encoding="utf-8"))
            payload["traceDigest"] = "expected"
            bundle.write_text(json.dumps(payload), encoding="utf-8")
            capture, detail = runner.external_observer_capture(
                {"externalObservationDir": str(root)},
                "case-1",
                {"traceDigest": "expected"},
            )
            self.assertEqual(detail["status"], "external_capture_loaded")
            self.assertTrue(capture["initial"]["readyObserved"])


if __name__ == "__main__":
    unittest.main()
