"""Bind early feature-entry failures to fresh, unchanged candidate UI execution."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
try:
    from . import tasks16_17_arkts_entry_binding_v2 as binding_guard
except ImportError:
    import tasks16_17_arkts_entry_binding_v2 as binding_guard

ROOT = Path(__file__).resolve().parents[2]
POLICY_ID = 'tasks16_17.arkts.real-common-entry.v1'
TASKS = {'16_identity_reset', '17_pinned_messages'}


def require(condition, message):
    if not condition:
        raise ValueError('ArkTS common entry: ' + message)


def record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def bound(item):
    path = Path(item['path']).resolve()
    require(path.is_relative_to(ROOT / 'experiment_results') or path.is_relative_to(ROOT / 'eval_runs'),
            'artifact outside retained runtime evidence')
    require(record(path) == item, 'artifact bytes changed')
    return path.read_bytes()


def prefix_observation(row, task_id):
    matches = ([item['raw'] for item in row.get('evidence', []) if item.get('kind') == 'native_base_entry_absence']
               if task_id == '16_identity_reset' else
               [item['nativeTransition'] for item in row.get('evidence', [])
                if item.get('nativeTransition', {}).get('baseFeatureAbsent') is True])
    if not matches:
        return None
    require(len(matches) == 1, 'ambiguous common-entry observation')
    return matches[0]


def check_prefix(raw, task_id, bundle_name):
    """Positive runtime trace only; failure scoring additionally requires binding_guard."""
    require(raw.get('entryExecuted') is True and raw.get('eventExecuted') is True and
            not raw.get('failure') and not raw.get('cleanupError'), 'runtime prefix did not complete')
    require(raw.get('bundleName') == bundle_name, 'prefix belongs to another installed application')
    frames = raw.get('frames', [])
    require(len(frames) == 2 and [frame.get('label') for frame in frames] == ['before_event', 'after_event'],
            'ordered common-entry frames missing')
    windows = [frame.get('windowIdentity', {}) for frame in frames]
    require(all(window.get('hostVerified') is True and window.get('focused') is True and
                window.get('bundleName') == bundle_name and window.get('routeName') == 'pages/Index'
                for window in windows), 'common page is not the actual focused candidate window')
    require(windows[0].get('stageMainWindowId') == windows[1].get('stageMainWindowId') and
            windows[0].get('stageMainWindowId') is not None, 'positive control changed application instance')
    if task_id == '16_identity_reset':
        require(raw.get('classification') == 'feature_entry_absent' and
                raw.get('positiveControl') == 'Backup state: enabled', 'identity entry was not observed absent')
        controls = [{item['name']: item for item in frame.get('controls', [])} for frame in frames]
        require(all(all(points.get(name, {}).get('present') is False for name in ('finalTitle', 'finalEntry'))
                    and points.get('root', {}).get('visible') is True for points in controls),
                'common backup surface or absent reset entry not established')
        enable = controls[0].get('enableBackup', {})
        require(all(enable.get(field) is True for field in ('visible', 'enabled', 'clickable')) and
                controls[0].get('enabledState', {}).get('present') is False and
                controls[1].get('enabledState', {}).get('visible') is True,
                'real backup state transition missing')
        require(raw.get('actions') == [{'target': 'enableBackup', 'executed': True, 'api': 'UiTest.Component.click'}],
                'physical backup positive-control action missing')
    else:
        require(raw.get('runtimeClassification') == 'feature_entry_absent' and raw.get('baseFeatureAbsent') is True,
                'pinned collection entry was not observed absent')
        positive = raw.get('basePositiveControl', {})
        require(all(positive.get(key) is True for key in
                    ('clickedBannerNext', 'bodyChanged', 'finalEntryAbsentBefore', 'finalEntryAbsentAfter')),
                'pinned banner positive control incomplete')
        for frame in frames:
            controls = {item['id']: item for item in frame.get('controls', [])}
            require(controls.get('open_pinned_messages', {}).get('present') is False and
                    controls.get('pinned_banner_next', {}).get('visible') is True,
                    'pinned common page or entry absence missing')
        require('Welcome to the room' not in frames[0].get('visibleTexts', []) and
                'Welcome to the room' in frames[1].get('visibleTexts', []), 'banner did not change after physical click')
        require(len(raw.get('actions', [])) == 1 and raw['actions'][0].get('target') == 'pinned_banner_next' and
                raw['actions'][0].get('executed') is True, 'physical banner click missing')


def normalized_row(raw_row, spec, evidence, sources, eligibility=None):
    require(raw_row.get('status') == 'not_scored' and raw_row.get('observed') == {} and
            raw_row.get('invariantChecks') == [] and
            raw_row.get('reason') == 'Adapter did not observe every canonical expectation and invariant',
            'raw adapter fabricated post-state or encountered another execution failure')
    row = {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'],
            'status': 'fail', 'failureKind': 'semantic_missing_feature_entry',
            'transitionExecuted': False, 'observed': None, 'invariantChecks': [],
            'unevaluatedInvariants': copy.deepcopy(spec.get('invariants', [])),
            'unobservedExpectedFields': list(spec['expected']),
            'checkpoints': copy.deepcopy(raw_row['checkpoints']), 'productionSources': sources,
            'entryFailureEvidence': evidence,
            'reason': 'Fresh unchanged candidate common page executes its real positive control, but the required feature entry is absent.'}
    if not eligibility or not eligibility.get('eligible'):
        row.update(status='not_scored', failureKind='unbound_actual_ui_or_enclosing_inputs',
                   entryBindingEvidence=row.pop('entryFailureEvidence'), entryBindingGuard=eligibility,
                   reason='Unknown complete enclosing input/UI binding; private selector absence alone is not semantic failure.')
    return row


def attach_entries(report, contract, input_bindings=None):
    provenance = report['provenance']
    evidence_root = Path(provenance['strictEvidence']['path'])
    indexed = {spec['caseId']: spec for spec in contract['cases']}
    executions = {item['caseId']: evidence_root / item['report'] for item in provenance['executions']}
    changed = False
    for index, row in enumerate(report['semantic']['cases']):
        raw = prefix_observation(row, report['taskId'])
        if raw is None:
            continue
        spec = indexed[row['caseId']]
        execution_path = executions[row['caseId']]
        build_path = execution_path.parent.parent / 'device-build-report.json'
        build = json.loads(build_path.read_text())
        check_prefix(raw, report['taskId'], build['bundleName'])
        sources = []
        for item in build['production']:
            source = Path(provenance['candidateSource']) / item['path']
            require(record(source)['sha256'] == item['sha256'], 'candidate changed after application packaging')
            snapshot = evidence_root / 'production-sources' / item['path']
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(source.read_bytes())
            sources.append({**item, 'bytes': source.stat().st_size})
            provenance.setdefault('productionSourceSnapshots', {})[item['path']] = record(snapshot)
        provenance['productionSources'] = sources
        evidence = {'policyId': POLICY_ID, 'execution': record(execution_path), 'build': record(build_path),
                    'nativeResult': record(execution_path.parent / 'native-result.json')}
        binding = (input_bindings or provenance.get('entryInputBindings', {})).get(row['caseId'])
        eligibility = binding_guard.assess(build, report['taskId'], raw, binding)
        evidence['closedInputBinding'] = eligibility
        report['semantic']['cases'][index] = normalized_row(row, spec, evidence, sources, eligibility)
        changed = True
    if changed:
        manifest_path = evidence_root / 'evidence-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'] = [{**record(path), 'path': path.relative_to(evidence_root).as_posix()}
                             for path in sorted(evidence_root.rglob('*')) if path.is_file() and path != manifest_path]
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        provenance['strictEvidence']['manifestSha256'] = record(manifest_path)['sha256']


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    require(report.get('taskId') in TASKS and report.get('platform') == 'arkts', 'wrong task/platform')
    require(contract is not None and contract['taskId'] == report['taskId'], 'canonical contract missing')
    spec = next(spec for spec in contract['cases'] if spec['caseId'] == row['caseId'])
    evidence = row['entryFailureEvidence']
    require(evidence.get('policyId') == POLICY_ID, 'unknown entry policy')
    execution = json.loads(bound(evidence['execution']))
    build = json.loads(bound(evidence['build']))
    raw_row = json.loads(bound(evidence['nativeResult']))
    require(execution.get('status') == 'transport_completed' and execution.get('transportCompleted') is True and
            execution.get('candidateAbsentBeforeInstall') is True and
            execution.get('cleanup', {}).get('ownedAppUninstalled') is True, 'fresh runtime transport incomplete')
    require(execution.get('rows') == [raw_row] and
            execution['buildReport']['sha256'] == evidence['build']['sha256'] and
            execution['rowArtifact']['sha256'] == evidence['nativeResult']['sha256'] and
            execution['rowArtifact']['bytes'] == evidence['nativeResult']['bytes'], 'raw row/build binding changed')
    require(all(raw_row.get(key) == value for key, value in
                {'taskId': report['taskId'], 'role': report['role'], 'caseId': spec['caseId'],
                 'traceDigest': spec['traceDigest']}.items()), 'runtime canonical identity changed')
    require(build.get('source') == report['provenance']['candidateSource'] and
            all(build.get(key) is True for key in ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved'))
            and build.get('runtimeCompile', {}).get('passed') is True, 'candidate production binding incomplete')
    for fixture in build['nativeUIObserver']['fixtures']:
        path = Path(fixture['file']).resolve()
        require(path.is_relative_to(ROOT / 'state_tests/runtime/arkts'), 'unreviewed evaluator module')
        require(record(path)['sha256'] == fixture.get('sourceSha256', fixture['sha256']),
                'runtime evaluator differs from reviewed module')
    require(bool(build['nativeUIObserver']['fixtures']), 'executed evaluator provenance missing')
    for command in execution['commands']:
        path = Path(evidence['execution']['path']).parent / command['log']
        require(record(path)['sha256'] == command['sha256'], 'device command log changed')
    raw = prefix_observation(raw_row, report['taskId'])
    require(raw is not None, 'no real common-entry proof')
    check_prefix(raw, report['taskId'], build['bundleName'])
    sources = row['productionSources']
    require([{key: item[key] for key in ('path', 'sha256')} for item in sources] == build['production'],
            'row production sources differ from executed application')
    for source in sources:
        data = bound(report['provenance']['productionSourceSnapshots'][source['path']])
        require(len(data) == source['bytes'] and hashlib.sha256(data).hexdigest() == source['sha256'],
                'retained production source changed')
    declared = evidence.get('closedInputBinding')
    input_binding = declared.get('inputEvidence') if declared and declared.get('inputEvidence') and \
        declared['inputEvidence'] not in binding_guard.reference()['tasks'][report['taskId']]['retainedBeforeRuntimeInputs'] else None
    eligibility = binding_guard.assess(build, report['taskId'], raw, input_binding)
    require(eligibility['eligible'], 'unbound actual UI/enclosing input eligibility: ' + '; '.join(eligibility['reasonCodes']))
    if declared is not None:
        require(declared == eligibility, 'closed input guard evidence changed')
    require(row == normalized_row(raw_row, spec, evidence, sources, eligibility), 'normalized entry verdict differs from runtime')
    identity = (execution.get('executionNonce'), execution.get('pid'))
    require(bool(identity[0]) and bool(identity[1]) and identity not in used_observation_ids,
            'fresh runtime execution identity missing or reused')
    used_observation_ids.add(identity)
