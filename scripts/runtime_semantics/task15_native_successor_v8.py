"""Source-param Task15 native successor: capability pair + full ten + base prefix.

Preparation/import never executes a device/model. Frozen V7 producers, V1
guards/runners, canonical contracts and production code remain byte-identical.
"""
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import subprocess
import time
import types

from . import task15_full_native_v7 as prior
from . import task15_fresh_admission_v2 as transport
from . import task14_15_arkts_layout_closure as prefix_closure
from . import task14_15_arkts_entry_evidence as prefix_admission
from . import task15_prefix_v4 as prefix_previous
from . import task14_15_formal_core as core

ROOT, TASK, CONTRACT = core.ROOT, prior.TASK, prior.CONTRACT
PROTOCOL = 'task15.full-native-capability-and-bridge.v8'
DIRECTORY = Path(__file__).with_name('task15_native_v8')
require = transport.require


def clone(function, **changes):
    result = types.FunctionType(function.__code__, {**function.__globals__, **changes},
        name=function.__name__, argdefs=function.__defaults__, closure=function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def observer_source():
    code = prior.observer_source().replace(prior.PROTOCOL, PROTOCOL)
    code = "import { task15BridgeReceiverIdV8 } from './Task15BridgeLedgerV8';\n" + code
    code = prior.transport.replace(code, '        Object.assign(value, { state: fields(receiver), instanceId: 1, serviceId: services.indexOf(service) + 1,',
        '''        const originalSession=service?.session;
        Object.assign(value, { bridgeReceiverId: task15BridgeReceiverIdV8(service),
          sessionIdentity: originalSession ? {userId:originalSession.userId,deviceId:originalSession.deviceId,
            authMode:originalSession.authMode,phase:originalSession.phase} : null,
          state: fields(receiver), instanceId: 1, serviceId: services.indexOf(service) + 1,''')
    return code


def engine_source():
    code = prior.engine_source().replace(prior.PROTOCOL, PROTOCOL)
    code = "import { observeTask15BridgeLedgerV8 } from './Task15BridgeLedgerV8';\nimport { runTask15CapabilityPairV8 } from './Task15CapabilityPairV8';\n" + code
    code = prior.transport.replace(code, "let sequence = 0, observer, stage = 'common_start';",
        "let sequence = 0, observer, bridgeLedger, nativeNamespace, stage = 'common_start';")
    code = prior.transport.replace(code, "confirmation: ON.text(binding.confirmationText), loading: ON.id(binding.loadingId), retry: selector('retry') };",
        "confirmation: ON.text(binding.confirmationText), loading: ON.id(binding.loadingId), retry: selector('retry'), session: selector('session'), signOut: selector('signOut') };")
    code = prior.transport.replace(code, '    observer = ports.observePage({ ...namespace, AccountClient: services.AccountClient }, binding.ownerBinding, result.sessionId);',
        '''    nativeNamespace = await ports.importModule(binding.nativeServiceModuleUrl);
    bridgeLedger = observeTask15BridgeLedgerV8(services,nativeNamespace);
    observer = ports.observePage({ ...namespace, AccountClient: services.AccountClient }, binding.ownerBinding, result.sessionId);''')
    code = prior.transport.replace(code, '      pageOwner: observer?.read(), provider: await integration.control.status(), controls: [] };',
        '      pageOwner: observer?.read(), bridgeLedger: bridgeLedger?.read(), provider: await integration.control.status(), controls: [] };')
    code = prior.transport.replace(code, "      await capture('before_event');\n      await receipt('ability_start','original_settings',()=>launch.reload(),{},'event');",
        '''      await runTask15CapabilityPairV8({ports,namespace,services,nativeNamespace,binding,result,capture,receipt,
        ledger:bridgeLedger,observer:()=>observer,replaceObserver:value=>{observer=value;}});''')
    code = prior.transport.replace(code, "    observer?.dispose();", "    result.bridgeLedger = bridgeLedger?.read();\n    observer?.dispose(); bridgeLedger?.dispose();")
    return code


def lifecycle_source():
    result = subprocess.run([prior.previous.NODE, '-e',
        'process.stdout.write(require(process.argv[1]).source());', str(DIRECTORY / 'lifecycle.cjs')],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10)
    return result.stdout


def source_api(source, deadline):
    helper = ROOT / 'state_tests/runtime/arkts/native/CandidateApiBindings.cjs'
    script = """const a=require(process.argv[1]),source=process.argv[2];
const store=a.exportedClass(source,'NativeAccountSessionStore'),transport=a.exportedClass(source,'NativeAccountTransport');
if(store.path!==transport.path||!a.reaches(source,'entry/src/main/ets/pages/Index.ets',store.path))throw Error('Unknown native SDK graph');
process.stdout.write(JSON.stringify({store,transport}));"""
    result = subprocess.run([prior.previous.NODE, '-e', script, str(helper), str(source)], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=min(20, core.remaining_deadline(deadline, 'native SDK graph discovery')))
    return json.loads(result.stdout)


def choose_probe(source):
    # Exact source identity is eligibility only. A result still requires this
    # candidate's fresh full UI + physical Notifications positive control.
    return 'reviewed_native_prefix' if prefix_closure.reviewed_source(TASK, core.directory_digest(Path(source))) else 'full_native'


def prepare_feature(*, source, case_id, output, deadline, serial='127.0.0.1:5555'):
    function = clone(prior.prepare, engine_source=engine_source, observer_source=observer_source,
        PROTOCOL=PROTOCOL, __file__=__file__)
    plan = function(source=source, case_id=case_id, output=output, deadline=deadline, serial=serial)
    output = Path(output)
    (output / 'v7-preparation-plan.json').write_bytes((output / 'plan.json').read_bytes())
    directory = output / 'native-environment-fixtures'
    api = source_api(Path(source).resolve(), deadline)
    native_path = api['store']['path']
    require(native_path.startswith('entry/src/main/ets/'), 'Native SDK namespace is not app-owned')
    # Bundle prefix is discovered by the actual installer, not a role/path hint.
    result = subprocess.run([prior.previous.NODE, str(DIRECTORY / 'bindings.cjs'), str(Path(source).resolve())],
        cwd=ROOT, capture_output=True, text=True, check=True,
        timeout=min(20, core.remaining_deadline(deadline, 'capability positive controls discovery')))
    capability_bindings = json.loads(result.stdout)
    bindings_file = output / 'actual-source-bindings.json'
    bindings = core.load(bindings_file)
    bindings['controlSelectors'].update(capability_bindings['selectors'])
    bindings['controlBindings'].update({key: capability_bindings[key] for key in ('session', 'signOut')})
    bindings['capabilitySourceBindings'] = capability_bindings
    core.write(bindings_file, bindings)
    installer = directory / 'Task15NativeUi.install.cjs'
    code = installer.read_text()
    code = prior.transport.replace(code, '  const observedSources = new Set(',
        '  binding.nativeServiceModuleUrl=url(' + json.dumps(native_path) + ');\n' +
        '  Object.assign(binding.controlSelectors,' + json.dumps(capability_bindings['selectors']) + ');\n  const observedSources = new Set(')
    code = prior.transport.replace(code, '  const sources = before.filter(item => observedSources.has(item.path));',
        '  for(const file of ' + json.dumps([native_path] + [item['path'] for item in bindings['sourceFiles']]) + ') observedSources.add(file);\n  const sources = before.filter(item => observedSources.has(item.path));')
    for name in ('Task15BridgeLedgerV8.js', 'Task15CapabilityPairV8.js'):
        target = directory / name
        target.write_bytes((DIRECTORY / name).read_bytes())
        code = prior.transport.replace(code, 'const modules = [', 'const modules = [' + json.dumps(name) + ',')
        code = prior.transport.replace(code, '    const file = name === ',
            '    const file = name === ' + json.dumps(name) + ' ? ' + json.dumps(str(target)) + ' : name === ')
    installer.write_text(code)
    integration = directory / 'Task15NativeE2E.js'
    text = integration.read_text()
    begin = text.index('    async continueSequence(tools) {')
    end = text.index('    async cleanup() {', begin)
    integration.write_text(text[:begin] + '''    async continueSequence() {
      throw new Error('V8 accepts only its own physical single-case episode; legacy detached-client continuation disabled');
    },

''' + text[end:])
    launch = directory / 'Task15Launch.js'
    launch.write_text(lifecycle_source())
    types = directory / 'Task15LaunchNative.d.ts'
    types.write_text("import type common from '@ohos.app.ability.common';\n" + prior.transport.replace(types.read_text(),
        '  start(): Promise<void>;', '  originalContext(): common.UIAbilityContext;\n  coldRestart(): Promise<void>;\n  start(): Promise<void>;'))
    suite = directory / 'Task15NativeUiSuite.ets'
    suite.write_text(prior.transport.replace(suite.read_text(),
        'const nativeWindow: window.Window = await this.launch.diagnosticMainWindow();',
        'const nativeWindow: window.Window = await this.launch.diagnosticMainWindow();\n    this.uiContext = nativeWindow.getUIContext();'))
    host = output / 'fresh-host.cjs'
    # External response selection is the canonical event, never a replacement
    # of AccountClient's authentication/retry/status mapping body.
    if plan['canonicalCase']['key'] == 'success_completes':
        host.write_text(prior.transport.replace(host.read_text(),
            'const allowed = { 1: 401, 2: 503, 3: 401, 4: 200 };',
            'const allowed = { 1: 401, 2: 200, 3: 401, 4: 200 };'))
    files = {item['path']: item for item in plan['evaluator']['files']}
    for path in [Path(__file__), Path(__file__).with_name('task15_native_successor_guard_v8.py'),
                 Path(__file__).with_name('task15_native_successor_runner_v8.py')] + list(DIRECTORY.iterdir()):
        if path.is_file():
            files[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    for path in directory.iterdir():
        if path.is_file() and path.name != 'manifest.json':
            files[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    records = [files[key] for key in sorted(files)]
    plan.update(fullNativeProtocol=PROTOCOL, pageOwnerProtocol=PROTOCOL,
        actualSourceBindings=transport.artifacts.artifact(bindings_file),
        nativeSdkApi=api, capabilitySourceBindings=capability_bindings,
        changedBodyBoundary='all app bridges call original; external HTTPS server only',
        evaluator={'protocol': prior.transport.PROTOCOL, 'files': records, 'sha256': transport.artifacts.row_digest(records)})
    result = subprocess.run([prior.previous.NODE, str(DIRECTORY / 'source_ledger.cjs'), str(Path(source).resolve())],
        cwd=ROOT, capture_output=True, text=True, check=True,
        timeout=min(20, core.remaining_deadline(deadline, 'changed application bridge source scope')))
    core.write(output / 'changed-body-source-ledger.json', json.loads(result.stdout))
    (output / 'immutable-task-manifest.json').write_bytes((CONTRACT.parent / 'task.json').read_bytes())
    plan['changedBodySourceLedger'] = transport.artifacts.artifact(output / 'changed-body-source-ledger.json')
    plan['immutableTaskManifest'] = transport.artifacts.artifact(output / 'immutable-task-manifest.json')
    manifest = directory / 'manifest.json'
    core.write(manifest, {'protocol': PROTOCOL, 'files': [transport.artifacts.artifact(path) for path in sorted(directory.iterdir())
        if path.is_file() and path != manifest]})
    plan['derivedFiles'] = [transport.artifacts.artifact(path) for path in sorted(directory.iterdir()) if path.is_file()] + [
        transport.artifacts.artifact(output / 'fresh-host.cjs')]
    core.write(output / 'plan.json', plan)
    return plan


def prepare_prefix(*, source, output, deadline, serial):
    require(choose_probe(source) == 'reviewed_native_prefix', 'Unreviewed source cannot infer absent feature')
    output = prior.transport.canonical_output(output)
    require(not output.exists(), 'No overwrites')
    output.mkdir(parents=True)
    inventory = prior.transport.snapshot_inputs(Path(source), output)
    core.write(output / 'input-inventory.json', inventory)
    (output / 'canonical-contract.json').write_bytes(CONTRACT.read_bytes())
    program = output / 'prefix-driver.cjs'
    program.write_text(derive_prefix_program(source=Path(source), build_report=output / 'base-application/application-build.json',
        contract=output / 'canonical-contract.json', deadline=deadline, device_serial=serial))
    epoch = int((time.time() + core.remaining_deadline(deadline, 'prefix prepare')) * 1000)
    plan = {'protocol': PROTOCOL, 'probe': 'reviewed_native_prefix', 'taskId': TASK, 'role': 'agent',
        'source': str(Path(source).resolve()), 'candidateRootSha256': inventory['rootSha256'],
        'inputInventory': transport.artifacts.artifact(output / 'input-inventory.json'),
        'contract': transport.artifacts.artifact(output / 'canonical-contract.json'), 'deadlineEpochMs': epoch,
        'driver': transport.artifacts.artifact(program),
        'deviceSerial': serial, 'nativeResultFromSource': False,
        'command': ['python3', '-B', '-m', 'scripts.runtime_semantics.task15_native_successor_runner_v8',
            '--prefix-worker', str(output / 'plan.json')]}
    core.write(output / 'plan.json', plan)
    return plan


def derive_prefix_program(*, source, build_report, contract, deadline, device_serial):
    """Pure preparation: no SDK/device discovery or application build."""
    import re
    require(type(device_serial) is str and re.fullmatch('[A-Za-z0-9.:_-]+', device_serial), 'Explicit safe serial required')
    code = inspect.getsource(prefix_previous.evaluate)
    start = code.index('    script = original.read_text')
    end = code.index('    derived = evidence /')
    segment = code[start:end]
    body = 'def derive(source, build_report, deadline, device_serial):\n' + \
        '    work_deadline = deadline - 120\n    original = ROOT / "scripts/runtime_semantics/Task15BaseAllDevice.cjs"\n' + segment + '    return script\n'
    scope = {**prefix_previous.evaluate.__globals__, '_discover_device': lambda serial, _: serial}
    exec(compile(body, str(Path(__file__)) + ':exact-offline-prefix-derivation', 'exec'), scope)
    script = scope['derive'](Path(source), Path(build_report), deadline, device_serial)
    old = "const contractFile = path.join(root,\n  'experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/15_account_deactivation/transitions.json');"
    return prior.transport.replace(script, old, 'const contractFile = ' + json.dumps(str(contract)) + ';')


def execute_prefix(*, source, evidence, deadline, device_serial):
    """Release-gated real application build + isolated real native entry probe."""
    from .task15_native_successor_runner_v8 import command
    evidence = Path(evidence)
    plan = core.load(evidence / 'plan.json')
    require(plan['source'] == str(Path(source).resolve()) and plan['deviceSerial'] == device_serial and
        choose_probe(source) == 'reviewed_native_prefix', 'Prefix source/serial eligibility changed')
    transport.artifacts.bound(plan['driver'])
    removed = []
    try:
        build = core.build_arkts_application(source=Path(source), output=evidence / 'base-application',
            deadline=deadline - 120, label='task15-v8-prefix-runtime')
        result = command([prior.previous.NODE, plan['driver']['path'], '--output', str(evidence / 'base-device')],
            deadline=deadline, log=evidence / 'base-device.log')
        require(result['exit'] == 0, 'Prefix device/compile failure is NS, never semantic fail')
        report = core.load(evidence / 'base-device/report.json')
        require(report['status'] == 'passed', 'Complete original entry/positive-control runtime missing')
        specs = {case['caseId']: case for case in transport.read(plan['contract'])['cases']}
        rows = [prefix_admission.entry_row(raw, specs[raw['caseId']], evidence / 'base-device/report.json', build['sources'])
            for raw in report['semantic']['cases']]
    finally:
        removed.extend(core.remove_binary_artifacts(evidence))
        core.write(evidence / 'prefix-cleanup.json', {'removedBinaries': removed, 'hashesBeforeRemoval': True,
            'remoteCleanupOnlyFromActualRaw': True})
    return rows, removed
