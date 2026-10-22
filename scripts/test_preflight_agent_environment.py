import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('standalone_preflight', Path(__file__).with_name('preflight_agent_environment.py'))
target = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target)
ACTUAL = target.load_runner()


class PreflightTests(unittest.TestCase):
    def setup_runner(self, root, build_exit=0):
        source = root / 'untouched-base'
        feature = source / 'entry/src/main/ets/Feature.ets'
        feature.parent.mkdir(parents=True)
        feature.write_text('export class OriginalFeature {}\n')
        runner_file = root / 'runner.py'
        runner_file.write_text('actual runner version\n')
        helper = root / 'audit.py'
        helper.write_text('actual audit version\n')
        events = []
        def prepare(task, platform, temporary, *, deadline=None):
            self.assertEqual('arkts', platform)
            events.append('prepare')
            candidate = temporary / platform / task
            shutil.copytree(source, candidate)
            return candidate
        def archive(candidate, output, phase, *, deadline=None):
            events.append('archive')
            self.assertEqual('preflight_before_standalone_build', phase)
            return {'path': 'source.tar.gz', 'capturePhase': phase}
        def environment(platform, candidate):
            events.append('environment')
            return {'PWD': str(candidate), 'OLDPWD': str(candidate), 'PATH': '/safe',
                    'SECRET_API_KEY': 'must-not-be-serialized'}
        def build(platform, candidate, env, log, *, deadline=None):
            events.append('build')
            directory = candidate / 'entry/build'
            directory.mkdir()
            (directory / 'application.hap').write_bytes(b'actual HAP bytes')
            (directory / 'modules.abc').write_bytes(b'actual intermediate bytes')
            log.write_text('standalone assembleHap\n')
            return build_exit, 'actual-runner standalone build command'
        def cleanup(candidate, output, *, deadline=None):
            events.append('clean-build')
            target.write(output, {'cleanupCompleted': True})
            shutil.rmtree(candidate / 'entry/build', ignore_errors=True)
        def remove(candidate, *, deadline=None):
            events.append('clean-candidate')
            shutil.rmtree(candidate)
        runner = SimpleNamespace(__file__=str(runner_file), ROOT=root,
            subagent_audit=SimpleNamespace(__file__=str(helper)),
            require_disk_space=Mock(), task_data=Mock(return_value={'arkts': {'basePath': source.name}}),
            prepare=Mock(side_effect=prepare), archive_candidate_baseline=Mock(side_effect=archive),
            environment=Mock(side_effect=environment), build=Mock(side_effect=build),
            status_paths=Mock(return_value=[]), is_production=ACTUAL.is_production,
            clean_application_build=Mock(side_effect=cleanup), clean_candidate=Mock(side_effect=remove),
            opencode_config=ACTUAL.opencode_config, fixed_shell_allowlist=ACTUAL.fixed_shell_allowlist,
            agent_build_command=ACTUAL.agent_build_command,
            score=Mock(side_effect=AssertionError('no evaluator is permitted')),
            run_one=Mock(side_effect=AssertionError('no model is permitted')))
        confirmation = root / 'review.json'
        target.write(confirmation, {'reviewer': 'test reviewer', 'recursiveAuditStable': True,
            'runnerSha256': target.record(runner_file)['sha256'],
            'auditHelperSha256': target.record(helper)['sha256']})
        return runner, confirmation, events

    def test_reuses_prepare_archive_environment_build_and_hash_cleanup_without_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, events = self.setup_runner(root)
            result = target.preflight(root / 'evidence', confirmation, runner=runner)
            self.assertTrue(result['passed'])
            self.assertEqual(['prepare', 'archive', 'environment', 'build', 'clean-build', 'clean-candidate'] * 2, events)
            self.assertTrue(all(row['cleanup']['candidateRemoved'] for row in result['tasks']))
            self.assertNotIn('must-not-be-serialized', json.dumps(result))
            for task in target.DEFAULT_TASKS:
                hashes = json.loads((root / 'evidence' / task / 'all-binary-hashes.json').read_text())
                self.assertEqual({'.hap', '.abc'}, {Path(item['path']).suffix for item in hashes['artifacts']})
                self.assertTrue(all(len(item['sha256']) == 64 for item in hashes['artifacts']))
            runner.score.assert_not_called()
            runner.run_one.assert_not_called()

    def test_build_failure_blocks_generation_and_still_hashes_cleans(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, _ = self.setup_runner(root, build_exit=1)
            result = target.preflight(root / 'evidence', confirmation, runner=runner)
            self.assertFalse(result['passed'])
            self.assertTrue(all(row['availability'] == 'preflight_build_failed' for row in result['tasks']))
            self.assertEqual(2, runner.clean_application_build.call_count)
            runner.run_one.assert_not_called()

    def test_diagnostic_builds_never_pass_model_start_review_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, _ = self.setup_runner(root)
            confirmation.write_text(json.dumps({'recursiveAuditStable': False}))
            result = target.preflight(root / 'evidence', confirmation, runner=runner, diagnostic_before_freeze=True)
            self.assertTrue(result['standaloneBuildsPassed'])
            self.assertFalse(result['passed'])
            self.assertFalse(result['reviewedStabilityGatePassed'])
            runner.run_one.assert_not_called()

    def test_disk_guard_prevents_prepare_and_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, _ = self.setup_runner(root)
            runner.require_disk_space.side_effect = RuntimeError('below 8 GiB')
            result = target.preflight(root / 'evidence', confirmation, runner=runner)
            self.assertFalse(result['passed'])
            runner.prepare.assert_not_called()
            runner.build.assert_not_called()

    def test_incomplete_cleanup_cannot_pass_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, _ = self.setup_runner(root)
            runner.clean_application_build.side_effect = lambda candidate, path, **opts: target.write(path, {'cleanupCompleted': False})
            result = target.preflight(root / 'evidence', confirmation, tasks=[target.TASKS[0]], runner=runner)
            self.assertFalse(result['passed'])
            self.assertEqual('preflight_cleanup_failed', result['tasks'][0]['availability'])

    def test_confirmation_must_bind_current_runner_and_audit_helper(self):
        for field in ('runner', 'helper', 'author'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                runner, confirmation, _ = self.setup_runner(root)
                if field == 'author':
                    value = json.loads(confirmation.read_text())
                    value['reviewer'] = '  '
                    confirmation.write_text(json.dumps(value))
                else:
                    file = Path(runner.__file__ if field == 'runner' else runner.subagent_audit.__file__)
                    file.write_text('changed revision')
                with self.assertRaises(ValueError):
                    target.preflight(root / 'evidence', confirmation, runner=runner)
                runner.prepare.assert_not_called()

    def test_source_mutation_and_secret_config_fail_closed(self):
        for variant in ('production', 'secret'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                runner, confirmation, _ = self.setup_runner(root)
                if variant == 'production':
                    runner.status_paths.return_value = ['entry/src/main/ets/Feature.ets']
                else:
                    config = ACTUAL.opencode_config('arkts', root / 'candidate')
                    config['provider'] = {'apiKey': 'not-allowed-in-source'}
                    runner.opencode_config = Mock(return_value=config)
                result = target.preflight(root / 'evidence', confirmation, tasks=[target.TASKS[0]], runner=runner)
                self.assertFalse(result['passed'])
                runner.score.assert_not_called()
                runner.run_one.assert_not_called()

    def test_actual_fixed_shell_allowlist_and_subagents_remain_enabled(self):
        result = target.shell_audit(ACTUAL, Path('/arbitrary/standalone/candidate'))
        self.assertEqual(7, len(result['allowedShellCommands']))
        self.assertTrue(result['subagentsAllowed'])
        self.assertFalse(result['apiSecretsInCandidateConfig'])
        config = ACTUAL.opencode_config('arkts', Path('/arbitrary/standalone/candidate'))
        config['permission']['shell']['ls *'] = 'allow'
        with patch.object(ACTUAL, 'opencode_config', return_value=config), self.assertRaises(ValueError):
            target.shell_audit(ACTUAL, Path('/arbitrary/standalone/candidate'))

    def test_explicit_14_15_are_supported_without_expanding_default_or_calling_model(self):
        tasks = ('14_join_room_by_address', '15_account_deactivation')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, events = self.setup_runner(root)
            result = target.preflight(root / 'evidence', confirmation, tasks=tasks, runner=runner, timeout=120.5)
            self.assertTrue(result['passed'])
            self.assertEqual(list(tasks), [row['taskId'] for row in result['tasks']])
            self.assertEqual(('11_room_upgrade_navigation', '12_report_room'), target.DEFAULT_TASKS)
            work = runner.prepare.call_args.kwargs['deadline']
            self.assertEqual(work, runner.build.call_args.kwargs['deadline'])
            self.assertEqual(work, runner.archive_candidate_baseline.call_args.kwargs['deadline'])
            self.assertGreater(runner.clean_candidate.call_args.kwargs['deadline'], work)
            self.assertEqual(120.5, result['overallTimeoutSeconds'])
            runner.run_one.assert_not_called()
            runner.score.assert_not_called()

    def test_unsupported_scope_and_invalid_budgets_rejected_before_prepare(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, _ = self.setup_runner(root)
            for timeout in (0, -1, 3601):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    target.preflight(root / 'invalid', confirmation, runner=runner, timeout=timeout)
            with self.assertRaisesRegex(ValueError, 'distinct ArkTS'):
                target.preflight(root / 'invalid', confirmation, tasks=('13_user_verification',), runner=runner)
            runner.prepare.assert_not_called()

    def test_explicit_16_17_diagnostic_untouched_builds_keep_review_gate_closed(self):
        tasks = ('16_identity_reset', '17_pinned_messages')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, events = self.setup_runner(root)
            confirmation.write_text(json.dumps({'purpose': 'diagnostic only; not a runner review'}))
            result = target.preflight(root/'evidence', confirmation, tasks=tasks, runner=runner,
                                      diagnostic_before_freeze=True, timeout=3600)
            self.assertTrue(result['standaloneBuildsPassed'])
            self.assertFalse(result['passed'])
            self.assertFalse(result['reviewedStabilityGatePassed'])
            self.assertEqual('diagnostic_before_runner_freeze', result['mode'])
            self.assertEqual(list(tasks), [row['taskId'] for row in result['tasks']])
            self.assertEqual(('11_room_upgrade_navigation', '12_report_room'), target.DEFAULT_TASKS)
            self.assertEqual(['prepare', 'archive', 'environment', 'build', 'clean-build', 'clean-candidate']*2, events)
            work = runner.prepare.call_args.kwargs['deadline']
            for method in (runner.prepare, runner.archive_candidate_baseline, runner.build):
                self.assertTrue(all(call.kwargs['deadline'] == work for call in method.call_args_list))
            cleanup = runner.clean_candidate.call_args.kwargs['deadline']
            self.assertGreater(cleanup, work)
            self.assertLessEqual(cleanup-work, 15.001)
            self.assertTrue(result['deadlineIncludesPrepareBuildAndCleanup'])
            self.assertTrue(all(row['cleanup']['candidateRemoved'] for row in result['tasks']))
            runner.run_one.assert_not_called()
            runner.score.assert_not_called()

    def test_16_17_reviewed_support_still_requires_exact_stability_confirmation(self):
        tasks = ('16_identity_reset', '17_pinned_messages')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, _ = self.setup_runner(root)
            Path(runner.__file__).write_text('unreviewed revision')
            with self.assertRaisesRegex(ValueError, 'different runner revision'):
                target.preflight(root/'evidence', confirmation, tasks=tasks, runner=runner)
            runner.prepare.assert_not_called()
            runner.build.assert_not_called()

    def test_16_17_disk_guard_and_duplicate_scope_cannot_start_build(self):
        tasks = ('16_identity_reset', '17_pinned_messages')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner, confirmation, _ = self.setup_runner(root)
            with self.assertRaisesRegex(ValueError, 'distinct ArkTS'):
                target.preflight(root/'duplicate', confirmation, tasks=(tasks[0],tasks[0]), runner=runner)
            runner.require_disk_space.side_effect = RuntimeError('below 8 GiB')
            result = target.preflight(root/'evidence', confirmation, tasks=tasks, runner=runner,
                                      diagnostic_before_freeze=True)
            self.assertFalse(result['standaloneBuildsPassed'])
            runner.prepare.assert_not_called()
            runner.build.assert_not_called()
            runner.score.assert_not_called()
            runner.run_one.assert_not_called()

    def test_whitelist_extension_does_not_accept_other_tasks_or_change_public_shell_policy(self):
        self.assertEqual((*target.DEFAULT_TASKS, '14_join_room_by_address', '15_account_deactivation',
                          '16_identity_reset', '17_pinned_messages'), target.TASKS)
        for task in ('16_identity_reset', '17_pinned_messages'):
            data = ACTUAL.task_data(task)
            self.assertTrue((ACTUAL.ROOT/data['arkts']['basePath']/'entry/src/main').is_dir())
            result = target.shell_audit(ACTUAL, Path('/arbitrary/candidate')/task)
            self.assertEqual(7,len(result['allowedShellCommands']))
            self.assertTrue(result['subagentsAllowed'])


if __name__ == '__main__':
    unittest.main()
