#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const sharedBuilder = path.join(__dirname, 'arkts_native_device.cjs');
const sharedSmoke = path.join(__dirname, 'arkts_native_smoke.cjs');
const sharedBundle = path.join(__dirname, 'arkts_native_bundle.cjs');
const contract = path.join(root, 'benchmark_tasks/16_identity_reset/transitions.json');
const auditedContract = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_5_task16/after/transitions.json');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) };
};

function value(args, flag) {
  const index = args.indexOf(flag);
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
  return args[index + 1];
}

function deriveBuilder(original) {
  const oldInstaller = "const installer = taskId === '16_identity_reset' &&\n            ['ir_state_005_oidc_handle_routes_and_resets', 'ir_state_010_cancel_cleans_up'].includes(caseId)\n            ? 'Task16NativeUi.install.cjs' : taskId === '17_pinned_messages' && caseId === 'pm_state_001_open_loading'\n              ? 'Task17LoadingUi.install.cjs' : 'Tasks16_18NativeUi.install.cjs';";
  const newInstaller = "const installer = taskId === '16_identity_reset'\n            ? 'Task16Revision5.install.cjs' : taskId === '17_pinned_messages' && caseId === 'pm_state_001_open_loading'\n              ? 'Task17LoadingUi.install.cjs' : 'Tasks16_18NativeUi.install.cjs';";
  const oldTask16Block = oldInstaller + "\n          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work);";
  const newTask16Block = newInstaller + "\n          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work, role);";
  const derived = original
    .replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';')
    .replace("require('./arkts_native_smoke.cjs')", 'require(' + JSON.stringify(sharedSmoke) + ')')
    .replace("require('./arkts_native_bundle.cjs')", 'require(' + JSON.stringify(sharedBundle) + ')')
    .replace('{ device: true, caseId });', '{ device: true, caseId, contractOverride: ' + JSON.stringify(contract) + ' });')
    .replace(oldTask16Block, newTask16Block);
  if (derived === original || !derived.includes(newTask16Block) || derived.includes(oldInstaller) ||
      !derived.includes('contractOverride: ' + JSON.stringify(contract)) ||
      derived.includes("'Task12PartialUi.install.cjs' : 'Tasks12_15NativeUi.install.cjs';\n          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work, role);")) {
    throw new Error('Shared builder shape changed; refusing unbound Task16 derivation');
  }
  return derived;
}

function main() {
  const args = process.argv.slice(2);
  const output = path.resolve(value(args, '--output-dir'));
  const source = path.resolve(value(args, '--source'));
  const role = value(args, '--role');
  const caseId = value(args, '--case');
  if (!['base', 'final', 'agent'].includes(role)) throw new Error('Task16 revision5 accepts base/final/agent only');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task16 build evidence: ' + output);
  const staged = JSON.parse(fs.readFileSync(contract));
  if (staged.taskId !== '16_identity_reset' || staged.revision !== 5 ||
      !staged.cases.some(item => item.caseId === caseId)) throw new Error('Invalid staged Task16 revision5 case');
  if (fileRecord(contract).sha256 !== fileRecord(auditedContract).sha256) {
    throw new Error('Canonical Task16 contract differs from audited revision 5');
  }
  fs.mkdirSync(output, { recursive: true });

  const original = fs.readFileSync(sharedBuilder, 'utf8');
  const derived = deriveBuilder(original);
  const derivedBuilder = path.join(output, 'task16-revision5-builder.generated.cjs');
  fs.writeFileSync(derivedBuilder, derived);
  const command = [derivedBuilder, '--source', source, '--task', '16_identity_reset', '--fixture', 'bundle',
    '--role', role, '--case', caseId, '--native-ui', '--output-dir', output];
  const run = spawnSync(process.execPath, command, {
    cwd: root,
    encoding: 'utf8',
    timeout: 600000,
    maxBuffer: 8 * 1024 * 1024
  });
  fs.writeFileSync(path.join(output, 'build-command.log'), (run.stdout || '') + (run.stderr || ''));
  if (run.error || run.status !== 0) throw new Error('Task16 revision5 build failed: ' + (run.error || run.status));

  const reportFile = path.join(output, 'device-build-report.json');
  const report = JSON.parse(fs.readFileSync(reportFile));
  const bundleManifest = JSON.parse(fs.readFileSync(path.join(output, 'bundle-manifest.json')));
  const contractRecord = bundleManifest.contracts.find(item => item.taskId === '16_identity_reset');
  if (report.status !== 'built_not_executed' || report.runtimeCompile?.passed !== true ||
      report.productionUnchanged !== true || report.copiedProductionUnchanged !== true ||
      report.temporaryProjectRemoved !== true || report.caseId !== caseId ||
      contractRecord?.override !== true || path.resolve(contractRecord.file) !== contract ||
      contractRecord.sha256 !== fileRecord(contract).sha256 || report.nativeUIObserver?.productionUnchanged !== true ||
      report.nativeUIObserver?.evaluatorRole !== role ||
      report.nativeUIObserver?.behaviorClassification !== 'runtime_entry_only_for_agent') {
    throw new Error('Task16 revision5 build provenance is incomplete');
  }
  report.task16Revision5 = {
    schemaVersion: 1,
    role,
    caseId,
    activeCanonicalPromoted: true,
    canonicalContract: fileRecord(contract),
    auditedContract: fileRecord(auditedContract),
    wrapper: fileRecord(__filename),
    sharedBuilder: fileRecord(sharedBuilder),
    generatedBuilder: fileRecord(derivedBuilder)
  };
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: report.status, role, caseId, reportFile }, null, 2));
}

if (require.main === module) {
  try { main(); }
  catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
}

module.exports = { deriveBuilder };
