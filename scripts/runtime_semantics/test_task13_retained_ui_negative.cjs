'use strict';
// Offline mutations of retained native trees, never additional device execution.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const home = path.join(root, 'experiment_results/runtime_transition_20261020/task13_page_owner_port_v1');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const policyPath = path.join(home, 'entry_policy_v8/policy.json');
assert.equal(sha(fs.readFileSync(policyPath)), 'f40d2715d7d644944152327032e1f95dda00e0634c10a597d24b4344cb869b2f');
const policy = JSON.parse(fs.readFileSync(policyPath));
function frozen(relative) {
  const record = policy.producerHashes.find(item => item.relativePath === relative);
  const file = path.join(path.dirname(policyPath), 'frozen', relative);
  const bytes = fs.readFileSync(file);
  assert.equal(bytes.length, record.bytes); assert.equal(sha(bytes), record.sha256);
  return require(file);
}
const adapter = frozen('state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs');
const closure = frozen('state_tests/runtime/arkts/native/Task13UiClosure.cjs');
const contractPath = path.join(root, 'benchmark_tasks/13_user_verification/transitions.json');
assert.equal(sha(fs.readFileSync(contractPath)), policy.canonicalContractSha256);
const contract = JSON.parse(fs.readFileSync(contractPath));
const clone = value => JSON.parse(JSON.stringify(value));
function checked(record) {
  const file = path.resolve(root, record.path);
  const bytes = fs.readFileSync(file);
  assert.equal(bytes.length, record.bytes); assert.equal(sha(bytes), record.sha256);
  return JSON.parse(bytes);
}
const mutations = {
  renamed_control(inventory) { inventory.nodes.find(item => item.id).id = 'unknown_renamed_control'; },
  extra_named_control(inventory) {
    inventory.nodes.push({ ...inventory.nodes.find(item => item.id), id: 'additional_candidate_action' });
    inventory.nodeCount++;
  },
  anonymous_action(inventory) {
    inventory.nodes.push({ ...inventory.nodes.find(item => item.id), id: '', type: 'Button', text: 'Alternate verify',
      clickable: true, enabled: true }); inventory.nodeCount++;
  },
  incomplete_tree(inventory) { inventory.complete = false; },
  truncated_tree(inventory) { inventory.nodeCount++; }
};
const reports = process.argv.slice(2);
if (!reports.length) reports.push(...['base', 'final'].map(role => path.join(home, 'controls-v4', role, 'runtime.json')));
const results = [];
for (const reportFile of reports) {
  const report = JSON.parse(fs.readFileSync(reportFile));
  const evidence = report.provenance.runtimeEvidence;
  const execution = checked(evidence.execution), build = checked(evidence.build);
  const final = build.nativeUIObserver.role === 'final';
  assert(['base', 'final'].includes(build.nativeUIObserver.role));
  let positives = 0, killed = 0;
  for (const artifact of execution.rowArtifacts) {
    const native = checked({ path: artifact.local, bytes: artifact.bytes, sha256: artifact.sha256 });
    const spec = contract.cases.find(item => item.caseId === native.caseId);
    const observations = native.calls.filter(call => call.method === 'Task13Revision5.originalProfileRuntime');
    assert.equal(observations.length, 1);
    const ui = observations[0].observation;
    if (!final && spec.key === 'identity_violation_surfaces') continue;
    const validate = raw => final ? adapter.evaluatePageOwner(spec, raw) :
      raw.frames.forEach(frame => closure.validate(frame.uiInventory));
    validate(ui); positives++;
    for (const mutate of Object.values(mutations)) {
      const changed = clone(ui);
      mutate(changed.frames[0].uiInventory);
      assert.throws(() => validate(changed), /Unknown|Unreviewed|Incomplete|Unbound/i);
      killed++;
    }
  }
  assert.equal(positives, final ? 10 : 9);
  results.push({ report: path.resolve(reportFile), reportSha256: sha(fs.readFileSync(reportFile)),
    callerRoleAuditOnly: report.role, actualBinding: build.nativeUIObserver.role,
    actualNativePositiveControls: positives, unknownUiMutationsKilled: killed });
}
console.log(JSON.stringify({ passed: true, tier: 'offline frozen-producer native-tree mutation test; no scoring authority',
  policySha256: sha(fs.readFileSync(policyPath)), canonicalSha256: sha(fs.readFileSync(contractPath)),
  mutations: Object.keys(mutations), results }, null, 2));
