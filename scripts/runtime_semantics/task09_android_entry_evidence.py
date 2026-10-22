"""Task09 original rendered HomeView entry proof, never lifecycle projections."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = '09_spaces_lifecycle'
HERE = ROOT / 'state_tests/runtime/android' / TASK / 'actual_render_prefix'
CONTRACT = ROOT / 'benchmark_tasks' / TASK / 'transitions.json'
POLICY_ID = 'task09.android.closed-original-home-ui-binding.v2'
_GUARD_SPEC = importlib.util.spec_from_file_location('task09_android_closed_ui_binding',
    Path(__file__).with_name('task09_android_ui_binding_guard.py'))
binding_guard = importlib.util.module_from_spec(_GUARD_SPEC)
_GUARD_SPEC.loader.exec_module(binding_guard)
PREFIX = 'features/home/impl/src/main/kotlin/io/element/android/features/home/impl/'
REQUIRED = {PREFIX + path for path in ('HomeView.kt', 'HomePresenter.kt', 'HomeState.kt',
    'HomeEvents.kt', 'HomeNavigationBarItem.kt', 'components/RoomListContentView.kt')}
REQUIRED.add('libraries/designsystem/src/main/kotlin/io/element/android/libraries/designsystem/theme/components/Scaffold.kt')
POINTS = ['common_start', 'positive_control_original_chat_action', 'after_real_spaces_click',
          'positive_control_chats_roundtrip', 'entry_blocked_at_original_coming_soon_surface']


def require(value, reason):
    if not value:
        raise ValueError('Task09 actual Android entry: ' + reason)


def artifact(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def bound(item):
    path = Path(item['path']).resolve()
    require(any(path.is_relative_to(ROOT / name) for name in ('experiment_results', 'eval_runs')),
            'evidence outside owned audit roots')
    data = path.read_bytes()
    require(len(data) == item.get('bytes') and hashlib.sha256(data).hexdigest() == item.get('sha256'),
            'archived artifact changed')
    return data


def reviewed(item, expected):
    require(Path(item['path']).resolve() == expected.resolve() and item == artifact(expected),
            'reviewed policy, contract or runner differs')
    return expected.read_bytes()


def check_trace(raw, key):
    require(raw.get('key') == key and raw.get('status') == 'pass', 'entry probe did not finish cleanly')
    require(raw.get('observed') == {} and raw.get('invariantChecks') == [],
            'fabricated canonical post-state or invariant')
    checkpoints = raw.get('checkpoints', [])
    require([p.get('name') for p in checkpoints] == POINTS, 'actual UI positive controls missing')
    states = [p['state'] for p in checkpoints]
    ids = {p.get('observationId') for p in states}
    require(len(ids) == 1 and isinstance(next(iter(ids)), str) and len(next(iter(ids))) >= 32,
            'independent observation id absent')
    for index, state in enumerate(states):
        require(state.get('key') == key and state.get('featureFlagEnabled') is True and
                state.get('runtimeBoundary') == 'original_HomeView_HomeScaffold_HomePresenter_ComposeUI' and
                bool(state.get('semanticsTree')), 'real production render evidence absent')
        require(state.get('selectedTab') == ('Spaces' if index in (2, 4) else 'Chats'),
                'real tab selection sequence differs')
        require(state.get('startChatCalls') == (0 if index == 0 else 1), 'chat action positive control failed')
        placeholder = index in (2, 4)
        require(state.get('placeholderText') == (['Spaces are coming soon!'] if placeholder else []),
                'actual placeholder text missing')
        require(('Spaces are coming soon!' in state['semanticsTree']) is placeholder,
                'placeholder observation disagrees with actual semantics')
    expected_events = ['SelectHomeNavigationBarItem(item=Spaces)', 'SelectHomeNavigationBarItem(item=Chats)',
                       'SelectHomeNavigationBarItem(item=Spaces)']
    for index, state in enumerate(states):
        require(state.get('deliveredEvents') == expected_events[:max(0, index-1)],
                'original production event delivery sequence differs')
    return next(iter(ids))


def check_actual(raw, key):
    observation_id = check_trace(raw, key)
    inventory = binding_guard.ui_inventory(raw)
    if not inventory['eligible']:
        raise binding_guard.UnboundUIBinding('; '.join(inventory['reasonCodes']))
    return observation_id


def validate_runtime(runtime, path):
    require(runtime.get('status') == 'passed' and runtime.get('runtimeCompile', {}).get('status') == 'passed'
            and not runtime.get('error'), 'runtime/compile/environment failure is not a semantic entry failure')
    provenance = runtime.get('provenance', {})
    require(json.loads(reviewed(provenance['entryPolicy'], HERE / 'policy.json')) == json.loads((HERE / 'policy.json').read_text()),
            'unreviewed entry policy')
    contract = reviewed(provenance['canonicalContract'], CONTRACT)
    require(contract == CONTRACT.read_bytes(), 'canonical contract changed')
    configuration = json.loads(bound(provenance['executedConfiguration']))
    require(configuration.get('testClass') == 'runtime.SpacesHomeRenderedPrefixTest', 'wrong executed test class')
    require(configuration.get('keys') and len(configuration['keys']) == len(set(configuration['keys'])),
            'independent JUnit invocation keys absent')
    reviewed(provenance['renderedRunner'], HERE / 'run.py')
    expected_evaluators = [HERE / 'SpacesHomeRenderedPrefixTest.kt',
        ROOT / 'state_tests/runtime/android/common/Harness.kt',
        ROOT / 'state_tests/runtime/android/08_threads/robolectric/EvidenceRobolectricRunner.java',
        ROOT / 'state_tests/runtime/android/08_threads/robolectric/RobolectricMain.java']
    evaluator_sources = provenance.get('evaluatorSources', [])
    require(len(evaluator_sources) == len(expected_evaluators) and
            len({p['path'] for p in evaluator_sources}) == len(expected_evaluators), 'complete reviewed evaluator set missing')
    for reviewed_path in expected_evaluators:
        matches = [p for p in evaluator_sources if Path(p['path']).resolve() == reviewed_path.resolve()]
        require(len(matches) == 1 and matches[0]['sha256'] == hashlib.sha256(reviewed_path.read_bytes()).hexdigest(),
                'self-signed evaluator does not match reviewed source')
        snapshot = Path(path).parent / 'evaluator-sources' / reviewed_path.name
        require(bound(artifact(snapshot)) == reviewed_path.read_bytes(), 'evaluator snapshot differs')
    sources = provenance.get('productionSources', [])
    require(REQUIRED.issubset({s['path'] for s in sources}), 'original HomeView/Scaffold/Presenter source closure incomplete')
    for source in sources:
        snapshot = provenance.get('productionSourceSnapshots', {}).get(source['path'])
        require(snapshot is not None, 'consumed original source/resource snapshot missing')
        data = bound(snapshot)
        require(len(data) == source['bytes'] and hashlib.sha256(data).hexdigest() == source['sha256'],
                'executed production bytes differ from archived snapshot')
    log = bound(runtime['log'])
    lines = [json.loads(line.removeprefix('RUNTIME_RESULT ')) for line in log.decode().splitlines()
             if line.startswith('RUNTIME_RESULT ')]
    require(lines == runtime.get('observations'), 'raw observations differ from actual runtime stdout')
    require(len(lines) == len(configuration['keys']) and [r['key'] for r in lines] == configuration['keys'],
            'JUnit method invocation coverage differs')
    observation_ids = [check_trace(row, row['key']) for row in lines]
    require(len(observation_ids) == len(set(observation_ids)), 'independent per-case runtime observation reused')
    return provenance


def normalized(spec, raw, runtime, path, binding_record=None):
    observation_id = check_trace(raw, spec['key'])
    guard = binding_guard.assess(runtime, raw, binding_record=binding_record, runtime_path=path)
    proof = {'policyId': POLICY_ID, 'runtimeEvidence': artifact(path),
             'policy': artifact(HERE / 'binding_policy_v2.json'), 'contract': artifact(CONTRACT),
             'validator': artifact(Path(__file__)),
             'bindingValidator': artifact(Path(binding_guard.__file__)),
             'bindingReference': artifact(binding_guard.REFERENCE), 'candidateInputs': binding_record,
             'observationIds': [f'{POLICY_ID}:{observation_id}:{spec["key"]}']}
    eligible = guard['eligible']
    return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'],
            'status': 'fail' if eligible else 'not_scored',
            'failureKind': 'semantic_missing_feature_entry' if eligible else 'unbound_actual_ui_or_inputs',
            'observed': None, 'invariantChecks': [], 'unevaluatedInvariants': copy.deepcopy(spec['invariants']),
            'canonicalEventExecuted': False, 'prefixTransitionExecuted': True,
            'transitionExecuted': False,
            'unobservedExpectedFields': list(spec['expected']),
            'checkpoints': copy.deepcopy(raw['checkpoints']),
            'productionSources': copy.deepcopy(runtime['provenance']['productionSources']),
            'entryFailureEvidence' if eligible else 'entryBindingEvidence': proof,
            'entryBindingGuard': guard,
            'reason': ('Closed original HomeView UI and inputs, real tab clicks and positive controls establish unavailable entry. '
                       'Canonical lifecycle post-state and invariants were not evaluated.') if eligible else
                      ('Unknown UI or production input binding; placeholder alone cannot establish missing functionality: ' +
                       '; '.join(guard['reasonCodes']))}


def entry_rows(runtime, path, contract=None, binding_record=None):
    contract = contract or json.loads(CONTRACT.read_text())
    validate_runtime(runtime, path)
    rows = {r['key']: r for r in runtime['observations']}
    require(len(rows) == len(runtime['observations']), 'duplicate case observations')
    return [normalized(spec, rows[spec['key']], runtime, path, binding_record) for spec in contract['cases']]


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    contract = contract or json.loads(CONTRACT.read_text())
    require((report.get('taskId'), report.get('platform')) == (TASK, 'android'), 'report identity differs')
    evidence = row.get('entryFailureEvidence', {})
    require(evidence.get('policyId') == POLICY_ID, 'unreviewed policy id')
    reviewed(evidence['policy'], HERE / 'binding_policy_v2.json')
    reviewed(evidence['contract'], CONTRACT)
    reviewed(evidence['validator'], Path(__file__))
    reviewed(evidence['bindingValidator'], Path(binding_guard.__file__))
    reviewed(evidence['bindingReference'], binding_guard.REFERENCE)
    path = Path(evidence['runtimeEvidence']['path'])
    runtime = json.loads(bound(evidence['runtimeEvidence']))
    provenance = validate_runtime(runtime, path)
    require(provenance.get('candidateSource') == report.get('provenance', {}).get('candidateSource'),
            'different candidate source')
    require(provenance.get('productionSources') == report.get('provenance', {}).get('productionSources'),
            'report source manifest differs')
    spec = next(c for c in contract['cases'] if c['caseId'] == row.get('caseId'))
    raw = next(r for r in runtime['observations'] if r['key'] == spec['key'])
    require(row == normalized(spec, raw, runtime, path, evidence.get('candidateInputs')) and row['status'] == 'fail',
            'scored row changed or UI binding is unknown')
    ids = evidence['observationIds']
    require(not used_observation_ids.intersection(ids), 'entry observation reused')
    used_observation_ids.update(ids)
    return {'caseId': spec['caseId'], 'status': 'fail', 'observationIds': ids}


def legacy_projection(row):
    return (bool(row.get('observed')) and any('renderedBaseSurface' in p.get('state', {}) or
            'canonicalObservation' in p.get('state', {}) for p in row.get('checkpoints', [])))
