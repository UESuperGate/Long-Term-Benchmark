"""Offline Task15 original-owner packaging, with actual source selector discovery.

The frozen v5 observer/producer and v2 transport remain byte-identical. A
versioned local function derivation changes only the set of cases admitted for
PREPARATION, never old globals/dispatch or semantic assertions. This module
then replaces evaluator-owned fixtures before any compiler/device execution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
import types

from . import task15_fresh_protocol_v2 as old
from . import task15_fresh_admission_v2 as transport
from . import task15_page_owner_v5 as owner
from . import task14_15_formal_core as core

PROTOCOL = 'task15.arkts.original-owner-packaging.v6'
CASES = {'ad_state_002_default_form_blocks_submit', 'ad_state_003_password_enables_submit',
         'ad_state_004_erase_data_option', 'ad_state_007_success_completes', 'ad_state_010_close_dialog_resets_action'}
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
BINDER = Path(__file__).with_suffix('.cjs')


def _engine():
    text = (owner.DIRECTORY / 'Task15FreshActionsV2.js').read_text()
    first = "  const names = { settings: ON.text('Settings'), notifications: ON.type('Button').text('Notifications'),"
    text = old.replace(text, first, """  const selector = name => {
    const spec = binding.controlSelectors?.[name];
    need(spec && Object.keys(spec).every(key => ['id', 'type', 'text'].includes(key)), 'Unbound actual source selector');
    let value = ON;
    if (spec.id) value = value.id(spec.id);
    if (spec.type) value = value.type(spec.type);
    if (spec.text !== undefined) value = value.text(spec.text);
    return value;
  };
  const names = { settings: ON.text('Settings'), notifications: ON.type('Button').text('Notifications'),""")
    text = old.replace(text, "    entry: ON.id(binding.entryId), password: ON.id(binding.passwordId), erase: ON.id(binding.eraseId),\n    submit: ON.id(binding.submitId), confirm: ON.type('Button').text(binding.confirmText),\n    close: ON.type('Button').text(binding.closeText) };",
        "    entry: selector('entry'), password: selector('password'), erase: selector('erase'),\n    submit: selector('submit'), confirm: ON.type('Button').text(binding.confirmText), close: selector('close') };")
    start = '    await integration.prepare({ find, inspect, click, receipt, inspectRaw: id => inspector.byKey(id), bundleName, result, binding });'
    end = "    need(observer.read().available, 'No actual production render receiver; NS, never getter/setter discovery');"
    begin_index, end_index = text.index(start), text.index(end) + len(end)
    # Acquire from the ORIGINAL page's real authenticated session-change
    # lifecycle. Starting an already running ability is not evidence that its
    # aboutToAppear() re-executed. No direct callback or getter is invoked.
    text = text[:begin_index] + """    result.integration = integration.evidence(); result.nonce = result.integration.nonce;
    need(/^[a-f0-9]{32}$/.test(result.nonce || ''), 'Own external session nonce unavailable');
    result.launchSetupSessionId = result.sessionId;
    result.sessionId = result.nonce + ':' + spec.caseId;
    stage = 'passive_original_owner_before_authenticated_session';
    need((await inspect('settings')).visible && (await inspect('notifications')).visible,
      'Original settings positive control unavailable before module postload');
    const namespace = await ports.importModule(binding.productionModuleUrl);
    const services = typeof namespace.AccountClient === 'function' ? namespace : await ports.importModule(binding.serviceModuleUrl);
    observer = ports.observePage({ ...namespace, AccountClient: services.AccountClient }, binding.ownerBinding, result.sessionId);
    await integration.prepare({ find, inspect, click, receipt, inspectRaw: id => inspector.byKey(id), bundleName, result, binding });
    result.integration = integration.evidence();
    for (let attempt = 0; attempt < 20 && !observer.read().available; attempt++) {
      budget(); await driver.delayMs(50);
    }
    need(observer.read().available, 'No original authenticated page lifecycle/render receiver; NS');""" + text[end_index:]
    return text


def discover(source, deadline):
    result = subprocess.run([NODE, str(BINDER), str(Path(source).resolve(strict=True))],
        cwd=old.ROOT, capture_output=True, text=True, check=True,
        timeout=min(30, core.remaining_deadline(deadline, 'Actual Task15 source control/owner discovery')))
    binding = json.loads(result.stdout)
    transport.require(binding['source'] == str(Path(source).resolve()) and binding['approvedNativeProfile'] is False,
                      'Discovery does not approve runtime/native behavior')
    return binding


def prepare(*, source, case_id, output, deadline, serial='127.0.0.1:5555'):
    transport.require(case_id in CASES, 'Only five original-owner cases in this successor')
    source = Path(source).resolve(strict=True)
    bindings = discover(source, deadline)
    # This scoped clone does not patch the imported module or a live function.
    # It reuses the exact reviewed transport preparation for a different own
    # canonical case. All derived bytes are recorded before any execution.
    function = types.FunctionType(old.prepare_case.__code__, {**old.prepare_case.__globals__, 'NATIVE_CASES': CASES},
        name='prepare_original_owner_transport_v6', argdefs=old.prepare_case.__defaults__, closure=old.prepare_case.__closure__)
    function.__kwdefaults__ = old.prepare_case.__kwdefaults__
    plan = function(source=source, case_id=case_id, output=output, deadline=deadline, serial=serial)
    output = Path(output)
    (output / 'transport-v2-preparation-plan.json').write_bytes((output / 'plan.json').read_bytes())
    core.write(output / 'actual-source-bindings.json', bindings)
    directory = output / 'native-environment-fixtures'
    engine = directory / 'Task15FreshActionsV2.js'
    engine.write_text(_engine())
    observer = directory / 'Task15PageOwnerObserverV5.js'
    observer.write_bytes((owner.DIRECTORY / observer.name).read_bytes())
    wrapper = directory / 'Task15NativeUi.js'
    text = wrapper.read_text()
    text = old.replace(text, "import { runTask15FreshPhysicalCase } from './Task15FreshActionsV2';",
        "import { runTask15PageOwnerCaseV5 } from './Task15FreshActionsV2';\nimport { observeTask15OriginalPageOwnerV5 } from './Task15PageOwnerObserverV5';")
    text = old.replace(text, 'await runTask15FreshPhysicalCase(', 'await runTask15PageOwnerCaseV5(')
    text = old.replace(text, 'observePage: observeTask15Page', 'observePage: observeTask15OriginalPageOwnerV5')
    wrapper.write_text(text)
    bridge = directory / 'Task15NativeUiBridge.js'
    text = bridge.read_text()
    text = old.replace(text, "['capability_gates_entry', 'first_submit_confirms', 'confirm_sends_payload', 'failure_preserves_form', 'retry_bypasses_confirmation']",
        json.dumps(sorted(owner.CASES)))
    bridge.write_text(text)
    installer = directory / 'Task15NativeUi.install.cjs'
    text = installer.read_text()
    text = old.replace(text, "const modules = ['Task15FreshActionsV2.js', 'Task15PageObserver.js'",
        "const modules = ['Task15PageOwnerObserverV5.js', 'Task15FreshActionsV2.js', 'Task15PageObserver.js'")
    # The original installer selects API namespace and compile fixtures. Attach
    # the source-scanned controls/actual owner, not guessed IDs by API shape.
    text = old.replace(text, '  const observedSources = new Set(', '  Object.assign(binding, ' + json.dumps({
        'ownerBinding': bindings['ownerBinding'], 'controlSelectors': bindings['controlSelectors'],
        'sourceOwnerProtocol': PROTOCOL, 'ownerAcquisitionMethods': bindings['ownerAcquisitionMethods']}) + ');\n' +
        '  const observedSources = new Set(')
    # Ensure the new observer is an actual packaged module rather than only an
    # entry in the outer evaluator inventory.
    text = old.replace(text, "const file = (", "const file = name === 'Task15PageOwnerObserverV5.js' ? " +
        json.dumps(str(observer)) + ' : (')
    installer.write_text(text)
    files = {item['path']: item for item in old.implementation()['files'] if Path(item['path']).name != 'Task15FreshActionsV2.js'}
    for path in (Path(__file__), BINDER, Path(owner.__file__), observer, engine,
                 Path(__file__).with_name('task15_page_owner_admission_v6.py')):
        files[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    records = [files[name] for name in sorted(files)]
    plan.update(evaluator={'protocol': old.PROTOCOL, 'files': records, 'sha256': transport.artifacts.row_digest(records)},
        pageOwnerProtocol=owner.PROTOCOL, packagingProtocol=PROTOCOL,
        actualSourceBindings=transport.artifacts.artifact(output / 'actual-source-bindings.json'),
        ready=False, nativeProfileApproved=False, requiresActualNativeReview=True,
        noAbilityRestartAssumed=True, ownerAcquiredBy='Actual original authenticated session-change lifecycle/render, observed passively')
    manifest = directory / 'manifest.json'
    core.write(manifest, {'protocol': PROTOCOL, 'productionModified': False,
        'files': [transport.artifacts.artifact(path) for path in sorted(directory.iterdir()) if path.is_file() and path != manifest]})
    plan['derivedFiles'] = [transport.artifacts.artifact(path) for path in sorted(directory.iterdir()) if path.is_file()] + [
        transport.artifacts.artifact(output / 'fresh-host.cjs')]
    core.write(output / 'plan.json', plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--case', required=True, choices=sorted(CASES))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    args = parser.parse_args()
    value = prepare(source=args.source, case_id=args.case, output=args.output,
        deadline=time.monotonic() + 3600, serial=args.device_serial)
    print(json.dumps({'preparedOnly': True, 'modelOrDeviceStarted': False,
        'ready': value['ready'], 'caseId': value['caseId'], 'commandAfterReleaseOnly': value['command']}))


if __name__ == '__main__':
    main()
