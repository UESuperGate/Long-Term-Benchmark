"""Offline preparation of fresh, source-parameterized Task15 physical cases.

No CLI in this module executes a device or model. Release-gated execution is a
separate caller responsibility; prepare_case only writes evaluator-owned files.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from . import task14_15_formal_core as core
    from . import task14_15_arkts_artifacts as artifacts
    from . import task15_device_scheduling as scheduling
    from . import task15_native_environment as environment
except ImportError:
    import task14_15_formal_core as core
    import task14_15_arkts_artifacts as artifacts
    import task15_device_scheduling as scheduling
    import task15_native_environment as environment

ROOT = artifacts.ROOT
NATIVE = ROOT / 'state_tests/runtime/arkts/native'
PROTOCOL = 'task15.arkts.fresh-physical-actions.v2'
POLICY_ID = 'task15.arkts.fresh-blocked-required-action.v2'
TASK = '15_account_deactivation'
CONTRACT = ROOT / 'benchmark_tasks' / TASK / 'transitions.json'
NATIVE_CASES = {
    'ad_state_001_capability_gates_entry', 'ad_state_005_first_submit_confirms',
    'ad_state_006_confirm_sends_payload', 'ad_state_008_failure_preserves_form',
    'ad_state_009_retry_bypasses_confirmation'}
replace = scheduling.replace_once
REVIEW = ROOT / 'experiment_results/runtime_transition_20261020/task15_fresh_protocol_v2_1'
WINDOW_SUITE = ROOT / ('experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1/'
    'candidate-ui-ime-onecase-v6/native-environment-fixtures/Task15NativeUiSuite.ets')


def canonical_output(output):
    path = Path(output).absolute()
    artifacts.require(path.resolve() == path and any(path.is_relative_to(ROOT / name)
        for name in ('experiment_results', 'eval_runs')), 'Use a canonical evidence directory')
    return path


def implementation():
    paths = [Path(__file__), Path(artifacts.__file__), Path(scheduling.__file__), Path(environment.__file__),
        Path(core.__file__), ROOT / 'scripts/runtime_semantics/task15_native_e2e.cjs',
        ROOT / 'scripts/runtime_semantics/arkts_native_device.cjs',
        ROOT / 'scripts/runtime_semantics/task15_fresh_admission_v2.py',
        ROOT / 'scripts/runtime_semantics/task15_arkts_action_eligibility.py',
        ROOT / 'scripts/runtime_semantics/task14_15_arkts_formal_verify.py',
        ROOT / 'scripts/runtime_semantics/task14_15_arkts_entry_evidence.py',
        ROOT / 'scripts/runtime_semantics/task14_15_arkts_layout_closure.py',
        ROOT / 'scripts/runtime_semantics/arkts_native_smoke.cjs',
        ROOT / 'scripts/runtime_semantics/arkts_native_bundle.cjs',
        ROOT / 'scripts/runtime_semantics/task15_formal_agent.py',
        ROOT / 'scripts/runtime_semantics/task15_capability_probe.py',
        ROOT / 'scripts/runtime_semantics/arkts_runtime.cjs',
        ROOT / 'state_tests/runtime/arkts/tasks12_15.cjs',
        ROOT / 'experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1/task15-action-eligibility-review-v1/profile.json',
        NATIVE / 'Task15FreshActionsV2.js', WINDOW_SUITE]
    paths.extend(NATIVE / name for name in ('Task15NativeUi.js', 'Task15NativeUi.install.cjs',
        'Task15NativeUiBridge.js', 'Task15NativeE2E.js', 'Task15Launch.js', 'Task15PageObserver.js',
        'CandidateApiBindings.cjs', 'Task15NativeUi.d.ts', 'Task15NativeE2E.d.ts',
        'Task15LaunchNative.js', 'Task15LaunchNative.d.ts', 'Task15NativeUiBridge.d.ts',
        'DeviceTestRunner.ets', 'Task15NativeE2E.verifier.cjs'))
    paths.extend(NATIVE / name for name in ('bundle-runtime.js', 'native-device-platform.js', 'native-platform.js'))
    paths.extend(sorted((ROOT / 'scripts/runtime_semantics/task15_capability').glob('*')))
    records = [artifacts.artifact(path) if path.is_relative_to(ROOT / 'experiment_results') else {
        'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)} for path in sorted(set(paths))]
    return {'protocol': PROTOCOL, 'files': records, 'sha256': artifacts.row_digest(records)}


def snapshot_inputs(source, output):
    source = Path(source).resolve(strict=True)
    excluded = {'.git', '.gradle', '.hvigor', '.idea', 'build', 'node_modules', 'oh_modules'}
    result = []
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if excluded.intersection(relative.parts):
            continue
        artifacts.require(not path.is_symlink(), 'Candidate symlink makes source closure ambiguous')
        if path.is_file():
            target = output / 'input' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            reference = artifacts.artifact(target)
            result.append({'path': relative.as_posix(), 'bytes': reference['bytes'],
                           'sha256': reference['sha256'], 'snapshot': reference})
    return {'source': str(source), 'rootSha256': core.directory_digest(source), 'files': result}


def prepare_case(*, source, case_id, output, deadline, serial='127.0.0.1:5555'):
    remaining = deadline - time.monotonic()
    artifacts.require(0 < remaining <= 3600, 'Preparation/wait/build/device share one remaining <=3600s budget')
    artifacts.require(remaining > 120, 'Reserve real cleanup within the same scorer deadline')
    output = canonical_output(output)
    artifacts.require(not output.exists(), 'Never overwrite an earlier case or historical v6')
    contract = core.load(CONTRACT)
    specs = [row for row in contract['cases'] if row['caseId'] == case_id]
    artifacts.require(len(specs) == 1 and case_id in NATIVE_CASES, 'Own canonical native case required; no case005 reuse')
    spec = specs[0]
    output.mkdir(parents=True)
    source = Path(source).resolve(strict=True)
    inventory = snapshot_inputs(source, output)
    core.write(output / 'input-inventory.json', inventory)
    (output / 'canonical-contract.json').write_bytes(CONTRACT.read_bytes())
    fixture, installer = environment.prepare(output)
    directory = fixture.parent
    fixture.write_text(replace(fixture.read_text(), '    async continueSequence(tools) {',
        '    control: { status: serverStatus, waitHeld, release },\n    async continueSequence(tools) {'))
    engine = directory / 'Task15FreshActionsV2.js'
    engine.write_bytes((NATIVE / engine.name).read_bytes())
    wrapper = directory / 'Task15NativeUi.js'
    original = (NATIVE / wrapper.name).read_text()
    configure = original[:original.index('export async function runTask15NativeUi(')]
    wrapper.write_text("import { runTask15FreshPhysicalCase } from './Task15FreshActionsV2';\n" + configure + """
