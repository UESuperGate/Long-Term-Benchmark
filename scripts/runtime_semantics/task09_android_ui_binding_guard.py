"""Closed original Home UI binding, never a source-hash semantic verdict."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / 'state_tests/runtime/android/09_spaces_lifecycle/actual_render_prefix/binding_reference_v2.json'
REFERENCE_SHA256 = 'bf93174d0d520f17718ae6bcaf067789463125be989dc184c87cbe64fd1977af'
HEADER = "Printing with useUnmergedTree = 'true'"
NODE = re.compile(r"^[ |]*(?:\|-)?Node #(\d+) at \(l=([^,]+), t=([^,]+), r=([^,]+), b=([^\)]+)\)px(?:, Tag: '(.*)')?$")
PROPERTY = re.compile(r'^([A-Za-z][A-Za-z0-9_]*) = (.+)$')
FLAG = re.compile(r'^\[([A-Za-z][A-Za-z0-9_]*)\]$')


class UnboundUIBinding(ValueError):
    """Unknown UI/source coverage is not evidence of a missing feature."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def reference():
    data = REFERENCE.read_bytes()
    if hashlib.sha256(data).hexdigest() != REFERENCE_SHA256:
        raise ValueError('Task09 reviewed UI binding reference changed')
    return json.loads(data)


def parse_semantics_tree(text):
    """Parse every unmerged node/property; unknown/truncated formats fail closed.

    Only ephemeral node IDs and layout coordinates are excluded from binding
    equality. Every action, text, tag, role, flag, parent and child is retained.
    """
    if not isinstance(text, str):
        raise UnboundUIBinding('Semantics tree is not text')
    lines = text.splitlines()
    if not lines or lines[0] != HEADER:
        raise UnboundUIBinding('Complete unmerged semantics header missing')
    nodes, stack, ids = [], [], set()
    for line in lines[1:]:
        if not line.strip():
            continue
        matched = NODE.fullmatch(line)
        if matched:
            column = line.index('Node #')
            if column % 3:
                raise UnboundUIBinding('Unrecognized semantics node indentation')
            depth = column // 3
            node_id = matched[1]
            if node_id in ids or depth > len(stack) or (depth == 0 and nodes):
                raise UnboundUIBinding('Duplicate node, root or incomplete semantics topology')
            ids.add(node_id)
            bounds = [float(matched[index]) for index in range(2, 6)]
            if not all(math.isfinite(value) for value in bounds) or bounds[0] > bounds[2] or bounds[1] > bounds[3]:
                raise UnboundUIBinding('Invalid semantics bounds')
            stack = stack[:depth]
            if depth:
                parent = stack[-1]
                path = parent['path'] + [parent['childCount']]
                parent['childCount'] += 1
            else:
                path = []
            node = {'path': path, 'tag': matched[6], 'properties': {}, 'childCount': 0}
            nodes.append(node)
            stack.append(node)
            continue
        if not stack:
            raise UnboundUIBinding('Semantics property precedes root')
        stripped = line.lstrip(' |')
        if len(line)-len(stripped) != (len(stack)-1)*3:
            raise UnboundUIBinding('Semantics property indentation is ambiguous')
        prop, flag = PROPERTY.fullmatch(stripped), FLAG.fullmatch(stripped)
        if prop:
            key, value = prop.groups()
            if key == 'Actions':
                if not re.fullmatch(r'\[(?:[A-Za-z]\w*(?:, [A-Za-z]\w*)*)?\]', value):
                    raise UnboundUIBinding('Unrecognized semantics action encoding')
                value = value[1:-1].split(', ') if value != '[]' else []
                if len(value) != len(set(value)):
                    raise UnboundUIBinding('Duplicate semantics action')
        elif flag:
            key, value = flag[1], True
        else:
            raise UnboundUIBinding('Unrecognized or truncated semantics line')
        if key in stack[-1]['properties']:
            raise UnboundUIBinding('Duplicate semantics property')
        stack[-1]['properties'][key] = value
    if not nodes:
        raise UnboundUIBinding('Empty semantics tree')
    actions = []
    for node in nodes:
        if 'Actions' not in node['properties']:
            continue
        labels = []
        for child in nodes:
            if child['path'][:len(node['path'])] == node['path']:
                for key in ('Text', 'ContentDescription'):
                    if key in child['properties']:
                        labels.append({'path': child['path'], 'kind': key, 'value': child['properties'][key]})
        actions.append({'path': node['path'], 'tag': node['tag'],
                        'actions': node['properties']['Actions'],
                        'role': node['properties'].get('Role'), 'labels': labels})
    return {'nodes': nodes, 'actionInventory': actions}


