"""OFFLINE synthetic/real-source tests. No SDK compile, HDC, model or native credit."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from . import task15_native_successor_v8 as producer
from . import task15_native_successor_guard_v8 as guard
from . import task15_native_successor_runner_v8 as runner
from .test_task15_page_owner_v5 import fixture as owner_fixture

ROOT = runner.ROOT
FINAL = ROOT / 'final_dev_nodes/15_account_deactivation_final_0_6_3'
BASE = ROOT / '15_account_deactivation_base_0_6_1'


def seal(frame):
    frame['windowIdentity']['checkedAt'] = frame['sequence'] * 10
    frame['bracketEnd'] = {key: copy.deepcopy(frame[key]) for key in
        ('nativeTree', 'windowIdentity', 'windowAndIme', 'pageOwner')}
    frame['bracketEnd']['windowIdentity']['checkedAt'] += 1


def capability_fixture():
    """Synthetic complete acquisition/schema example, NEVER a reviewed profile."""
    data, profile = owner_fixture(2)
    spec = runner.core.load(producer.CONTRACT)['cases'][0]
    data['spec'] = spec
    native = data['native']
    native.update(pageOwnerProtocol=guard.PROTOCOL, caseId=spec['caseId'], traceDigest=spec['traceDigest'],
        sessionId=native['nonce'] + ':' + spec['caseId'])
    template = copy.deepcopy(native['frames'][1])
    template['pageOwner']['protocol'] = guard.PROTOCOL
    template['pageOwner']['episodeId'] = native['sessionId']
    template['pageOwner']['state']['serverCanDeactivateAccount'] = True
    for name, kind in (('session', 'Text'), ('signOut', 'Button')):
        index = len(template['nativeTree']['$children'])
        attrs = {'id': 'native_' + name, 'visibility': 'Visibility.Visible', 'enabled': True}
        if name == 'session': attrs['text'] = '@unit'
        template['nativeTree']['$children'].append({'$type': kind, '$rect': '[10,10],[90,40]', '$attrs': attrs, '$children': []})
        profile['controls'][name] = {'id': attrs['id'], 'type': kind, 'treePath': 'root/' + str(index)}
        template['controls'].append({'name': name, 'id': attrs['id'], 'treePath': 'root/' + str(index),
            'present': True, 'visible': True, 'enabled': True,
            'bounds': {'left': 10, 'top': 10, 'right': 90, 'bottom': 40}, **({'text': '@unit'} if name == 'session' else {})})
    template['nativeTree']['$children'][2]['$attrs']['fontColor'] = '#ff0000'
    profile['reviewedEntryColors'] = {'#ff0000': 'destructive'}
    profile['closedLayouts'] = []
    native['frames'], native['actions'] = [], []
    phases, calls, fixtures, history = [], [], [], []
    def call(class_name, method, receiver, *, args=None, result=None):
        value = {'id': len(calls) + 1, 'className': class_name, 'method': method,
            'receiverId': receiver, 'parentCallId': None, 'startedAt': len(calls) + 1,
            'stack': 'UNIT synthetic original callback', 'calledOriginal': True, 'returned': True,
            'args': args or [], 'settlement': {'status': 'fulfilled', 'value': result}}
        calls.append(value)
    def ledger():
        return {'protocol': 'task15.changed-body-ledger.v8', 'calls': copy.deepcopy(calls),
            'allWrappersPassOriginal': True, 'controlledBoundary': 'external HTTPS server only', 'systemHttpReplaced': False}
    for index, label in enumerate(('before_event', 'after_event', 'capability:unsupported_after', 'capability:restored_positive')):
        mode = 'oidc' if index == 2 else 'matrix'
        if index in (2, 3):
            start = len(calls)
            call('NativeAccountSessionStore', 'save', 99, args=[{'authMode': mode}])
            call('NativeAccountSessionStore', 'read', 99, result={'authMode': mode})
            fixtures.append({'kind': 'system_persisted_unsupported_session' if index == 2 else 'system_persisted_matrix_restore',
                'bridgeCallStart': start, 'bridgeCallEnd': len(calls)})
        previous = copy.deepcopy(history)
        if index:
            history += [{'method': method} for method in ('coldRestartRequested', 'abilityDestroy', 'windowStageDestroy',
                'abilityCreate', 'windowStageCreate', 'abilityForeground', 'coldRestartReturned')]
        frame = copy.deepcopy(template)
        frame.update(label=label, sequence=10 + index * 20, sessionId=native['sessionId'])
        p = frame['pageOwner']
        p.update(bridgeReceiverId=10 + index, sessionIdentity={'userId': '@unit', 'deviceId': 'UNIT', 'authMode': mode})
        p['state']['serverCanDeactivateAccount'] = index != 2
        call('AccountClient', 'restore', 10 + index)
        call('AccountClient', 'canDeactivateAccount', 10 + index, result=index != 2)
        frame['bridgeLedger'] = ledger()
        if index == 2:
            frame['nativeTree']['$children'][2]['$attrs']['visibility'] = 'Visibility.Hidden'
            control = guard.transport._control(frame, 'entry')
            control.clear(); control.update(name='entry', present=False, visible=False)
        seal(frame)
        signature = guard.owner.layout_signature(frame['nativeTree'], profile)
        if signature not in profile['closedLayouts']: profile['closedLayouts'].append(signature)
        if index == 2: profile['absentControlLayouts'] = {'entry': [signature]}
        native['frames'].append(frame)
        if index:
            action = {'sequence': frame['sequence'] - 5, 'kind': 'cold_settings_load', 'target': 'original_settings',
                'executed': True, 'sessionId': native['sessionId'], 'phase': 'event' if index == 1 else 'invariant'}
            native['actions'].append(action)
            phases.append({'label': label, 'frameSequence': frame['sequence'], 'eventSequence': action['sequence'],
                'previousLifecycle': {'events': previous}, 'lifecycle': {'events': copy.deepcopy(history)}, 'bridgeLedger': ledger()})
    native['capabilityPair'] = {'protocol': 'task15.capability-cold-original-owner.v8', 'complete': True,
        'restored': True, 'parentEpisodeId': native['sessionId'], 'phases': phases, 'fixtures': fixtures, 'bridgeLedger': ledger()}
    return data, profile


def sdk_fixture():
    script = "require(process.argv[1]).fixture().then(x=>process.stdout.write(JSON.stringify(x)));"
    result = subprocess.run(['node', '-e', script, str(producer.DIRECTORY / 'sdk_unit_fixture.cjs')],
        capture_output=True, text=True, timeout=20, check=True)
    return json.loads(result.stdout)


def dialog_fixture(number):
    """Synthetic native UI/HTTP shapes for the OTHER four canonical episodes."""
    data, profile = owner_fixture(2)
    spec = runner.core.load(producer.CONTRACT)['cases'][number-1]
    data['spec'] = spec
    native = data['native']
    native.update(pageOwnerProtocol=guard.PROTOCOL, caseId=spec['caseId'], traceDigest=spec['traceDigest'],
        sessionId=native['nonce'] + ':' + spec['caseId'])
    prefix, before, after = native['frames']
    for frame in native['frames']:
        frame.update(sessionId=native['sessionId'])
        p = frame['pageOwner']; p.update(protocol=guard.PROTOCOL, episodeId=native['sessionId'])
        for name, kind in (('confirmation', 'Text'), ('confirm', 'Button'), ('loading', 'Text'), ('retry', 'Button')):
            index = len(frame['nativeTree']['$children'])
            binding = {'id': 'native_' + name, 'type': kind, 'treePath': 'root/' + str(index)}
            profile['controls'][name] = binding
            frame['nativeTree']['$children'].append({'$type': kind, '$rect': '[10,10],[90,40]',
                '$attrs': {'id': binding['id'], 'visibility': 'Visibility.Visible', 'enabled': True}, '$children': []})
            frame['controls'].append({'name': name, 'id': binding['id'], 'treePath': binding['treePath'],
                'present': True, 'visible': True, 'enabled': True,
                'bounds': {'left': 10, 'top': 10, 'right': 90, 'bottom': 40}})
    prior, current = before['pageOwner'], after['pageOwner']
    prior['state'].update(password='secret', eraseData=True, action={5:'uninitialized',6:'confirming',8:'loading',9:'failure'}[number],
        requestCount=1 if number in (8,9) else 0, accountSessionActive=True)
    current['state'] = {**prior['state'], 'action': {5:'confirming',6:'loading',8:'failure',9:'loading'}[number],
        'requestCount': {5:0,6:1,8:1,9:2}[number]}
    service = {'instanceId': prior['serviceId'], 'method': 'deactivateAccount', 'args': ['secret', True], 'returned': True}
    if number in (8,9):
        prior['serviceCalls'] = [copy.deepcopy(service)]
        current['serviceCalls'] = [copy.deepcopy(service)]
    if number == 8: current['serviceCalls'][0]['settlement'] = {'status':'rejected'}
    if number in (6,9): current['serviceCalls'].append(copy.deepcopy(service))
    for frame in (before, after):
        guard.transport._control(frame, 'password')['text'] = 'secret'
        frame['nativeTree']['$children'][3]['$attrs']['text'] = 'secret'
        guard.transport._control(frame, 'erase')['checked'] = True
        frame['nativeTree']['$children'][4]['$attrs']['isOn'] = 'true'
        guard.transport._control(frame, 'submit')['enabled'] = True
        frame['nativeTree']['$children'][5]['$attrs']['enabled'] = True
        frame['provider'] = {'loginCount':1,'deactivationCount': 0 if number==5 else 2}
    if number == 5: before['provider']['deactivationCount'] = 0
    if number == 6: before['provider']['deactivationCount'] = 0
    if number == 9: after['provider']['deactivationCount'] = 3
    target = {5:'submit',6:'confirm',8:'own_pending_deactivation',9:'retry'}[number]
    event = {'sequence':20,'phase':'event','executed':True,'sessionId':native['sessionId'],
        'kind':'https_response' if number==8 else 'click','target':target,'callStart':0,'callEnd':0}
    if number == 8: event.update(status=503,requestId=2)
    else:
        event['nativeControl'] = copy.deepcopy(guard.transport._control(before,target))
        event['callEnd'] = 1
        current['calls'] = [{'method':'deactivateAccount','args':[number==9], 'returned':True,'instanceId':current['instanceId']}]
    native['actions'] = [{'sequence':2,'kind':'click','target':'entry','phase':'setup',
        'executed':True,'sessionId':native['sessionId']}, event]
    data['provider'] = {'nonce':native['nonce'],'loginCount':1,'deactivationCount':after['provider']['deactivationCount'],
        'requests':[{'kind':'login','secure':True,'responseStatus':200}]}
    if number in (6,8,9): data['provider']['requests'].append({'kind':'deactivation','number':2,'secure':True,
        **({'responseStatus':503} if number in (8,9) else {}),'body':{'erase':True,'passwordSha256':guard.digest('secret')}})
    if number == 9:
        guard.transport._control(after,'confirmation').update(present=False,visible=False)
        after['nativeTree']['$children'][7]['$attrs']['visibility'] = 'Visibility.Hidden'
        profile['absentControlLayouts'] = {'confirmation':[guard.owner.layout_signature(after['nativeTree'],profile)]}
    if number == 6:
        modal = copy.deepcopy(after); modal.update(label='after_modal_input',sequence=50)
        native['frames'].append(modal)
        native['actions'].append({'kind':'modal_physical_input','sequence':40,'target':'password_coordinates',
            'phase':'invariant','executed':True,'sessionId':native['sessionId'],'attemptedText':'tampered','geometry':[[10,10],[90,40]]})
        native['modalProbe']={'beforeSequence':30,'afterSequence':50}
    profile['closedLayouts']=[]
    for frame in native['frames']:
        seal(frame)
        sig = guard.owner.layout_signature(frame['nativeTree'],profile)
        if sig not in profile['closedLayouts']: profile['closedLayouts'].append(sig)
    return data, profile


class GuardTests(unittest.TestCase):
    def test_capability_complete_original_owner_negative_restored_ui(self):
        data, profile = capability_fixture()
        row = guard.inspect_capability(data, profile)
        self.assertEqual('pass', row['status'])
        self.assertEqual(data['spec']['expected'], row['observed'])
        self.assertEqual(data['spec']['invariants'], [c['description'] for c in row['invariantChecks']])

    def test_capability_unknown_ui_missing_lifecycle_and_fixture_mutations_rejected(self):
        mutations = ('extra', 'renamed', 'tree_missing', 'selector_absence_only', 'cold_missing', 'restore_missing',
            'restored_positive_missing', 'wrong_receiver', 'wrong_episode', 'getter_receiver', 'native_style_missing',
            'session_query_mismatch', 'source', 'duplicate_event', 'mixed_window')
        for mutation in mutations:
            data, profile = capability_fixture()
            negative, restored = data['native']['frames'][2:]
            pair = data['native']['capabilityPair']
            if mutation == 'extra': negative['nativeTree']['$children'].append({'$type': 'Button', '$attrs': {'id': 'alternate'}, '$children': []})
            elif mutation == 'renamed': negative['nativeTree']['$children'][2]['$attrs']['id'] = 'different-entry'
            elif mutation == 'tree_missing': negative['nativeTree'] = {}
            elif mutation == 'selector_absence_only': profile['absentControlLayouts'] = {}
            elif mutation == 'cold_missing': pair['phases'][0]['lifecycle']['events'][1]['method'] = 'not_destroyed'
            elif mutation == 'restore_missing': pair['fixtures'].pop()
            elif mutation == 'restored_positive_missing': guard.transport._control(restored, 'entry')['present'] = False
            elif mutation == 'wrong_receiver': pair['phases'][0]['bridgeLedger']['calls'][-1]['receiverId'] = 1000
            elif mutation == 'wrong_episode': negative['sessionId'] = 'borrowed001'
            elif mutation == 'getter_receiver': negative['pageOwner']['observerMode'] = 'getter_created_owner'
            elif mutation == 'native_style_missing': del data['native']['frames'][1]['nativeTree']['$children'][2]['$attrs']['fontColor']
            elif mutation == 'session_query_mismatch': guard.transport._control(negative, 'session')['text'] = '@other'
            elif mutation == 'source': data['inputs']['rootSha256'] = '0' * 64
            elif mutation == 'duplicate_event': data['native']['actions'].append(copy.deepcopy(data['native']['actions'][0]))
            else: negative['windowIdentity']['stageMainWindowId'] = 123
            if mutation not in ('mixed_window',):
                for frame in data['native']['frames']: seal(frame)
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError, IndexError)):
                guard.inspect_capability(data, profile)

    def test_original_service_sdk_projection_and_bypass_mutations(self):
        raw = sdk_fixture()
        self.assertTrue(raw['UNIT_ONLY_NOT_NATIVE_RUNTIME'])
        data = {'spec': {'key': 'success_completes'}, 'provider': raw['provider'], 'native': {
            'nonce': raw['provider']['nonce'], 'frames': [{'label': 'after_event', 'sequence': 30,
                'bridgeLedger': raw['ledger'], 'provider': raw['provider'],
                'pageOwner': {'available': True, 'bridgeReceiverId': raw['receiverId']}}]}}
        self.assertFalse(guard.changed_body(data)['mockedApplicationBridges'])
        for mutation in ('bridge_bypass', 'server_password', 'challenge', 'token', 'server_status', 'wrong_receiver', 'fixture_clear', 'sdk_replaced'):
            value = copy.deepcopy(data)
            calls = value['native']['frames'][0]['bridgeLedger']['calls']
            request = value['provider']['requests'][-1]
            if mutation == 'bridge_bypass': calls[-1]['calledOriginal'] = False
            elif mutation == 'server_password': request['body']['passwordSha256'] = '0' * 64
            elif mutation == 'challenge': request['body']['session'] = 'another-challenge'
            elif mutation == 'token': request['authorizationSha256'] = '0' * 64
            elif mutation == 'server_status': request['responseStatus'] = 503
            elif mutation == 'wrong_receiver': value['native']['frames'][0]['pageOwner']['bridgeReceiverId'] = 999
            elif mutation == 'fixture_clear':
                next(c for c in calls if c['className'] == 'NativeAccountSessionStore' and c['method'] == 'clear')['receiverId'] = 999
            else: value['native']['frames'][0]['bridgeLedger']['systemHttpReplaced'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): guard.changed_body(value)

    def test_five_formerly_host_cases_still_use_original_native_ui_not_getter(self):
        raw = sdk_fixture()
        login_end = next(c['id'] for c in raw['ledger']['calls'] if c['className'] == 'AccountClient' and c['method'] == 'deactivateAccount') - 1
        for number in (2, 3, 4, 7, 10):
            data, profile = owner_fixture(number)
            data['native']['pageOwnerProtocol'] = guard.PROTOCOL
            data['provider'] = copy.deepcopy(raw['provider'])
            data['provider']['nonce'] = data['native']['nonce']
            if number not in (7, 10):
                data['provider'].update(deactivationCount=0, requests=data['provider']['requests'][:1])
            for frame in data['native']['frames']:
                frame['pageOwner'].update(protocol=guard.PROTOCOL, bridgeReceiverId=raw['receiverId'])
                frame['provider'] = {'loginCount': 1, 'deactivationCount': data['provider']['deactivationCount']}
                frame['bridgeLedger'] = copy.deepcopy(raw['ledger'])
                if number not in (7, 10): frame['bridgeLedger']['calls'] = frame['bridgeLedger']['calls'][:login_end]
                seal(frame)
            row = guard.inspect_native(data, profile)
            self.assertEqual('pass', row['status'])
            self.assertFalse(row['presenterGetterUsedAsUiVerdict'])
            if number == 3:
                after = data['native']['frames'][-1]
                guard.transport._control(after, 'submit')['enabled'] = False
                after['nativeTree']['$children'][5]['$attrs']['enabled'] = False
                seal(after)
                self.assertEqual('fail', guard.inspect_native(data, profile)['status'])

    def test_profiles_are_not_approved_by_unit_tests_or_callers(self):
        self.assertEqual({}, guard.REVIEWED_PROFILES)
        with self.assertRaisesRegex(ValueError, 'No reviewed V8'):
            guard.admit({'UNIT_ONLY_NOT_NATIVE_RUNTIME': True}, {}, profile_key='unit')

    def test_remaining_four_obligations_are_own_native_not_old_presenter_projection(self):
        for number in (5,6,8,9):
            data, profile = dialog_fixture(number)
            with self.subTest(number=number):
                row = guard.inspect_obligations(data,profile)
                self.assertEqual('pass',row['status'])
                self.assertEqual(data['spec']['expected'], row['observed'])
                self.assertEqual(data['spec']['invariants'], [c['description'] for c in row['invariantChecks']])
                after = data['native']['frames'][-1]
                after['nativeTree']['$children'].append({'$type':'Button','$attrs':{'id':'unbound'},'$children':[]})
                seal(after)
                with self.assertRaises(ValueError): guard.inspect_obligations(data,profile)

    def test_window_normalization_only_allows_real_timestamp_advance(self):
        first = {'checkedAt': 1, 'id': 7, 'focused': True}
        self.assertTrue(guard.stable_window(first, {**first, 'checkedAt': 2}))
        self.assertFalse(guard.stable_window(first, {**first, 'checkedAt': 2, 'id': 8}))
        with self.assertRaises(ValueError): guard.stable_window(first, {**first, 'checkedAt': 0})


class PackagingTests(unittest.TestCase):
    def temporary(self):
        value = tempfile.TemporaryDirectory(prefix='task15-v8-offline-unit-', dir=ROOT / 'experiment_results')
        self.addCleanup(value.cleanup)
        return Path(value.name)

    def test_all_ten_real_source_plans_and_actual_installer_no_sdk(self):
        root = self.temporary()
        before = runner.core.directory_digest(FINAL)
        for case_id in sorted(producer.prior.CASES):
            plan = producer.prepare_feature(source=FINAL, case_id=case_id, output=root / case_id, deadline=time.monotonic()+300)
            self.assertEqual(producer.PROTOCOL, plan['fullNativeProtocol'])
            self.assertEqual(case_id, plan['caseId'])
            for item in plan['derivedFiles']: runner.artifacts.bound(item)
            directory = root / case_id / 'native-environment-fixtures'
            self.assertNotIn('const reopened =', (directory / 'Task15NativeE2E.js').read_text())
            subprocess.run(['node', '--check', str(root / case_id / 'fresh-host.cjs')], check=True, timeout=10, capture_output=True)
        selected = sorted(producer.prior.CASES)[2]
        script = """const fs=require('node:fs'),path=require('node:path');
