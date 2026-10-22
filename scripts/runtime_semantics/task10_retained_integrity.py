"""Bind Task10 repository-adapter verdicts to unchanged original native output."""
import gzip
import copy
import argparse
import hashlib
import json
from pathlib import Path

from . import task10_repository_evidence as repository
from . import task10_repository_prefix_policy as prefix
from . import tasks10_11_runtime_evidence as shared


def require(value, reason):
    if not value:
        raise ValueError('Task10 retained runtime integrity: ' + reason)


def load(item):
    return json.loads(shared.read_record(item))


def read_pair(pair, original):
    require(pair['original'] == original, 'original artifact reference was replaced')
    data = shared.read_record(pair['retained'])
    if pair.get('encoding') == 'gzip':
        data = gzip.decompress(data)
    else:
        require(pair.get('encoding') == 'identity', 'unsupported retained artifact encoding')
    require(len(data) == original['bytes'] and hashlib.sha256(data).hexdigest() == original['sha256'],
            'decoded artifact differs from exact original bytes')
    return data


def json_artifact(row, name, original):
    retained = row.get('nativeArtifacts')
    return json.loads(read_pair(retained[name], original)) if retained else load(original)


def same_reference(left, right):
    return (Path(left['path']).resolve() == Path(right['path']).resolve() and
            all(left.get(key) == right.get(key) for key in ('bytes', 'sha256')))


def layout_controls(tree):
    if not isinstance(tree, dict):
        return []
    result, pending = [], [tree]
    while pending:
        node = pending.pop()
        require(isinstance(node, dict), 'malformed original UI tree')
        result.append(node.get('attributes', {}))
        pending.extend(reversed(node.get('children', [])))
    return result


