#!/usr/bin/env python3
"""Independent fullraw Task13 page-owner verifier. No public registry mutation."""
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess

try:
    from . import task12_13_formal_core as core
    from . import task12_13_runtime_support as support
    from . import task13_page_owner_entry_audit_v8 as entry
    from .task13_compiled_input_evidence import verify as verify_compiled_inputs
except ImportError:
    import task12_13_formal_core as core
    import task12_13_runtime_support as support
    import task13_page_owner_entry_audit_v8 as entry
    import sys
    sys.path.insert(0, str(core.ROOT))
    from scripts.runtime_semantics.task13_compiled_input_evidence import verify as verify_compiled_inputs


def require(condition, message):
    if not condition:
        raise ValueError('Task13 retained page-owner verification: ' + message)


def checked(record):
    target = Path(record['path'])
    if not target.is_absolute():
        target = core.ROOT / target
    actual = core.file_record(target)
    require(actual['sha256'] == record['sha256'] and actual['bytes'] == record['bytes'], 'raw bytes/size changed: ' + str(target))
    return target


def compare(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and compare(value, actual[key]) for key, value in expected.items())
    return type(expected) is type(actual) and expected == actual


def recompute(spec, ui):
    adapter = core.ROOT / 'state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs'
    command = ['node', '-e', "const fs=require('node:fs');const a=require(process.argv[1]);const i=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(a.evaluatePageOwner(i.spec,i.ui)));", str(adapter)]
    result = subprocess.run(command, input=json.dumps({'spec': spec, 'ui': ui}), text=True, capture_output=True, timeout=20)
    require(result.returncode == 0, 'native owner assertion re-evaluation rejected: ' + result.stderr[:500])
    return json.loads(result.stdout)


