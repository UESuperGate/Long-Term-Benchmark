#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_full_reconstruction", ROOT / "scripts" / "audit_full_reconstruction.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FullReconstructionAuditTest(unittest.TestCase):
    def test_audit_fails_closed_for_current_incomplete_reconstruction(self) -> None:
        report = MODULE.audit()
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("native_sdk_linked", report)
        self.assertIn("native_client_lifecycle_ready", report)
        self.assertTrue(report["failures"])

    def test_final_and_progress_dispositions_do_not_overlap(self) -> None:
        self.assertFalse(MODULE.FINAL_DISPOSITIONS & MODULE.PROGRESS_DISPOSITIONS)

    def test_native_export_patterns_accept_bridge_lifecycle_names(self) -> None:
        self.assertIsNotNone(MODULE.CLIENT_CREATE_EXPORT.search("elementx_matrix_bridge_create_client"))
        self.assertIsNotNone(MODULE.CLIENT_RELEASE_EXPORT.search("elementx_matrix_bridge_release_client"))

    def test_spec_forbids_fixture_backed_completion(self) -> None:
        spec = (ROOT / "specs" / "elementx-full-client-reconstruction.md").read_text(encoding="utf-8")
        self.assertIn("ArkTS must not import or instantiate fixture", spec)
        self.assertIn("unmapped`, `planned`, and `partial`", spec)


if __name__ == "__main__":
    unittest.main()
