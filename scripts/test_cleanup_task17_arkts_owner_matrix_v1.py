#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cleanup_task17_owner", ROOT / "scripts/cleanup_task17_arkts_owner_matrix_v1.py"
)
CLEANUP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CLEANUP)


class Task17OwnerCleanupTests(unittest.TestCase):
    def test_removes_only_hash_verified_owned_haps(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task17-owner-cleanup-", dir=ROOT) as directory:
            root = Path(directory)
            build = root / "case" / "build"
            build.mkdir(parents=True)
            hap = build / "entry-default-unsigned.hap"
            hap.write_bytes(b"verified hap")
            digest = hashlib.sha256(hap.read_bytes()).hexdigest()
            (build / "device-build-report.json").write_text(json.dumps({
                "haps": [{"path": str(hap), "bytes": hap.stat().st_size, "sha256": digest}]
            }))
            removed = CLEANUP.remove_haps(root)
            self.assertEqual(1, len(removed))
            self.assertTrue(removed[0]["deleted"])
            self.assertFalse(hap.exists())

    def test_refuses_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task17-owner-cleanup-", dir=ROOT) as directory:
            root = Path(directory)
            build = root / "build"
            build.mkdir()
            hap = build / "entry-ohosTest-unsigned.hap"
            hap.write_bytes(b"tampered")
            (build / "device-build-report.json").write_text(json.dumps({
                "haps": [{"path": str(hap), "bytes": hap.stat().st_size, "sha256": "0" * 64}]
            }))
            with self.assertRaisesRegex(ValueError, "differs from retained build metadata"):
                CLEANUP.remove_haps(root)
            self.assertTrue(hap.exists())


if __name__ == "__main__":
    unittest.main()
