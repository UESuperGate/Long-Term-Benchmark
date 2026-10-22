#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

function validate(reportFile, policyFile, usedObservationIds = []) {
  const report = JSON.parse(fs.readFileSync(reportFile, 'utf8'));
  const policy = JSON.parse(fs.readFileSync(policyFile, 'utf8'));
  if (!/^\d\d_[a-z_]+$/.test(policy.taskId)) throw new Error('Invalid policy task');
  const contractFile = path.join(root, 'benchmark_tasks', policy.taskId, 'transitions.json');
  const contract = JSON.parse(fs.readFileSync(contractFile, 'utf8'));
  const spec = contract.cases.find(item => item.caseId === policy.caseId);
  if (!spec) throw new Error('Unknown canonical case');
  const errors = [];
  const check = (condition, reason) => { if (!condition) errors.push(reason); };
  check(report.taskId === policy.taskId && report.entryRequest?.provenance?.contractSha256 === hash(contractFile), 'Canonical contract provenance differs');
  check(report.nativeRuntimeExecuted === true && report.runtime === 'native_previewer_arkvm_hypium', 'Native runtime was not established');
  check(report.nativeProcess?.command?.includes('/previewer/common/bin/Previewer ') &&
    report.nativeProcess?.arkRuntimeLibraries?.some(file => file.endsWith('/libark_jsruntime.dylib')), 'Native process/library evidence missing');
  check(report.bytecode?.sha256 && hash(report.bytecode.file) === report.bytecode.sha256, 'Bytecode digest differs');
  check(report.nativeLogSha256 && hash(report.nativeLog) === report.nativeLogSha256, 'Native log digest differs');
  const source = path.join(report.source, report.productionFile);
  check(report.productionUnchanged === true && report.sourceSha256 === hash(source), 'Current production differs from the executed page');
  if (policy.approval === 'approved') {
    check(path.resolve(root, policy.reviewedSourceRoot || '') === path.resolve(report.source), 'Reviewed candidate root differs');
    const closure = policy.reviewedSourceClosure || [];
    check(closure.length > 0, 'Reviewed entry source closure missing');
    for (const entry of closure) {
      const file = path.resolve(report.source, entry.path);
      check(file.startsWith(path.resolve(report.source) + path.sep) && hash(file) === entry.sha256,
        'Reviewed source closure changed: ' + entry.path);
    }
  }
  const fragments = [];
  let expectedChunks = 0;
  for (const line of fs.readFileSync(report.nativeLog, 'utf8').split('\n')) {
    const marker = 'ARKTS_NATIVE_PLATFORM_CHUNK ';
    const start = line.indexOf(marker);
    if (start < 0) continue;
    const fragment = JSON.parse(line.slice(start + marker.length));
    check(Number.isInteger(fragment.index) && fragment.index >= 0 && fragment.index < fragment.chunks &&
      (!expectedChunks || expectedChunks === fragment.chunks) && fragments[fragment.index] === undefined,
    'Invalid or repeated native evidence fragment');
    expectedChunks = fragment.chunks;
    fragments[fragment.index] = fragment.text;
  }
  check(expectedChunks > 0 && fragments.filter(part => part !== undefined).length === expectedChunks, 'Incomplete native log record');
  let logged;
  try { logged = JSON.parse(fragments.join('')).entryAssertion; }
  catch (error) { errors.push('Native assertion cannot be reconstructed: ' + String(error)); }
  check(!!logged && JSON.stringify(logged) === JSON.stringify(report.platform?.entryAssertion), 'Report assertion differs from native log');
  const context = vm.createContext({});
  const validatorFile = path.join(root, 'state_tests/runtime/arkts/native/entry-assertion.js');
  vm.runInContext(fs.readFileSync(validatorFile, 'utf8').replace(/^export /gm, ''), context, { timeout: 1000 });
  const binding = { taskId: policy.taskId, role: report.role, sourceSha256: hash(source), policySha256: hash(policyFile) };
  const assessment = context.assessEntryAssertion(logged?.assertion, spec, policy, binding, usedObservationIds);
  errors.push(...assessment.errors);
  return { schemaVersion: 1, taskId: policy.taskId, role: report.role, caseId: spec.caseId, traceDigest: spec.traceDigest,
    status: errors.length ? 'not_scored' : 'fail', failPhase: errors.length ? null : 'entry', errors,
    report: path.resolve(reportFile), policy: path.resolve(policyFile), validatorSha256: hash(validatorFile),
    postStateEvaluated: false, invariantsEvaluated: false,
    observationIds: logged?.assertion?.probes.map(probe => probe.observationId) || [] };
}

if (require.main === module) {
  try {
    const args = process.argv.slice(2);
    const value = flag => {
      const index = args.indexOf(flag);
      if (index < 0 || !args[index + 1]) throw new Error('--report FILE --policy FILE are required');
      return args[index + 1];
    };
    console.log(JSON.stringify(validate(value('--report'), value('--policy')), null, 2));
  } catch (error) { console.error(String(error)); process.exitCode = 1; }
}
module.exports = { validate };
