"""Synthetic native-schema guard fixtures only; no device/HAP/model evidence."""
import copy
from pathlib import Path
import unittest

from . import task15_page_owner_v5 as guard


def fixture(number):
    contract = guard.core.load(guard.core.ROOT / 'benchmark_tasks/15_account_deactivation/transitions.json')
    spec = contract['cases'][number - 1]
    nonce = 'b' * 32
    session = nonce + ':' + spec['caseId']
    controls = {}
    children = []
    for index, (name, kind) in enumerate((('settings', 'Text'), ('notifications', 'Button'), ('entry', 'Button'),
            ('password', 'TextInput'), ('erase', 'Toggle'), ('submit', 'Button'), ('close', 'Button'))):
        node = {'$type': kind, '$rect': '[[10,10],[90,40]]'[1:-1], '$children': [],
                '$attrs': {'id': 'native_' + name, 'visibility': 'Visibility.Visible', 'enabled': True}}
        if name == 'password': node['$attrs']['text'] = ''
        if name == 'erase': node['$attrs']['isOn'] = 'false'
        children.append(node)
        controls[name] = {'id': node['$attrs']['id'], 'type': kind, 'treePath': 'root/' + str(index)}
    tree = {'$type': 'Column', '$attrs': {}, '$children': children}
    profile = {'UNIT_ONLY_NOT_A_REVIEWED_NATIVE_PROFILE': True, 'sourceRootSha256': 'a' * 64,
        'compiledProduction': [{'path': 'entry/src/main/ets/pages/Index.ets', 'sha256': 'd' * 64}],
        'controls': controls, 'ownerBinding': {'pageSource': 'entry/src/main/ets/pages/Index.ets',
            'presenterSource': 'entry/src/main/ets/features/AccountDeactivationFeature.ets', 'ownerProperty': 'presenter'},
        'ownerAcquisitionMethods': ['loadCapability', 'submitEnabled'], 'pageOwnerSymbols': ['Index.aboutToAppear', 'Index.refresh'],
        'dynamicAttributes': {control['id']: ['enabled', 'text', 'isOn'] for control in controls.values()}, 'closedLayouts': []}
    state = {'password': '', 'eraseData': False, 'action': 'uninitialized', 'requestCount': 0}
    if number in (7, 10): state.update(password='secret', eraseData=True, action='loading' if number == 7 else 'failure', requestCount=1)
    owner = {'protocol': guard.PROTOCOL, 'episodeId': session, 'available': True, 'instanceCount': 1,
        'observerMode': 'pass_through_original_page_owner', 'readScope': 'original_receiver_fields_only', 'originalService': True,
        'binding': profile['ownerBinding'], 'instanceId': 1, 'serviceId': 2,
        'acquisition': {'kind': 'production_page_lifecycle_or_render', 'ownerCallSequence': 1},
        'ownerCalls': [{'method': 'loadCapability', 'sequence': 1, 'instanceId': 1, 'returned': True,
                        'stack': 'Original AccountDeactivationPresenter.loadCapability\nIndex.aboutToAppear'}],
        'calls': [], 'serviceCalls': [], 'state': state,
        # Deliberately contradictory diagnostic getter: NEVER a UI verdict.
        'submitEnabledRead': {'value': True}}
    if number in (7, 10): owner['serviceCalls'] = [{'instanceId': 2, 'method': 'deactivateAccount', 'args': ['secret', True], 'returned': True}]
    bounds = {'left': 0, 'top': 0, 'right': 200, 'bottom': 200}
    before = {'label': 'before_event', 'sequence': 10, 'sessionId': session, 'pageOwner': owner, 'nativeTree': tree,
        'windowIdentity': {'hostVerified': True, 'focused': True, 'bundleName': 'unit', 'bounds': bounds,
                          'stageMainWindowId': 1, 'lastWindowId': 1},
        'windowAndIme': {'visibilitySource': 'native_window_keyboard_avoid_area', 'keyboardVisible': False,
            'nativeWindow': {'id': 1}, 'nativeWindowShowing': True, 'activeWindow': {'focused': True, 'bundleName': 'unit'},
            'keyboardAvoidArea': {name: {'width': 0, 'height': 0} for name in ('topRect', 'bottomRect', 'leftRect', 'rightRect')}},
        'provider': {'deactivationCount': 0 if number not in (7, 10) else 2}, 'controls': []}
    for name, binding in controls.items():
        value = {'name': name, 'id': binding['id'], 'treePath': binding['treePath'], 'present': True,
            'visible': True, 'enabled': True, 'bounds': {'left': 10, 'top': 10, 'right': 90, 'bottom': 40}}
        if name == 'password': value['text'] = state['password']; tree['$children'][3]['$attrs']['text'] = state['password']
        if name == 'erase': value['checked'] = state['eraseData']; tree['$children'][4]['$attrs']['isOn'] = str(state['eraseData']).lower()
        if name == 'submit' and not state['password']:
            value['enabled'] = False; tree['$children'][5]['$attrs']['enabled'] = False
        before['controls'].append(value)
    prefix = copy.deepcopy(before); prefix.update(label='common_start', sequence=1)
    after = copy.deepcopy(before); after.update(label='after_event', sequence=30)
    event = {'sequence': 20, 'phase': 'event', 'executed': True, 'sessionId': session, 'callStart': 0, 'callEnd': 0}
    def physical(kind, target):
        event.update(kind=kind, target=target, nativeControl=copy.deepcopy(guard.transport._control(before, target)))
    def callback(method, args):
        after['pageOwner']['calls'].append({'method': method, 'args': args, 'instanceId': 1, 'returned': True})
        event['callEnd'] = 1
    if number == 2:
        physical('click', 'entry')
    elif number == 3:
        physical('input', 'password'); event.update(value='secret\n', driverArguments=['secret\n'])
        callback('setPassword', ['secret\n'])
        after['pageOwner']['state']['password'] = 'secret'
        guard.transport._control(after, 'password')['text'] = 'secret'
        after['nativeTree']['$children'][3]['$attrs']['text'] = 'secret'
        guard.transport._control(after, 'submit')['enabled'] = True
        after['nativeTree']['$children'][5]['$attrs']['enabled'] = True
    elif number == 4:
        physical('click', 'erase'); callback('setEraseData', [True])
        after['pageOwner']['state']['eraseData'] = True
        guard.transport._control(after, 'erase')['checked'] = True
        after['nativeTree']['$children'][4]['$attrs']['isOn'] = 'true'
    elif number == 7:
        event.update(kind='https_response', target='own_pending_deactivation', status=200, requestId=2)
        after['pageOwner']['state']['action'] = 'success'
        after['pageOwner']['serviceCalls'][0]['settlement'] = {'status': 'fulfilled'}
    else:
        physical('click', 'close'); callback('closeDialogs', [])
        after['pageOwner']['state']['action'] = 'uninitialized'
    actions = [event]
    if number != 2: actions.insert(0, {'kind': 'click', 'target': 'entry', 'phase': 'setup', 'executed': True, 'sequence': 2, 'sessionId': session})
    native = {'pageOwnerProtocol': guard.PROTOCOL, 'caseId': spec['caseId'], 'traceDigest': spec['traceDigest'],
        'nonce': nonce, 'sessionId': session, 'bundleName': 'unit', 'outcome': 'transition_observed',
        'eventExecuted': True, 'entryExecuted': True, 'failure': None, 'frames': [prefix, before, after], 'actions': actions}
    requests = [{'kind': 'login', 'secure': True, 'responseStatus': 200}]
    if number == 7: requests.append({'kind': 'deactivation', 'number': 2, 'secure': True, 'responseStatus': 200})
    provider = {'nonce': nonce, 'loginCount': 1, 'deactivationCount': after['provider']['deactivationCount'], 'requests': requests}
    for frame in native['frames']:
        signature = guard.layout_signature(frame['nativeTree'], profile)
        if signature not in profile['closedLayouts']: profile['closedLayouts'].append(signature)
    return {'spec': spec, 'native': native, 'provider': provider, 'inputs': {'rootSha256': 'a' * 64},
            'build': {'production': profile['compiledProduction']}}, profile


