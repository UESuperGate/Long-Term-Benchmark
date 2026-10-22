"""Staged case005 physical-action admission; not wired into the public scorer.

Source/layout identity is only a binding eligibility guard. A missing selector,
unknown tree/source, or incomplete physical prefix never establishes a failure.
Historical diagnostic evidence can be reviewed, but cannot acquire the new
producer protocol retroactively. Central registration and calibration are pending.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

try:
    from . import task14_15_arkts_artifacts as artifacts
except ImportError:
    import task14_15_arkts_artifacts as artifacts

ROOT = artifacts.ROOT
POLICY_ID = 'task15.arkts.source-bound-physical-action-eligibility.v1'
TASK = '15_account_deactivation'
CASE = 'ad_state_005_first_submit_confirms'
PROFILE = ROOT / ('experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1/'
                  'task15-action-eligibility-review-v1/profile.json')
PROFILE_SHA = 'e51a784eda11ba2019298cd3bdbfaf1a9b922016f216310bbfca73f925550c92'
FIELDS = ('id', 'text', 'content', 'label', 'enabled', 'visibility', 'focused', 'focusable',
          'touchable', 'hitTestBehavior', 'clip', 'opacity', 'zIndex', 'isOn', 'scrollable',
          'accessibilityLevel', 'accessibilityText', 'isLayoutDirtyMarked', 'isRenderDirtyMarked',
          'hasPendingRequest', 'isFirstBuilding')
require = artifacts.require


def profile():
    data = PROFILE.read_bytes()
    require(hashlib.sha256(data).hexdigest() == PROFILE_SHA, 'Staged eligibility profile changed')
    value = json.loads(data)
    require(value['taskId'] == TASK and value['sourceIdentityIsEligibilityGuardNotVerdict'] is True,
            'Wrong action closure profile')
    return value


def source_closure(inputs, build, binding):
    require(build.get('runtimeCompile', {}).get('passed') is True and
            all(build.get(key) is True for key in ('productionUnchanged', 'copiedProductionUnchanged',
                                                  'temporaryProjectRemoved')),
            'Packaging/environment/source error is not a semantic failure')
    require(build.get('production') == binding['compiledProduction'],
            'Changed/extra/renamed production source: binding unavailable')
    require([{key: item[key] for key in ('path', 'bytes', 'sha256')} for item in inputs] ==
            [{key: item[key] for key in ('path', 'bytes', 'sha256')} for item in binding['inputFiles']],
            'Unreviewed full input closure: binding unavailable')
    digest = hashlib.sha256()
    for item in inputs:
        path = Path(item['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'Unsafe input member')
        data = artifacts.bound(item['snapshot'])
        require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'],
                'Executed input snapshot differs')
        name = item['path'].encode()
        digest.update(len(name).to_bytes(8, 'big'))
        digest.update(name)
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    require(digest.hexdigest() == binding['rootSha256'], 'Candidate input digest differs')
    indexed = {item['path']: item for item in inputs}
    require(all(indexed[item['path']]['sha256'] == item['sha256'] for item in build['production']),
            'Packaged input differs from full source closure')
    return digest.hexdigest()


def inventory(tree, expected_user):
    rows = []
    def visit(node, path):
        require(isinstance(node, dict) and isinstance(node.get('$children', []), list), 'Unknown native tree')
        attrs = node.get('$attrs', {})
        selected = {key: attrs.get(key) for key in FIELDS}
        if attrs.get('id') == 'account_session_user':
            require(selected['content'] == expected_user, 'Native login identity differs')
            selected['content'] = '$observed_https_login_user_id'
        rows.append({'path': path, 'type': node.get('$type'), 'rect': node.get('$rect'),
                     'attributes': selected, 'children': len(node.get('$children', []))})
        for index, child in enumerate(node.get('$children', [])):
            visit(child, path + '/' + str(index))
    visit(tree, 'root')
    return rows


def unique(tree, node_id):
    found = []
    def visit(node):
        if node.get('$attrs', {}).get('id') == node_id:
            found.append(node)
        for child in node.get('$children', []):
            visit(child)
    visit(tree)
    require(len(found) == 1, 'Missing/ambiguous bound native action; verdict unavailable')
    return found[0]


def inspect_evidence(*, raw, provider, build, inputs, contract):
    """Review one actual disabled action, without applying a semantic verdict."""
    binding = profile()
    require(contract.get('taskId') == TASK, 'Wrong canonical task')
    spec = next(item for item in contract['cases'] if item['caseId'] == CASE)
    require(spec['key'] == 'first_submit_confirms' and
            spec['given'] == {'password': 'secret', 'eraseData': True, 'action': 'uninitialized'} and
            spec['event'] == {'name': 'deactivate_account', 'isRetry': False}, 'Unsupported action/given boundary')
    root_sha = source_closure(inputs, build, binding)
    require(raw.get('taskId') == TASK and raw.get('caseId') == CASE and raw.get('role') == 'agent' and
            raw.get('traceDigest') == spec['traceDigest'], 'Raw case/contract identity differs')
    transitions = [item['nativePageTransition'] for item in raw.get('evidence', []) if 'nativePageTransition' in item]
    require(len(transitions) == 1, 'Missing/ambiguous actual runtime prefix')
    native = transitions[0]
    require(native.get('entryExecuted') is True and native.get('eventExecuted') is False and
            native.get('readiness', {}).get('ready') is True and native.get('prerequisite', {}).get('rootConfirmed') is True,
            'Real common-start/form prefix was not established')
    require(native.get('taskId') == TASK and native.get('caseId') == CASE and native.get('traceDigest') == spec['traceDigest'],
            'Native prefix contract differs')
    require(native.get('failure', {}).get('stage') == 'diagnostic_only_after_input' and
            native['failure']['message'] == 'Error: DIAGNOSTIC_ONLY_COMPLETE_BEFORE_SUBMIT_NO_SEMANTIC_VERDICT',
            'Unreviewed transport/failure boundary; remain NOT_SCORED')
    frames = native.get('imeDiagnostic', {}).get('frames', [])
    require(len(frames) == 2 and all(isinstance(frame.get('nativeTree'), dict) for frame in frames),
            'Complete pre/post IME native tree missing')
    prior, ready = frames
    first, last = prior.get('windowAndIme', {}), ready.get('windowAndIme', {})
    require(first.get('visibilitySource') == last.get('visibilitySource') == 'native_window_keyboard_avoid_area' and
            first.get('keyboardVisible') is True and last.get('keyboardVisible') is False and
            first['keyboardAvoidArea']['bottomRect']['height'] > 0 and
            all(last['keyboardAvoidArea'][key]['width'] == last['keyboardAvoidArea'][key]['height'] == 0
                for key in ('topRect', 'bottomRect', 'leftRect', 'rightRect')),
            'Actual unoccluded post-IME action boundary missing')
    require(first['nativeWindow']['id'] == last['nativeWindow']['id'] and last['nativeWindowShowing'] is True and
            last['activeWindow']['bundleName'] == native['bundleName'] and last['activeWindow']['focused'] is True,
            'Original form/window was not retained')
    login = native['integration']['login']
    requests = [item for item in provider['requests'] if item['kind'] == 'login']
    require(len(requests) == provider['loginCount'] == login['providerLoginCount'] == 1 and
            requests[0]['secure'] is True and requests[0]['responseStatus'] == 200 and
            login['expectedUserId'] == '@' + requests[0]['body']['user'] + ':task15.test', 'Actual HTTPS login positive control missing')
    require(inventory(ready['nativeTree'], login['expectedUserId']) == binding['postImeClosedInventory'],
            'Extra/renamed/unbound native code or control: remain NOT_SCORED')
    owner = binding['sourceBinding']
    button = unique(ready['nativeTree'], owner['actionControlId'])
    require(button['$type'] == owner['actionControlType'] and button['$attrs']['visibility'] == 'Visibility.Visible' and
            button['$attrs']['enabled'] is False, 'Actual visible native disabled action not proven')
    require(all(button['$attrs'].get(key) is False for key in ('isLayoutDirtyMarked', 'isRenderDirtyMarked', 'hasPendingRequest')),
            'Native action is unsettled; remain NOT_SCORED')
    control = next(item for item in ready['controls'] if item['name'] == 'submit')
    require(control['id'] == owner['actionControlId'] and control['present'] is control['visible'] is True and
            control['enabled'] is False, 'Missing selector is not a disabled-action proof')
    rect = json.loads('[' + button['$rect'] + ']')
    require(rect == [[control['bounds']['left'], control['bounds']['top']],
                     [control['bounds']['right'], control['bounds']['bottom']]], 'Inspector/UiTest target geometry differs')
    password = unique(ready['nativeTree'], owner['passwordControlId'])
    erase = unique(ready['nativeTree'], owner['eraseControlId'])
    require(password['$attrs']['text'] == spec['given']['password'] and erase['$attrs']['isOn'] == 'true',
            'Physical form values do not establish original givens')
    state = native['failure']['presenter']
    require(state.get('available') is True and state.get('originalService') is True and state.get('accountSessionActive') is True and
            state.get('instanceCount') == 1 and all(state.get(key) == value for key, value in spec['given'].items()),
            'Original receiver/canonical given differs')
    module = state['binding']
    require(module['presenterSourcePath'] == owner['presenterModule'] and module['importCompleted'] is True and
            module['importPhase'] == 'after_original_page_ready_before_fixture', 'Original production handler binding missing')
    for method, argument in (('setPassword', spec['given']['password']), ('setEraseData', True)):
        require(any(call['method'] == method and call.get('returned') is True and call['args'] == [argument] and
                    call['instanceId'] == state['instanceId'] for call in state['calls']), 'Physical setter/owner evidence missing')
    actions = native['actions']
    backs = [item for item in actions if item['kind'] == 'system_back']
    require(len(backs) == 1 and backs[0]['executed'] is True and backs[0]['observedImeBefore'] == first,
            'No positive-IME-conditioned actual Back')
    for kind, target in (('input', 'password'), ('click', 'erase')):
        require(any(item['kind'] == kind and item['target'] == target and item['executed'] is True and
                    item['sessionId'] == native['sessionId'] and item['sequence'] < backs[0]['sequence'] for item in actions),
                'Common reachable physical operation prefix incomplete')
    require(state['requestCount'] == 0 and state['serviceCalls'] == [] and provider['deactivationCount'] == 0 and
            not any(item['method'] == 'deactivateAccount' for item in state['calls']) and
            not any(item['target'] in ('submit', 'confirm') and item['executed'] for item in actions),
            'Not a blocked-before-event prefix')
    return {'classification': 'proven_visible_disabled_required_action', 'caseId': CASE,
        'candidateRootSha256': root_sha, 'canonicalObligations': copy.deepcopy({
            key: spec[key] for key in ('given', 'event', 'expected', 'invariants', 'traceDigest')}),
        'givenEstablishedByPhysicalPrefix': True, 'transitionExecuted': False,
        'observedPostState': None, 'evaluatedInvariants': [],
        'proposedSemanticStatusAfterReviewAndFreshProtocol': 'fail', 'scoringApplied': False,
        'publicAdmissionReady': False,
        'presenterCanSubmitGetterUsedForVerdict': False,
        'limitations': ['Only case005; no reuse for other givens/events',
            'Only the complete source/UI closure in the staged profile is bound; unknown variants remain NOT_SCORED',
            'Current v6 is historical diagnostic-only, not a new producer-protocol execution',
            'Central registration, reviewed producer, dynamic four-pole calibration and public admission remain pending']}


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    """Proposed public signature. Fail closed until a reviewed producer actually executes it."""
    require(contract is not None and contract.get('taskId') == TASK and report.get('taskId') == TASK and
            report.get('platform') == 'arkts' and report.get('role') == 'agent', 'Wrong action admission identity')
    evidence = row.get('entryFailureEvidence', {})
    require(evidence.get('policyId') == POLICY_ID, 'Unknown action eligibility policy')
    raw = json.loads(artifacts.bound(evidence['raw']))
    # No after-the-fact marker on diagnostic v6 can authorize a score.
    require(raw.get('actionEligibilityProtocol') == POLICY_ID and
            report.get('provenance', {}).get('actionEligibilityProtocol') == POLICY_ID,
            'Historical diagnostic lacks reviewed fresh producer protocol; NOT_SCORED')
    raise ValueError('Staged policy has no reviewed dynamic four-pole/public admission yet; NOT_SCORED')
