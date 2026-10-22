'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { generate } = require('./arkts_native_bundle.cjs');

const root = path.resolve(__dirname, '../..');
const staged = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/12_report_room/transitions.json');
const source = path.join(root, 'final_dev_nodes/12_report_room_final_25_05_4');

function workspace(action) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-contract-override-'));
  const evidence = path.join(work, 'evidence');
  fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true });
  fs.mkdirSync(evidence, { recursive: true });
  try { return action(work, evidence); }
  finally { fs.rmSync(work, { recursive: true, force: true }); }
}

test('single-task native bundle binds the staged contract without changing active metadata', () => {
  workspace((work, evidence) => {
    const manifest = generate(work, evidence, '12_report_room', 'final', source, false,
      { contractOverride: staged });
    assert.equal(manifest.caseCount, 10);
    assert.equal(manifest.contracts.length, 1);
    assert.equal(manifest.contracts[0].file, staged);
    assert.equal(manifest.contracts[0].override, true);
    const active = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/12_report_room/transitions.json')));
    const selected = JSON.parse(fs.readFileSync(staged));
    assert.equal(active.cases[0].setup, undefined);
    assert.equal(selected.cases[0].setup.initialState.screen, 'room_details');
  });
});

test('contract override rejects a contract belonging to another task', () => {
  workspace((work, evidence) => {
    const wrong = path.join(root, 'benchmark_tasks/13_user_verification/transitions.json');
    assert.throws(() => generate(work, evidence, '12_report_room', 'final', source, false,
      { contractOverride: wrong }), /different task/);
  });
});