def verify_unconfigured_final_discovery(discovery_path, build, inventory):
    """App health without an SDK is distinct from the later SDK-driven cases."""
    discovery = core.load(discovery_path)
    binding = build['nativeUIObserver']['config']['pageBinding']
    require(discovery['source'] == inventory['source'] and discovery['observedBinding'] == 'final' and
            discovery['pageBinding'] == binding and discovery['bundleName'] == build['bundleName'] and
            discovery['status'] == 'production_common_entry_completed' and
            discovery['positiveControl'] == 'production_sdk_unavailable_profile_dm_opened' and
            discovery['freshInstall'] is True and discovery['ownedAppUninstalled'] is True,
            'unconfigured final profile discovery differs')
    require(checked(build['task13Revision5']['entryDiscovery']).resolve() == discovery_path.resolve(),
            'packaging uses another common discovery')
    application = core.load(checked(discovery['build']))
    require(application['source'] == inventory['source'] and application['passed'] is True and
            application['productionUnchanged'] is True, 'common production application binding differs')
    commands = discovery['commands']
    logs = [checked(item['log']).read_text() for item in commands]
    require(all(item['exitCode'] in ({0, 255} if item['args'][0] == 'uninstall' or
                item['args'][:3] == ['shell', 'bm', 'dump'] else {0}) for item in commands),
            'common entry command failed')
    require(commands[0]['args'] == ['uninstall', build['bundleName']] and
            commands[1]['args'] == ['shell', 'bm', 'dump', '-n', build['bundleName']] and
            re.search(r'failed|not exist|error', logs[1], re.I) and
            commands[2]['args'] == ['install', '-r', application['hap']['path']] and
            any(item['args'] == ['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', build['bundleName'],
                                  '-m', 'entry'] for item in commands) and
            sum(item['args'] == ['uninstall', build['bundleName']] for item in commands) == 2,
            'fresh actual production entry/install/cleanup commands missing')
    layouts = discovery['layouts']
    require([item['label'] for item in layouts] == ['profile', 'profile-stable', 'sdk-unavailable-dm-opened'],
            'unconfigured profile checkpoints incomplete')
    trees = [core.load(checked(item['layout'])) for item in layouts]
    require(trees[0] == trees[1], 'unsettled common profile')
    readbacks = [json.loads(log) for item, log in zip(commands, logs) if item['args'][:2] == ['shell', 'cat']]
    require(readbacks == trees, 'native discovery layouts differ from actual command readback')
    readback_indices = [i for i, item in enumerate(commands) if item['args'][:2] == ['shell', 'cat']]
    flattened = []
    for tree in trees:
        nodes = []
        def visit(node):
            require(isinstance(node.get('attributes'), dict) and isinstance(node.get('children'), list),
                    'incomplete native discovery tree')
            nodes.append(node['attributes'])
            for child in node['children']:
                visit(child)
        visit(tree)
        roots = [item for item in nodes if item.get('type') == 'root']
        require(len(roots) == 1 and roots[0].get('bundleName') == build['bundleName'] and
                roots[0].get('pagePath') == 'pages/Index' and roots[0].get('focused') == 'true',
                'wrong common-entry native window')
        require(sum(item.get('id') == 'verification_unavailable' and item.get('visible') == 'true'
                    for item in nodes) == 1 and
                not any(item.get('id') in {'verify_user_action', 'request_user_verification'} and
                        item.get('visible') == 'true' for item in nodes),
                'common discovery is not the unconfigured SDK boundary')
        flattened.append(nodes)
    targets = [item for item in flattened[0] if item.get('id') == 'start_direct_message']
    require(len(targets) == 1 and all(targets[0].get(key) == 'true' for key in ('visible', 'enabled', 'clickable')),
            'actual enabled common DM control missing')
    rect = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', targets[0]['bounds'])
    require(rect is not None, 'common control bounds missing')
    left, top, right, bottom = map(int, rect.groups())
    require(right > left and bottom > top, 'common control has empty bounds')
    click = ['shell', 'uitest', 'uiInput', 'click', str((left + right + 1) // 2), str((top + bottom + 1) // 2)]
    require([item['args'] for item in commands if item['args'][:4] == click[:4]] == [click],
            'common physical DM action missing/ambiguous')
    click_index = next(i for i, item in enumerate(commands) if item['args'] == click)
    require(readback_indices[1] < click_index < readback_indices[2],
            'common physical click is outside the before/after observation boundary')
    def opened(nodes):
        return sum(item.get('text') == 'Opening direct message' and item.get('visible') == 'true' for item in nodes)
    require(opened(flattened[0]) == 0 and opened(flattened[2]) == 1,
            'common DM positive transition not observed')
    return {'verified': True, 'sdkConfigured': False, 'canonicalVerificationClaimed': False}


def verify(report_path):
    return verify_value(core.load(report_path), report_path=report_path)


def verify_value(report, *, report_path=None):
    contract = core.load(core.ROOT / 'benchmark_tasks/13_user_verification/transitions.json')
    require(core.sha256(core.ROOT / 'benchmark_tasks/13_user_verification/transitions.json') ==
            'c038fddc0beba7933076cef4f63a8d156ccf914628cb39c3b5eec708c7035e90', 'canonical changed')
    require(report['taskId'] == contract['taskId'] and report['platform'] == 'arkts' and
            report['role'] in {'base', 'final', 'agent'}, 'report identity differs')
    evidence = report['provenance']['runtimeEvidence']
    execution_path, build_path = checked(evidence['execution']), checked(evidence['build'])
    checked(evidence['commonEntry'])
    raw, build = core.load(execution_path), core.load(build_path)
    require(entry.checked_record(raw['buildReport']).resolve() == build_path.resolve(), 'runtime used another build')
    require(raw.get('transportCompleted') is True and raw.get('candidateAbsentBeforeInstall') is True and
            raw.get('cleanup', {}).get('ownedAppUninstalled') is True, 'fresh native transport/cleanup missing')
    nonce = raw.get('executionNonce')
    require(isinstance(nonce, str) and len(nonce) == 32 and all(char in '0123456789abcdef' for char in nonce), 'native nonce invalid')
    for command in raw['commands']:
        log = execution_path.parent / command['log']
        require(log.is_file() and core.sha256(log) == command['sha256'], 'raw command log changed')
    require(build.get('productionUnchanged') is True and build.get('copiedProductionUnchanged') is True and
            build.get('temporaryProjectRemoved') is True and not build['task13Revision5'].get('compileOnly'),
            'runtime not compiled from untouched candidate / compile-only artifact used')
    inventory = core.load(checked(evidence['sourceInventory']))
    compiler_proof = verify_compiled_inputs(build, inventory)
    require(inventory['source'] == report['provenance']['candidateSource'] and inventory['sha256'] ==
            report['provenance']['sourceInventorySha256'], 'source inventory/provenance differs')
    hashes = {item['path']: item['sha256'] for item in inventory['files']}
    require(build['source'] == inventory['source'] and all(hashes.get(item['path']) == item['sha256'] for item in build['production']),
            'actual compiled production inventory differs')
    native = {}
    for artifact in raw['rowArtifacts']:
        require(artifact['executionNonce'] == nonce, 'artifact execution nonce differs')
        path = checked({'path': artifact['local'], 'bytes': artifact['bytes'], 'sha256': artifact['sha256']})
        row = core.load(path)
        require(row['caseId'] not in native and row['nativeBridge']['capabilities']['execution']['nonce'] == nonce,
                'native case duplicated or fresh process nonce differs')
        native[row['caseId']] = row
    require(len(native) == 10 and list(native.values()) == raw['rows'], 'full native rows differ from execution raw')
    rows = {row['caseId']: row for row in report['semantic']['cases']}
    require(len(report['semantic']['cases']) == 10 and set(rows) == set(native), 'formal/native case set differs')
    internal = build['nativeUIObserver']['role']
    require(internal in {'base', 'final'}, 'unknown native page binding')
    entry.load_policy(contract)
    if internal == 'base':
        entry.inspect_report(execution_path, build_path, inventory=inventory, contract=contract)
    else:
        verify_unconfigured_final_discovery(checked(evidence['commonEntry']), build, inventory)
    executors = raw.get('task13ExecutionSources', [])
    executor_hashes = {
        str(core.ROOT / 'scripts/runtime_semantics/task13_arkts_revision5_execute.cjs'):
            'fa07b2ba2d6b4e1f4e1edc8e095f5fb130897fd6946681ab11b2145bb30e45a1',
        str(core.ROOT / 'scripts/runtime_semantics/arkts_device_execute.cjs'):
            '86631e64ce0a1bbdcc054ab3b465aef90d0144ccf03f3b878854e575e5cb4f25',
    }
    require(len(executors) == 3 and len({item['original']['path'] for item in executors}) == 3,
            'complete execution producer set missing')
    for item in executors:
        original, retained = checked(item['original']), checked(item['retained'])
        require(core.sha256(original) == core.sha256(retained), 'execution producer snapshot differs')
        expected = executor_hashes.get(str(original))
        if expected is None:
            require(original.resolve() == (build_path.parent / 'task13-revision5-execute.generated.cjs').resolve(),
                    'unbound generated execution producer')
        else:
            require(core.sha256(original) == expected, 'unreviewed execution producer')
    require(set(executor_hashes) <= {item['original']['path'] for item in executors}, 'execution producer missing')
    sessions = set()
    cases = []
    for spec in contract['cases']:
        row, native_row = rows[spec['caseId']], native[spec['caseId']]
        require(native_row['traceDigest'] == row['traceDigest'] == spec['traceDigest'], 'trace digest differs')
        observations = [call['observation'] for call in native_row['calls'] if call.get('method') == 'Task13Revision5.originalProfileRuntime']
        require(len(observations) == 1, 'native page replay missing/duplicated')
        ui = observations[0]
        require(ui['productionSources'] == build['nativeUIObserver']['sources'] == build['production'] and
                native_row.get('productionSources') and all(hashes.get(item['path']) == item['sha256']
                    for item in native_row['productionSources']), 'native page/source binding differs')
        require(ui['sessionId'] not in sessions, 'native case session reused')
        sessions.add(ui['sessionId'])
        require(ui.get('launchCleanup', {}).get('destroyed') is True, 'page lifecycle cleanup missing')
        windows = set()
        for frame in ui['frames']:
            window = frame['windowIdentity']
            require(frame['sessionId'] == ui['sessionId'] and window.get('focused') is True and
                    window.get('hostVerified') is True and type(window.get('stageMainWindowId')) is int and
                    window['stageMainWindowId'] == window.get('lastWindowId') and
                    window['bounds'] == frame['uiInventory']['windowBounds'], 'actual focused window/geometry differs')
            windows.add(window['stageMainWindowId'])
        require(len(windows) == 1, 'case changed native owner window')
        if internal == 'base' and spec['key'] != 'identity_violation_surfaces':
            expected = entry.entry_row(spec, native_row, execution_path, build_path,
                                       checked(evidence['sourceInventory']))
            require(all(row.get(key) == value for key, value in expected.items()), 'base entry row not exact independent replay')
        elif internal == 'final':
            calculated = recompute(spec, ui)
            require([item['description'] for item in calculated['invariantChecks']] == spec['invariants'],
                    'original canonical invariant coverage differs')
            require(compare(calculated['observed'], row['observed']), 'formal observed state differs from full native owner evidence')
            require([(item['description'], item['passed']) for item in calculated['invariantChecks']] ==
                    [(item['description'], item['passed']) for item in row['invariantChecks']], 'original invariant verdict differs')
            status = 'pass' if compare(spec['expected'], calculated['observed']) and all(item['passed'] for item in calculated['invariantChecks']) else 'fail'
            require(row['status'] == status, 'accepted verdict differs from actual original assertions')
        else:
            require(row['observed'] == native_row['observed'] and row['status'] == native_row['status'], 'base identity row changed')
        cases.append({'caseId': spec['caseId'], 'status': row['status'], 'nativeSource': str(execution_path), 'sessionId': ui['sessionId']})
    require(len(cases) == 10, 'case coverage incomplete')
    return {'verified': True, 'report': core.file_record(report_path) if report_path is not None else None,
            'compilerInputs': compiler_proof, 'cases': cases,
            'counts': {key: sum(row['status'] == value for row in cases)
                       for key, value in [('passed', 'pass'), ('failed', 'fail'), ('notScored', 'not_scored')]},
            'publicRoutingEdited': False, 'readyClaim': False}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.report.resolve())
    core.write(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}))


if __name__ == '__main__':
    main()
