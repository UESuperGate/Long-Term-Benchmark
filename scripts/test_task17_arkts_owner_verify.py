#!/usr/bin/env python3
"""Mutation tests for the Task17 owner-bound ArkTS verifier."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "experiment_results/runtime_transition_20261022/task17_arkts_owner_matrix_v1/matrix.json"
SPEC = importlib.util.spec_from_file_location(
    "task17_arkts_owner_verify", ROOT / "scripts/runtime_semantics/task17_arkts_owner_verify.py"
)
VERIFY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VERIFY)


class Task17OwnerVerifierMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MATRIX.is_file():
            raise unittest.SkipTest(f"owner-bound matrix unavailable: {MATRIX}")
        cls.document = json.loads(MATRIX.read_text(encoding="utf-8"))

    def verify_mutation(self, mutate) -> None:
        document = copy.deepcopy(self.document)
        mutate(document)
        with tempfile.TemporaryDirectory(prefix="task17-owner-verify-", dir=ROOT) as directory:
            matrix = Path(directory) / "matrix.json"
            matrix.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(VERIFY.VerificationError):
                VERIFY.verify_matrix(matrix)

    def test_complete_matrix_passes(self) -> None:
        result = VERIFY.verify_matrix(MATRIX)
        self.assertTrue(result["validated"])
        self.assertEqual({"pass": 0, "fail": 9}, result["roles"]["base"])
        self.assertEqual({"pass": 9, "fail": 0}, result["roles"]["final"])
        self.assertEqual({"pass": 2, "fail": 7}, result["roles"]["agent"])

    def test_rejects_incomplete_matrix(self) -> None:
        self.verify_mutation(lambda value: value.__setitem__("complete", False))

    def test_rejects_unscored_row(self) -> None:
        self.verify_mutation(lambda value: value["rows"][20].__setitem__("status", "not_scored"))

    def test_rejects_compile_mutation(self) -> None:
        self.verify_mutation(lambda value: value["rows"][9].__setitem__("compile", False))

    def test_rejects_case_reordering(self) -> None:
        def mutate(value):
            value["rows"][0], value["rows"][1] = value["rows"][1], value["rows"][0]
        self.verify_mutation(mutate)

    def test_rejects_evidence_digest_mutation(self) -> None:
        self.verify_mutation(lambda value: value["rows"][18]["nativeResult"].__setitem__("sha256", "0" * 64))

    def test_rejects_base_polarity_mutation(self) -> None:
        self.verify_mutation(lambda value: value["rows"][0].__setitem__("status", "pass"))


if __name__ == "__main__":
    unittest.main()