NEGATIVE_CASES = ('independent_host_receiver', 'getter_ui_disagreement', 'borrowed_case005', 'newline_substitution',
                  'default_setter_repair', 'forced_render_or_direct_presenter', 'invented_success',
                  'close_wrong_receiver', 'unknown_alternate_control')


class SamePageOwnerTests(unittest.TestCase):
    def test_five_own_synthetic_native_episodes_keep_original_obligations_and_ui_scope(self):
        episodes = set()
        for number in (2, 3, 4, 7, 10):
            data, profile = fixture(number)
            row = guard.inspect_same_page_owner(data, profile)
            self.assertEqual('pass', row['status'])
            self.assertFalse(row['presenterGetterUsedAsUiVerdict'])
            self.assertEqual({key: data['spec'][key] for key in ('given', 'event', 'expected', 'invariants')}, row['canonicalObligations'])
            episodes.add(row['episodeId'])
            if number in (2, 3):
                self.assertEqual([{'scope': 'native_button_enabled', 'value': number == 3}], row['fieldEvidence']['submitEnabled'])
        self.assertEqual(5, len(episodes))

    def test_exact_nine_negative_boundaries(self):
        for name in NEGATIVE_CASES:
            number = {'default_setter_repair': 2, 'invented_success': 7, 'close_wrong_receiver': 10}.get(name, 3)
            data, profile = fixture(number)
            after = data['native']['frames'][-1]
            event = next(action for action in data['native']['actions'] if action['phase'] == 'event')
            if name == 'independent_host_receiver': after['pageOwner']['observerMode'] = 'host_new_presenter'
            elif name == 'getter_ui_disagreement':
                # Fully proven native button is disabled: genuine semantic FAIL,
                # even though its same page owner has canSubmit/getter=true.
                guard.transport._control(after, 'submit')['enabled'] = False
                after['nativeTree']['$children'][5]['$attrs']['enabled'] = False
            elif name == 'borrowed_case005': after['sessionId'] = 'old005:ad_state_005_first_submit_confirms'
            elif name == 'newline_substitution': event['driverArguments'] = ['secret']
            elif name == 'default_setter_repair':
                after['pageOwner']['calls'].append({'method': 'setPassword', 'instanceId': 1, 'args': [''], 'returned': True})
            elif name == 'forced_render_or_direct_presenter': after['pageOwner']['forcedRender'] = True
            elif name == 'invented_success': data['provider']['requests'] = data['provider']['requests'][:1]
            elif name == 'close_wrong_receiver': after['pageOwner']['calls'][0]['instanceId'] = 999
            else:
                after['nativeTree']['$children'].append({'$type': 'Button', '$attrs': {'id': 'new-action', 'enabled': True}, '$children': []})
            with self.subTest(name=name):
                if name == 'getter_ui_disagreement':
                    row = guard.inspect_same_page_owner(data, profile)
                    self.assertEqual('fail', row['status'])
                    self.assertFalse(row['observed']['submitEnabled'])
                else:
                    with self.assertRaises(ValueError): guard.inspect_same_page_owner(data, profile)

    def test_domain_only_or_unapproved_raw_cannot_enter_default_admission(self):
        self.assertEqual({}, guard.APPROVED_PROFILES)
        with self.assertRaisesRegex(ValueError, 'No reviewed native v5'):
            guard.admit({'old_host_report': True}, {}, profile_key='invented-approved')

    def test_original_production_disagreement_is_fail_not_normalized_to_oracle(self):
        data, profile = fixture(4)
        after = data['native']['frames'][-1]
        after['pageOwner']['state']['eraseData'] = False
        guard.transport._control(after, 'erase')['checked'] = False
        after['nativeTree']['$children'][4]['$attrs']['isOn'] = 'false'
        self.assertEqual('fail', guard.inspect_same_page_owner(data, profile)['status'])

    def test_source_mutation_missing_fulltree_and_unknown_ime_remain_ns(self):
        for kind in ('source', 'tree', 'ime'):
            data, profile = fixture(3)
            if kind == 'source': data['inputs']['rootSha256'] = '0' * 64
            elif kind == 'tree': data['native']['frames'][-1]['nativeTree'] = {}
            else: data['native']['frames'][-1]['windowAndIme']['keyboardVisible'] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError): guard.inspect_same_page_owner(data, profile)


if __name__ == '__main__': unittest.main()
