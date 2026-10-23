import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const tools = path.dirname(new URL(import.meta.url).pathname);
const migrations = path.resolve(tools, '..');
const read = relative => fs.readFileSync(path.join(migrations, relative), 'utf8');
const checks = [];
const check = (name, passed, detail) => checks.push({ name, passed, detail });
const includes = (text, values) => values.every(value => text.includes(value));

const mediaFinal = read('01_media_keyboard/android/evaluator/final/ImmutableMediaProbe.kt');
const mediaBase = read('01_media_keyboard/android/evaluator/base/ImmutableMediaProbe.kt');
const mediaScorer = read('01_media_keyboard/android/evaluator/run-semantic.mjs');
const stickerFinal = read('02_sticker_management/android/evaluator/final/ImmutableStickerProbe.kt');
const stickerBase = read('02_sticker_management/android/evaluator/base/ImmutableStickerBaseProbe.kt');
const stickerRuntimeGate = read('02_sticker_management/android/evaluator/runtime-gate/MandatoryStickerContractProbe.kt');
const stickerScorer = read('02_sticker_management/android/evaluator/run-semantic.mjs');
const stickerFinalDatabase = read('02_sticker_management/android/final/stubs/org/thoughtcrime/securesms/database/DatabaseLeaves.kt');
const stickerBaseDatabase = read('02_sticker_management/android/base/stubs/org/thoughtcrime/securesms/database/DatabaseLeaves.kt');
const prepare = read('tools/prepare_agent_harness.mjs');
const agentBuild = read('tools/build_android_agent_harness.sh');
const deviceRunner = read('tools/run_android_device_semantic.mjs');

