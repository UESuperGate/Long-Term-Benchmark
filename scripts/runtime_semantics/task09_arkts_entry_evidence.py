"""Verify a real Spaces-tab entry failure without inventing lifecycle post-state."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = '09_spaces_lifecycle'
POLICY_ID = 'task09.arkts.real-spaces-entry.v1'


def require(value, message):
    if not value:
        raise ValueError('Task09 Spaces entry: ' + message)


def record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def bound_bytes(item):
    path = Path(item['path']).resolve()
    require(path.is_relative_to(ROOT / 'experiment_results') or path.is_relative_to(ROOT / 'eval_runs'),
            'artifact outside retained evidence')
    require(record(path) == item, 'retained artifact changed')
    return path.read_bytes()


def bound(item):
    return json.loads(bound_bytes(item))


def prefix(row):
    values = [item['data'] for item in row.get('evidence', [])
              if item.get('label') == 'Task09.missingFeatureEntry']
    require(len(values) <= 1, 'ambiguous entry proof')
    return values[0] if values else None


def legacy_projection(row):
    return any(item.get('label') == 'after:event' and
               item.get('data', {}).get('frame', {}).get('state', {}).get('surface') == 'spaces' and
               item.get('data', {}).get('frame', {}).get('controls', {}).get('placeholder', {}).get('visible') is True
               for item in row.get('evidence', []))


def check_prefix(raw, row):
    require(raw is not None and raw.get('eventExecuted') is True, 'real entry event missing')
    before, after = raw['before'], raw['after']
    require(before.get('routeName') == after.get('routeName') == 'pages/Index' and
            before.get('windowId') == after.get('windowId') and before.get('windowId') is not None,
            'entry changed candidate route/window')
    tab = before['controls']['spaces']
    require(all(tab.get(key) is True for key in ('present', 'visible', 'enabled', 'clickable')) and
            tab.get('id') == 'home_spaces_tab', 'real enabled Spaces tab missing')
    placeholder = after['controls']['placeholder']
    require(placeholder.get('present') is True and placeholder.get('visible') is True and
            placeholder.get('id') == 'spaces_unavailable', 'actual unavailable surface missing')
    require(before['controls'].get('placeholder', {}).get('present') is False,
            'common start already shows the unavailable surface')
    nodes = []

    def visit(value):
        if isinstance(value, dict):
            if '$type' in value:
                nodes.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(after.get('tree'))
    # Only the observed common two-tab placeholder can establish this prefix.
    # An additional candidate control requires a real binding, not a base FAIL.
    require(len(nodes) == 10 and all(node['$type'] in {'root', 'Column', 'Row', 'Text', 'Button'}
                                    for node in nodes) and
            sorted(node.get('$attrs', {}).get('id') for node in nodes if node['$type'] == 'Button') ==
            ['home_chats_tab', 'home_spaces_tab'] and
            {node.get('$attrs', {}).get('id') for node in nodes} <=
            {None, '', 'home_chats_tab', 'home_spaces_tab', 'spaces_unavailable'},
            'candidate exposes an additional or unbound surface; missing-entry classification is unavailable')
    state_before, state_after = raw['stateBefore'], raw['stateAfter']
    require(state_before.get('available') is True and state_after.get('available') is True and
            state_before.get('surface') == 'chats' and state_after.get('surface') == 'spaces' and
            state_before.get('instanceId') == state_after.get('instanceId') and
            state_before.get('instanceId') is not None, 'original presenter transition missing')
    actions = [item['observation'] for item in row.get('calls', [])
               if item.get('method') == 'Task11.uiAction' and
               item.get('observation', {}).get('selector', {}).get('id') == 'home_spaces_tab']
    require(len(actions) == 1 and actions[0].get('kind') == 'click' and
            all(actions[0].get('target', {}).get(key) is True for key in ('visible', 'enabled', 'clickable')),
            'physical Spaces-tab click missing')
    calls = [item for item in state_after.get('calls', [])
             if item.get('method') == 'openSpaces' and item.get('completed') is True]
    require(len(calls) == 1 and calls[0].get('receiverId') == state_after['instanceId'],
            'original production receiver did not execute')


def normalized(raw, spec, evidence, sources):
    require(raw.get('status') == 'not_scored' and raw.get('observed') == {} and
            raw.get('invariantChecks') == [] and
            raw.get('reason') == 'Adapter did not observe every canonical expectation and invariant',
            'raw row is not an unknown post-state after successful entry probe')
    return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'],
            'status': 'fail', 'failureKind': 'semantic_missing_feature_entry',
            'transitionExecuted': False, 'observed': None, 'invariantChecks': [],
            'unevaluatedInvariants': copy.deepcopy(spec.get('invariants', [])),
            'unobservedExpectedFields': list(spec['expected']),
            'checkpoints': copy.deepcopy(raw['checkpoints']), 'productionSources': sources,
            'entryFailureEvidence': evidence,
            'reason': 'The real Spaces tab opens its unavailable surface; lifecycle post-state and invariants remain unknown.'}


def attach_entry(row, spec, report, evidence_root):
    if prefix(row) is None:
        require(not legacy_projection(row), 'withdrawn synthetic base post-state')
        return row
    build_path, execution_path, native_path = (Path(row[key]['path']).resolve()
                                              for key in ('build', 'execution', 'nativeResult'))
    build = json.loads(build_path.read_text())
    sources, snapshots = [], {}
    for item in build['production']:
        source = Path(report['source']) / item['path']
        receipt = record(source)
        require(receipt['sha256'] == item['sha256'], 'candidate changed after packaging')
        destination = evidence_root / 'production-sources' / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        sources.append({**item, 'bytes': receipt['bytes']})
        snapshots[item['path']] = record(destination)
    evidence = {'policyId': POLICY_ID, 'build': record(build_path), 'execution': record(execution_path),
                'nativeResult': record(native_path), 'productionSnapshots': snapshots}
    return normalized(json.loads(native_path.read_text()), spec, evidence, sources)


def normalize_report(report, evidence_root, contract):
    require((report.get('taskId'), report.get('platform')) == (TASK, 'arkts'), 'wrong task/platform')
    rows = report['rows']
    require([(row.get('caseId'), row.get('traceDigest')) for row in rows] ==
            [(spec['caseId'], spec['traceDigest']) for spec in contract['cases']],
            'incomplete canonical execution sequence')
    result = copy.deepcopy(report)
    result['rows'] = [attach_entry(row, spec, result, evidence_root)
                      for row, spec in zip(rows, contract['cases'])]
    used = set()
    for row in result['rows']:
        if row.get('entryFailureEvidence'):
            validate_entry_failure(row, result, used, contract=contract)
    return result


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    require((report.get('taskId'), report.get('platform')) == (TASK, 'arkts'), 'wrong task/platform')
    require(contract is not None and contract['taskId'] == TASK, 'canonical contract missing')
    spec = next(spec for spec in contract['cases'] if spec['caseId'] == row['caseId'])
    evidence = row['entryFailureEvidence']
    require(evidence.get('policyId') == POLICY_ID, 'unknown entry policy')
    execution, build, raw = (bound(evidence[key]) for key in ('execution', 'build', 'nativeResult'))
    require(execution.get('status') == 'transport_completed' and execution.get('transportCompleted') is True and
            execution.get('candidateAbsentBeforeInstall') is True and
            execution.get('cleanup', {}).get('ownedAppUninstalled') is True, 'fresh device execution incomplete')
    require(execution.get('rows') == [raw] and execution['buildReport']['sha256'] == evidence['build']['sha256'] and
            execution['rowArtifact']['sha256'] == evidence['nativeResult']['sha256'] and
            execution['rowArtifact']['bytes'] == evidence['nativeResult']['bytes'], 'native build/result binding changed')
    require(all(raw.get(key) == value for key, value in
                {'taskId': TASK, 'role': report['role'], 'caseId': spec['caseId'],
                 'traceDigest': spec['traceDigest']}.items()), 'canonical runtime identity changed')
    require(build.get('source') == report.get('source', report.get('target')) and
            build.get('runtimeCompile', {}).get('passed') is True and
            all(build.get(key) is True for key in
                ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
            'candidate packaging/source binding incomplete')
    observer = build['nativeUIObserver']
    require(bool(observer.get('fixtures')), 'executed evaluator provenance missing')
    for fixture in [*observer['fixtures'], observer['installer']]:
        path = Path(fixture.get('source', fixture.get('file', ''))).resolve()
        require(path.is_relative_to(ROOT / 'state_tests/runtime/arkts') and
                record(path)['sha256'] == fixture['sha256'], 'executed evaluator differs from reviewed module')
    for command in execution['commands']:
        path = (Path(evidence['execution']['path']).parent / command['log']).resolve()
        require(path.is_relative_to(Path(evidence['execution']['path']).parent) and
                record(path)['sha256'] == command['sha256'], 'device command log changed')
    check_prefix(prefix(raw), raw)
    sources = row['productionSources']
    require([{key: item[key] for key in ('path', 'sha256')} for item in sources] == build['production'],
            'production inventory differs from packaged candidate')
    for item in sources:
        snapshot = evidence['productionSnapshots'][item['path']]
        bound_bytes(snapshot)
        require(snapshot['bytes'] == item['bytes'] and snapshot['sha256'] == item['sha256'],
                'retained production source changed')
    require(row == normalized(raw, spec, evidence, sources), 'entry verdict changed after execution')
    identity = (execution.get('executionNonce'), execution.get('pid'))
    require(bool(identity[0]) and bool(identity[1]) and identity not in used_observation_ids,
            'device execution missing or reused')
    used_observation_ids.add(identity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'refusing to overwrite normalized evidence')
    contract = json.loads((ROOT / 'benchmark_tasks' / TASK / 'transitions.json').read_text())
    report = json.loads(args.report.read_text())
    result = normalize_report(report, args.report.resolve().parent, contract)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