def ui_inventory(raw, reviewed=None):
    reviewed = reviewed or reference()
    checkpoints = []
    reasons = []
    for point in raw.get('checkpoints', []):
        name = point.get('name')
        item = {'name': name, 'matched': False}
        expected = reviewed['checkpoints'].get(name)
        try:
            observed = parse_semantics_tree(point.get('state', {}).get('semanticsTree'))
            item.update(inventory=observed, sha256=digest(observed))
            if expected is None or observed != expected['inventory']:
                reasons.append('unbound_semantics_inventory:' + str(name))
            else:
                item['matched'] = True
        except (UnboundUIBinding, ValueError) as error:
            item['error'] = str(error)
            reasons.append('incomplete_semantics_inventory:' + str(name))
        checkpoints.append(item)
    if [point['name'] for point in checkpoints] != list(reviewed['checkpoints']):
        reasons.append('incomplete_checkpoint_inventory')
    return {'eligible': not reasons, 'reasonCodes': reasons, 'checkpoints': checkpoints}


def source_binding(runtime, reviewed=None):
    reviewed = reviewed or reference()
    provenance = runtime.get('provenance', {})
    sources = sorted(provenance.get('productionSources', []), key=lambda item: item['path'])
    expected = reviewed['productionClosure']
    reasons = []
    if sources != expected:
        reasons.append('unbound_production_ui_closure')
    # The complete captured Git tree additionally fences changes to enclosing
    # Home/Root navigation wiring that this component slice does not execute.
    # Unknown trees are NS, not an inferred semantic failure or candidate role.
    tree = provenance.get('snapshotTree')
    if tree not in reviewed['reviewedCapturedTrees']:
        reasons.append('unbound_enclosing_production_tree')
    return {'eligible': not reasons, 'reasonCodes': reasons,
            'observedClosureSha256': digest(sources), 'expectedClosureSha256': digest(expected),
            'observedSourceCount': len(sources), 'expectedSourceCount': len(expected),
            'capturedTree': tree, 'reviewedTrees': reviewed['reviewedCapturedTrees'],
            'usage': 'binding eligibility only; a hash match cannot establish semantic failure'}


EXCLUDED_DIRECTORIES = {'.git', 'build', '.gradle', '.hvigor', 'oh_modules', 'node_modules', '__pycache__'}
PRIVATE_CONFIGURATIONS = {'local.properties', 'key.properties', 'keystore.properties', '.npmrc', '.netrc'}


def input_path(path):
    relative = Path(path)
    return (not relative.is_absolute() and '..' not in relative.parts and
            not EXCLUDED_DIRECTORIES.intersection(relative.parts) and
            not (relative.parts and relative.parts[0] == '_benchmark_inputs') and path != 'opencode.json')


def input_manifest(rows):
    selected = [dict(row) for row in rows if input_path(row['path'])]
    if len({row['path'] for row in selected}) != len(selected):
        raise UnboundUIBinding('Duplicate full-input inventory path')
    return sorted(selected, key=lambda row: row['path'])


