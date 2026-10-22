"""Eligibility only: complete enclosing input closure plus actual native prefix."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path(__file__).with_name('tasks16_17_arkts_entry_binding_reference_v2.json')
REFERENCE_SHA256 = '37cea0e4a0012199dd378d2c6c12ef59c9171d52048dc1ab8a0aae56a18d63a4'
POLICY_ID = 'tasks16_17.arkts.closed-input-entry.v2'
EXCLUDED = {'.git', 'build', '.hvigor', '.gradle', 'oh_modules', 'node_modules', '__pycache__'}
CONTROL_KEYS = {
    '16_identity_reset': ('name', ['root','finalTitle','finalEntry','enableBackup','enabledState']),
    '17_pinned_messages': ('id', ['pinned_messages_banner','pinned_banner_next','open_pinned_messages',
        'pinned_messages_back','pinned_messages_loading','pinned_messages_filled','pinned_messages_empty',
        'pinned_messages_failed','focused_event_label']),
}


def record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def bound(item):
    path = Path(item['path']).resolve()
    if not any(path.is_relative_to(ROOT/name) for name in ('experiment_results', 'eval_runs')):
        raise ValueError('Closed entry input evidence outside audit roots')
    if record(path) != item:
        raise ValueError('Closed entry input evidence bytes changed')
    return json.loads(path.read_text())


def reference():
    if record(REFERENCE)['sha256'] != REFERENCE_SHA256:
        raise ValueError('Reviewed Task16/17 input reference changed')
    return json.loads(REFERENCE.read_text())


def ordered(rows):
    if len({item['path'] for item in rows}) != len(rows):
        raise ValueError('Duplicate closed-input path')
    return sorted(rows, key=lambda item: item['path'])


def capture_inputs(source, output, *, phase, deadline):
    """For prospective callers: capture before packaging and after execution."""
    if phase not in ('before_runtime', 'after_runtime'):
        raise ValueError('Explicit input acquisition phase required')
    source = Path(source).resolve()
    rows = []
    for parent, directories, files in os.walk(source, followlinks=False):
        for name in list(directories):
            path = Path(parent)/name
            if name in EXCLUDED or (path.relative_to(source).parts[0] == '_benchmark_inputs'):
                directories.remove(name)
            elif path.is_symlink():
                raise ValueError('Unknown enclosing input symlink')
        for name in files:
            if time.monotonic() >= deadline:
                raise TimeoutError('Closed entry inventory task deadline exhausted')
            path = Path(parent)/name
            relative = path.relative_to(source).as_posix()
            if relative == 'opencode.json' or name == '.git':
                continue
            if path.is_symlink() or name.startswith('.env') or name in ('local.properties','.npmrc','.netrc','key.properties'):
                raise ValueError('Unknown/private enclosing configuration cannot be silently omitted')
            item = record(path)
            item['path'] = relative
            rows.append(item)
    payload = {'candidateSource': str(source), 'phase': phase, 'files': ordered(rows),
               'producer': record(__file__), 'complete': True}
    with Path(output).open('x') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    return record(output)


def assess(build, task_id, raw, input_binding=None):
    """An eligible binding is never a missing-feature verdict by itself.

    The old device prefix records selected controls, not a complete native tree.
    Exact ALL source/config/resource inputs therefore fence unseen extra controls.
    Changed enclosing files or missing full inventories are NS, not feature fail.
    """
    reviewed = reference()['tasks'][task_id]
    reasons = []
    production = ordered(build.get('production', []))
    if production != reviewed['compiledProduction'] or ordered(build.get('nativeUIObserver', {}).get('production', [])) != production:
        reasons.append('unbound_compiled_production_closure')
    field, expected_controls = CONTROL_KEYS[task_id]
    for frame in raw.get('frames', []):
        controls = frame.get('controls', [])
        if [item.get(field) for item in controls] != expected_controls:
            reasons.append('extra_renamed_or_incomplete_recorded_controls')
    inputs, support = None, None
    if input_binding is not None:
        binding = bound(input_binding)
        if bound(binding['build']) != build or binding['buildRecordHash'] != hashlib.sha256(
                json.dumps(build, sort_keys=True, separators=(',', ':')).encode()).hexdigest():
            # buildRecordHash is canonical JSON to avoid trusting a different build's inventory.
            raise ValueError('Full input binding does not belong to this actual build')
        before, after = (bound(binding[key]) for key in ('before','after'))
        for item, phase in ((before,'before_runtime'),(after,'after_runtime')):
            if (item.get('phase') != phase or item.get('producer') != record(__file__) or item.get('complete') is not True
                    or Path(item['candidateSource']).resolve() != Path(build['source']).resolve()):
                raise ValueError('Full input acquisition phase/source/producer differs')
        if before['files'] != after['files']:
            reasons.append('enclosing_inputs_changed_during_runtime')
        else:
            inputs = ordered(before['files'])
            support = input_binding
    else:
        # These exact archived before-runtime inventories are evidence, not
        # candidate path/ref/role rules. Unknown candidates receive no default.
        for item in reviewed['retainedBeforeRuntimeInputs']:
            captured = bound(item)
            if Path(captured['source']).resolve() == Path(build['source']).resolve():
                inputs, support = ordered(captured['files']), item
                break
    if inputs is None:
        reasons.append('missing_complete_enclosing_input_inventory')
    elif inputs != reviewed['completeInputs']:
        reasons.append('unbound_complete_enclosing_inputs')
    return {'policyId': POLICY_ID, 'eligible': not reasons, 'reasonCodes': reasons,
            'reference': record(REFERENCE), 'validator': record(__file__), 'inputEvidence': support,
            'completeInputFileCount': len(inputs) if inputs is not None else None,
            'compiledSourceCount': len(production),
            'nativeUIInventoryComplete': False,
            'closureScope': 'All enclosing source/config/resource inputs, not selected private IDs alone',
            'usage': 'eligibility only; independent physical click and runtime positive controls still required'}


def seal_inputs(build_path, before, after, output):
    build = json.loads(Path(build_path).read_text())
    payload = {'build': record(build_path),
               'buildRecordHash': hashlib.sha256(json.dumps(build, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
               'before': before, 'after': after}
    with Path(output).open('x') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    return record(output)
