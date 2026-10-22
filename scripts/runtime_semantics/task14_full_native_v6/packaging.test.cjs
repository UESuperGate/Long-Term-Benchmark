'use strict';
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '../../..');
const installer = require('./install.cjs');
const generate = require('../arkts_native_bundle.cjs').generate;
const source = path.join(root,
  'experiment_results/runtime_transition_20261021/task14_createroom_boundaries_v6_11/projects/final');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const excluded = new Set(['.git', 'build', '.hvigor', 'oh_modules', 'node_modules']);

function withWork(run) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-full-native-v6-offline-'));
  const previousCA = process.env.TASK14_NATIVE_E2E_CA_DER;
  try {
    const work = path.join(temporary, 'work');
    const evidence = path.join(temporary, 'evidence');
    const ca = path.join(temporary, 'task14-ca.der');
    fs.cpSync(source, work, { recursive: true, filter: file => !excluded.has(path.basename(file)) });
    fs.cpSync(path.join(root, 'elementx_harmony_full/entry/src/ohosTest'),
      path.join(work, 'entry/src/ohosTest'), { recursive: true });
    fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true });
    fs.mkdirSync(evidence);
    fs.writeFileSync(ca, Buffer.from('offline-task14-ca-fixture'));
    process.env.TASK14_NATIVE_E2E_CA_DER = ca;
    generate(work, evidence, '14_join_room_by_address', 'agent', source, true,
      { device: true, caseId: 'jr_state_002_update_trims_and_debounces' });
    return run(work);
  } finally {
    if (previousCA === undefined) delete process.env.TASK14_NATIVE_E2E_CA_DER;
    else process.env.TASK14_NATIVE_E2E_CA_DER = previousCA;
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

test('V6.11 final packages configured SDK/HTTPS evaluator without changing production', () => withWork(work => {
  const report = installer.install(work, { deadlineEpochMs: Date.now() + 60000 });
  assert.equal(report.productionUnchanged, true);
  assert.equal(report.protocol, 'task14.full-nine-configured-sdk.v6');
  assert.equal(report.controlledBoundary.applicationMethodsReplaced, false);
  assert.equal(report.controlledBoundary.externalLeaf, 'matrix_sdk::Client.resolve_room_alias');
  assert.equal(report.config.entryRoute, 'pages/StartChat');
  assert.match(report.config.configuredRoomsModuleUrl, /ConfiguredSessionRooms$/);
  assert.match(report.config.nativeBridgeModuleUrl, /AddonNativeMatrixBridge$/);
  assert.equal(report.e2e.testPermission, 'ohos.permission.ACCESS_CERT_MANAGER');
  assert.equal(hash(fs.readFileSync(path.join(work, report.e2e.installedPath))), report.e2e.caSha256);
  for (const item of report.production) {
    assert.equal(hash(fs.readFileSync(path.join(source, item.path))), item.sha256, item.path);
    assert.equal(hash(fs.readFileSync(path.join(work, item.path))), item.sha256, item.path);
  }
  const observer = fs.readFileSync(path.join(work, 'entry/src/test/Task14JoinOwnerV3.js'), 'utf8');
  assert.match(observer, /nativeDescriptor\.value\.call\(this, handle, alias\)/);
  assert.doesNotMatch(observer, /NativeDataOperationResult|new Promise\(resolve =>/);
  const bridge = fs.readFileSync(path.join(work, 'entry/src/test/Task14DeviceUi.js'), 'utf8');
  assert.match(bridge, /createTask14NativeE2E/);
  assert.match(bridge, /ports\.providerControl = e2e\.control/);
  const expected = JSON.parse(cp.execFileSync('python3', ['-B', '-c',
    'import json; from scripts.runtime_semantics.task14_full_native_packaging_v6 import expected_fixtures; print(json.dumps(expected_fixtures()))'],
  { cwd: root, env: { ...process.env, PYTHONPATH: 'scripts:.' }, encoding: 'utf8', timeout: 10000 }));
  const order = (left, right) => left.name.localeCompare(right.name);
  assert.deepEqual(report.fixtures.map(item => ({ name: path.basename(item.path), sha256: item.sha256 })).sort(order),
    expected.sort(order));
}));
