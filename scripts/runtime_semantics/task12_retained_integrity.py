"""Independently bind retained Task12 verdicts to raw runtime and control inputs."""
import hashlib
import json
from pathlib import Path

try:
    from ..run_runtime_transition_matrix import validate_report
except ImportError:
    from run_runtime_transition_matrix import validate_report


def require(value, message):
    if not value:
        raise ValueError('Task12 retained integrity: ' + message)


def verify_report(path, contract, inventory):
    report = json.loads(Path(path).read_text())
    require(report.get('taskId') == contract.get('taskId') == '12_report_room', 'wrong contract/task')
    validate_report(report, contract)
    provenance = report['provenance']
    require(provenance.get('sourceInventorySha256') == inventory['sha256'], 'different input inventory')
    require(Path(provenance['candidateSource']).resolve() == Path(inventory['source']).resolve(),
            'different source directory')
    files = {item['path']: item for item in inventory['files']}
    for item in provenance['productionSources']:
        require(files.get(item['path']) == item, 'declared production differs from frozen control input')
    artifacts = []

    def bind(value):
        if isinstance(value, dict):
            if {'path', 'sha256', 'bytes'} <= set(value):
                artifact = Path(value['path'])
                data = artifact.read_bytes()
                require(len(data) == value['bytes'] and hashlib.sha256(data).hexdigest() == value['sha256'],
                        'runtime artifact bytes changed: ' + str(artifact))
                artifacts.append(str(artifact))
            for child in value.values():
                bind(child)
        elif isinstance(value, list):
            for child in value:
                bind(child)

    evidence = provenance['runtimeEvidence']
    bind(evidence)
    raw = json.loads(Path(evidence['raw']['path']).read_text())
    original = raw.get('semantic', {}).get('cases') or raw.get('observations') or raw.get('cases')
    require(isinstance(original, list), 'raw canonical observations missing')
    by_id = {row.get('caseId', row.get('key')): row for row in original}
    compared = 0
    for row in report['semantic']['cases']:
        if row.get('entryFailureEvidence'):
            continue  # The public entry policy separately verifies actual prefix logs/positive controls.
        actual = by_id.get(row['caseId'], by_id.get(row['key']))
        require(actual is not None, 'raw canonical row missing')
        for field in ('status', 'observed', 'checkpoints'):
            require(row.get(field) == actual.get(field), 'normalized ' + field + ' differs from runtime')
        checks = row['invariantChecks']
        for original_check in actual['invariantChecks']:
            require(any(all(check.get(key) == value for key, value in original_check.items()) for check in checks),
                    'runtime invariant was replaced during normalization')
        compared += 1
    return {'verified': True, 'runtimeArtifactsVerified': len(set(artifacts)),
            'rawTransitionRowsCompared': compared, 'productionSourceRecords': len(provenance['productionSources']),
            'modelAgentResult': False}
