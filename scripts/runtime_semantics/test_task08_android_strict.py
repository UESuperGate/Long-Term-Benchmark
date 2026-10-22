import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
import sys
sys.path.insert(0, str(HERE))


def load_target():
    spec = importlib.util.spec_from_file_location(
        'task08_android_strict_test_target', HERE / 'task08_android_strict.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Task08AndroidStrictTest(unittest.TestCase):
    def test_withdrawn_adapter_is_not_executed_as_formal_runtime_fallback(self):
        target = load_target()
        with tempfile.TemporaryDirectory() as directory, patch.object(target.subprocess, 'run') as execute:
            output = Path(directory) / 'strict.json'
            report = target.run(ROOT / '_sources/element-x-android', 'base', output, 100)
        execute.assert_not_called()
        self.assertFalse(report['diagnostics']['strictReady'])
        self.assertFalse(report['diagnostics']['publishable'])
        self.assertNotIn('compile', report)
        self.assertEqual('not_run', report['runtimeCompile']['status'])
        self.assertEqual(['not_scored'] * 9, [row['status'] for row in report['semantic']['cases']])

    def test_dynamic_candidate_does_not_promote_adapter_marker_rows(self):
        target = load_target()
        contract = json.loads((ROOT / 'benchmark_tasks/08_threads/transitions.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate-randomized-name'
            candidate.mkdir()
            (candidate / 'feature.kt').write_text('class CandidateFeature\n')
            output = root / 'strict.json'
            expected_digest = target.directory_digest(candidate)
            commands = []

            def execute(command, **kwargs):
                commands.append(command)
                self.assertEqual(90, kwargs['timeout'])
                self.assertEqual('90.0', command[command.index('--timeout') + 1])
                self.assertEqual(str(candidate.resolve()), command[command.index('--source') + 1])
                self.assertNotIn('--adapter-config', command)
                self.assertIn('--no-supplemental', command)
                adapter_output = Path(command[command.index('--output') + 1])
                rows = [{'caseId': case['caseId'], 'key': case['key'],
                         'traceDigest': case['traceDigest'], 'status': 'pass'}
                        for case in contract['cases']]
                adapter_output.write_text(json.dumps({
                    'taskId': '08_threads', 'platform': 'android',
                    'runtimeCompile': {'passed': True, 'status': 'passed'},
                    'semantic': {'cases': rows},
                    'provenance': {'candidateMode': 'standalone_directory',
                                   'archivedPatchApplied': False,
                                   'candidateRootSha256': expected_digest},
                    'diagnostics': {'adapter': 'ready'},
                }))
                return subprocess.CompletedProcess(command, 0, stdout='strict adapter complete\n', stderr='')

            with patch.object(target, 'LEGACY_ADAPTER_WITHDRAWN', False), \
                    patch.object(target.subprocess, 'run', side_effect=execute), \
                    patch.object(target.time, 'monotonic', side_effect=[10.0, 20.0, 30.0]):
                report = target.run(candidate, 'agent', output, 100)
            self.assertEqual(1, len(commands))
            self.assertFalse(report['diagnostics']['strictReady'])
            self.assertFalse(report['diagnostics']['publishable'])
            self.assertEqual(['not_scored'] * 9, [row['status'] for row in report['semantic']['cases']])
            self.assertEqual(expected_digest, report['provenance']['candidateRootSha256'])
            self.assertTrue(report['runtimeCompile']['passed'])
            self.assertNotIn('compile', report)
            self.assertIn('no reviewed complete RoomFlow/UI', report['diagnostics']['reason'])

    def test_candidate_provenance_mismatch_fails_closed_to_nine_ns(self):
        target = load_target()
        contract = json.loads((ROOT / 'benchmark_tasks/08_threads/transitions.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate'
            candidate.mkdir()
            (candidate / 'feature.kt').write_text('class CandidateFeature\n')
            output = root / 'strict.json'

            def execute(command, **_kwargs):
                adapter_output = Path(command[command.index('--output') + 1])
                adapter_output.write_text(json.dumps({
                    'taskId': '08_threads', 'platform': 'android',
                    'runtimeCompile': {'passed': True, 'status': 'passed'},
                    'semantic': {'cases': [
                        {'caseId': case['caseId'], 'key': case['key'],
                         'traceDigest': case['traceDigest'], 'status': 'pass'}
                        for case in contract['cases']]},
                    'provenance': {'candidateMode': 'standalone_directory',
                                   'archivedPatchApplied': False,
                                   'candidateRootSha256': 'wrong-source'},
                    'diagnostics': {'adapter': 'ready'},
                }))
                return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

            with patch.object(target, 'LEGACY_ADAPTER_WITHDRAWN', False), \
                    patch.object(target.subprocess, 'run', side_effect=execute):
                report = target.run(candidate, 'agent', output, 100)
            self.assertFalse(report['diagnostics']['strictReady'])
            self.assertEqual(['not_scored'] * 9,
                             [row['status'] for row in report['semantic']['cases']])
            self.assertIn('no reviewed complete RoomFlow/UI', report['diagnostics']['reason'])


if __name__ == '__main__':
    unittest.main()
