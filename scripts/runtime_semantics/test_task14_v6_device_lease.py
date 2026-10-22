import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.runtime_semantics import task14_v6_device_lease as lease


class Task14V6DeviceLeaseTests(unittest.TestCase):
    def test_derivation_binds_provider_without_modifying_shared_executor(self):
        original = lease.prior.shared.ROOT / "scripts/runtime_semantics/arkts_device_execute.cjs"
        before = original.read_bytes()
        source, changes = lease.derive_executor_source(original)
        self.assertEqual(original.read_bytes(), before)
        self.assertIn("TASK14_NATIVE_E2E_CONFIG", source)
        self.assertIn("task14ExternalProvider", source)
        self.assertIn("'task14E2E', '1'", source)
        self.assertIn("'task14Homeserver'", source)
        self.assertIn("run('aa-test', command, 240000)", source)
        self.assertNotIn("run('aa-test', command, 150000)", source)
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                         hashlib.sha256(before).hexdigest())
        self.assertEqual(len(changes), len(set(changes)))


if __name__ == "__main__":
    unittest.main()
