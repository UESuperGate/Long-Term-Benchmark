#!/usr/bin/env python3
"""Audit actual OpenCode v2 `session export` JSON recursively, without model calls.

audit_sessions(root_id, candidate, load_session, allowed_shell_commands=...) returns
session_logs (per-session hashes/normalized records), all flattened records,
violations, complete (telemetry coverage), and valid (complete with no violations).
The loader returns original export bytes. Raw inputs, results and reasoning are
never included in the returned structure. Preserve the original exports locally.
`executed: false` denotes client-side execution, not an unexecuted tool.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import sqlite3
import subprocess
import time
import tempfile
from typing import Callable, Iterable


SESSION_ID = re.compile(r'^ses_[A-Za-z0-9]+$')
PATH_KEYS = {'path', 'file', 'filePath', 'file_path', 'directory', 'dir', 'cwd', 'root', 'workdir'}
FILE_TOOLS = {'read', 'write', 'edit', 'glob', 'grep', 'list'}
DELEGATE_TOOLS = {'task', 'subagent'}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def value_hash(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True).encode())


def tool_output(part: dict) -> str:
    """Actual v2 exports use state.content; JSONL instead uses state.output."""
    content = part['state'].get('content', [])
    if not isinstance(content, list) or any(not isinstance(c, dict) or c.get('type') != 'text' or
                                           not isinstance(c.get('text'), str) for c in content):
        raise ValueError('unsupported_tool_content')
    return '\n'.join(c['text'] for c in content)


def string_fields(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str):
                yield key, child
            else:
                yield from string_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_fields(child)


def child_ids(part: dict) -> set[str]:
    state = part['state']
    result = {v for k, v in string_fields(state.get('metadata', {}))
              if k in {'sessionID', 'sessionId', 'session_id'} and SESSION_ID.fullmatch(v)}
    output = tool_output(part)
    result.update(re.findall(r'<subagent\b[^>]*\bsessionID=["\'](ses_[A-Za-z0-9]+)["\']', output))
    return result


class CliExportLoader:
    """Export existing history only; this class cannot invoke `run` or a model.

    Existing raw archives are never overwritten. Export errors are propagated to
    audit_sessions, which records missing telemetry and returns complete=False.
    """

    def __init__(self, directory: Path, prefix: str, executable: str = 'opencode', *, deadline: float | None = None):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', prefix):
            raise ValueError('unsafe archive prefix')
        self.directory = Path(directory)
        self.prefix = prefix
        self.executable = executable
        self.paths: dict[str, Path] = {}
        self.deadline = deadline

    def __call__(self, session_id: str) -> bytes:
        budget = 90 if self.deadline is None else min(90, self.deadline-time.monotonic())
        if budget <= 0:
            raise TimeoutError('Overall task deadline exhausted during history export')
        if not SESSION_ID.fullmatch(session_id):
            raise ValueError('invalid session id')
        path = self.directory / f'{self.prefix}_{session_id}.export.json'
        if path.exists():
            raw = path.read_bytes()
        else:
            command = [self.executable, 'session', 'export', '--standalone', session_id]
            if self.deadline is None:
                process = subprocess.run(command, capture_output=True, check=True, timeout=budget)
                raw = process.stdout
            else:
                with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                    process = subprocess.Popen(command, stdout=output, stderr=errors, start_new_session=True)
                    try:
                        process.wait(timeout=max(0, min(budget, self.deadline-time.monotonic())))
                    except BaseException:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        raise
                    if process.returncode:
                        raise subprocess.CalledProcessError(process.returncode, command)
                    output.seek(0)
                    raw = output.read()
            data = json.loads(raw)
            if data.get('info', {}).get('id') != session_id:
                raise ValueError('wrong exported session id')
            self.directory.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
        if json.loads(raw).get('info', {}).get('id') != session_id:
            raise ValueError('wrong archived session id')
        self.paths[session_id] = path
        return raw


def read_db_session_inventory(database: Path, root_id: str, *, deadline: float | None = None) -> dict:
    """Read v2 descendants and exact message digests in one read-only transaction.

    This is a coverage crosscheck, not a substitute for CLI tool transcripts.
    Neither message text nor credentials are returned. Never use immutable=1 on
    this WAL database: doing so would silently omit recently committed history.
    """
    if not SESSION_ID.fullmatch(root_id):
        raise ValueError('invalid root session id')
    remaining = 5 if deadline is None else min(5, deadline-time.monotonic())
    if remaining <= 0:
        raise TimeoutError('Overall task deadline exhausted during history DB inventory')
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=remaining)
    try:
        if deadline is not None:
            connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        rows = connection.execute(
            'WITH RECURSIVE subtree(id) AS ('
            ' SELECT id FROM session_v2 WHERE id=? UNION '
            ' SELECT s.id FROM session_v2 s JOIN subtree t ON s.parent_id=t.id) '
            'SELECT s.id,s.parent_id,s.project_id,s.directory,s.time_idle,s.idle_outcome '
            'FROM session_v2 s JOIN subtree t ON s.id=t.id ORDER BY s.id', (root_id,)).fetchall()
        if not rows:
            raise ValueError('root session absent from v2 database')
        sessions = []
        for sid, parent, project, directory, idle, outcome in rows:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Overall task deadline exhausted during history DB inventory')
            messages = connection.execute(
                'SELECT id,type,seq,data FROM session_message WHERE session_id=? ORDER BY seq', (sid,)).fetchall()
            sessions.append({'sessionID': sid, 'parentID': parent, 'projectID': project,
                             'directory': directory, 'timeIdle': idle, 'outcome': outcome,
                             'messages': [{'id': mid, 'type': kind, 'seq': seq,
                                           'dataSha256': value_hash(json.loads(raw))}
                                          for mid, kind, seq, raw in messages]})
        return {'schema': 'session_v2/session_message', 'rootSessionID': root_id,
                'readOnly': True, 'queryOnly': True, 'transactionSnapshot': True,
                'sessions': sessions}
    finally:
        connection.close()


def audit_sessions(root_id: str, candidate: Path, load_session: Callable[[str], bytes], *,
                   allowed_shell_commands: Iterable[str] = (), max_sessions: int = 128,
                   discover_children: Callable[[str], Iterable[str]] | None = None,
                   deadline: float | None = None) -> dict:
    """Fail closed on unknown schema/tools, missing child exports, and nonterminal history.

    `complete` indicates all discoverable delegate sessions/tool events could be
    audited, not that accesses were valid. Violations and complete are separate.
    Path checks include current symlinks, not a historical syscall trace. Exact
    shell allowlists are caller-reviewed policy, never automatically inferred.
    """
    if not SESSION_ID.fullmatch(root_id) or max_sessions < 1:
        raise ValueError('invalid root session or session limit')
    root = Path(candidate).resolve()
    allowed = set(allowed_shell_commands)
    sessions, records, violations = [], [], []
    seen, visiting = set(), set()
    coverage = True

    def issue(code, sid, call=None, *, incomplete=False):
        nonlocal coverage
        violations.append({'code': code, 'sessionID': sid, 'callID': call})
        if incomplete:
            coverage = False

    def target(value, sid, call, key):
        if not value or value.startswith('~') or '$' in value or '\0' in value:
            issue('unresolved_path', sid, call, incomplete=True)
            return {'key': key, 'valueSha256': sha(value.encode()), 'insideCandidate': False}
        expanded = Path(value)
        resolved = (expanded if expanded.is_absolute() else root / expanded).resolve()
        inside = resolved == root or root in resolved.parents
        if not inside:
            issue('outside_candidate_path', sid, call)
        return {'key': key, 'valueSha256': sha(value.encode()), 'insideCandidate': inside,
                'candidateRelativePath': str(resolved.relative_to(root)) if inside else None}

    def visit(sid, expected_parent=None):
        if deadline is not None and time.monotonic() >= deadline:
            issue('history_deadline_exhausted', sid, incomplete=True)
            return
        if sid in visiting:
            issue('session_cycle', sid, incomplete=True)
            return
        if sid in seen:
            issue('reused_child_session', sid, incomplete=True)
            return
        if len(seen) >= max_sessions:
            issue('session_limit_exceeded', sid, incomplete=True)
            return
        seen.add(sid)
        visiting.add(sid)
        try:
            raw = load_session(sid)
            data = json.loads(raw)
            info, messages = data['info'], data['messages']
            if info['id'] != sid or not isinstance(messages, list):
                raise ValueError('bad export identity/schema')
        except Exception as error:
            issue('missing_or_invalid_session_export', sid, incomplete=True)
            sessions.append({'sessionID': sid, 'available': False, 'errorType': type(error).__name__, 'records': []})
            visiting.remove(sid)
            return
        local_records, children = [], []
        session = {'sessionID': sid, 'parentID': info.get('parentID'), 'available': True,
                   'exportBytes': len(raw), 'exportSha256': sha(raw), 'messageCount': len(messages),
                   'outcome': info.get('outcome'), 'records': local_records, 'children': children}
        sessions.append(session)
        if expected_parent is not None and info.get('parentID') != expected_parent:
            issue('child_parent_mismatch', sid, incomplete=True)
        location_data = info.get('location')
        location = location_data.get('directory') if isinstance(location_data, dict) else None
        if not isinstance(location, str):
            issue('missing_session_directory', sid, incomplete=True)
        else:
            session['directory'] = target(location, sid, None, 'sessionDirectory')
        if (info.get('outcome') not in {'succeeded', 'failed', 'cancelled'} or
                not messages or not isinstance(messages[-1], dict) or messages[-1].get('type') != 'idle' or
                messages[-1].get('outcome') != info.get('outcome') or
                not isinstance(info.get('time', {}).get('idle'), int)):
            issue('session_not_terminal', sid, incomplete=True)
        ids = set()
        background_shells: dict[str, str] = {}
        completed_background_shells: set[str] = set()
        session['syntheticShellNotifications'] = []
        for message_index, message in enumerate(messages):
            if deadline is not None and time.monotonic() >= deadline:
                issue('history_deadline_exhausted', sid, incomplete=True)
                break
            if not isinstance(message, dict):
                issue('unknown_message_schema', sid, incomplete=True)
                continue
            if message.get('type') == 'synthetic':
                metadata = message.get('metadata')
                shell_id = metadata.get('shellID') if isinstance(metadata, dict) else None
                command = message.get('description')
                state = metadata.get('state') if isinstance(metadata, dict) else None
                text = message.get('text')
                expected_prefix = (f'<shell id="{shell_id}" state="{state}" command="{command}">\n'
                                   if all(isinstance(value, str) for value in (shell_id, state, command)) else '')
                valid = (isinstance(metadata, dict) and metadata.get('source') == 'shell' and
                         shell_id == metadata.get('jobID') and background_shells.get(shell_id) == command and
                         state in {'completed', 'failed'} and isinstance(metadata.get('exit'), int) and
                         isinstance(metadata.get('truncated'), bool) and
                         isinstance(message.get('time', {}).get('created'), int) and isinstance(text, str) and
                         text.startswith(expected_prefix) and text.endswith('\n</shell>') and command in allowed)
                if not valid or shell_id in completed_background_shells:
                    issue('unknown_synthetic_message', sid, incomplete=True)
                else:
                    completed_background_shells.add(shell_id)
                    session['syntheticShellNotifications'].append({
                        'shellIDSha256': sha(shell_id.encode()), 'commandSha256': sha(command.encode()),
                        'state': state, 'exit': metadata['exit'], 'truncated': metadata['truncated'],
                        'textSha256': sha(text.encode()), 'messageIndex': message_index,
                    })
                continue
            if message.get('type') not in {'user', 'assistant', 'idle'}:
                issue('unknown_message_schema', sid, incomplete=True)
                continue
            if message.get('type') == 'assistant' and 'content' not in message:
                issue('missing_assistant_content', sid, incomplete=True)
            content = message.get('content', [])
            if not isinstance(content, list):
                issue('unknown_message_content', sid, incomplete=True)
                continue
            for content_index, part in enumerate(content):
                if not isinstance(part, dict):
                    issue('unknown_message_part', sid, incomplete=True)
                    continue
                if part.get('type') in {'text', 'reasoning'}:
                    continue
                if part.get('type') != 'tool':
                    issue('unknown_message_part', sid, incomplete=True)
                    continue
                call, tool, state = part.get('id'), part.get('name'), part.get('state', {})
                if not isinstance(tool, str):
                    issue('missing_tool_name', sid, call, incomplete=True)
                    continue
                if not isinstance(state, dict):
                    issue('missing_tool_state', sid, call, incomplete=True)
                    continue
                if not call or call in ids:
                    issue('duplicate_or_missing_call_id', sid, call, incomplete=True)
                ids.add(call)
                status, inputs = state.get('status'), state.get('input')
                row = {'sessionID': sid, 'callID': call, 'tool': tool, 'status': status,
                       'messageIndex': message_index, 'contentIndex': content_index,
                       'messageID': message.get('id'), 'time': part.get('time', {}), 'targets': []}
                records.append(row)
                local_records.append(row)
                if not isinstance(inputs, dict):
                    issue('missing_tool_input', sid, call, incomplete=True)
                    continue
                row['inputSha256'] = value_hash(inputs)
                try:
                    output = tool_output(part)
                except (ValueError, KeyError, TypeError):
                    issue('unknown_tool_content', sid, call, incomplete=True)
                    continue
                row['outputSha256'] = sha(output.encode())
                metadata = state.get('metadata', {})
                if not isinstance(metadata, dict):
                    issue('invalid_tool_metadata', sid, call, incomplete=True)
                    metadata = {}
                row['outputTruncated'] = metadata.get('truncated', False)
                times = part.get('time')
                if not isinstance(times, dict):
                    times = {}
                if (not all(isinstance(times.get(k), int) for k in ('created', 'ran', 'completed')) or
                        not times.get('created', 1) <= times.get('ran', 0) <= times.get('completed', -1)):
                    issue('missing_or_invalid_tool_time', sid, call, incomplete=True)
                if status not in {'completed', 'error'}:
                    issue('tool_not_terminal', sid, call, incomplete=True)
                    continue
                if status == 'error':
                    row['notCountedAsCompletedAccess'] = True
                    row['errorSha256'] = sha(str(state.get('error', '')).encode())
                    if tool in DELEGATE_TOOLS:
                        references = child_ids(part)
                        for child in sorted(references):
                            children.append({'sessionID': child, 'viaCallID': call})
                            visit(child, sid)
                        if not references and not str(state.get('error', '')).startswith(
                                ('Permission denied:', 'Invalid arguments for tool')):
                            issue('failed_delegate_without_child_evidence', sid, call, incomplete=True)
                    continue
                if tool in FILE_TOOLS | {'shell', 'bash'}:
                    for key, value in string_fields(inputs):
                        if key in PATH_KEYS or (tool == 'glob' and key == 'pattern'):
                            row['targets'].append(target(value, sid, call, key))
                    for key, value in string_fields(metadata.get('files', [])):
                        if key in PATH_KEYS:
                            row['targets'].append(target(value, sid, call, 'result.' + key))
                    if tool in {'glob', 'grep', 'list'}:
                        for value in output.splitlines():
                            if value.startswith('/'):
                                row['targets'].append(target(value.rstrip(':'), sid, call, 'returnedPath'))
                    if tool == 'read':
                        requested = inputs.get('path')
                        if not requested or not output.startswith(('Read file ' + requested + ',',
                                                                   'Read directory ' + requested + ',')):
                            issue('unrecognized_read_result', sid, call, incomplete=True)
                    if tool in {'shell', 'bash'}:
                        command = inputs.get('command', inputs.get('cmd'))
                        row['shellCommandSha256'] = sha(str(command).encode())
                        if command not in allowed:
                            issue('unreviewed_shell_command', sid, call, incomplete=True)
                        if isinstance(command, str):
                            if any(marker in command for marker in ('$', '`')):
                                issue('unresolved_shell_expansion', sid, call, incomplete=True)
                            try:
                                operands = shlex.split(command)
                            except ValueError:
                                operands = []
                                issue('unparseable_shell_command', sid, call, incomplete=True)
                            for operand in operands:
                                path = operand.split('=', 1)[-1]
                                if path.startswith(('/', '../', '~')) or path == '..':
                                    row['targets'].append(target(path, sid, call, 'shellOperand'))
                        row['implicitWorkingDirectory'] = session.get('directory')
                        if inputs.get('background') is True:
                            shell_id = metadata.get('shellID')
                            if (not isinstance(shell_id, str) or not shell_id or
                                    metadata.get('status') != 'running' or shell_id in background_shells or
                                    inputs.get('timeout') != 0 or not isinstance(command, str)):
                                issue('invalid_background_shell', sid, call, incomplete=True)
                            else:
                                background_shells[shell_id] = command
                elif tool in DELEGATE_TOOLS:
                    references = child_ids(part)
                    if not references:
                        issue('missing_child_session_reference', sid, call, incomplete=True)
                    for child in sorted(references):
                        children.append({'sessionID': child, 'viaCallID': call})
                        visit(child, sid)
                elif tool in {'webfetch', 'websearch'}:
                    issue('network_tool_access', sid, call)
                else:
                    issue('unknown_tool', sid, call, incomplete=True)
        for shell_id in sorted(set(background_shells) - completed_background_shells):
            issue('missing_background_shell_notification', sid, shell_id, incomplete=True)
        if discover_children is not None:
            try:
                discovered = set(discover_children(sid))
                if any(not SESSION_ID.fullmatch(child) for child in discovered):
                    raise ValueError('invalid discovered session id')
                referenced = {child['sessionID'] for child in children}
                if referenced - discovered:
                    issue('referenced_child_absent_from_inventory', sid, incomplete=True)
                for child in sorted(discovered - referenced):
                    issue('unreferenced_child_session', sid, incomplete=True)
                    children.append({'sessionID': child, 'viaCallID': None})
                    visit(child, sid)
            except Exception:
                issue('child_discovery_unavailable', sid, incomplete=True)
        visiting.remove(sid)

    visit(root_id)
    return {'schemaVersion': 1, 'rootSessionID': root_id, 'candidate': str(root),
            'session_logs': sessions, 'records': records, 'violations': violations,
            'complete': coverage, 'valid': coverage and not violations,
            'independentChildInventoryChecked': discover_children is not None,
            'scope': 'Recorded CLI tool events and current path resolution, not OS syscall confinement. '
                     'Tool timestamps are forensic ordering only, not benchmark duration metrics.'}
