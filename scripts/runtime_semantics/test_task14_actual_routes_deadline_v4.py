"""Real short process/timer tests. Fake worker does no SDK/device/model work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from . import task14_actual_routes_scorer_v4 as full


class DeadlineTests(unittest.TestCase):
    def run_case(self, *, finish=False, slow_assembly=False):
        with tempfile.TemporaryDirectory(prefix='offline-task14-deadline-',
                dir=full.packaging.ROOT / 'experiment_results/runtime_transition_20261020') as raw:
            root = Path(raw) / 'capture'
            process = None
            popen = subprocess.Popen
            def prepare(**kwargs):
                kwargs['output'].mkdir()
                (kwargs['output'] / 'plan.json').write_text('{}')
            def launch(argv, **options):
                nonlocal process
                request = Path(argv[-1])
                script = 'import time; time.sleep(60)'
                if finish:
                    script = ('import json,time; from pathlib import Path; '
                        'Path(' + repr(str(request.parent / 'worker-finished.json')) + ').write_text(json.dumps({"completed":True})); '
                        'time.sleep(60)')
                process = popen([sys.executable, '-B', '-c', script], **options)
                return process
            def assemble(*args, **kwargs):
                if slow_assembly:
                    time.sleep(1)
                return full._fallback(full.packaging.ROOT, True, 'original passed compile', 'synthetic completed diagnostic')
            started = time.monotonic()
            with patch.object(full.packaging, 'prepare', side_effect=prepare), \
                    patch.object(full.subprocess, 'Popen', side_effect=launch), \
                    patch.object(full, 'assemble', side_effect=assemble):
                value = full.evaluate(source=full.packaging.ROOT, output=root, timeout=0.5,
                    compile_passed=True, compile_command='original passed compile', execute=True)
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 0.9)
            self.assertFalse(value['publication']['eligible'])
            self.assertTrue(value['compile']['passed'])
            self.assertIsNotNone(process)
            self.assertIsNotNone(process.returncode, 'Owned worker must be reaped')
            with self.assertRaises(ProcessLookupError):
                os.kill(process.pid, 0)
            seal = json.loads((root.with_name('capture-supervision') / 'admission.json').read_text())
            self.assertEqual(seal['state'], 'complete_diagnostic_only' if finish and not slow_assembly else 'revoked')
            written = json.loads((root / 'report.json').read_text())
            self.assertTrue(written['compile']['passed'])
            self.assertFalse(written['publication']['eligible'])

    def test_owned_worker_timeout_cannot_be_semantic_fail(self):
        self.run_case()

    def test_assembly_is_inside_same_deadline_and_revokes_atomically(self):
        self.run_case(finish=True, slow_assembly=True)

    def test_short_normal_path_preserves_diagnostic_only_seal(self):
        self.run_case(finish=True)


if __name__ == '__main__':
    unittest.main()