def verify_host_report(path, contract):
    """Device UI controls have a host observer, not a native ohosTest result."""
    report = json.loads(Path(path).read_text())
    shared.validate_report(report, contract)
    provenance = report['provenance']
    seen, verdicts = set(), []
    for row in report['semantic']['cases']:
        retained = row['nativeArtifacts']
        require(retained.get('backend') == 'host_device_ui_observer', 'wrong host observer backend')
        execution_bytes = read_pair(retained['execution'], provenance['deviceReport'])
        require(read_pair(retained['nativeResult'], provenance['deviceReport']) == execution_bytes,
                'observer result differs from original execution')
        execution = json.loads(execution_bytes)
        build = json.loads(read_pair(retained['build'], provenance['buildReport']))
        require(all(execution.get(key) == report.get(key) for key in ('taskId', 'platform', 'role')) and
                execution.get('status') == 'passed' and
                execution['diagnostics']['cleanup'].get('ownedAppUninstalled') is True and
                execution['diagnostics']['cleanup'].get('deviceLockRemoved') is True,
                'original host device execution or cleanup incomplete')
        require(same_reference(execution['compile']['build'], provenance['buildReport']) and
                build.get('source') == provenance.get('productionSourceRoot') and
                all(build.get(key) is True for key in
                    ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
                'host observer build used different production or incomplete cleanup')
        sources = {item['path']: item['sha256'] for item in provenance['productionSources']}
        require({item['path']: item['sha256'] for item in build['production']} == sources ==
                {item['path']: item['sha256'] for item in execution['provenance']['buildProduction']},
                'original host production input inventory differs')
        location = retained['caseResultPath']
        require(len(location) == 3 and location[:2] == ['semantic', 'cases'] and
                type(location[2]) is int and 0 <= location[2] < len(execution['semantic']['cases']) and
                location[2] not in seen, 'original host case locator missing, reused or invalid')
        seen.add(location[2])
        native = execution['semantic']['cases'][location[2]]
        require(all(native.get(key) == row.get(key) for key in ('caseId', 'traceDigest')),
                'original host case identity differs')
        logs = {}
        for pair in retained['commandLogs']:
            data = read_pair(pair, pair['original'])
            logs[str(Path(pair['original']['path']).resolve())] = hashlib.sha256(data).hexdigest()
        for command in [*provenance['commands'], *execution['diagnostics']['commands']]:
            item = command['log']
            require(logs.get(str(Path(item['path']).resolve())) == item['sha256'],
                    'original host command log missing or changed')
        layouts = {}
        for pair in retained['layouts']:
            data = read_pair(pair, pair['original'])
            layouts[str(Path(pair['original']['path']).resolve())] = data
        points = {point['name']: point for point in native['checkpoints']}
        require(len(points) == len(native['checkpoints']), 'ambiguous original host checkpoints')
        for point in row['checkpoints']:
            label = point.get('sourceName', point.get('name'))
            require(label in points, 'unknown host checkpoint')
            original = points[label]['layout']
            data = layouts.get(str(Path(original['path']).resolve()))
            require(data is not None and hashlib.sha256(data).hexdigest() == original['sha256'] and
                    len(data) == original['bytes'] and shared.read_record(point['actualSnapshot']) == data,
                    'retained host snapshot differs from exact actual layout')
            require(point['state'] == {'controls': layout_controls(json.loads(data))},
                    'normalized host controls differ from original device tree')
        if row.get('entryFailureEvidence'):
            require(row.get('observed') is None and row.get('invariantChecks') == [] and
                    row.get('transitionExecuted') is False,
                    'early entry cannot claim a canonical post-state or invariant result')
        else:
            checks = copy.deepcopy(native['invariantChecks'])
            for check in checks:
                if not check.get('description'):
                    check['description'] = check.get('invariant', check.get('text'))
            require(row['status'] == native['status'] and row['observed'] == native['observed'] and
                    row['invariantChecks'] == checks,
                    'host status, observations or invariants differ from original execution')
        verdicts.append(row['status'])
    require(len(verdicts) == len(contract['cases']) and set(verdicts) <= {'pass', 'fail'},
            'incomplete host device case coverage')
    return {'validated': True, 'taskId': report['taskId'], 'platform': report['platform'],
            'passed': verdicts.count('pass'), 'failed': verdicts.count('fail'), 'notScored': 0,
            'backend': 'host_device_ui_observer', 'originalCases': len(seen),
            'newModelOrDeviceRun': False, 'genericCandidateBindingReadinessClaimed': False}


def verify_report(path, contract):
    report = json.loads(Path(path).read_text())
    repository.validate_report(report, contract)
    provenance = report['provenance']
    require(provenance.get('runtimeBinding') == repository.BINDING, 'wrong original-page runtime binding')
    seen = set()
    verdicts = []
    specs = {spec['caseId']: spec for spec in contract['cases']}
    for row in report['semantic']['cases']:
        execution = json_artifact(row, 'execution', row['execution'])
        build = json_artifact(row, 'build', row['build'])
        require(execution.get('transportCompleted') is True and execution.get('candidateAbsentBeforeInstall') is True and
                execution.get('cleanup', {}).get('ownedAppUninstalled') is True, 'incomplete fresh native execution')
        require(execution.get('buildReport', {}).get('sha256') == row['build']['sha256'] and
                build.get('source') == provenance.get('productionSourceRoot') and
                build.get('task10SourceInventory', {}).get('sha256') == provenance['sourceInventory']['sha256'],
                'native execution used a different compiled candidate')
        nonce = execution.get('executionNonce')
        require(isinstance(nonce, str) and len(nonce) == 32 and nonce not in seen,
                'native execution nonce missing or reused')
        seen.add(nonce)
        artifact = execution['rowArtifact']
        original_native = {'path': artifact['local'], 'bytes': artifact['bytes'], 'sha256': artifact['sha256']}
        retained = row.get('nativeArtifacts')
        native = json.loads(read_pair(retained['nativeResult'], original_native)) if retained else load(original_native)
        require(execution.get('rows') == [native] and
                native.get('nativeBridge', {}).get('capabilities', {}).get('execution', {}).get('nonce') == nonce,
                'native result bytes or execution nonce differ')
        require(all(native.get(key) == row.get(key) for key in ('taskId', 'role', 'caseId', 'traceDigest')) and
                row['key'] == specs[row['caseId']]['key'],
                'native case identity differs from formal row')
        if retained:
            logs = {}
            for pair in retained['commandLogs']:
                data = read_pair(pair, pair['original'])
                logs[str(Path(pair['original']['path']).resolve())] = hashlib.sha256(data).hexdigest()
            for command in execution.get('commands', []):
                original_log = Path(row['execution']['path']).parent / command['log']
                require(logs.get(str(original_log.resolve())) == command['sha256'],
                        'original device command log was lost or substituted')
        points = {point['label']: point for point in native['checkpoints']}
        require(len(points) == len(native['checkpoints']), 'ambiguous original native checkpoints')
        for point in row['checkpoints']:
            snapshot = load(point['actualSnapshot'])
            label = snapshot['label']
            require(label in points and snapshot['state'] == points[label]['state'],
                    'retained snapshot differs from actual native checkpoint')
        if row.get('entryFailureEvidence'):
            require(row['caseId'] == prefix.CASE, 'unexpected entry normalization')
            prefix.validate_entry_failure(row, report, set(), contract=contract)
        else:
            require(all(row.get(key) == native.get(key) for key in ('status', 'observed', 'invariantChecks')),
                    'semantic status, observed state or invariants differ from original native output')
        verdicts.append(row['status'])
    require(len(verdicts) == len(contract['cases']) and set(verdicts) <= {'pass', 'fail'},
            'incomplete scored native case coverage')
    return {'validated': True, 'taskId': report['taskId'], 'platform': report['platform'],
            'passed': verdicts.count('pass'), 'failed': verdicts.count('fail'), 'notScored': 0,
            'nativeExecutions': len(seen), 'newModelOrDeviceRun': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error('Refusing to overwrite an existing integrity receipt')
    contract = json.loads(arguments.contract.read_text())
    results = []
    for path in arguments.report:
        report = json.loads(path.read_text())
        backend = report['semantic']['cases'][0]['nativeArtifacts']['backend']
        function = verify_host_report if backend == 'host_device_ui_observer' else verify_report
        results.append({'report': shared.record(path), 'assessment': function(path, contract)})
    receipt = {'scope': 'original_runtime_bytes_independent_verification', 'modelCalled': False,
        'deviceCalled': False, 'genericScorerReadinessClaimed': False,
        'contract': shared.record(arguments.contract), 'verifier': shared.record(Path(__file__)),
        'reports': results}
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'validated': True, 'reportCount': len(results), 'receipt': str(arguments.output)}))
