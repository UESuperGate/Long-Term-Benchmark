'use strict';
// Mutations of retained native evidence only. No device, model or scoring authority.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const home = path.join(root, 'experiment_results/runtime_transition_20261020/task13_page_owner_port_v1');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const policyFile = path.join(home, 'entry_policy_v8/policy.json');
assert.equal(sha(fs.readFileSync(policyFile)), 'f40d2715d7d644944152327032e1f95dda00e0634c10a597d24b4344cb869b2f');
const policy = JSON.parse(fs.readFileSync(policyFile));
const relative = 'state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs';
const pin = policy.producerHashes.find(item => item.relativePath === relative);
const adapterFile = path.join(path.dirname(policyFile), 'frozen', relative);
assert.equal(sha(fs.readFileSync(adapterFile)), pin.sha256);
assert.equal(fs.statSync(adapterFile).size, pin.bytes);
const adapter = require(adapterFile);
const canonicalFile = path.join(root, 'benchmark_tasks/13_user_verification/transitions.json');
assert.equal(sha(fs.readFileSync(canonicalFile)), policy.canonicalContractSha256);
const canonical = JSON.parse(fs.readFileSync(canonicalFile));
function read(record) {
  const file = path.resolve(root, record.path), bytes = fs.readFileSync(file);
  assert.equal(bytes.length, record.bytes); assert.equal(sha(bytes), record.sha256);
  return JSON.parse(bytes);
}
const sameExpected = (actual, expected) => expected && typeof expected === 'object' && !Array.isArray(expected) ?
  !!actual && Object.entries(expected).every(([key, value]) => sameExpected(actual[key], value)) :
  JSON.stringify(actual) === JSON.stringify(expected);
function accepted(spec, ui) {
  const value = adapter.evaluatePageOwner(spec, ui);
  assert.deepEqual(value.invariantChecks.map(item => item.description), spec.invariants);
  return sameExpected(value.observed, spec.expected) && value.invariantChecks.every(item => item.passed === true);
}
const last = ui => ui.frames.find(frame => frame.label === 'after_event').pageObserver;
const mutations = {
  detached_owner: ui => { last(ui).instanceCount = 2; },
  wrong_service_receiver: ui => { last(ui).state.sameService = false; },
  wrong_identity_store: ui => { last(ui).state.sameRoom = false; },
  missing_attach: ui => { last(ui).calls = last(ui).calls.filter(item => item.method !== 'attach'); },
  missing_subscription: ui => { last(ui).ledger = last(ui).ledger.filter(item => item.kind !== 'production_subscribe'); },
  missing_owner_dispose: ui => { ui.ownerCleanup.calls = ui.ownerCleanup.calls.filter(item => item.method !== 'dispose'); },
  missing_unsubscribe: ui => { ui.ownerCleanup.ledger = ui.ownerCleanup.ledger.filter(item => item.kind !== 'production_unsubscribe'); }
};
const hideEntry = ui => { ui.frames.find(frame => frame.label === 'initial_profile').controls.find(item => item.name === 'verify').visible = false; };
const results = [];
for (const label of ['final', 'random_final_agent']) {
  const reportFile = path.join(home, 'controls-v4', label, 'runtime.json');
  const report = JSON.parse(fs.readFileSync(reportFile));
  const execution = read(report.provenance.runtimeEvidence.execution);
  let positives = 0, rejected = 0;
  for (const record of execution.rowArtifacts) {
    const native = read({ path: record.local, bytes: record.bytes, sha256: record.sha256 });
    const spec = canonical.cases.find(item => item.caseId === native.caseId);
    const observations = native.calls.filter(item => item.method === 'Task13Revision5.originalProfileRuntime');
    assert.equal(observations.length, 1);
    const ui = observations[0].observation;
    assert(accepted(spec, ui), native.caseId); positives++;
    const relevant = spec.key === 'identity_violation_surfaces' ? [hideEntry] : [hideEntry, ...Object.values(mutations)];
    for (const mutate of relevant) {
      const changed = JSON.parse(JSON.stringify(ui)); mutate(changed);
      let verdict;
      try { verdict = accepted(spec, changed); } catch (error) {
        assert.match(error.message, /Real common|actual attached|disposal\/unsubscription/i);
        verdict = false;
      }
      assert.equal(verdict, false, 'Mutation accepted: ' + native.caseId);
      rejected++;
    }
  }
  assert.equal(positives, 10); assert.equal(rejected, 73);
  results.push({ label, report: reportFile, reportSha256: sha(fs.readFileSync(reportFile)), positives, rejected });
}
console.log(JSON.stringify({ passed: true,
  tier: 'offline mutations of retained actual native evidence, NOT fresh runtime negative controls',
  canonicalUnmodified: true, pinnedAdapterSha256: pin.sha256, results }, null, 2));
