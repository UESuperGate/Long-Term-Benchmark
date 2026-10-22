"""Additional Task13 raw-mapping/source closure conjunct; no verdict generation or gate edits."""
import json
from pathlib import Path
import sys

try:
    from . import task13_page_owner_verify as original
except ImportError:
    import task13_page_owner_verify as original

core = original.core
require = original.require
checked = original.checked


def verify(report_path):
    report_path = Path(report_path).resolve()
    result = original.verify(report_path)
    report = core.load(report_path)
    evidence = report['provenance']['runtimeEvidence']
    execution_path, build_path = checked(evidence['execution']), checked(evidence['build'])
    execution, build = core.load(execution_path), core.load(build_path)
    inventory = core.load(checked(evidence['sourceInventory']))
    hashes = {item['path']: item['sha256'] for item in inventory['files']}
    require(report['provenance']['productionSources'] ==
            [item for item in inventory['files'] if item['path'].endswith(('.kt', '.ets'))],
            'formal declared production sources differ from immutable inventory')
    bindings = build['nativeUIObserver']['sources']
    require(bindings and {item['path']: item['sha256'] for item in bindings} ==
            {item['path']: item['sha256'] for item in build['production']},
            'native page observer does not bind the whole actual compiled production closure')
    require(all(hashes.get(item['path']) == item['sha256'] for item in bindings),
            'native production source not in candidate snapshot')
    native = {}
    for artifact in execution['rowArtifacts']:
        record = {'path': artifact['local'], 'bytes': artifact['bytes'], 'sha256': artifact['sha256']}
        path = checked(record)
        native[core.load(path)['caseId']] = (core.load(path), core.file_record(path))
    logs = [core.file_record(execution_path.parent / command['log']) for command in execution['commands']]
    for row in report['semantic']['cases']:
        child, child_record = native[row['caseId']]
        require(child.get('productionSources') and all(hashes.get(item['path']) == item['sha256']
                                                     for item in child['productionSources']),
                'native case source provenance differs from executed source snapshot')
        calls = [call['observation'] for call in child['calls']
                 if call.get('method') == 'Task13Revision5.originalProfileRuntime']
        require(len(calls) == 1 and calls[0]['productionSources'] == bindings,
                'original page replay source closure differs from compiled observer binding')
        expected = {
            'execution': {'original': core.file_record(execution_path), 'retained': core.file_record(execution_path)},
            'build': {'original': core.file_record(build_path), 'retained': core.file_record(build_path)},
            'nativeResult': {'original': child_record, 'retained': child_record},
            'commandLogs': [{'original': item, 'retained': item} for item in logs],
        }
        require(row.get('nativeArtifacts') == expected, 'per-case original -> retained full raw mapping differs')
        for item in [*expected.values()][:3]:
            require(checked(item['original']) == checked(item['retained']), 'original/retained raw bytes differ')
    result['additionalRawMappingVerified'] = True
    result['additionalSourceClosureVerified'] = True
    result['verifierSource'] = core.file_record(Path(__file__))
    return result


if __name__ == '__main__':
    path, output = map(Path, sys.argv[1:])
    result = verify(path)
    core.write(output, result)
    print(json.dumps({'verified': True, 'counts': result['counts'], 'output': str(output)}))
