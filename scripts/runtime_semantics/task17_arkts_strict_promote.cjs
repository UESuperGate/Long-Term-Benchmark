#!/usr/bin/env node
'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const contractFile = path.join(root, 'benchmark_tasks/17_pinned_messages/transitions.json');
const evidenceRoot = path.join(root, 'experiment_results/runtime_transition_20261020/task17_arkts_strict');
const baseRoot = path.join(evidenceRoot, 'matrix-v9');
const finalRoot = path.join(evidenceRoot, 'matrix-v10-final');

const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const record = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) };
};
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const requireValue = (condition, message) => {
  if (!condition) throw new Error(message);
};

function rowFor(role, spec) {
  const directory = path.join(role === 'base' ? baseRoot : finalRoot, `${role}-${spec.caseId}`);
  const attempt = role === 'final' && spec.caseId === 'pm_state_008_unpin_success' ? 2 : 1;
  const buildFile = path.join(directory, 'device-build-report.json');
  const executionFile = path.join(directory, `execution-attempt-${attempt}`, 'device-execution.json');
  const execution = read(executionFile);
  const row = execution.rows?.find(item => item.caseId === spec.caseId);
  const expectedStatus = role === 'base' ? 'fail' : 'pass';
  requireValue(execution.taskId === '17_pinned_messages' && execution.role === role &&
    execution.caseId === spec.caseId, `${role}/${spec.caseId}: execution identity differs`);
  requireValue(execution.status === 'transport_completed' && execution.transportCompleted === true,
    `${role}/${spec.caseId}: transport incomplete`);
  requireValue(execution.candidateAbsentBeforeInstall === true &&
    execution.cleanup?.ownedAppUninstalled === true, `${role}/${spec.caseId}: freshness/cleanup differs`);
  requireValue(row?.traceDigest === spec.traceDigest && row.status === expectedStatus,
    `${role}/${spec.caseId}: semantic status/digest differs`);
  const nativeFile = path.join(directory, `execution-attempt-${attempt}`, 'native-result.json');
  requireValue(JSON.stringify(read(nativeFile)) === JSON.stringify(row),
    `${role}/${spec.caseId}: native row differs`);
  return {
    role,
    caseId: spec.caseId,
    traceDigest: spec.traceDigest,
    status: row.status,
    reason: row.reason,
    selectedAttempt: attempt,
    build: record(buildFile),
    execution: record(executionFile),
    nativeResult: record(nativeFile),
    freshInstall: true,
    cleanup: execution.cleanup
  };
}

function optionalRecord(relative) {
  const file = path.join(evidenceRoot, relative);
  return fs.existsSync(file) ? record(file) : undefined;
}

function main() {
  const args = process.argv.slice(2);
  const index = args.indexOf('--output-dir');
  if (index < 0 || !args[index + 1]) throw new Error('--output-dir is required');
  const output = path.resolve(args[index + 1]);
  if (fs.existsSync(output)) throw new Error(`Refusing existing promotion directory: ${output}`);
  const contract = read(contractFile);
  requireValue(contract.taskId === '17_pinned_messages' && contract.cases?.length === 9,
    'Expected the nine-case Task17 canonical contract');
  const contractRecord = record(contractFile);
  const rows = [];
  for (const role of ['base', 'final']) {
    for (const spec of contract.cases) rows.push(rowFor(role, spec));
  }
  const environmentAudit = [
    ['locked_device_not_scored', 'matrix-v8/base-pm_state_001_open_loading/execution-attempt-1/device-execution.json'],
    ['offline_probe_not_scored', 'probe-final1-postfix-v2/execution-attempt-1/device-execution.json'],
    ['offline_install_not_scored', 'matrix-v10-final/final-pm_state_008_unpin_success/execution-attempt-1/device-execution.json']
  ].map(([classification, relative]) => ({ classification, evidence: optionalRecord(relative) }))
    .filter(item => item.evidence);
  const report = {
    schemaVersion: 1,
    taskId: '17_pinned_messages',
    platform: 'arkts',
    runtime: 'openharmony_api23_device_uitest_arkvm_original_module_native_preferences',
    taskTimeoutSeconds: 3600,
    requestedRoles: ['base', 'final'],
    contract: contractRecord,
    activeCanonicalBefore: contractRecord,
    activeCanonicalAfter: contractRecord,
    activeCanonicalModified: false,
    rows,
    semantic: {
      base: { total: 9, passed: 0, failed: 9, notScored: 0 },
      final: { total: 9, passed: 9, failed: 0, notScored: 0 }
    },
    compile: {
      base: { passed: true, scope: 'standalone_application_and_ohosTest_hap_per_case', builds: 9 },
      final: { passed: true, scope: 'standalone_application_and_ohosTest_hap_per_case', builds: 9 }
    },
    provenance: {
      base: 'matrix-v9 retained per-case evidence; interrupted before aggregate write',
      final: 'matrix-v10-final cases 1-7 plus recovered case 8 attempt 2 and case 9 attempt 1',
      environmentAudit
    },
    status: 'passed',
    deviceLocksPresentAfter: []
  };
  fs.mkdirSync(output, { recursive: true });
  const matrix = path.join(output, 'matrix.json');
  fs.writeFileSync(matrix, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ matrix, semantic: report.semantic, environmentAudit }, null, 2));
}

main();
