"""Offline, source-parameterized packaging plan for Task14 physical routes.

This prepares a real native builder with the versioned installer. It never
invokes Hvigor/HDC/model at preparation time and never calls an old domain
adapter to obtain a semantic result.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from . import task14_15_formal_core as core
from . import task14_15_arkts_artifacts as artifacts
from . import task15_fresh_protocol_v2 as snapshot
from . import task14_actual_routes_guard_v4 as guard

ROOT = core.ROOT
TASK = guard.TASK
CONTRACT = ROOT / 'benchmark_tasks' / TASK / 'transitions.json'
DIRECTORY = Path(__file__).with_name('task14_real_routes_v4')
CASES = {'jr_state_005_found_then_continue_navigates', 'jr_state_006_continue_waits_for_resolution',
         'jr_state_009_dismiss_closes_flow'}


def expected_fixtures():
    native = ROOT / 'state_tests/runtime/arkts/native'
    names = ['Task14DeviceUi.d.ts', 'Task14DeviceUi.core.js', 'Task14DeviceUi.suite.js',
        'Task14DeviceUi.adapter.js', 'Task14PageObserver.js', 'Task14AncestorObserver.js', 'Task14FrameAcquisition.js',
        'Task14RealFlowV2Observer.js', 'Task14RealFlowV2Frame.js', 'Task14RealFlowV2.suite.js', 'Task14RealFlowV2.adapter.js']
    bridge = (native / 'Task14DeviceUi.js').read_text()
    cases = json.dumps(sorted(CASES), separators=(',', ':'))
    bridge = "import { evaluateTask14RealRoutesV4 } from './Task14RealRoutesV4.adapter';\n" + bridge
    bridge = replace_once(bridge, 'TASK14_CASES[caseSpec.caseId] !== caseSpec.key',
        '(TASK14_CASES[caseSpec.caseId] !== caseSpec.key && !' + cases + '.includes(caseSpec.caseId))')
    bridge = replace_once(bridge, "return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?",
        'if (' + cases + '.includes(caseSpec.caseId)) return evaluateTask14RealRoutesV4(args, config, ports, record);\n' +
        "    return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?")
    import hashlib
    records = [{'name': 'Task14DeviceUi.js', 'sha256': hashlib.sha256(bridge.encode()).hexdigest()}]
    paths = [native / name for name in names] + [DIRECTORY / 'Task14RealRoutesV4.adapter.js',
        DIRECTORY.parent / 'task14_real_routes_v3/Task14JoinOwnerV3.js',
        DIRECTORY.parent / 'task14_real_routes_v3/Task14RealRoutesV3.suite.js']
    records += [{'name': path.name, 'sha256': core.sha256(path)} for path in paths]
    return sorted(records, key=lambda item: item['name'])


def replace_once(source, old, new):
    artifacts.require(source.count(old) == 1, 'Versioned builder anchor changed: ' + old)
    return source.replace(old, new)


def implementation():
    native = ROOT / 'state_tests/runtime/arkts/native'
    paths = [Path(__file__), Path(guard.__file__), Path(__file__).with_name('task14_actual_routes_scorer_v4.py'),
        Path(__file__).with_name('task15_page_owner_v5.py'),
        Path(__file__).with_name('task15_fresh_admission_v2.py'),
        Path(__file__).with_name('task14_15_arkts_artifacts.py'),
        Path(core.__file__), Path(__file__).with_name('task14_15_device_lease.py'),
        Path(__file__).with_name('task15_deadline_v4.py'), Path(__file__).with_name('task15_supervision_v4.py'),
        Path(__file__).with_name('arkts_native_device.cjs'), Path(__file__).with_name('arkts_native_bundle.cjs'),
        Path(__file__).with_name('arkts_device_execute.cjs'), Path(__file__).with_name('arkts_strict_agent_scorer.py')]
    paths += [native / name for name in ['Task14DeviceUi.install.cjs', 'CandidateApiBindings.cjs',
        'Task14DeviceUi.js', 'Task14DeviceUi.d.ts', 'Task14DeviceUi.adapter.js', 'Task14DeviceUi.suite.js',
        'Task14DeviceUi.core.js', 'Task14AncestorObserver.js', 'Task14FrameAcquisition.js', 'Task14PageObserver.js',
        'Task14RealFlowV2Observer.js', 'Task14RealFlowV2Frame.js', 'Task14RealFlowV2.suite.js',
        'Task14RealFlowV2.adapter.js', 'bundle-runtime.js', 'native-device-platform.js', 'native-platform.js']]
    paths += list(DIRECTORY.glob('*.js')) + list(DIRECTORY.glob('*.cjs'))
    paths += [Path(__file__).with_name('task14_real_routes_v3') / name for name in
        ('Task14JoinOwnerV3.js', 'Task14RealRoutesV3.suite.js')]
    records = [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)} for path in sorted(set(paths))]
    return {'protocol': guard.PROTOCOL, 'files': records, 'sha256': artifacts.row_digest(records)}


def derive_builder(contract, deadline_epoch_ms):
    original = Path(__file__).with_name('arkts_native_device.cjs')
    code = original.read_text()
    code = replace_once(code, "'use strict';", "'use strict';\nprocess.argv.splice(2, 0, '--task', " +
        json.dumps(TASK) + ", '--fixture', 'bundle', '--native-ui');\n" +
        'process.env.LTB_TASK14_ROUTE_DEADLINE_EPOCH_MS = ' + json.dumps(str(deadline_epoch_ms)) + ';')
    code = replace_once(code, "const root = path.resolve(__dirname, '../..');", 'const root = ' + json.dumps(str(ROOT)) + ';')
    for name in ('arkts_native_smoke.cjs', 'arkts_native_bundle.cjs'):
        code = replace_once(code, "require('./" + name + "')", 'require(' + json.dumps(str(original.parent / name)) + ')')
    code = replace_once(code, '{ device: true, caseId });', '{ device: true, caseId, contractOverride: ' +
                        json.dumps(str(contract)) + ' });')
    return replace_once(code, "require(path.join(root, 'state_tests/runtime/arkts/native/Task14DeviceUi.install.cjs'))",
                        'require(' + json.dumps(str(DIRECTORY / 'install.cjs')) + ')')


def prepare(*, source, output, deadline, case_ids=None):
    remaining = core.remaining_deadline(deadline, 'Task14 packaging preparation')
    artifacts.require(0 < remaining <= 3600, 'Preparation belongs to one <=3600s budget')
    output = snapshot.canonical_output(output)
    artifacts.require(not output.exists(), 'Never overwrite an earlier runtime/preparation')
    source = Path(source).resolve(strict=True)
    contract = core.load(CONTRACT)
    selected = set(CASES if case_ids is None else case_ids)
    artifacts.require(selected and selected <= CASES, 'Only physical005/006/009 supported by this packaging version')
    output.mkdir(parents=True)
    inventory = snapshot.snapshot_inputs(source, output)
    core.write(output / 'input-inventory.json', inventory)
    (output / 'canonical-contract.json').write_bytes(CONTRACT.read_bytes())
    (output / 'immutable-task-manifest.json').write_bytes((CONTRACT.parent / 'task.json').read_bytes())
    subset = {**contract, 'cases': [case for case in contract['cases'] if case['caseId'] in selected]}
    core.write(output / 'selected-contract.json', subset)
    epoch = int((time.time() + core.remaining_deadline(deadline, 'Task14 builder derivation')) * 1000)
    builder = output / 'native-builder.cjs'
    builder.write_text(derive_builder(output / 'selected-contract.json', epoch))
    plan = {'protocol': guard.PROTOCOL, 'taskId': TASK, 'role': 'agent', 'source': str(source),
        'contract': artifacts.artifact(output / 'canonical-contract.json'),
        'immutableTaskManifest': artifacts.artifact(output / 'immutable-task-manifest.json'),
        'inputInventory': artifacts.artifact(output / 'input-inventory.json'),
        'selectedCases': sorted(selected), 'deadlineEpochMs': epoch,
        'implementation': implementation(), 'builder': artifacts.artifact(builder),
        'packagedFixtures': expected_fixtures(),
        'preparedOnly': True, 'modelCalled': False, 'buildStarted': False, 'deviceStarted': False,
        'applicationCompile': 'Separate full app evidence, never inferred from runtime HAP packaging',
        'requirements': {'freeBytes': 8 * 1024**3, 'canonicalDeviceLease': True,
            'binaryHashesBeforeRemoval': True, 'singleBudgetIncludesQueueAndCleanup': True},
        'ready': False, 'reason': 'Offline packaging is not runtime calibration or profile approval'}
    core.write(output / 'plan.json', plan)
    return plan
