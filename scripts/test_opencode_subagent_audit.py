#!/usr/bin/env python3
"""Focused tests using the actual v2 info/messages/content/tool export shape."""

import importlib.util
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location('opencode_audit', Path(__file__).with_name('opencode_subagent_audit.py'))
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def tool(name='read', path='/candidate/a.ets', *, call='call_one', status='completed'):
    return {'type': 'tool', 'id': call, 'name': name, 'executed': False,
            'state': {'status': status, 'input': {'path': path},
                      'content': [{'type': 'text', 'text': f'Read file {path}, lines 1-1\n1: x'}]},
            'time': {'created': 10, 'ran': 11, 'completed': 12}}


def session(sid='ses_root', parent=None, tools=None):
    info = {'id': sid, 'location': {'directory': '/candidate'}, 'outcome': 'succeeded',
            'time': {'created': 1, 'idle': 30}}
    if parent:
        info['parentID'] = parent
    return {'info': info, 'messages': [
        {'id': 'msg_user', 'type': 'user', 'text': 'review'},
        {'id': 'msg_assistant', 'type': 'assistant', 'content': tools if tools is not None else [tool()]},
        {'id': 'msg_idle', 'type': 'idle', 'outcome': 'succeeded'}]}


def delegate(child='ses_child', name='subagent'):
    result = tool(name, call='call_' + child)
    result['state'].update({'input': {'agent': 'general', 'prompt': 'read only'},
                            'metadata': {'sessionID': child},
                            'content': [{'type': 'text', 'text': f'<subagent sessionID="{child}">done</subagent>'}]})
    return result


def background_shell(command='pwd', shell_id='sh_fixture'):
    result = tool('shell', call='call_background')
    result['state'].update({
        'input': {'command': command, 'background': True, 'timeout': 0},
        'metadata': {'status': 'running', 'truncated': False, 'shellID': shell_id},
        'content': [{'type': 'text', 'text': f'Command moved to the background (shell ID: {shell_id}).'}],
    })
    return result


def synthetic_shell(command='pwd', shell_id='sh_fixture'):
    return {
        'id': 'msg_synthetic',
        'type': 'synthetic',
        'metadata': {'source': 'shell', 'shellID': shell_id, 'jobID': shell_id,
                     'state': 'completed', 'truncated': False, 'exit': 0},
        'time': {'created': 20},
        'description': command,
        'text': f'<shell id="{shell_id}" state="completed" command="{command}">\ndone\n</shell>',
    }