check('media final never invokes reducer helper directly', !/\bapplyEvent\s*\(/.test(mediaFinal), 'events must enter application-owned owners');
check('media final never constructs reducer state', !/\b(?:MediaKeyboardState|GifPageState)\s*\(/.test(mediaFinal), 'given must come from leaves or production transitions');
check('media final invokes production owners', includes(mediaFinal, ['MediaKeyboardViewModel', 'GifPageViewModel', '.onEvent(', 'controller.confirm']), 'ViewModel/controller entrypoints are required');
check('media final reads controller confirmation state', mediaFinal.includes('confirmationState(controller)'), 'after must be read from the controller');
check('media base proves a reachable production prefix', includes(mediaBase, ['controller.show(', 'missing_canonical_transition_after_reachable_prefix', 'prefixReached']), 'base failures require a real common prefix');
check('media scorer validates given and observation cardinality', includes(mediaScorer, ['const givenPassed', 'invalid_runtime_observation_set', 'terminalPrefixPassed']), 'invalid setup or duplicate/missing cases cannot score');

check('sticker final uses production ViewModel/repository entrypoints', includes(stickerFinal, ['StickerManagementViewModel', 'StickerManagementRepository', 'toggleSelection(', 'installStickerPack(']), 'canonical events must enter application owners');
check('sticker final reopens persistent backing', includes(stickerFinal, ['reopenBacking()', 'reopenedInstalledPackIds']), 'drop persistence must survive a fresh table instance');
check('sticker download effect comes from observation leaf', includes(stickerFinal, ['DownloadStatusObservationLeaf', 'collect(observationLeaf::onState)', 'observationLeaf.calls.toList()']), 'the evaluator must not synthesize a clear-status effect');
check('sticker install timeline drains production state before leaf return', includes(stickerFinal, ['CountDownLatch', 'inProgressObserved.await', 'recordAsynchronousEffect', 'recordInlineEffect', 'statusAtEffect']), 'both external-leaf scheduling models must observe IN_PROGRESS before the install effect');
check('sticker evaluator has no direct observable state write', !/\.value\s*=(?!=)/.test(stickerFinal), 'after must come from production state');
check('sticker final backing is file persisted', includes(stickerFinalDatabase, ['DataInputStream', 'DataOutputStream', 'backingFile']), 'persistence cannot be memory-only');
check('sticker base backing is file persisted', includes(stickerBaseDatabase, ['DataInputStream', 'DataOutputStream', 'backingFile']), 'base and final must use equivalent external input shape');
check('sticker base reports missing canonical transitions', includes(stickerBase, ['missing_canonical_transition_after_reachable_prefix', 'prefixReached']), 'base verdict must follow a real legacy prefix');
check('sticker scorer validates given and observation cardinality', includes(stickerScorer, ['const givenPassed', 'invalid_runtime_observation_set', 'terminalPrefixPassed']), 'invalid setup or duplicate/missing cases cannot score');
check('sticker public bridge observes job order without final-only leaf ABI', includes(stickerFinal, ['installBeforeJobAddHook', 'BeforeAddList', 'setBeforeAdd', 'recordAsynchronousEffect', 'recordInlineEffect', 'statusAtEffect']) && !includes(stickerFinal, ['RuntimeTrace', 'jobManager.beforeAdd']), 'both asynchronous and inline external leaves must prove IN_PROGRESS before the install effect');
check('sticker public bridge records unreachable givens after a real owner prefix', includes(stickerFinal, ['emitReachableTransitionFailure', 'canonical_given_unreachable_after_executed_production_prefix', 'StickerManagementViewModel.installStickerPack']), 'candidate semantic defects must not abort the remaining runtime cases');
check('sticker install probes wait for production callbackFlow registration', (stickerFinal.match(/callbackFlow|production repository owns the external database notification leaf/g) ?? []).length >= 2, 'database events must reach the current production owner rather than a prior testcase owner');
check('sticker chained given uses bounded public-state synchronization', includes(stickerFinal, ['waitUntilObserved', 'canonicalGivenReached', 'downloadStatus(vm.uiState.value, "p1") == "DOWNLOADED"']), 'final async projection may settle while candidates that cannot establish the given become scored failures');
check('sticker missing public ABI is measured in the Android app runtime', includes(stickerRuntimeGate, ['application.javaClass.classLoader', 'Class.forName', 'mandatory_public_integration_contract_unavailable_after_app_launch', 'missingDeclarations']) && !includes(stickerRuntimeGate, ['java.io.File', 'readText', 'exists']), 'fail-closed capability evidence must come from the installed app process');
check('sticker runtime gate cannot pass a compatible candidate', stickerRuntimeGate.includes('The public sticker integration ABI is present; the executable state bridge must handle this candidate'), 'a compatible public ABI must execute the state/effect/persistence bridge');
check('sticker scorer admits only validated runtime terminal failures', includes(stickerScorer, ['terminalCapabilityFailurePassed', 'terminalReachableGivenFailurePassed', 'executed_android_application_runtime_capability_gate', 'mandatory_public_integration_contract_unavailable_in_android_app_runtime']), 'missing public ABI and unreachable canonical givens remain scored while malformed evidence remains unscored');

check('agent adapter binds the public integration contract', includes(prepare, ['bindingContract', 'compile_compatible_public_action_bridge_without_source_role_inference', 'integration_contract.md']), 'formal agent binding must be contract based');
check('agent adapter carries compile-compatible production bridges', includes(prepare, ['public-integration-contract', 'reachable-legacy-production-prefix', 'mandatory-public-abi-runtime-gate', 'sourceDirectory', 'probeMainClass']), 'candidate binding must be selected by ABI compatibility');
check('agent build selects by compilation rather than source inspection', includes(agentBuild, ['bindingContract?.candidates', 'first_compile_compatible_public_action_bridge', 'EVALUATOR_SRC="$source"']) && !/rg |grep |find .*immutable-src/.test(agentBuild), 'candidate source shape must not decide the bridge');
check('agent adapter does not infer role from a marker filename', !prepare.includes('finalMarker') && !prepare.includes('existsSync(finalMarker)'), 'role selection may only use the explicit probe profile');
check('device runner consumes prepared runtime binding', includes(deviceRunner, ['PREPARED', 'probeMainClass']), 'runtime main class must come from adapter output');
check('device runner preserves per-report agent observations', includes(deviceRunner, ["role === 'agent'", 'outputStem', '.observations.jsonl', '.transport.json']), 'later controls must not overwrite a formal agent runtime receipt');

for (const result of checks) {
  process.stdout.write(`${result.passed ? 'PASS' : 'FAIL'} ${result.name}: ${result.detail}\n`);
}
const failed = checks.filter(result => !result.passed);
process.stdout.write(`SUMMARY ${checks.length - failed.length}/${checks.length} checks passed\n`);
const outputIndex = process.argv.indexOf('--output');
if (outputIndex >= 0) {
  const output = path.resolve(process.argv[outputIndex + 1]);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify({
    schemaVersion: 1,
    platform: 'android',
    scope: ['01_media_keyboard', '02_sticker_management', 'tools/agent-runtime-binding'],
    passed: checks.length - failed.length,
    failed: failed.length,
    total: checks.length,
    checks
  }, null, 2)}\n`);
}
process.exit(failed.length === 0 ? 0 : 1);
