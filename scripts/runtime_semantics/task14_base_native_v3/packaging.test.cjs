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
const source = path.join(root, 'experiment_results/runtime_transition_20261021/task14_base_internet_v1/project');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

test('base V3 packages prepared-page acquisition without changing production', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-base-v3-package-'));
  const priorCA = process.env.TASK14_NATIVE_E2E_CA_DER;
  try {
    const work = path.join(temporary, 'work'), evidence = path.join(temporary, 'evidence');
    fs.cpSync(source, work, { recursive: true, filter: file =>
      !new Set(['.git', 'build', '.hvigor', 'oh_modules', 'node_modules']).has(path.basename(file)) });
    fs.cpSync(path.join(root, 'elementx_harmony_full/entry/src/ohosTest'),
      path.join(work, 'entry/src/ohosTest'), { recursive: true });
    fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true });
    fs.mkdirSync(evidence);
    const ca = path.join(temporary, 'ca.der'); fs.writeFileSync(ca, 'task14-base-v3-offline-ca');
    process.env.TASK14_NATIVE_E2E_CA_DER = ca;
    generate(work, evidence, '14_join_room_by_address', 'base', source, true,
      { device: true, caseId: 'jr_state_001_entry_opens_address_flow' });
    const report = installer.install(work, { deadlineEpochMs: Date.now() + 60000 });
    assert.equal(report.protocol, 'task14.base-entry-absence.v3');
    assert.equal(report.config.preparedForegroundEntry, true);
    assert.equal(report.productionUnchanged, true);
    for (const item of report.production) {
      assert.equal(hash(fs.readFileSync(path.join(source, item.path))), item.sha256, item.path);
      assert.equal(hash(fs.readFileSync(path.join(work, item.path))), item.sha256, item.path);
    }
    for (const item of report.fixtures) {
      assert.equal(hash(fs.readFileSync(path.join(work, item.path))), item.sha256, item.path);
    }
  } finally {
    if (priorCA === undefined) delete process.env.TASK14_NATIVE_E2E_CA_DER;
    else process.env.TASK14_NATIVE_E2E_CA_DER = priorCA;
    fs.rmSync(temporary, { recursive: true, force: true });
  }
});
