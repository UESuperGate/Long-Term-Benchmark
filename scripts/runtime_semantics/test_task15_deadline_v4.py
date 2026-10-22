"""Real short timers/owned subprocesses only. No SDK, device or model execution."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from . import task15_deadline_v4 as timer
from . import task15_supervision_v4 as supervisor
from . import task15_full_report_v4 as full
from . import task15_full_report_verify_v4 as guard


class TimerTests(unittest.TestCase):
    def test_normal_timer_restores_exclusive_ownership(self):
        with timer.OverallDeadline(0.5) as clock:
            value = clock.child_budget(0.01)
            self.assertEqual({'remainingSeconds', 'deadlineEpochMs'}, set(value))
            self.assertLess(value['remainingSeconds'], 0.5)
        self.assertEqual(signal.SIG_DFL, signal.getsignal(signal.SIGALRM))
        self.assertEqual((0.0, 0.0), signal.getitimer(signal.ITIMER_REAL))

    def test_real_hard_alarm_interrupts_cleanup_no_restarted_budget(self):
        start = time.monotonic()
        with self.assertRaises(timer.HardDeadlineExpired):
            with timer.OverallDeadline(0.2):
                try:
                    time.sleep(2)
                except timer.WorkDeadlineExpired:
                    time.sleep(2)
        self.assertLess(time.monotonic() - start, 0.5)
        self.assertEqual((0.0, 0.0), signal.getitimer(signal.ITIMER_REAL))

    def test_foreign_alarm_is_not_replaced_or_cancelled(self):
        handler = lambda *_: None
        signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, 5)
        try:
            with self.assertRaises(timer.DeadlineOwnershipError):
                with timer.OverallDeadline(0.2):
                    self.fail('Work started under foreign ownership')
            self.assertIs(handler, signal.getsignal(signal.SIGALRM))
            self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0], 4)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)

    def test_thread_refused_before_any_files(self):
        errors = []
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw:
            output = Path(raw) / 'unstarted'
            def call():
                try:
                    supervisor.supervise(mode='candidate', output=output, timeout=0.1)
                except BaseException as error:
                    errors.append(error)
            worker = threading.Thread(target=call)
            worker.start(); worker.join(timeout=2)
            self.assertEqual(1, len(errors))
            self.assertIsInstance(errors[0], timer.DeadlineOwnershipError)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_name(output.name + '-supervision').exists())

    def test_same_process_clock_and_cross_process_relative_budget(self):
        with timer.OverallDeadline(0.5) as clock:
            with mock.patch.object(timer.os, 'getpid', return_value=-99):
                with self.assertRaises(timer.DeadlineOwnershipError):
                    clock.check_work()
        payload = {'remainingSeconds': 1.5, 'deadlineEpochMs': int((time.time() + 1.5) * 1000)}
        # Simulate a Python 3.9 monotonic origin unrelated to the parent's.
        with mock.patch.object(timer.time, 'monotonic', return_value=987654321):
            value = timer.child_local_deadline(payload)
            self.assertGreater(value, 987654321)
            self.assertLessEqual(value, 987654322.5)
        payload['deadlineEpochMs'] = int((time.time() - 1) * 1000)
        with self.assertRaises(timer.WorkDeadlineExpired):
            timer.child_local_deadline(payload)

    def test_invalid_budgets_refused(self):
        for value in (0, -1, True, float('inf'), float('nan'), 3600.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                timer.OverallDeadline(value)


class SupervisorTests(unittest.TestCase):
    def launch_fixture(self, code):
        original = subprocess.Popen
        seen = []
        def launch(argv, **kwargs):
            # A real isolated child, but explicitly not a runtime/control fixture.
            request = argv[argv.index('--worker') + 1]
            wrapped = code + '\nimport json,time,pathlib\npathlib.Path(' + repr(str(Path(request).parent / 'worker-finished.json')) + ").write_text(json.dumps({'completed': True}))\ntime.sleep(10)"
            child = original([sys.executable, '-B', '-c', wrapped], **kwargs)
            seen.append(child)
            return child
        return mock.patch.object(supervisor.subprocess, 'Popen', side_effect=launch), seen

    def test_real_ignores_term_process_cannot_extend_hard_deadline(self):
        patch, children = self.launch_fixture('import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)')
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw, patch:
            output = Path(raw) / 'late'
            start = time.monotonic()
            result = supervisor.supervise(mode='candidate', output=output, timeout=0.45,
                arguments={'compile_passed': True, 'compile_command': 'UNIT prior application proof'})
            self.assertLess(time.monotonic() - start, 0.8)
            self.assertEqual((0, 0, 10), tuple(result['semantic'][key] for key in ('passed', 'failed', 'notScored')))
            self.assertTrue(result['compile']['passed'])
            seal = full.core.load(output.with_name(output.name + '-supervision') / 'admission.json')
            self.assertEqual('revoked', seal['state'])
            # Bounded test teardown reaps only this test's child, never a foreign PID.
            children[0].wait(timeout=1)
            self.assertIsNotNone(children[0].poll())

    def test_slow_finalizer_and_post_seal_delay_atomically_revoke(self):
        for writes_seal in (False, True):
            patch, _ = self.launch_fixture('pass')
            def slow(mode, output, scope, clock, stopped, temporary):
                output.mkdir()
                full.core.write(output / 'report.json', {'UNIT_ONLY': True})
                if writes_seal:
                    supervisor.atomic_json(scope / 'admission.json', {'state': 'complete', 'publicationEligible': True})
                time.sleep(1)
                self.fail('Timer failed to interrupt finalization')
            with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw, patch, \
                    mock.patch.object(supervisor, '_finalize', side_effect=slow):
                output = Path(raw) / 'late-finalize'
                start = time.monotonic()
                result = supervisor.supervise(mode='candidate', output=output, timeout=0.4)
                self.assertLess(time.monotonic() - start, 0.75)
                self.assertEqual(10, result['semantic']['notScored'])
                self.assertEqual('revoked', full.core.load(output.with_name(output.name + '-supervision') / 'admission.json')['state'])
                self.assertEqual(10, full.core.load(output / 'report.json')['semantic']['notScored'])
                self.assertTrue((output / 'report.unadmitted.json').exists())

    def test_slow_cleanup_hard_stop_does_not_restart_timeout(self):
        patch, _ = self.launch_fixture('pass')
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw, patch, \
                mock.patch.object(supervisor, '_cleanup_temporary', side_effect=lambda *_: time.sleep(1)):
            output = Path(raw) / 'slow-cleanup'
            start = time.monotonic()
            result = supervisor.supervise(mode='candidate', output=output, timeout=0.3)
            self.assertLess(time.monotonic() - start, 0.65)
            self.assertEqual(10, result['semantic']['notScored'])
            scope = output.with_name(output.name + '-supervision')
            self.assertEqual('revoked', full.core.load(scope / 'admission.json')['state'])
            self.assertFalse((scope / 'temporary-cleanup.json').exists())
            self.assertEqual((0.0, 0.0), signal.getitimer(signal.ITIMER_REAL))

    def test_worker_receives_only_relative_and_epoch_clock_fields(self):
        patch, _ = self.launch_fixture('raise SystemExit(1)')
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw, patch:
            output = Path(raw) / 'no-device'
            supervisor.supervise(mode='candidate', output=output, timeout=1)
            request = full.core.load(output.with_name(output.name + '-supervision') / 'request.json')
            self.assertEqual({'remainingSeconds', 'deadlineEpochMs'}, set(request['childBudget']))
            self.assertNotIn('deadline', request['arguments'])
            self.assertLess(request['childBudget']['remainingSeconds'], 1)

    def test_real_timer_covers_public_guard_hashing_and_report_serialization(self):
        code = "import json,pathlib,sys; request=json.loads(pathlib.Path(sys.argv[1]).read_text()); output=pathlib.Path(request['output']); output.mkdir(); (output/'report.json').write_text(json.dumps({'diagnostics':{}, 'UNIT_ONLY':True}))"
        original_popen = subprocess.Popen
        for phase in ('public_guard', 'hashing', 'serialization'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw:
                output = Path(raw) / 'phase'
                def launch(argv, **kwargs):
                    request = argv[argv.index('--worker') + 1]
                    wrapped = code + "\n(pathlib.Path(sys.argv[1]).parent/'worker-finished.json').write_text(json.dumps({'completed':True}))\nimport time; time.sleep(10)"
                    return original_popen([sys.executable, '-B', '-c', wrapped, request], **kwargs)
                original_atomic = supervisor.atomic_json
                original_artifact = full.raw.artifacts.artifact
                def write(path, value):
                    if phase == 'serialization' and Path(path) == output / 'report.json':
                        time.sleep(1)
                    return original_atomic(path, value)
                def artifact(path):
                    if phase == 'hashing' and Path(path) == output / 'report.json':
                        time.sleep(1)
                    return original_artifact(path)
                def verify(_):
                    if phase == 'public_guard':
                        time.sleep(1)
                    return {'publicationEligible': True, 'UNIT_ONLY': True}
                with mock.patch.object(supervisor.subprocess, 'Popen', side_effect=launch), \
                        mock.patch.object(supervisor, 'atomic_json', side_effect=write), \
                        mock.patch.object(full.raw.artifacts, 'artifact', side_effect=artifact), \
                        mock.patch.object(guard, '_verify_report_unsealed', side_effect=verify):
                    started = time.monotonic()
                    result = supervisor.supervise(mode='candidate', output=output, timeout=0.4)
                    self.assertLess(time.monotonic() - started, 0.75)
                self.assertEqual(10, result['semantic']['notScored'])
                self.assertEqual('revoked', full.core.load(output.with_name(output.name + '-supervision') / 'admission.json')['state'])

    def test_preexisting_scope_is_untouched_on_refusal(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw:
            output = Path(raw) / 'already-owned'
            scope = output.with_name(output.name + '-supervision'); scope.mkdir()
            marker = scope / 'revoked.json'; marker.write_bytes(b'foreign sentinel')
            with self.assertRaisesRegex(ValueError, 'Never overwrite'):
                supervisor.supervise(mode='candidate', output=output, timeout=1)
            self.assertEqual(b'foreign sentinel', marker.read_bytes())
            self.assertFalse((scope / 'admission.json').exists())

    def test_controls_cannot_combine_four_new_standalone_deadlines(self):
        refs = {pole: {'path': '/UNIT/' + pole + '/report.json'} for pole in
            ('base', 'final', 'base_copy_agent', 'final_copy_agent')}
        with mock.patch.object(supervisor, 'verify_admission', return_value={'mode': 'candidate'}), \
                mock.patch.object(guard, '_verify_controls_unsealed') as raw_guard:
            with self.assertRaisesRegex(ValueError, 'one control budget'):
                guard.verify_controls(refs, evaluator_sha='UNIT')
            raw_guard.assert_not_called()

    def test_failed_group_has_no_invented_aggregate_semantic_verdict(self):
        patch, _ = self.launch_fixture('raise SystemExit(1)')
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw, patch:
            output = Path(raw) / 'failed-group'
            result = supervisor.supervise(mode='controls', output=output, timeout=0.4)
            self.assertEqual('not_ready', result['status'])
            self.assertFalse(result['semanticReportsAdmitted'])
            self.assertNotIn('semantic', result)
            self.assertEqual('not_ready', full.core.load(output / 'four-controls.json')['status'])

    def test_cleanup_hashes_owned_binary_and_never_follows_foreign_symlink(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw:
            root = Path(raw); scope = root / 'scope'; scope.mkdir()
            temporary = scope / 'work-tmp'; temporary.mkdir()
            binary = temporary / 'unit.hap'; binary.write_bytes(b'not a real HAP')
            digest = full.core.sha256(binary)
            foreign = root / 'foreign'; foreign.mkdir()
            (foreign / 'keep.txt').write_text('foreign cache')
            (temporary / 'cache-link').symlink_to(foreign, target_is_directory=True)
            receipt = supervisor._cleanup_temporary(root / 'out', scope)
            manifest = full.raw.read(receipt)
            self.assertEqual(digest, next(item['sha256'] for item in manifest['files'] if item['path'].endswith('unit.hap')))
            self.assertFalse(temporary.exists())
            self.assertEqual('foreign cache', (foreign / 'keep.txt').read_text())

    def test_deadline_cli_and_four_controls_do_not_default_to_execution(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw:
            output = Path(raw) / 'never'
            with self.assertRaisesRegex(ValueError, 'explicit coordinator release'):
                full.run_four_controls(base_source=Path('UNIT'), final_source=Path('UNIT'), output=output)
            self.assertFalse(output.exists())


class NormalCompatibilityTests(unittest.TestCase):
    def test_modal_geometry_json_boundary_in_successor_has_original_assertions(self):
        from . import task15_native_transition_v3 as old
        from . import task15_native_transition_v4 as projection
        from .test_task15_fresh_protocol_v2 import unit_transition
        # Synthetic raw-schema projection only; not actual native evidence.
        self.assertEqual(Path(old.__file__).read_text(), Path(projection.__file__).read_text().replace('import json\n', '', 1))
        value = unit_transition(6)
        self.assertEqual('pass', projection.inspect_transition(value)['status'])
        for mutation in ('wrong_geometry', 'transport_error', 'value_changed'):
            changed = copy.deepcopy(value)
            if mutation == 'wrong_geometry':
                next(item for item in changed['native']['actions'] if item['kind'] == 'modal_physical_input')['geometry'] = [[0, 0], [1, 1]]
            elif mutation == 'transport_error':
                changed['native']['modalProbe']['inputError'] = 'hypium failed'
            else:
                changed['native']['frames'][-1]['presenter']['password'] = 'tampered'
            if mutation == 'value_changed':
                self.assertEqual('fail', projection.inspect_transition(changed)['status'])
            else:
                with self.assertRaises(ValueError):
                    projection.inspect_transition(changed)

    def test_real_five_host_episodes_default_guard_and_seal_then_reject_mutations(self):
        # Real production VM only. The five absent native cases MUST remain NS.
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as raw:
            root = Path(raw)
            source = full.ROOT / 'final_dev_nodes/15_account_deactivation_final_0_6_3'
            evidence = root / 'episodes'
            index, deadline = full.prepare_index(source=source, output=evidence, timeout=120)
            for case_id in sorted(full.HOST_CASES):
                directory = evidence / 'host' / case_id
                plan = full.prepare_host(source=source, case_id=case_id, output=directory,
                    deadline=deadline, inputs=index['inputInventory'])
                full.command(plan['command'], log=directory / 'host.log', deadline=deadline)
                index['host'][case_id] = {key: full.raw.artifacts.artifact(path) for key, path in {
                    'plan': directory / 'plan.json', 'raw': directory / 'raw.json',
                    'command': directory / 'host.command.json'}.items()}
            index['finishedAtEpochMs'] = int(time.time() * 1000)
            full.core.write(evidence / 'episode-index.json', index)
            output = root / 'assembled'
            report = supervisor.supervise(mode='assemble', output=output, timeout=90,
                arguments={'index': full.raw.artifacts.artifact(evidence / 'episode-index.json')})
            self.assertEqual((5, 0, 5), tuple(report['semantic'][key] for key in ('passed', 'failed', 'notScored')))
            receipt = guard.verify_report(output / 'report.json')
            self.assertTrue(guard.verify_value(report, full.core.load(full.native.CONTRACT))['publicValidatorPassed'])
            self.assertFalse(receipt['publicationEligible'])
            self.assertTrue(receipt['publicValidatorPassed'])
            seal_path = output.with_name(output.name + '-supervision') / 'admission.json'
            original = seal_path.read_bytes()
            for mutation in ('revoked', 'late', 'source', 'process_alive', 'report_hash', 'cleanup_missing'):
                seal = json.loads(original)
                if mutation == 'revoked': seal['state'] = 'revoked'
                elif mutation == 'late': seal['elapsedSecondsBeforeAdmissionCommit'] = 90.01
                elif mutation == 'source': seal['evaluatorSha256'] = '0' * 64
                elif mutation == 'process_alive': seal['ownedProcessCleanup']['groupGone'] = False
                elif mutation == 'report_hash': seal['files'][0]['sha256'] = '0' * 64
                else: seal['temporaryCleanup']['sha256'] = '0' * 64
                supervisor.atomic_json(seal_path, seal)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    guard.verify_report(output / 'report.json')
                with self.subTest(value_api=mutation), self.assertRaises(ValueError):
                    guard.verify_value(report, full.core.load(full.native.CONTRACT))
                seal_path.write_bytes(original)

    def test_v3_and_public_frozen_source_bytes_untouched(self):
        review = full.core.load(full.ROOT / 'experiment_results/runtime_transition_20261020/task15_full_report_v3/review.json')
        for row in review['implementationSources']:
            record = row['original']
            self.assertEqual(record['sha256'], full.core.sha256(Path(record['path'])))
        self.assertEqual('161152c2020795051922411f675a3ba3b82d022a30a723376ed9b9b3f33b3e73',
            full.core.sha256(full.ROOT / 'scripts/run_runtime_transition_matrix.py'))


if __name__ == '__main__':
    unittest.main()