class SubagentAuditTests(unittest.TestCase):
    def run_audit(self, sessions, **options):
        return AUDIT.audit_sessions('ses_root', Path('/candidate'),
                                    lambda sid: json.dumps(sessions[sid]).encode(), **options)

    def test_actual_client_executed_false_still_counts_access(self):
        result = self.run_audit({'ses_root': session()})
        self.assertTrue(result['complete'])
        self.assertTrue(result['valid'])
        self.assertEqual(1, len(result['records']))

    def test_actual_cli_preserves_exit_footer_as_second_result_block(self):
        part = tool('shell')
        part['state']['content'] = [{'type': 'text', 'text': 'build failed\n'},
                                    {'type': 'text', 'text': 'Exited with code 255'}]
        self.assertEqual('build failed\n\nExited with code 255', AUDIT.tool_output(part))

    def test_recursive_task_and_subagent(self):
        sessions = {'ses_root': session(tools=[delegate()]),
                    'ses_child': session('ses_child', 'ses_root', [delegate('ses_leaf', 'task')]),
                    'ses_leaf': session('ses_leaf', 'ses_child')}
        result = self.run_audit(sessions)
        self.assertTrue(result['valid'])
        self.assertEqual(3, len(result['session_logs']))
        self.assertEqual(3, len(result['records']))

    def test_missing_child_not_a_pass(self):
        result = self.run_audit({'ses_root': session(tools=[delegate()])})
        self.assertFalse(result['complete'])
        self.assertFalse(result['valid'])

    def test_completed_delegate_summary_without_session_id_incomplete(self):
        part = delegate()
        part['state'].pop('metadata')
        part['state']['content'] = [{'type': 'text', 'text': 'I stayed in candidate'}]
        result = self.run_audit({'ses_root': session(tools=[part])})
        self.assertFalse(result['complete'])

    def test_outside_child_access_has_complete_telemetry_but_invalid_boundary(self):
        result = self.run_audit({'ses_root': session(tools=[delegate()]),
                                'ses_child': session('ses_child', 'ses_root', [tool(path='/private/secret')])})
        self.assertTrue(result['complete'])
        self.assertFalse(result['valid'])
        self.assertIn('outside_candidate_path', [v['code'] for v in result['violations']])

    def test_parent_escape_and_similar_prefix_rejected(self):
        for path in ('../secret', '/candidate-sibling/a'):
            with self.subTest(path=path):
                self.assertFalse(self.run_audit({'ses_root': session(tools=[tool(path=path)])})['valid'])

    def test_current_symlink_escape_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'candidate'
            root.mkdir()
            (root / 'link').symlink_to(Path(directory))
            data = session(tools=[tool(path=str(root / 'link/secret'))])
            data['info']['location']['directory'] = str(root)
            result = AUDIT.audit_sessions('ses_root', root, lambda _: json.dumps(data).encode())
            self.assertFalse(result['valid'])

    def test_permission_denial_not_a_completed_external_access(self):
        part = tool(path='/private/secret', status='error')
        part['state']['error'] = 'Permission denied: read'
        result = self.run_audit({'ses_root': session(tools=[part])})
        self.assertTrue(result['valid'])
        self.assertTrue(result['records'][0]['notCountedAsCompletedAccess'])

    def test_unknown_tool_fails_closed(self):
        self.assertFalse(self.run_audit({'ses_root': session(tools=[tool('mystery')])})['complete'])

    def test_reviewed_background_shell_notification_is_audited(self):
        data = session(tools=[background_shell()])
        data['messages'].insert(-1, synthetic_shell())
        result = self.run_audit({'ses_root': data}, allowed_shell_commands={'pwd'})
        self.assertTrue(result['valid'])
        self.assertEqual(1, len(result['session_logs'][0]['syntheticShellNotifications']))

    def test_unknown_or_unbound_synthetic_message_fails_closed(self):
        data = session(tools=[])
        data['messages'].insert(-1, synthetic_shell())
        result = self.run_audit({'ses_root': data}, allowed_shell_commands={'pwd'})
        self.assertFalse(result['complete'])
        self.assertIn('unknown_synthetic_message', [row['code'] for row in result['violations']])

    def test_missing_background_shell_notification_fails_closed(self):
        result = self.run_audit({'ses_root': session(tools=[background_shell()])},
                                allowed_shell_commands={'pwd'})
        self.assertFalse(result['complete'])
        self.assertIn('missing_background_shell_notification', [row['code'] for row in result['violations']])

    def test_unknown_export_shape_fails_closed(self):
        self.assertFalse(self.run_audit({'ses_root': {'messages': []}})['complete'])

    def test_malformed_tool_fields_return_incomplete_not_pass_or_exception(self):
        for key, value in [('state', None), ('name', None), ('time', None)]:
            with self.subTest(key=key):
                part = tool()
                part[key] = value
                self.assertFalse(self.run_audit({'ses_root': session(tools=[part])})['complete'])

    def test_malformed_result_block_returns_incomplete(self):
        part = tool()
        part['state']['content'] = [None]
        self.assertFalse(self.run_audit({'ses_root': session(tools=[part])})['complete'])

    def test_nonterminal_tool_fails_closed(self):
        self.assertFalse(self.run_audit({'ses_root': session(tools=[tool(status='running')])})['complete'])

    def test_missing_idle_session_fails_closed(self):
        data = session()
        data['messages'].pop()
        self.assertFalse(self.run_audit({'ses_root': data})['complete'])

    def test_wrong_parent_incomplete(self):
        result = self.run_audit({'ses_root': session(tools=[delegate()]),
                                'ses_child': session('ses_child', 'ses_other')})
        self.assertFalse(result['complete'])

    def test_cycle_incomplete(self):
        result = self.run_audit({'ses_root': session(tools=[delegate()]),
                                'ses_child': session('ses_child', 'ses_root', [delegate('ses_root')])})
        self.assertFalse(result['complete'])

    def test_missing_time_incomplete(self):
        part = tool()
        part['time'].pop('ran')
        self.assertFalse(self.run_audit({'ses_root': session(tools=[part])})['complete'])

    def test_known_shell_requires_exact_reviewed_command(self):
        part = tool('shell')
        part['state'].update({'input': {'command': 'pwd'}, 'content': [{'type': 'text', 'text': '/candidate'}]})
        self.assertTrue(self.run_audit({'ses_root': session(tools=[part])}, allowed_shell_commands={'pwd'})['valid'])
        self.assertFalse(self.run_audit({'ses_root': session(tools=[part])})['complete'])

    def test_external_shell_operand_even_if_allowlisted(self):
        part = tool('shell')
        part['state']['input'] = {'command': 'ls /private'}
        result = self.run_audit({'ses_root': session(tools=[part])}, allowed_shell_commands={'ls /private'})
        self.assertFalse(result['valid'])

    def test_grep_external_returned_path_rejected(self):
        part = tool('grep')
        part['state']['content'][0]['text'] = '/outside/a.ets:\n Line 1: x'
        self.assertFalse(self.run_audit({'ses_root': session(tools=[part])})['valid'])

    def test_no_raw_prompt_content_or_credentials_in_returned_records(self):
        part = tool('write')
        part['state']['input']['content'] = 'private_synthetic_credential_value'
        result = self.run_audit({'ses_root': session(tools=[part])})
        self.assertNotIn('private_synthetic_credential_value', json.dumps(result))

    def test_duplicate_call_id_incomplete(self):
        self.assertFalse(self.run_audit({'ses_root': session(tools=[tool(), tool()])})['complete'])

    def test_failed_delegate_with_child_still_traversed(self):
        part = delegate()
        part['state'].update({'status': 'error', 'error': 'child failed'})
        result = self.run_audit({'ses_root': session(tools=[part])})
        self.assertFalse(result['complete'])
        self.assertEqual(2, len(result['session_logs']))

    def test_unknown_failed_delegate_without_child_is_incomplete(self):
        part = delegate()
        part['state'] = {'status': 'error', 'input': {}, 'error': 'transport interrupted'}
        self.assertFalse(self.run_audit({'ses_root': session(tools=[part])})['complete'])

    def test_session_limit_cannot_hide_descendants(self):
        self.assertFalse(self.run_audit({'ses_root': session(tools=[delegate()])}, max_sessions=1)['complete'])

    def test_independent_inventory_discovers_unreferenced_child_and_fails_closed(self):
        sessions = {'ses_root': session(), 'ses_child': session('ses_child', 'ses_root')}
        result = self.run_audit(sessions, discover_children=lambda sid: ['ses_child'] if sid == 'ses_root' else [])
        self.assertFalse(result['complete'])
        self.assertEqual(2, len(result['session_logs']))
        self.assertIn('unreferenced_child_session', [r['code'] for r in result['violations']])

    def test_matching_independent_child_inventory(self):
        result = self.run_audit({'ses_root': session(tools=[delegate()]),
                                 'ses_child': session('ses_child', 'ses_root')},
                                discover_children=lambda sid: ['ses_child'] if sid == 'ses_root' else [])
        self.assertTrue(result['valid'])
        self.assertTrue(result['independentChildInventoryChecked'])

    def test_db_inventory_is_read_only_and_scoped_to_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.db'
            connection = sqlite3.connect(path)
            connection.execute('CREATE TABLE session_v2 (id TEXT, parent_id TEXT, project_id TEXT, '
                               'directory TEXT, time_idle INTEGER, idle_outcome TEXT)')
            connection.execute('CREATE TABLE session_message (id TEXT,type TEXT,seq INTEGER,data TEXT,session_id TEXT)')
            for sid, parent in [('ses_root', None), ('ses_child', 'ses_root'), ('ses_unrelated', None)]:
                connection.execute('INSERT INTO session_v2 VALUES (?,?,?,?,?,?)',
                                   (sid, parent, 'project', '/candidate', 30, 'succeeded'))
            connection.execute('INSERT INTO session_message VALUES (?,?,?,?,?)',
                               ('msg_one', 'user', 1, json.dumps({'text': 'private_value'}), 'ses_child'))
            connection.commit()
            connection.close()
            before = path.read_bytes()
            result = AUDIT.read_db_session_inventory(path, 'ses_root')
            self.assertEqual({'ses_root', 'ses_child'}, {r['sessionID'] for r in result['sessions']})
            self.assertNotIn('private_value', json.dumps(result))
            self.assertEqual(before, path.read_bytes())

    def test_missing_db_never_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'absent.db'
            with self.assertRaises(sqlite3.Error):
                AUDIT.read_db_session_inventory(path, 'ses_root')
            self.assertFalse(path.exists())

    def test_cli_loader_only_exports_and_never_overwrites_history(self):
        raw = json.dumps(session()).encode()
        with tempfile.TemporaryDirectory() as directory, patch.object(AUDIT.subprocess, 'run') as run:
            run.return_value.stdout = raw
            loader = AUDIT.CliExportLoader(Path(directory), 'task10')
            self.assertEqual(raw, loader('ses_root'))
            self.assertEqual(raw, loader('ses_root'))
            self.assertEqual(1, run.call_count)
            self.assertEqual(['opencode', 'session', 'export', '--standalone', 'ses_root'], run.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
