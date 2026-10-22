"""Retain real unbound initial probes as NS, never fabricate canonical transitions."""
import copy
import json
from pathlib import Path

try:
    from . import tasks10_11_runtime_evidence as shared
    from .task10_native_artifacts import retain_pair, retain_logs
except ImportError:
    import tasks10_11_runtime_evidence as shared
    from task10_native_artifacts import retain_pair, retain_logs


def attach_unbound_entry(report, contract, artifacts, retained):
    result = copy.deepcopy(report)
    retained = Path(retained)
    retained.mkdir(parents=True, exist_ok=True)
    if result['provenance'].get('runtimeBinding') != 'task10.arkts.unbound-entry.v1' or any(
            row['status'] != 'not_scored' or row.get('observed') is not None or row.get('invariantChecks')
            for row in result['semantic']['cases']):
        raise ValueError('Unbound Task10 initial probe cannot infer canonical observations/verdicts')
    blob = retained / 'native-artifacts'
    snapshot = retain_pair(result['provenance']['entryCapability']['snapshot'], blob)
    build = retain_pair(result['provenance']['buildReport'], blob)
    logs = retain_logs(artifacts, blob)
    result['provenance']['unboundProbeArtifacts'] = {
        'backend': 'unbound_initial_entry_probe', 'initialUI': snapshot, 'build': build, 'commandLogs': logs,
        'canonicalTransitionExecuted': False}
    sources = shared.collect_slice_sources(Path(artifacts))
    if not sources:
        raise ValueError('Unbound Task10 probe has no actual compiled production manifest')
    manifests = {}
    for source in sources:
        original = source['runtimeSlice']
        identity = original['path'], original['sha256']
        if identity not in manifests:
            target = retained / f'slice-{len(manifests)}.json'
            target.write_bytes(shared.read_record(original))
            manifests[identity] = shared.record(target)
        source['runtimeSlice'] = manifests[identity]
    result['provenance']['productionSources'] = sources
    (retained / 'unbound-not-scored.runtime.json').write_text(json.dumps(result, indent=2) + '\n')
    shared.validate_report(result, contract)
    return result
