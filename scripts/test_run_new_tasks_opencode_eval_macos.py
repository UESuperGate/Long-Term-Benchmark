#!/usr/bin/env python3
"""Focused isolation tests for the OpenCode benchmark runner."""

from __future__ import annotations

import importlib.util
import copy
from contextlib import nullcontext
import hashlib
import json
import subprocess
import tempfile
import threading
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("run_new_tasks_opencode_eval_macos.py")
SPEC = importlib.util.spec_from_file_location("new_tasks_runner", SCRIPT)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class CandidatePatchTest(unittest.TestCase):
    def git(self, candidate, *arguments):
        return subprocess.check_output(['git', '-C', str(candidate), *arguments])

    def base(self, root):
        candidate = root / 'candidate'
        candidate.mkdir()
        self.git(candidate, 'init', '-q')
        self.write(candidate, '.gitignore', b'*.json\nbuild/\n')
        self.write(candidate, 'entry/src/main/ets/pages/Index.ets', b'original production\n')
        self.write(candidate, 'entry/src/main/resources/base/media/existing.png', b'\x89PNG\0old\xff')
        self.write(candidate, 'local.properties', b'old local config\n')
        self.git(candidate, 'add', '-A')
        self.git(candidate, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                 'commit', '-qm', 'base')
        return candidate, self.git(candidate, 'rev-parse', 'HEAD').decode().strip()

    @staticmethod
    def write(candidate, relative, data):
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def reconstruct(self, root, candidate, commit, patch_path, expected):
        replay = root / 'replay'
        self.git(root, 'clone', '-q', '--no-local', str(candidate), str(replay))
        self.git(replay, 'checkout', '-q', '--detach', commit)
        self.git(replay, 'apply', '--index', '--binary', str(patch_path))
        for relative, value in expected.items():
            path = replay / relative
            if value is None:
                self.assertFalse(path.exists(), relative)
            else:
                self.assertEqual(value, path.read_bytes(), relative)
        return self.git(replay, 'write-tree').decode().strip()

    def test_new_main_resource_json_binary_and_test_inputs_exactly_reconstruct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, commit = self.base(root)
            inputs = {
                'entry/src/main/resources/base/element/new strings.json': b'{"strings":[{"name":"title","value":"new"}]}\n',
                'entry/src/main/resources/base/profile/line\nbreak.json': b'{"pages":["pages/Index"]}\n',
                'entry/src/main/resources/base/media/new.png': b'\x89PNG\x00\xff\x00new image',
                'entry/src/test/resources/scenario.yaml': b'events: [open, retry]\n',
            }
            for relative, value in inputs.items():
                self.write(candidate, relative, value)
            resource = next(iter(inputs))
            self.assertFalse(RUNNER.is_production(resource, 'arkts'))
            patch_path = root / 'result.patch'
            receipt = RUNNER.archive_candidate_patch(candidate, patch_path, baseline_commit=commit)
            self.assertEqual(sorted(inputs), receipt['files'])
            self.assertTrue(receipt['reconstructionVerified'])
            self.assertEqual(receipt['tree'], self.reconstruct(root, candidate, commit, patch_path, inputs))
            self.assertIn(b'GIT binary patch', patch_path.read_bytes())
            self.assertEqual(b'', self.git(candidate, 'diff', '--cached'))

    def test_staged_changes_deletions_and_exclusions_do_not_mutate_candidate_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, commit = self.base(root)
            changed = 'entry/src/main/ets/pages/Index.ets'
            deleted = 'entry/src/main/resources/base/media/existing.png'
            self.write(candidate, changed, b'changed production\n')
            (candidate / deleted).unlink()
            self.git(candidate, 'add', '-A')
            forbidden = {'opencode.json': b'{"apiKey":"fixture-secret"}',
                'local.properties': b'fixture-secret', '.env.local': b'fixture-secret',
                'build/generated/input.json': b'fixture-secret', 'oh_modules/vendor/input.json': b'fixture-secret',
                '.hvigor/output/hap.bin': b'fixture-secret'}
            for relative, value in forbidden.items():
                self.write(candidate, relative, value)
            before = self.git(candidate, 'diff', '--cached', '--binary')
            patch_path = root / 'result.patch'
            receipt = RUNNER.archive_candidate_patch(candidate, patch_path, baseline_commit=commit)
            self.assertEqual(sorted([changed, deleted]), receipt['files'])
            self.assertEqual(before, self.git(candidate, 'diff', '--cached', '--binary'))
            self.assertNotIn(b'fixture-secret', patch_path.read_bytes())
            self.assertEqual(receipt['tree'], self.reconstruct(root, candidate, commit, patch_path,
                {changed: b'changed production\n', deleted: None, 'local.properties': b'old local config\n'}))

    def test_empty_patch_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, commit = self.base(root)
            patch_path = root / 'result.patch'
            receipt = RUNNER.archive_candidate_patch(candidate, patch_path, baseline_commit=commit)
            self.assertEqual([], receipt['files'])
            self.assertEqual(b'', patch_path.read_bytes())
            self.assertTrue(receipt['reconstructionVerified'])

    def test_run_one_archives_resource_only_change_without_changing_legacy_metric(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, commit = self.base(root)
            self.write(candidate, '_benchmark_inputs/prompt.md', b'fixture task')
            resource = 'entry/src/main/resources/base/element/generated.json'
            resource_bytes = b'{"strings":[{"name":"new","value":"value"}]}\n'

            def model(*args, **kwargs):
                self.write(candidate, resource, resource_bytes)
                return 0

            def score(task, platform, source, generated, build_exit, command, output, **kwargs):
                self.assertEqual([], generated)
                output.write_text(json.dumps({'observationMode': 'runtime_state_transition',
                    'semantic': {'cases': [{'status': 'pass'}]}}))

            with patch.object(RUNNER, 'require_disk_space'), patch.object(RUNNER, 'prepare', return_value=candidate), \
                    patch.object(RUNNER, 'archive_candidate_baseline', return_value={'commit': commit}), \
                    patch.object(RUNNER, 'environment', return_value={}), \
                    patch.object(RUNNER, 'application_build_slot', return_value=nullcontext()), \
                    patch.object(RUNNER, 'run_logged', side_effect=model), \
                    patch.object(RUNNER, 'provider_failure_kind', return_value=None), \
                    patch.object(RUNNER, 'audit_recursive_agent_log', return_value={'availability': 'available'}), \
                    patch.object(RUNNER, 'build', return_value=(0, 'fixture build, not executed')), \
                    patch.object(RUNNER, 'clean_application_build'), patch.object(RUNNER, 'score', side_effect=score):
                result = RUNNER.run_one('fixture', 'arkts', root, root / 'run', 3600, True)
            self.assertFalse(result['codeGenerated'])
            self.assertEqual([], result['generatedCodeFiles'])
            self.assertEqual([resource], result['candidatePatch']['files'])
            self.assertEqual(result['candidatePatch']['tree'], self.reconstruct(root, candidate, commit,
                Path(result['candidatePatch']['path']), {resource: resource_bytes}))

    def test_archive_policy_is_not_a_language_suffix_filter(self):
        for relative in ('entry/src/main/resources/base/profile/main_pages.json',
                         'entry/src/main/resources/base/media/icon.png', 'entry/src/test/Example.ets',
                         'app/src/main/res/raw/input.bin', 'oh-package-lock.json5', 'package-lock.json'):
            self.assertTrue(RUNNER.is_patch_input(relative), relative)
        for relative in ('../outside.json', '/tmp/outside.json', '.git/config', '.gradle/cache/file',
                         '_benchmark_inputs/prompt.md', 'opencode.json', '.opencode/config.json',
                         'AppScope/resources/rawfile/.env', 'signing/config.json', 'local.properties',
                         'entry/build/generated.json', 'entry/.cxx/debug/object.o',
                         'node_modules/dep/file.ts', '.secret.json', 'key.p12'):
            self.assertFalse(RUNNER.is_patch_input(relative), relative)

    def test_application_cleanup_hashes_hap_and_removes_native_intermediates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate'
            self.write(candidate, 'entry/build/output/app.hap', b'hap-bytes')
            self.write(candidate, 'entry/.cxx/debug/object.o', b'object-bytes')
            self.write(candidate, '.hvigor/cache/state.json', b'{}')
            manifest = root / 'artifacts.json'
            RUNNER.clean_application_build(candidate, manifest)
            value = json.loads(manifest.read_text())
            self.assertTrue(value['cleanupCompleted'])
            self.assertEqual(['entry/build/output/app.hap'], [row['path'] for row in value['artifacts']])
            self.assertFalse((candidate / 'entry/build').exists())
            self.assertFalse((candidate / 'entry/.cxx').exists())
            self.assertFalse((candidate / '.hvigor').exists())


class IsolationTest(unittest.TestCase):
    def recursive_fixture(self, root, child_path=None, child_command=None):
        candidate = root / 'candidate'
        directory = str(candidate.resolve())
        def read_tool(call, path):
            return {'id': call, 'type': 'tool', 'name': 'read', 'executed': False,
                    'state': {'status': 'completed', 'input': {'path': path},
                              'content': [{'type': 'text', 'text': f'Read file {path}, lines 1-1\n1: x'}],
                              'metadata': {'truncated': False}},
                    'time': {'created': 10, 'ran': 11, 'completed': 12}}
        parent = read_tool('call_root', directory + '/a.ets')
        delegate = read_tool('call_delegate', directory + '/a.ets')
        delegate['name'] = 'subagent'
        delegate['state'].update({'input': {'agent': 'general', 'prompt': 'read only'},
                                 'metadata': {'sessionID': 'ses_child'},
                                 'content': [{'type': 'text', 'text': '<subagent sessionID="ses_child">done</subagent>'}]})
        child = read_tool('call_child', child_path or directory + '/a.ets')
        if child_command:
            child['name'] = 'shell'
            child['state']['input'] = {'command': child_command}
        def export(sid, tools, parent=None):
            info = {'id': sid, 'projectID': 'cleanroom', 'outcome': 'succeeded',
                    'location': {'directory': directory}, 'time': {'created': 1, 'idle': 30}}
            if parent:
                info['parentID'] = parent
            return {'info': info, 'messages': [
                {'id': 'msg_user', 'type': 'user', 'text': 'implement'},
                {'id': 'msg_reply', 'type': 'assistant', 'content': tools},
                {'id': 'msg_idle', 'type': 'idle', 'outcome': 'succeeded'}]}
        exports = {'ses_root': export('ses_root', [parent, delegate]),
                   'ses_child': export('ses_child', [child], 'ses_root')}
        logs = root / 'logs'
        logs.mkdir()
        for sid, data in exports.items():
            (logs / f'arkts_task_{sid}.export.json').write_text(json.dumps(data))
        events = [{'type': 'step_start', 'sessionID': 'ses_root', 'part': {'sessionID': 'ses_root'}}]
        for p in (parent, delegate):
            state = p['state']
            events.append({'type': 'tool_use', 'sessionID': 'ses_root', 'part': {
                'id': p['id'], 'sessionID': 'ses_root', 'tool': p['name'], 'state': {
                    'status': state['status'], 'input': state['input'], 'output': state['content'][0]['text'],
                    'metadata': {'content': state['content']},
                    'time': {'start': p['time']['created'], 'end': p['time']['completed']}}}})
        log = logs / 'arkts_task_opencode.jsonl'
        log.write_text('\n'.join(json.dumps(e) for e in events) + '\n')
        inventory = {'sessions': [{'sessionID': sid, 'parentID': data['info'].get('parentID'),
                    'projectID': 'cleanroom', 'directory': directory, 'timeIdle': 30, 'outcome': 'succeeded',
                    'messages': [{'id': m['id'], 'type': m['type'], 'seq': i,
                        'dataSha256': RUNNER.subagent_audit.value_hash({k: v for k, v in m.items() if k not in {'id', 'type'}})}
                        for i, m in enumerate(data['messages'])]} for sid, data in exports.items()]}
        return candidate, log, inventory

    def test_actual_recursive_exports_and_db_inventory_pass_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, log, inventory = self.recursive_fixture(root)
            with patch.object(RUNNER.subagent_audit, 'read_db_session_inventory', return_value=inventory):
                receipt = RUNNER.audit_recursive_agent_log(log, candidate, 'arkts', root)
            self.assertEqual('available', receipt['availability'])
            audit = json.loads(Path(receipt['path']).read_text())
            self.assertTrue(audit['independentChildInventoryChecked'])
            self.assertEqual(2, len(audit['session_logs']))
            row = {'taskId': 'task', 'platform': 'arkts', 'availability': 'available',
                   'isolationAudit': receipt, 'benchmarkMetricsAvailable': True}
            # Validation needs the original candidate location, not a role-based path.
            self.assertEqual('available', RUNNER._validate_retained_isolation(row, candidate, 'arkts', root))
            child = root / 'logs/arkts_task_ses_child.export.json'
            child.write_text('{}')
            with self.assertRaises(ValueError):
                RUNNER._validate_retained_isolation(row, candidate, 'arkts', root)

    def test_completed_external_child_isolation_violation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, log, inventory = self.recursive_fixture(root, child_path='/private/secret')
            with patch.object(RUNNER.subagent_audit, 'read_db_session_inventory', return_value=inventory):
                self.assertEqual('isolation_violation', RUNNER.audit_recursive_agent_log(log, candidate, 'arkts', root)['availability'])

    def test_unknown_historical_shell_not_automatically_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, log, inventory = self.recursive_fixture(root, child_command='echo historical')
            with patch.object(RUNNER.subagent_audit, 'read_db_session_inventory', return_value=inventory):
                receipt = RUNNER.audit_recursive_agent_log(log, candidate, 'arkts', root)
            self.assertEqual('isolation_unverified', receipt['availability'])

    def test_missing_child_export_or_nonterminal_child_fails_closed(self) -> None:
        for variant in ('missing', 'nonterminal'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                candidate, log, inventory = self.recursive_fixture(root)
                child = root / 'logs/arkts_task_ses_child.export.json'
                if variant == 'missing':
                    child.unlink()
                else:
                    data = json.loads(child.read_text())
                    data['messages'].pop()
                    child.write_text(json.dumps(data))
                with patch.object(RUNNER.subagent_audit, 'read_db_session_inventory', return_value=inventory), \
                        patch.object(RUNNER.subagent_audit.subprocess, 'run', side_effect=FileNotFoundError('no export')):
                    receipt = RUNNER.audit_recursive_agent_log(log, candidate, 'arkts', root)
                self.assertEqual('isolation_unverified', receipt['availability'])

    def test_db_unreferenced_child_prevents_full_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, log, inventory = self.recursive_fixture(root)
            extra = copy.deepcopy(inventory['sessions'][1])
            extra['sessionID'] = 'ses_orphan'
            inventory['sessions'].append(extra)
            with patch.object(RUNNER.subagent_audit, 'read_db_session_inventory', return_value=inventory), \
                    patch.object(RUNNER.subagent_audit.subprocess, 'run', side_effect=FileNotFoundError('no export')):
                self.assertEqual('isolation_unverified', RUNNER.audit_recursive_agent_log(log, candidate, 'arkts', root)['availability'])

    def test_run_one_unverified_skips_build_score_and_all_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate'
            (candidate / '_benchmark_inputs').mkdir(parents=True)
            (candidate / '_benchmark_inputs/prompt.md').write_text('implement')
            receipt = {'availability': 'isolation_unverified', 'complete': False, 'violations': []}
            with patch.object(RUNNER, 'require_disk_space'), patch.object(RUNNER, 'prepare', return_value=candidate), \
                    patch.object(RUNNER, 'archive_candidate_baseline', return_value={'commit': 'fixture'}), \
                    patch.object(RUNNER, 'status_paths', return_value=[]), \
                    patch.object(RUNNER, 'archive_candidate_patch', return_value={'files': []}), \
                    patch.object(RUNNER, 'environment', return_value={}), \
                    patch.object(RUNNER, 'application_build_slot', return_value=nullcontext()), \
                    patch.object(RUNNER, 'run_logged', return_value=0), \
                    patch.object(RUNNER, 'provider_failure_kind', return_value=None), \
                    patch.object(RUNNER, 'audit_recursive_agent_log', return_value=receipt), \
                    patch.object(RUNNER, 'build') as build, patch.object(RUNNER, 'score') as score:
                result = RUNNER.run_one('task', 'arkts', root, root / 'run', 3600, True)
            build.assert_not_called()
            score.assert_not_called()
            self.assertFalse(result['benchmarkMetricsAvailable'])
            self.assertFalse(any(result['metricAvailability'].values()))
            self.assertIsNone(result['workspacePathLeakDetected'])

    def test_recursive_shell_policy_comes_only_from_config_exact_allows(self) -> None:
        candidate = Path('/tmp/candidate')
        allowed = RUNNER.fixed_shell_allowlist('arkts', candidate)
        policy = RUNNER.opencode_config('arkts', candidate)['permission']['shell']
        self.assertEqual({command for command, decision in policy.items() if decision == 'allow'}, allowed)
        self.assertNotIn('cat /etc/passwd', allowed)
        self.assertIn(RUNNER.agent_build_command('arkts'), allowed)

    def test_recursive_policy_rejects_wildcard_allow_even_if_config_regresses(self) -> None:
        with patch.object(RUNNER, 'opencode_config', return_value={'permission': {'shell': {'ls *': 'allow'}}}):
            with self.assertRaises(ValueError):
                RUNNER.fixed_shell_allowlist('arkts', Path('/tmp/candidate'))

    def test_root_session_id_comes_from_actual_jsonl_not_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'arbitrary.jsonl'
            log.write_text(json.dumps({'type': 'step_start', 'sessionID': 'ses_actual',
                                       'part': {'sessionID': 'ses_actual'}}) + '\n')
            self.assertEqual('ses_actual', RUNNER.root_session_id_from_log(log))
            log.write_text('{}\n')
            with self.assertRaises(ValueError):
                RUNNER.root_session_id_from_log(log)

    def test_unreviewed_shell_is_unverified_not_confirmed_leak(self) -> None:
        result = {'complete': False, 'valid': False, 'records': [
            {'sessionID': 'ses_root', 'callID': 'call_one', 'status': 'completed'}],
            'violations': [{'code': 'unreviewed_shell_command', 'sessionID': 'ses_root', 'callID': 'call_one'}]}
        self.assertEqual('isolation_unverified', RUNNER.isolation_availability(result))

    def test_only_completed_external_access_is_isolation_violation(self) -> None:
        result = {'complete': True, 'valid': False, 'records': [
            {'sessionID': 'ses_child', 'callID': 'call_one', 'status': 'completed'}],
            'violations': [{'code': 'outside_candidate_path', 'sessionID': 'ses_child', 'callID': 'call_one'}]}
        self.assertEqual('isolation_violation', RUNNER.isolation_availability(result))
        result['records'][0]['status'] = 'error'
        self.assertEqual('isolation_unverified', RUNNER.isolation_availability(result))

    def test_missing_db_inventory_fails_closed_without_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'logs/arkts_task_opencode.jsonl'
            log.parent.mkdir()
            log.write_text(json.dumps({'type': 'step_start', 'sessionID': 'ses_actual',
                                       'part': {'sessionID': 'ses_actual'}}) + '\n')
            with patch.object(RUNNER.subagent_audit, 'read_db_session_inventory', side_effect=OSError('unavailable')):
                result = RUNNER.audit_recursive_agent_log(log, root / 'candidate', 'arkts', root)
            self.assertEqual('isolation_unverified', result['availability'])
            self.assertFalse(result['complete'])

    def test_resume_legacy_available_is_preserved_and_not_eligible_for_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = {'taskId': 'task', 'platform': 'arkts', 'availability': 'available',
                   'agentExit': 0, 'buildExit': 0, 'compile': 'passed',
                   'semanticReport': 'historical-report.json', 'benchmarkMetricsAvailable': True}
            rows = RUNNER.resume_checkpoint_rows({'tasks': [old]}, root / 'candidates', root)
            self.assertEqual(1, len(rows))
            self.assertEqual('isolation_unverified', rows[0]['availability'])
            self.assertTrue(rows[0]['completedCheckpointPreserved'])
            self.assertEqual('historical-report.json', rows[0]['semanticReport'])
            self.assertFalse(rows[0]['benchmarkMetricsAvailable'])
            self.assertFalse(any(rows[0]['metricAvailability'].values()))
            self.assertEqual('available', old['availability'])

    def test_resume_unverified_stays_completed_on_next_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {'taskId': 'task', 'platform': 'arkts', 'availability': 'isolation_unverified',
                   'completedCheckpointPreserved': True}
            self.assertEqual(1, len(RUNNER.resume_checkpoint_rows({'tasks': [row]}, root, root)))

    def test_resume_never_overwrites_old_logs_or_deletes_preserved_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / 'eval_runs/unit'
            run.mkdir(parents=True)
            candidate = root / 'candidates/arkts/task'
            candidate.mkdir(parents=True)
            sentinel = candidate / 'old-source.ets'
            sentinel.write_text('keep\n')
            log = run / 'logs/arkts_task_opencode.jsonl'
            log.parent.mkdir()
            log.write_text('old immutable generation log\n')
            prior = {'startedAt': '2026-10-20T00:00:00+00:00', 'tasks': [
                {'taskId': 'task', 'platform': 'arkts', 'availability': 'available', 'agentExit': 0, 'buildExit': 0}]}
            (run / 'eval_manifest.partial.json').write_text(json.dumps(prior))
            argv = ['runner', '--run-id', 'unit', '--resume', '--task', 'task', '--platform', 'arkts',
                    '--candidate-root', str(root / 'candidates')]
            with patch.object(RUNNER, 'ROOT', root), patch.object(RUNNER, 'task_ids', return_value=['task']), \
                    patch.object(RUNNER, 'run_with_platform_lock') as run_model, \
                    patch.object(RUNNER.subprocess, 'check_output', return_value='test-version'), patch('sys.argv', argv):
                self.assertEqual(1, RUNNER.main())
            run_model.assert_not_called()
            self.assertEqual('old immutable generation log\n', log.read_text())
            self.assertEqual('keep\n', sentinel.read_text())
            current = json.loads((run / 'eval_manifest.json').read_text())
            self.assertEqual('isolation_unverified', current['tasks'][0]['availability'])
            original = json.dumps(prior).encode()
            history = run / 'manifest_history' / (hashlib.sha256(original).hexdigest() + '.json')
            self.assertEqual(original, history.read_bytes())

    def test_resume_orphan_logs_without_checkpoint_never_regenerates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / 'eval_runs/unit/logs'
            logs.mkdir(parents=True)
            log = logs / 'arkts_task_opencode.jsonl'
            log.write_text('old log')
            with patch.object(RUNNER, 'ROOT', root), patch.object(RUNNER, 'task_ids', return_value=['task']), \
                    patch('sys.argv', ['runner', '--resume', '--run-id', 'unit']), \
                    patch.object(RUNNER, 'run_with_platform_lock') as model:
                with self.assertRaisesRegex(ValueError, 'without checkpoint'):
                    RUNNER.main()
            model.assert_not_called()
            self.assertEqual('old log', log.read_text())

    def test_existing_run_without_resume_is_not_regenerated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / 'eval_runs/unit'
            run.mkdir(parents=True)
            (run / 'eval_manifest.partial.json').write_text('{}')
            with patch.object(RUNNER, 'ROOT', root), patch.object(RUNNER, 'task_ids', return_value=['task']), \
                    patch('sys.argv', ['runner', '--run-id', 'unit', '--task', 'task', '--platform', 'arkts']):
                with self.assertRaisesRegex(ValueError, 'existing|already|new run'):
                    RUNNER.main()

    def test_baseline_archive_captures_committed_input_not_later_candidate_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'candidate'
            candidate.mkdir()
            production = candidate / 'Feature.ets'
            production.write_text('export const original = true;\n')
            for command in (['git', 'init', '-q'], ['git', 'add', '-A'],
                            ['git', '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
                             'commit', '-q', '-m', 'clean-room base']):
                RUNNER.subprocess.run(command, cwd=candidate, check=True)
            production.write_text('export const changed = true;\n')
            (candidate / 'New.ets').write_text('export const created = true;\n')
            receipt = RUNNER.archive_candidate_baseline(candidate, root / 'inputs', phase='unit_recovery')
            archive = Path(receipt['path'])
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), receipt['sha256'])
            self.assertEqual('unit_recovery', receipt['capturePhase'])
            with tarfile.open(archive) as stream:
                self.assertEqual(b'export const original = true;\n', stream.extractfile('Feature.ets').read())
                self.assertNotIn('New.ets', stream.getnames())
            self.assertEqual('export const changed = true;\n', production.read_text())
            self.assertEqual(receipt, RUNNER.archive_candidate_baseline(candidate, root / 'inputs'))
            archive.write_bytes(b'tampered archive')
            with self.assertRaisesRegex(ValueError, 'baseline archive or receipt changed'):
                RUNNER.archive_candidate_baseline(candidate, root / 'inputs')

    def test_partial_checkpoint_replaces_stale_complete_manifest_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = b'{"status":"complete","tasks":["old"]}\n'
            (root / "eval_manifest.json").write_bytes(previous)
            manifest = {"status": "partial", "tasks": ["old", "unavailable"]}
            RUNNER.write_manifest_checkpoint(root, manifest)
            for name in ("eval_manifest.json", "eval_manifest.partial.json"):
                self.assertEqual(manifest, json.loads((root / name).read_text()))
            history = root / "manifest_history" / (hashlib.sha256(previous).hexdigest() + ".json")
            self.assertEqual(previous, history.read_bytes())
            RUNNER.write_manifest_checkpoint(root, manifest)
            self.assertEqual(2, len(list((root / "manifest_history").glob("*.json"))))
            self.assertFalse(list(root.glob("*.tmp")))

    def test_storage_guard_does_not_start_agent_and_removes_partial_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_root = root / "candidates"
            candidate = candidate_root / "android" / "08_threads"
            candidate.mkdir(parents=True)
            (candidate / "partial.bin").write_bytes(b"partial")
            with patch.object(RUNNER.shutil, "disk_usage") as disk, \
                    patch.object(RUNNER, "prepare") as prepare:
                disk.return_value.free = RUNNER.MIN_FREE_BYTES - 1
                result = RUNNER.run_with_platform_lock(
                    threading.Lock(), threading.Event(), "08_threads", "android",
                    candidate_root, root / "run", 3600, False)
            prepare.assert_not_called()
            self.assertEqual("storage_protection_environment", result["availability"])
            self.assertFalse(result["benchmarkMetricsAvailable"])
            self.assertEqual('unknown', result['compile'])
            self.assertFalse(result['metricAvailability']['compile'])
            self.assertFalse(candidate.exists())

    def test_build_outputs_are_hashed_and_removed_before_semantic_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            artifact = candidate / "app/build/outputs/candidate.apk"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"application-artifact")
            production = candidate / "app/src/main/Feature.kt"
            production.parent.mkdir(parents=True)
            production.write_text("class Feature\n")
            manifest = root / "reports/artifacts.json"
            RUNNER.clean_application_build(candidate, manifest)
            report = json.loads(manifest.read_text())
            self.assertTrue(report["cleanupCompleted"])
            self.assertEqual(hashlib.sha256(b"application-artifact").hexdigest(),
                             report["artifacts"][0]["sha256"])
            self.assertEqual(len(b"application-artifact"), report["artifacts"][0]["bytes"])
            self.assertFalse(artifact.exists())
            self.assertEqual("class Feature\n", production.read_text())

    def test_android_agent_build_uses_serial_workers(self) -> None:
        self.assertIn("--max-workers=1", RUNNER.agent_build_command("android"))

    def test_storage_drop_terminates_process_and_is_not_a_task_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "process.jsonl"
            with patch.object(RUNNER.subprocess, "Popen") as create, \
                    patch.object(RUNNER.os, "killpg") as kill, \
                    patch.object(RUNNER, "require_disk_space", side_effect=RUNNER.StorageProtectionError("low space")):
                create.return_value.pid = 12345
                create.return_value.wait.return_value = -15
                with self.assertRaises(RUNNER.StorageProtectionError):
                    RUNNER.run_logged(["build"], root, {}, output, 3600, protect_storage=True)
            kill.assert_called_once_with(12345, RUNNER.signal.SIGTERM)
            event = json.loads(output.read_text())
            self.assertEqual("storage_protection_environment", event["type"])
            self.assertNotIn("timeoutSeconds", event)

    def test_user_interrupt_stops_process_before_candidate_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(RUNNER.subprocess, "Popen") as create, \
                    patch.object(RUNNER.os, "killpg") as kill:
                process = create.return_value
                process.pid = 12345
                process.poll.return_value = None
                process.wait.side_effect = [KeyboardInterrupt(), -15]
                with self.assertRaises(KeyboardInterrupt):
                    RUNNER.run_logged(["agent"], root, {}, root / "agent.log", 3600)
            kill.assert_called_once_with(12345, RUNNER.signal.SIGTERM)
            self.assertEqual(2, process.wait.call_count)

    def test_provider_failures_are_parsed_from_error_events_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "agent.jsonl"
            scenarios = (
                ({"type": "error", "error": {"type": "provider.quota"}}, "provider_quota"),
                ({"type": "error", "error": {"data": {"statusCode": 402}}}, "provider_quota"),
                ({"type": "error", "error": {"data": {"statusCode": 401}}}, "provider_auth"),
                ({"type": "error", "error": {"type": "unknown"}}, "agent_runtime_error"),
                ({"type": "tool_use", "part": {"output": '{"status":402}'}}, None),
            )
            for event, expected in scenarios:
                log.write_text(json.dumps(event) + "\n")
                self.assertEqual(expected, RUNNER.provider_failure_kind(log))

    def test_android_mirror_uses_proven_repo_order_without_clearing_dependencies(self) -> None:
        source = RUNNER.MIRROR_INIT.read_text(encoding="utf-8")
        self.assertNotIn("maven.aliyun.com", source)
        self.assertLess(source.index("maven { url = uri(repo1) }"),
                        source.index("gradlePluginPortal()"))
        self.assertIn('repository.url.host == "repo.maven.apache.org"', source)
        dependency_block = source.split("settings.dependencyResolutionManagement.repositories", 1)[1]
        self.assertNotIn("repositories.clear()", dependency_block)

    def test_android_build_is_serial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            log = candidate / "build.log"
            (candidate / '_benchmark_inputs').mkdir()
            (candidate / RUNNER.android_inputs.INIT_RELATIVE).write_text('public fixture')
            env = RUNNER.environment('android', candidate)
            with patch.object(RUNNER, "run_logged", return_value=0) as run_logged, \
                    patch.object(RUNNER, "application_build_slot", return_value=nullcontext()):
                exit_code, command = RUNNER.build("android", candidate, env, log)

            self.assertEqual(exit_code, 0)
            self.assertIn("--max-workers=1", command)
            self.assertIn("--max-workers=1", run_logged.call_args.args[0])

    def test_failed_run_removes_candidate_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_root = root / "candidates"
            candidate = candidate_root / "android" / "08_threads"

            def fail_after_prepare(*_args, **_kwargs):
                candidate.mkdir(parents=True)
                (candidate / "partial.bin").write_bytes(b"partial")
                raise RuntimeError("build failed")

            with patch.object(RUNNER, "run_one", side_effect=fail_after_prepare), self.assertRaises(RuntimeError):
                RUNNER.run_with_platform_lock(
                    threading.Lock(), threading.Event(), "08_threads", "android",
                    candidate_root, root / "run", 3600, False,
                )

            self.assertFalse(candidate.exists())

    def test_android_java_home_uses_jdk17_for_legacy_gradle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            wrapper = candidate / "gradle/wrapper/gradle-wrapper.properties"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("distributionUrl=https\\://services.gradle.org/distributions/gradle-8.10-bin.zip\n")

            self.assertEqual(RUNNER.android_java_home(candidate), RUNNER.JAVA_HOME_17)

    def test_android_java_home_uses_jdk21_for_current_gradle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            wrapper = candidate / "gradle/wrapper/gradle-wrapper.properties"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("distributionUrl=https\\://services.gradle.org/distributions/gradle-8.12.1-bin.zip\n")

            self.assertEqual(RUNNER.android_java_home(candidate), RUNNER.JAVA_HOME_21)

    def test_shell_permissions_have_no_wildcard_allow_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            for platform in ("android", "arkts"):
                shell = RUNNER.opencode_config(platform, candidate)["permission"]["shell"]
                allowed = [pattern for pattern, decision in shell.items() if decision == "allow"]
                self.assertFalse(any("*" in pattern for pattern in allowed))
                self.assertIn(RUNNER.agent_build_command(platform), allowed)

    def test_file_tools_deny_external_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            permission = RUNNER.opencode_config("arkts", candidate)["permission"]
            for tool in ("read", "edit", "glob", "list"):
                rules = permission[tool]
                self.assertEqual(list(rules.items())[0], ("*", "allow"))
                self.assertEqual(list(rules.items())[1], ("/*", "deny"))
                self.assertEqual(list(rules.items())[2], (f"{candidate.resolve()}/*", "allow"))

    def test_candidate_paths_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            log = candidate / "agent.jsonl"
            event = {
                "type": "tool_use",
                "part": {"tool": "read", "state": {"status": "completed", "input": {"path": str(candidate / "src/Main.kt")}}},
            }
            log.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertEqual(RUNNER.audit_agent_log(log, candidate), [])

    def test_external_file_and_shell_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            events = [
                {"type": "tool_use", "part": {"tool": "read", "state": {"status": "completed", "input": {"path": "/tmp/oracle.json"}}}},
                {"type": "tool_use", "part": {"tool": "shell", "state": {"status": "completed", "input": {"command": "ls /Users/example/benchmark"}}}},
                {"type": "tool_use", "part": {"tool": "shell", "state": {"status": "completed", "input": {"command": "find ~/.gradle -name '*.jar'"}}}},
            ]
            log = candidate / "agent.jsonl"
            log.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
            violations = RUNNER.audit_agent_log(log, candidate)
            self.assertEqual(len(violations), 3)

    def test_dev_null_redirection_is_not_an_external_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            event = {
                "type": "tool_use",
                "part": {"tool": "shell", "state": {"status": "completed", "input": {"command": "find . -name '*.kt' 2>/dev/null"}}},
            }
            log = candidate / "agent.jsonl"
            log.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertEqual(RUNNER.audit_agent_log(log, candidate), [])

    def test_denied_external_shell_command_is_not_a_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            event = {
                "type": "tool_use",
                "part": {"tool": "shell", "state": {"status": "error", "input": {"command": "ls /Users/example/benchmark"}, "output": None}},
            }
            log = candidate / "agent.jsonl"
            log.write_text(json.dumps(event) + "\n", encoding="utf-8")
            self.assertEqual(RUNNER.audit_agent_log(log, candidate), [])


if __name__ == "__main__":
    unittest.main()