const root=process.argv[1],directory=process.argv[2],work=process.argv[3],plan=JSON.parse(fs.readFileSync(path.join(directory,'plan.json')));
fs.cpSync(plan.source,work,{recursive:true,filter:f=>!['.git','build','.hvigor','oh_modules','node_modules'].includes(path.basename(f))});
fs.mkdirSync(path.join(work,'entry/src/test'),{recursive:true});const evidence=path.join(work,'bundle-evidence');fs.mkdirSync(evidence);
require(path.join(root,'scripts/runtime_semantics/arkts_native_bundle.cjs')).generate(work,evidence,'15_account_deactivation','agent',plan.source,true,{device:true,caseId:plan.caseId});
const report=require(path.join(directory,'native-environment-fixtures/Task15NativeUi.install.cjs')).install(work);
const hash=x=>require('node:crypto').createHash('sha256').update(fs.readFileSync(x)).digest('hex');
for(const item of report.fixtures)if(hash(path.join(work,item.installedPath))!==item.sha256)throw Error('Installed bytes mismatch');
process.stdout.write(JSON.stringify(report));"""
        result = subprocess.run(['node', '-e', script, str(ROOT), str(root / selected), str(root / 'work')],
            capture_output=True, text=True, timeout=30, check=True)
        report = json.loads(result.stdout)
        self.assertTrue(report['productionUnchanged'])
        self.assertIn('nativeServiceModuleUrl', report['binding'])
        self.assertIn('signOut', report['binding']['controlSelectors'])
        self.assertTrue({'Task15BridgeLedgerV8.js', 'Task15CapabilityPairV8.js'} <=
            {Path(item['installedPath']).name for item in report['fixtures']})
        self.assertEqual(before, runner.core.directory_digest(FINAL))

    def test_random_copies_and_unknown_source_route_selection_not_role_or_filename(self):
        root = self.temporary()
        for source, expected in ((BASE, 'reviewed_native_prefix'), (FINAL, 'full_native')):
            copy_root = root / ('random-' + str(time.time_ns()))
            shutil.copytree(source, copy_root, ignore=shutil.ignore_patterns('build', '.hvigor', 'oh_modules', 'node_modules', '.git'))
            self.assertEqual(expected, producer.choose_probe(copy_root))
            if source == BASE:
                page = copy_root / 'entry/src/main/ets/pages/Index.ets'
                page.write_text(page.read_text() + '\n// UNIT unknown alternate source revision\n')
                self.assertEqual('full_native', producer.choose_probe(copy_root))

    def test_base_prefix_offline_program_full_closed_ui_and_same_budget(self):
        root = self.temporary() / 'prefix'
        plan = producer.prepare_prefix(source=BASE, output=root, deadline=time.monotonic()+300, serial='127.0.0.1:5555')
        driver = runner.artifacts.bound(plan['driver']).decode()
        self.assertIn(str(root / 'canonical-contract.json'), driver)
        self.assertIn('notifications', driver.lower())
        subprocess.run(['node', '--check', plan['driver']['path']], check=True, capture_output=True, timeout=10)
        self.assertFalse((root / 'base-device').exists())
        self.assertLess(plan['deadlineEpochMs'], int((time.time()+301)*1000))

    def test_renamed_native_service_module_discovered_in_arbitrary_source(self):
        root = self.temporary()
        source = root / 'random-candidate'
        shutil.copytree(FINAL, source, ignore=shutil.ignore_patterns('build', '.hvigor', 'oh_modules', 'node_modules', '.git'))
        old_path = source / 'entry/src/main/ets/services/NativeAccountClient.ets'
        old_path.rename(old_path.with_name('DifferentSdkBoundary.ets'))
        for path in source.rglob('*.ets'):
            code = path.read_text()
            if 'NativeAccountClient' in code: path.write_text(code.replace('NativeAccountClient', 'DifferentSdkBoundary'))
        plan = producer.prepare_feature(source=source, case_id=sorted(producer.prior.CASES)[2],
            output=root / 'episode', deadline=time.monotonic()+300)
        self.assertTrue(plan['nativeSdkApi']['store']['path'].endswith('/DifferentSdkBoundary.ets'))
        self.assertEqual('full_native', producer.choose_probe(source))
        self.assertNotIn("/services/NativeAccountClient'", (root / 'episode/native-environment-fixtures/Task15NativeE2E.js').read_text())

    def test_all_generated_js_syntax_and_no_host_presenter(self):
        for code in (producer.engine_source(), producer.observer_source(), producer.lifecycle_source()):
            subprocess.run(['node', '--input-type=module', '--check'], input=code, text=True, capture_output=True, timeout=10, check=True)
        code = producer.engine_source()
        self.assertNotIn('tasks12_15.cjs', code)
        self.assertNotIn('new AccountDeactivationPresenter', code)
        self.assertIn('runTask15CapabilityPairV8', code)
        self.assertIn('bridgeLedger = observeTask15BridgeLedgerV8', code)
        for case in runner.core.load(producer.CONTRACT)['cases']: self.assertIn(case['key'], code)

    def test_default_score_public_ns_no_overwrite_and_compile_separation(self):
        path = self.temporary() / 'not-executed.json'
        report = runner.score(platform='arkts', source=FINAL, output=path, compile_passed=True, compile_command='retained app compile')
        self.assertEqual((0, 0, 10), tuple(report['semantic'][key] for key in ('passed', 'failed', 'notScored')))
        self.assertTrue(report['compile']['passed'])
        self.assertIsNone(report['runtimeCompile']['passed'])
        self.assertTrue(report['diagnostics']['publicReportValidated'])
        before = path.read_bytes()
        with self.assertRaises(ValueError): runner.score(platform='arkts', source=FINAL, output=path)
        self.assertEqual(before, path.read_bytes())

    def test_no_hardware_or_budget_reset_implicit_and_bad_budgets_rejected(self):
        root = self.temporary()
        for kwargs in ({}, {'execute': True, 'original_deadline_epoch': time.time()-1}):
            with self.assertRaises(ValueError): runner.evaluate(source=FINAL, output=root / 'never', **kwargs)
        self.assertFalse((root / 'never').exists())
        for timeout in (0, -1, float('nan'), float('inf'), 3601):
            with self.assertRaises(ValueError): runner.score(platform='arkts', source=FINAL, output=root / 'never.json', timeout=timeout)

    def test_owned_prefix_cleanup_retains_inner_log_hashes_no_remote_claim(self):
        root = self.temporary()
        tree = root / 'prefix/base-application/build'
        tree.mkdir(parents=True)
        (tree / 'only-inner-compiler.log').write_text('UNIT unique inner failure log')
        (tree / 'unit.hap').write_bytes(b'UNIT not a real HAP')
        value = json.loads(runner.artifacts.bound(runner.cleanup(root, time.monotonic()+10)))
        self.assertFalse(tree.exists())
        self.assertFalse(value['remoteCleanupInferred'])
        self.assertTrue(value['files'][0]['removed'])
        retained = value['intermediateTrees'][0]['files'][0]['retainedText']
        self.assertEqual(b'UNIT unique inner failure log', runner.artifacts.bound(retained))


if __name__ == '__main__': unittest.main()
