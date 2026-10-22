"""Lightweight orchestration checks; no hvigor, device lock or model operation."""
import inspect
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.runtime_semantics import task13_page_owner_controls as controls
from scripts.runtime_semantics import task13_arkts_strict_runtime as runtime
from scripts.runtime_semantics import task13_page_owner_entry_audit as audit


class ControlsTest(unittest.TestCase):
    def test_shared_budget_survives_process_local_macos_monotonic_origin(self):
        budget = {'startedEpoch': 1000, 'startedMonotonic': 0.03}
        self.assertEqual(controls.deadline_for_budget(budget, epoch=1600, monotonic=0.1), 3000.1)
        self.assertEqual(controls.deadline_for_budget(budget, epoch=4601, monotonic=0.2), 0.2)

    def test_no_independent_unbounded_runtime_deadline(self):
        source = inspect.getsource(runtime.evaluate)
        self.assertNotIn('time.monotonic() + 3600', source)
        self.assertIn('deadline -= 60', source)
        self.assertIn('with support.arkts_device_lock(serial=serial, deadline=deadline)', source)
        self.assertIn('deadline=deadline', source)

    def test_entry_policy_source_and_canonical_freeze(self):
        policy = audit.load_policy(audit.core.load(audit.CANONICAL))
        self.assertEqual(policy['canonicalContractSha256'], 'c038fddc0beba7933076cef4f63a8d156ccf914628cb39c3b5eec708c7035e90')
        self.assertEqual(len(policy['caseDigests']), 9)

    def test_direct_script_importer_no_implicit_repository_sys_path(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, '-B', str(root / 'scripts/runtime_semantics/task13_page_owner_entry_audit.py')],
                                cwd='/tmp', capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
