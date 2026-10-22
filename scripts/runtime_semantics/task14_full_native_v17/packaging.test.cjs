'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const installer = require('./install.cjs');
const generate = require('../arkts_native_bundle.cjs').generate;
const root = path.resolve(__dirname, '../../..');
const source = path.join(root,
  'experiment_results/runtime_transition_20261021/task14_createroom_boundaries_v6_13/projects/final');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

test('V17 packages checkpoint and physical-route admission without changing production', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-v17-package-'));
  const priorCA = process.env.TASK14_NATIVE_E2E_CA_DER;
  try {
    const work = path.join(temporary, 'work'), evidence = path.join(temporary, 'evidence');
    fs.cpSync(source, work, { recursive: true, filter: file =>
      !new Set(['.git', 'build', '.hvigor', 'oh_modules', 'node_modules']).has(path.basename(file)) });
    fs.cpSync(path.join(root, 'elementx_harmony_full/entry/src/ohosTest'),
      path.join(work, 'entry/src/ohosTest'), { recursive: true });
    fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true });
    fs.mkdirSync(evidence);
    const ca = path.join(temporary, 'ca.der'); fs.writeFileSync(ca, 'task14-v17-offline-ca');
    process.env.TASK14_NATIVE_E2E_CA_DER = ca;
    generate(work, evidence, '14_join_room_by_address', 'agent', source, true,
      { device: true, caseId: 'jr_state_005_found_then_continue_navigates' });
    const report = installer.install(work, { deadlineEpochMs: Date.now() + 60000 });
    assert.equal(report.protocol, 'task14.full-nine-configured-sdk.v17');
    assert.equal(report.productionUnchanged, true);
    assert.equal(report.controlledBoundary.applicationMethodsReplaced, false);
    for (const item of report.production) {
      assert.equal(hash(fs.readFileSync(path.join(source, item.path))), item.sha256, item.path);
      assert.equal(hash(fs.readFileSync(path.join(work, item.path))), item.sha256, item.path);
    }
    for (const item of report.fixtures) {
      assert.equal(hash(fs.readFileSync(path.join(work, item.path))), item.sha256, item.path);
    }
    assert.match(fs.readFileSync(path.join(work, 'entry/src/test/Task14ScalarCasesV17.js'), 'utf8'),
      /trace\(label, clone\(sample\)\)/);
    assert.match(fs.readFileSync(path.join(work, 'entry/src/test/Task14ConfiguredRoutesV17.suite.js'), 'utf8'),
      /pages\/Room/);
  } finally {
    if (priorCA === undefined) delete process.env.TASK14_NATIVE_E2E_CA_DER;
    else process.env.TASK14_NATIVE_E2E_CA_DER = priorCA;
    fs.rmSync(temporary, { recursive: true, force: true });
  }
});
