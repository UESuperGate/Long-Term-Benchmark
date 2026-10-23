#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("audit_arkts_runtime_harness.py")
SPEC = importlib.util.spec_from_file_location("audit_arkts_runtime_harness", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ArktsRuntimeHarnessAuditTest(unittest.TestCase):
    def test_pages_harness(self) -> None:
        AUDIT.audit_task(SCRIPT.resolve().parents[1], "01_pages_list")

    def test_unified_support_harness(self) -> None:
        AUDIT.audit_task(SCRIPT.resolve().parents[1], "02_unified_support")

    def test_hidden_adapter_uses_stable_base_surface(self) -> None:
        migrations = SCRIPT.resolve().parents[1]
        for task_id in AUDIT.TASKS:
            with self.subTest(task_id=task_id):
                AUDIT.audit_hidden_adapter(migrations, task_id)

    def test_agent_draft_transport_allows_nonretained_controller(self) -> None:
        rows = []
        for index in range(10):
            evidence = {
                "pageOwnerId": f"owner-{index}-new",
                "controllerOwnerId": f"controller-{index}-new",
                "storeSource": "UnifiedSupportPageOwner.controller.store",
                "evaluatorStoreWrites": 0,
                "detachedControllers": 0,
                "leafCalls": [],
            }
            key = "draft_lifecycle" if index == 8 else f"case_{index}"
            if key == "draft_lifecycle":
                evidence.update({
                    "pageRecreated": True,
                    "previousPageOwnerId": "owner-8-old",
                    "previousControllerOwnerId": "controller-8-old",
                })
            rows.append({
                "caseId": f"SUP-{index + 1:03d}", "key": key, "status": "fail",
                "observed": {}, "effects": [],
                "checkpoints": [{"label": "before", "state": {}}, {"label": "after", "state": {}}],
                "runtimeEvidence": evidence,
            })
        report = {
            "taskId": "02_unified_support", "role": "agent",
            "device": {"apiLevel": 23, "target": "127.0.0.1:10180"},
            "semantic": {"summary": {"passed": 0, "failed": 10, "notScored": 0, "total": 10}, "cases": rows},
            "diagnostics": {"transport": "hdc", "productionEntryExecuted": True},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            AUDIT.audit_no_change_report(path, "02_unified_support", "127.0.0.1:10180")


if __name__ == "__main__":
    unittest.main()