def capture_inputs(source, *, deadline=None):
    """Read all eligible files, including ignored inputs; never follow symlinks."""
    import time
    rows = []
    for parent, directories, files in os.walk(source, followlinks=False):
        for name in list(directories):
            path = Path(parent) / name
            relative = path.relative_to(source).as_posix()
            if not input_path(relative):
                directories.remove(name)
            elif path.is_symlink():
                raise UnboundUIBinding('Unknown input directory symlink: ' + relative)
        for name in files:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Task09 complete-input binding budget exhausted')
            path = Path(parent) / name
            relative = path.relative_to(source).as_posix()
            if not input_path(relative):
                continue
            if path.is_symlink() or name in PRIVATE_CONFIGURATIONS or name.startswith('.env'):
                raise UnboundUIBinding('Unsupported private configuration or symlink: ' + relative)
            data = path.read_bytes()
            rows.append({'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    return input_manifest(rows)


def artifact(path):
    data = Path(path).read_bytes()
    return {'path': str(Path(path).resolve()), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def read_artifact(item):
    path = Path(item['path']).resolve()
    if not any(path.is_relative_to(ROOT / name) for name in ('experiment_results', 'eval_runs')):
        raise ValueError('Task09 binding artifact outside audit roots')
    if artifact(path) != item:
        raise ValueError('Task09 binding artifact bytes changed')
    return json.loads(path.read_text())


def full_input_binding(binding_record, runtime, runtime_path, reviewed):
    if binding_record is None:
        return {'eligible': False, 'reasonCodes': ['missing_complete_candidate_input_inventory']}
    binding = read_artifact(binding_record)
    if binding['runtimeEvidence'] != artifact(runtime_path):
        raise ValueError('Task09 full-input inventory belongs to another runtime')
    if Path(binding['candidateSource']).resolve() != Path(runtime['provenance']['candidateSource']).resolve():
        raise ValueError('Task09 full-input inventory belongs to another candidate')
    kind = binding['acquisition']
    if kind == 'retained_v1_cleanup_inventory':
        if binding['support'] != reviewed['retainedCleanupSupport']:
            raise ValueError('Task09 unreviewed historical cleanup inventory')
        support = read_artifact(binding['support'])
        if Path(support['candidateSource']).resolve() != Path(binding['candidateSource']).resolve():
            raise ValueError('Task09 retained cleanup belongs to another candidate')
        rows = input_manifest(support['deletedCandidateFiles'])
    elif kind == 'immutable_v1_runtime_tree':
        if runtime['provenance'].get('candidateMode') == 'standalone_directory':
            raise ValueError('Task09 standalone inputs cannot be attested by Git tree alone')
        if binding['gitTree'] != runtime['provenance'].get('tree') or binding['gitCommit'] != runtime['provenance'].get('commit'):
            raise ValueError('Task09 immutable input inventory belongs to another tree')
        rows = input_manifest(binding['files'])
    elif kind == 'live_before_after_inventory':
        before, after = (read_artifact(binding[key]) for key in ('before', 'after'))
        for captured in (before, after):
            if (captured['candidateSource'] != binding['candidateSource'] or
                    captured['producer'] != artifact(Path(__file__)) or not captured['complete']):
                raise ValueError('Task09 full-input producer/source binding changed')
        if before['files'] != after['files']:
            return {'eligible': False, 'reasonCodes': ['candidate_inputs_changed_during_runtime']}
        rows = input_manifest(before['files'])
    else:
        raise ValueError('Task09 unknown full-input acquisition')
    observed = digest(rows)
    eligible = observed == reviewed['completeInputManifestSha256'] and len(rows) == reviewed['completeInputFileCount']
    return {'eligible': eligible,
            'reasonCodes': [] if eligible else ['unbound_complete_candidate_inputs'],
            'manifestSha256': observed, 'fileCount': len(rows), 'acquisition': kind,
            'evidence': binding_record, 'usage': 'eligibility only; unknown enclosing UI/input is NS'}


def assess(runtime, raw, *, binding_record=None, runtime_path=None):
    reviewed = reference()
    source = source_binding(runtime, reviewed)
    ui = ui_inventory(raw, reviewed)
    full = full_input_binding(binding_record, runtime, runtime_path, reviewed)
    return {'eligible': source['eligible'] and ui['eligible'] and full['eligible'],
            'reasonCodes': source['reasonCodes'] + ui['reasonCodes'] + full['reasonCodes'],
            'sourceBinding': source, 'uiInventory': ui, 'completeInputBinding': full,
            'policy': 'closed observed UI plus unchanged captured production wiring; unknown is not_scored'}


def write_inventory(source, output, *, deadline):
    source = Path(source).resolve()
    captured = {'candidateSource': str(source), 'producer': artifact(Path(__file__)),
                'complete': True, 'files': capture_inputs(source, deadline=deadline)}
    Path(output).write_text(json.dumps(captured, indent=2) + '\n')
    return artifact(output)


def seal_live_binding(source, runtime_path, before, after, output):
    binding = {'acquisition': 'live_before_after_inventory',
               'candidateSource': str(Path(source).resolve()),
               'runtimeEvidence': artifact(runtime_path), 'before': before, 'after': after}
    Path(output).write_text(json.dumps(binding, indent=2) + '\n')
    return artifact(output)


def immutable_binding(runtime, runtime_path, output):
    """Git-ref acquisition reads only that immutable tree, never a worktree."""
    provenance = runtime['provenance']
    if provenance.get('candidateMode') == 'standalone_directory' or not provenance.get('commit'):
        raise UnboundUIBinding('A live worktree needs ignored-inclusive before/after inventories')
    reviewed = reference()
    if provenance.get('tree') not in reviewed['reviewedCapturedTrees']:
        raise UnboundUIBinding('Unbound immutable input tree')
    binding = {'acquisition': 'immutable_v1_runtime_tree', 'candidateSource': provenance['candidateSource'],
               'runtimeEvidence': artifact(runtime_path), 'gitTree': provenance['tree'],
               'gitCommit': provenance['commit'], 'files': reviewed['completeInputManifest']}
    Path(output).write_text(json.dumps(binding, indent=2) + '\n')
    return artifact(output)