export async function runTask15NativeUi(caseJson, bundleName, driver, ON, launch, integration, inspector,
  ignoredDismissKeyboard, deadlineEpochMs, modalInput) {
  const result = await runTask15FreshPhysicalCase({ spec: JSON.parse(caseJson), bundleName, driver, ON,
    launch, integration, inspector, deadlineEpochMs, modalInput,
    binding: binding.config, importModule: binding.importModule, observePage: observeTask15Page });
  return JSON.stringify(result);
}
""")
    types = directory / 'Task15NativeUi.d.ts'
    types.write_text("""import type { Driver, On } from '@ohos.UiTest';
import type { Task15Launch } from './Task15LaunchNative';
export function configureTask15Binding(configJson: string): void;
export function runTask15NativeUi(caseJson: string, bundleName: string, driver: Driver, selectors: On,
  launch: Task15Launch, integration?: Object, inspector?: Object, ignoredDismissKeyboard?: Object,
  deadlineEpochMs?: number, modalInput?: (geometry: number[][], value: string) => Promise<void>): Promise<string>;
""")
    suite = directory / 'Task15NativeUiSuite.ets'
    code = WINDOW_SUITE.read_text()
    code = replace(code, '    undefined);', """    undefined,
    Number(abilityDelegatorRegistry.getArguments().parameters['-s task15DeadlineEpochMs'] ||
      abilityDelegatorRegistry.getArguments().parameters['task15DeadlineEpochMs']),
    async (geometry: number[][], value: string): Promise<void> => {
      await driver.inputText({ x: Math.floor((geometry[0][0] + geometry[1][0]) / 2),
        y: Math.floor((geometry[0][1] + geometry[1][1]) / 2) }, value);
    });""")
    suite.write_text(code)
    launch = directory / 'Task15Launch.js'
    launch.write_text(replace((NATIVE / launch.name).read_text(), '    read() { return', """    async reload() {
      if (!registered || disposed) throw new Error('Original lifecycle not active');
      await ports.delegator.startAbility({ bundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
    },
    async diagnosticMainWindow() {
      if (!stage || disposed) throw new Error('Actual original WindowStage unavailable');
      return stage.getMainWindow();
    },
    read() { return"""))
    launch_types = directory / 'Task15LaunchNative.d.ts'
    launch_types.write_text("import type window from '@ohos.window';\n" + replace(
        (NATIVE / launch_types.name).read_text(), '  start(): Promise<void>;',
        '  reload(): Promise<void>;\n  diagnosticMainWindow(): Promise<window.Window>;\n  start(): Promise<void>;'))
    bridge = directory / 'Task15NativeUiBridge.js'
    bridge_code = replace((NATIVE / bridge.name).read_text(),
        "['capability_gates_entry', 'first_submit_confirms', 'confirm_sends_payload']",
        "['capability_gates_entry', 'first_submit_confirms', 'confirm_sends_payload', 'failure_preserves_form', 'retry_bypasses_confirmation']")
    bridge_code = replace(bridge_code, 'raw.entryExecuted && raw.prerequisite?.rootConfirmed',
        "raw.entryExecuted && raw.protocol === '" + PROTOCOL + "' && raw.frames.some(frame => "
        "frame.nativeTree && frame.windowIdentity?.hostVerified === true)")
    bridge.write_text(bridge_code)
    adapter = directory / 'Task15FreshRaw.adapter.cjs'
    adapter.write_text("""'use strict';
module.exports.runCase = async args => {
  const native = args.native || args.context?.native;
  const raw = await native.runTask15UI(args.caseSpec);
  if (raw.protocol !== 'task15.arkts.fresh-physical-actions.v2' || raw.caseId !== args.caseSpec.caseId ||
      raw.traceDigest !== args.caseSpec.traceDigest) throw Error('Fresh case protocol/identity mismatch');
  return { observed: {}, invariantChecks: [], evidence: [{ nativePageTransition: raw }],
    unsupported: 'Fresh raw requires independent case admission; no projected semantic verdict',
    observationLevel: 'native_candidate_ui' };
};
""")
    code = installer.read_text()
    code = replace(code, "const modules = ['Task15PageObserver.js'", "const modules = ['Task15FreshActionsV2.js', 'Task15PageObserver.js'")
    mapping = {path.name: str(path) for path in (fixture, engine, wrapper, types, suite, launch, launch_types, bridge)}
    old = 'const file = name === \'Task15NativeE2E.js\' ? ' + json.dumps(str(fixture)) + \
        ' : path.join(' + json.dumps(str(NATIVE)) + ', name), bytes = fs.readFileSync(file);'
    code = replace(code, old, 'const file = (' + json.dumps(mapping) + ')[name] || path.join(' +
                   json.dumps(str(NATIVE)) + ', name), bytes = fs.readFileSync(file);')
    code = replace(code, "const adapterFile = path.join(" + json.dumps(str(NATIVE)) + ", 'Task15NativeUi.adapter.cjs');",
                   'const adapterFile = ' + json.dumps(str(adapter)) + ';')
    installer.write_text(code)
    core.write(directory / 'manifest.json', {'protocol': PROTOCOL,
        'productionModified': False, 'canonicalAssertionsModified': False,
        'files': [artifacts.artifact(path) for path in sorted(directory.iterdir())
                  if path.is_file() and path.name != 'manifest.json']})
    script = (ROOT / 'scripts/runtime_semantics/task15_native_e2e.cjs').read_text()
    script = replace(script, "require('../../state_tests/runtime/arkts/native/Task15NativeE2E.verifier.cjs')",
                     'require(' + json.dumps(str(NATIVE / 'Task15NativeE2E.verifier.cjs')) + ')')
    root = "const root = path.resolve(__dirname, '../..');"
    artifacts.require(script.count(root) == 2, 'Host/builder root anchors changed')
    script = script.replace(root, 'const root = ' + json.dumps(str(ROOT)) + ';', 1)
    script = replace(script, "const source = path.join(root, 'final_dev_nodes/15_account_deactivation_final_0_6_3');",
                     'const source = ' + json.dumps(str(source)) + ';')
    artifacts.require(script.count("'ad_state_005_first_submit_confirms'") == 2, 'Own raw-marker/build-case anchors changed')
    script = script.replace("'ad_state_005_first_submit_confirms'", json.dumps(case_id))
    script = replace(script, "'--fixture', 'bundle', '--role', 'final', '--case'", "'--fixture', 'bundle', '--role', 'agent', '--case'")
    epoch_ms = int((time.time() + core.remaining_deadline(deadline, 'Fresh case preparation')) * 1000)
    script = replace(script, '  const timeout = options.timeout || 30000;',
        '  const cap = /cleanup-/.test(options.log || "") ? ' + str(epoch_ms) + ' : ' + str(epoch_ms - 120000) + ';\n'
        '  if (Date.now() >= cap) throw Error("Whole scorer deadline exhausted");\n'
        '  const timeout = Math.max(1, Math.min(options.timeout || 30000, cap - Date.now()));')
    script = replace(script, '    certificates = await generateCertificates(certificateDirectory, nonce, run.commands);',
        '    const disk = fs.statfsSync(output);\n'
        '    run.diskGuard = { availableBytes: disk.bavail * disk.bsize, minimumBytes: 8 * 1024 ** 3 };\n'
        '    if (run.diskGuard.availableBytes < run.diskGuard.minimumBytes) throw Error("8GiB disk guard: environment not ready");\n'
        '    certificates = await generateCertificates(certificateDirectory, nonce, run.commands);')
    script = scheduling.native_scenario_lease(script, deadline=deadline - 120)
    # Test-only certificate readiness remains identical to the accepted real SDK implementation.
    old_module = ROOT / 'scripts/runtime_semantics/task15_formal_agent.py'
    spec_module = importlib.util.spec_from_file_location('task15_fresh_existing_environment', old_module)
    legacy = importlib.util.module_from_spec(spec_module)
    sys.path.insert(0, str(old_module.parent))
    spec_module.loader.exec_module(legacy)
    script = legacy._derive_native_environment(script)
    script = environment.derive_runtime(script, fixture, installer)
    script = replace(script, "'-s', 'task15E2E', '1',", "'-s', 'task15DeadlineEpochMs', " + json.dumps(str(epoch_ms - 120000)) + ",\n      '-s', 'task15E2E', '1',")
    script = replace(script, "canonicalScope: 'case005 only; E2E continuation verified separately'",
        'canonicalScope: ' + json.dumps('own fresh physical case only: ' + case_id) + ", protocol: '" + PROTOCOL + "'")
    script = replace(script, 'const verification = verifyTask15NativeE2E({ evidence, provider: transcript, run });',
        "const verification = { status: 'fresh_raw_pending_independent_admission', passed: 0, total: 0, semanticScored: false };")
    script = replace(script, "run.status = verification.status === 'passed' ? 'passed' : 'failed';\n      if (verification.status !== 'passed') process.exitCode = 1;",
        "run.status = run.error ? 'incomplete' : 'fresh_raw_pending_independent_admission';\n"
        "      if (run.error) process.exitCode = 1;")
    script = replace(script, "    write(path.join(output, 'run.json'), run);", """    // Hash before removal; keep text compiler logs, never retain HAP/build trees.
    const removed = [], retained = [];
    const visit = directory => {
      if (!fs.existsSync(directory)) return;
      for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
        const file = path.join(directory, item.name);
        if (item.isSymbolicLink()) throw Error('Cleanup refuses symbolic link: ' + file);
        if (item.isDirectory()) visit(file);
        else {
          const record = { path: file, bytes: fs.statSync(file).size, sha256: hashFile(file) };
          if (/\\.(json|log|txt|cjs|js|ets|ts)$/.test(file)) {
            const destination = path.join(output, 'retained-build-text', path.relative(output, file));
            fs.mkdirSync(path.dirname(destination), { recursive: true });
            fs.copyFileSync(file, destination); retained.push({ ...record, retainedPath: destination });
          }
          removed.push(record);
        }
      }
    };
    for (const directory of [buildDirectory, certificateDirectory]) {
      visit(directory); fs.rmSync(directory, { recursive: true, force: true });
    }
    for (const record of removed) record.removed = !fs.existsSync(record.path);
    run.binaryCleanup = { files: removed, retainedText: retained,
      buildDirectoryRemoved: !fs.existsSync(buildDirectory), certificatesRemoved: !fs.existsSync(certificateDirectory),
      removedAfterRecordingHashes: true };
    write(path.join(output, 'cleanup-manifest.json'), run.binaryCleanup);
    write(path.join(output, 'run.json'), run);""")
    host = output / 'fresh-host.cjs'
    host.write_text(script)
    identity = implementation()
    plan = {'schemaVersion': 2, 'protocol': PROTOCOL, 'taskId': TASK, 'caseId': case_id,
        'contract': artifacts.artifact(output / 'canonical-contract.json'),
        'canonicalCase': spec, 'source': str(source), 'inputInventory': artifacts.artifact(output / 'input-inventory.json'),
        'evaluator': identity, 'deadlineEpochMs': epoch_ms, 'remainingAtPreparationSeconds': remaining,
        'command': ['/Applications/DevEco-Studio.app/Contents/tools/node/bin/node', str(host),
                    '--output-dir', str(output / 'native-e2e'), '--serial', serial],
        'preparedOnly': True, 'deviceOrModelStarted': False,
        'derivedFiles': [artifacts.artifact(path) for path in sorted(directory.iterdir()) if path.is_file()] + [artifacts.artifact(host)],
        'applicationCompileScope': 'separate source-bound application preflight; packaging is runtimeCompile only',
        'executionRequirements': {'freeBytes': 8 * 1024**3, 'canonicalDeviceLease': True,
            'singleScorerDeadlineIncludesPreparationWaitingAndCleanup': True,
            'hashThenRemoveHapsAndBuildIntermediates': True}}
    core.write(output / 'plan.json', plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--case', required=True, choices=sorted(NATIVE_CASES))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    value = prepare_case(source=args.source, case_id=args.case, output=args.output, deadline=time.monotonic() + 3600)
    print(json.dumps({'preparedOnly': True, 'deviceOrModelStarted': False, 'caseId': value['caseId']}, indent=2))
