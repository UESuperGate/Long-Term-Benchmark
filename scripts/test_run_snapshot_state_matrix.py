#!/usr/bin/env python3
"""Focused regression tests for strict state-phase scoring."""

from __future__ import annotations

import json
import unittest

from run_snapshot_state_matrix import score_case, tree_selector_facts


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


if __name__ == "__main__":
    unittest.main()
