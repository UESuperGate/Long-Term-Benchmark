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
const contract = path.join(root, 'benchmark_tasks/17_pinned_messages/transitions.json');
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
  const newInstaller = "const installer = taskId === '17_pinned_messages'\n            ? 'Task17StrictNativeUi.install.cjs' : taskId === '16_identity_reset' &&\n            ['ir_state_005_oidc_handle_routes_and_resets', 'ir_state_010_cancel_cleans_up'].includes(caseId)\n            ? 'Task16NativeUi.install.cjs' : 'Tasks16_18NativeUi.install.cjs';";
  const oldTask17Block = oldInstaller + "\n          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work);";
  const newTask17Block = newInstaller + "\n          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work, role);";
  const derived = original
    .replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';')
    .replace("require('./arkts_native_smoke.cjs')", 'require(' + JSON.stringify(sharedSmoke) + ')')
    .replace("require('./arkts_native_bundle.cjs')", 'require(' + JSON.stringify(sharedBundle) + ')')
    .replace(oldTask17Block, newTask17Block);
  if (derived === original || !derived.includes(newTask17Block) || derived.includes(oldInstaller) ||
      derived.includes("'Task12PartialUi.install.cjs' : 'Tasks12_15NativeUi.install.cjs';\n          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work, role);")) {
    throw new Error('Shared builder shape changed; refusing unbound Task17 derivation');
  }
  return derived;
}

function main() {
  const args = process.argv.slice(2);
  const output = path.resolve(value(args, '--output-dir'));
  const source = path.resolve(value(args, '--source'));
  const role = value(args, '--role');
  const caseId = value(args, '--case');
  if (!['base', 'final', 'agent'].includes(role)) throw new Error('Task17 strict build accepts base/final/agent only');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task17 build evidence: ' + output);
  const canonical = JSON.parse(fs.readFileSync(contract));
  if (canonical.taskId !== '17_pinned_messages' || canonical.cases.length !== 9 ||
      !canonical.cases.some(item => item.caseId === caseId)) throw new Error('Invalid canonical Task17 case');
  fs.mkdirSync(output, { recursive: true });

  const original = fs.readFileSync(sharedBuilder, 'utf8');
  const derived = deriveBuilder(original);
  const derivedBuilder = path.join(output, 'task17-strict-builder.generated.cjs');
  fs.writeFileSync(derivedBuilder, derived);
  const command = [derivedBuilder, '--source', source, '--task', '17_pinned_messages', '--fixture', 'bundle',
    '--role', role, '--case', caseId, '--native-ui', '--output-dir', output];
  const run = spawnSync(process.execPath, command, { cwd: root, encoding: 'utf8', timeout: 600000,
    maxBuffer: 12 * 1024 * 1024 });
  fs.writeFileSync(path.join(output, 'build-command.log'), (run.stdout || '') + (run.stderr || ''));
  if (run.error || run.status !== 0) throw new Error('Task17 strict build failed: ' + (run.error || run.status));

  const reportFile = path.join(output, 'device-build-report.json');
  const report = JSON.parse(fs.readFileSync(reportFile));
  const bundleManifest = JSON.parse(fs.readFileSync(path.join(output, 'bundle-manifest.json')));
  const contractRecord = bundleManifest.contracts.find(item => item.taskId === '17_pinned_messages');
  if (report.status !== 'built_not_executed' || report.runtimeCompile?.passed !== true ||
      report.productionUnchanged !== true || report.copiedProductionUnchanged !== true ||
      report.temporaryProjectRemoved !== true || report.caseId !== caseId ||
      path.resolve(contractRecord?.file || '') !== contract || contractRecord?.sha256 !== fileRecord(contract).sha256 ||
      report.nativeUIObserver?.productionUnchanged !== true ||
      report.nativeUIObserver?.binding?.evaluatorRole !== role ||
      report.nativeUIObserver?.binding?.behaviorClassification !== 'runtime_ui_entry') {
    throw new Error('Task17 strict build provenance is incomplete');
  }
  const applicationHaps = report.haps.filter(item => path.basename(item.path).includes('default'));
  if (applicationHaps.length !== 1) throw new Error('Expected one standalone Task17 application HAP');
  report.compile = { passed: true, scope: 'standalone_application_hap',
    hap: { ...applicationHaps[0] } };
  report.task17Strict = { schemaVersion: 1, role, caseId, canonicalContract: fileRecord(contract),
    wrapper: fileRecord(__filename), sharedBuilder: fileRecord(sharedBuilder), generatedBuilder: fileRecord(derivedBuilder) };
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: report.status, role, caseId, reportFile }, null, 2));
}

if (require.main === module) {
  try { main(); }
  catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
}

module.exports = { deriveBuilder };
