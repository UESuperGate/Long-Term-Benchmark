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
const installer = path.join(root, 'state_tests/runtime/arkts/native/Task13Revision5NativeUi.install.cjs');
const contract = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_5_task13/after/transitions.json');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const record = file => { const bytes = fs.readFileSync(file); return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) }; };

function value(args, flag) {
  const index = args.indexOf(flag);
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
  return args[index + 1];
}

function main() {
  const disk = fs.statfsSync(root);
  if (disk.bavail * disk.bsize < 8 * 1024 ** 3) throw new Error('storage_protection_environment: Task13 runtime build requires 8 GiB free');
  const args = process.argv.slice(2);
  const output = path.resolve(value(args, '--output-dir'));
  const source = path.resolve(value(args, '--source'));
  const role = value(args, '--role');
  const compileOnly = args.includes('--compile-only');
  const discoveryPath = compileOnly ? null : path.resolve(value(args, '--entry-discovery'));
  const discovery = compileOnly ? null : JSON.parse(fs.readFileSync(discoveryPath));
  if (!compileOnly && (discovery.source !== fs.realpathSync(source) || discovery.observedBinding !== role ||
      discovery.status !== 'production_common_entry_completed' || !discovery.pageBinding ||
      discovery.freshInstall !== true || discovery.ownedAppUninstalled !== true)) {
    throw new Error('Task13 runtime requires actual source-bound common entry discovery');
  }
  const binding = require(path.join(root, 'state_tests/runtime/arkts/native/Task13PageBinding.cjs')).bind(source, role);
  if (!compileOnly && JSON.stringify(binding) !== JSON.stringify(discovery.pageBinding)) throw new Error('Page import binding changed after actual UI discovery');
  const requestedCase = args.includes('--case') ? value(args, '--case') : 'all';
  if (!['base', 'final'].includes(role)) throw new Error('Task13 revision5 accepts base/final only');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task13 build evidence: ' + output);
  const staged = JSON.parse(fs.readFileSync(contract));
  if (staged.taskId !== '13_user_verification' || staged.revision !== 5 || staged.cases.length !== 10) {
    throw new Error('Invalid staged Task13 revision5 contract');
  }
  if (requestedCase !== 'all' && !staged.cases.some(item => item.caseId === requestedCase)) {
    throw new Error('Unknown staged Task13 revision5 case: ' + requestedCase);
  }
  fs.mkdirSync(output, { recursive: true });
  const original = fs.readFileSync(sharedBuilder, 'utf8');
  let derived = original
    .replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';')
    .replace("require('./arkts_native_smoke.cjs')", 'require(' + JSON.stringify(sharedSmoke) + ')')
    .replace("require('./arkts_native_bundle.cjs')", 'require(' + JSON.stringify(sharedBundle) + ')')
    .replace("const caseId = fixture === 'bundle' ? value('--case') : null;",
      requestedCase === 'all' ? "const caseId = fixture === 'bundle' ? null : null;" :
        "const caseId = fixture === 'bundle' ? value('--case') : null;")
    .replace('const manifest = require(' + JSON.stringify(sharedBundle) + ').generate(work, output, taskId, role, source, nativeUI, { device: true, caseId });',
      'const manifest = require(' + JSON.stringify(sharedBundle) + ').generate(work, output, taskId, role, source, nativeUI, { device: true, caseId, contractOverride: ' + JSON.stringify(contract) + ' });')
    .replace("report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native/Task13NativeUi.install.cjs')).install(work);",
      'report.nativeUIObserver = require(' + JSON.stringify(installer) + ').install(work, ' + JSON.stringify(binding) + ');');
  if (derived === original || !derived.includes('contractOverride: ' + JSON.stringify(contract)) ||
    !derived.includes(JSON.stringify(installer))) throw new Error('Shared builder shape changed; refusing Task13 derivation');
  const inputHelper = path.join(__dirname, 'Task13CompiledInputs.cjs');
  const copyAnchor = "      fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work";
  if (derived.split(copyAnchor).length !== 2) throw new Error('Raw copy instrumentation anchor changed');
  derived = derived.replace(copyAnchor,
    '      report.task13InputCopy = require(' + JSON.stringify(inputHelper) + ').beginCopy(source, work, output);\n' + copyAnchor);
  const commandAnchor = '        report.commands.push(command);';
  const afterAnchor = "        const log = redact((result.stdout || '') + (result.stderr || ''));";
  const producers = [__filename, installer, sharedBuilder, sharedSmoke, sharedBundle,
    path.join(root, 'state_tests/runtime/arkts/native/DeviceTestRunner.ets'),
    path.join(root, 'state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs'),
    path.join(root, 'state_tests/runtime/arkts/native/Task13Revision5NativeUi.js'),
    path.join(root, 'state_tests/runtime/arkts/native/Task13PageOwnerSdk.js')];
  if (derived.split(commandAnchor).length !== 2 || derived.split(afterAnchor).length !== 2) throw new Error('Compiler instrumentation anchors changed');
  derived = derived.replace(commandAnchor, commandAnchor + '\n' +
    '        const task13CompileReceipt = require(' + JSON.stringify(inputHelper) + ').beforeCompile(work, output, target, ' + JSON.stringify(producers) + ');\n' +
    '        (report.task13CompilerInputs ||= []).push(task13CompileReceipt);');
  derived = derived.replace(afterAnchor,
    '        require(' + JSON.stringify(inputHelper) + ').afterCompile(work, output, target, task13CompileReceipt);\n' + afterAnchor);
  const derivedBuilder = path.join(output, 'task13-revision5-builder.generated.cjs');
  fs.writeFileSync(derivedBuilder, derived);
  const command = [derivedBuilder, '--source', source, '--task', '13_user_verification', '--fixture', 'bundle',
    '--role', role, '--case', requestedCase, '--native-ui', '--output-dir', output];
  const run = spawnSync(process.execPath, command, { cwd: root, encoding: 'utf8', timeout: 900000,
    maxBuffer: 12 * 1024 * 1024 });
  fs.writeFileSync(path.join(output, 'build-command.log'), (run.stdout || '') + (run.stderr || ''));
  if (run.error || run.status !== 0) throw new Error('Task13 revision5 build failed: ' + (run.error || run.status));
  const reportFile = path.join(output, 'device-build-report.json');
  const report = JSON.parse(fs.readFileSync(reportFile));
  const manifest = JSON.parse(fs.readFileSync(path.join(output, 'bundle-manifest.json')));
  const contractRecord = manifest.contracts.find(item => item.taskId === '13_user_verification');
  const expectedCaseCount = requestedCase === 'all' ? 10 : 1;
  const expectedCaseId = requestedCase === 'all' ? null : requestedCase;
  if (report.status !== 'built_not_executed' || report.runtimeCompile?.passed !== true ||
    report.productionUnchanged !== true || report.copiedProductionUnchanged !== true ||
    report.temporaryProjectRemoved !== true || report.caseCount !== expectedCaseCount || report.caseId !== expectedCaseId ||
    report.nativeUIObserver?.role !== role || report.nativeUIObserver?.productionUnchanged !== true ||
    contractRecord?.override !== true || path.resolve(contractRecord.file) !== contract ||
    contractRecord.sha256 !== record(contract).sha256) throw new Error('Task13 build provenance incomplete');
  const appHap = report.haps.find(item => item.path.endsWith('entry-default-unsigned.hap'));
  const testHap = report.haps.find(item => item.path.endsWith('entry-ohosTest-unsigned.hap'));
  if (!appHap || !testHap) throw new Error('Task13 standalone app or ohosTest HAP missing');
  report.standaloneAppCompile = { passed: true, artifact: appHap };
  report.ohosTestCompile = { passed: true, artifact: testHap };
  const waitIndex = report.deviceTestCommand.indexOf('-w');
  if (waitIndex < 0 || report.deviceTestCommand[waitIndex + 1] !== '120000') throw Error('Shared native wait shape changed');
  report.deviceTestCommand[waitIndex + 1] = '600000';
  const timeoutIndex = report.deviceTestCommand.indexOf('timeout');
  if (timeoutIndex < 0) throw Error('Native case timeout missing');
  report.deviceTestCommand[timeoutIndex + 1] = '120000';
  report.task13Revision5 = { schemaVersion: 1, role, caseCount: expectedCaseCount,
    compileOnly, noDeviceCalibrationClaim: compileOnly,
    entryDiscovery: discoveryPath ? record(discoveryPath) : null, pageBinding: binding,
    caseSelection: requestedCase, activeCanonicalModified: false,
    stagedContract: record(contract), wrapper: record(__filename), sharedBuilder: record(sharedBuilder),
    generatedBuilder: record(derivedBuilder), installer: record(installer) };
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: report.status, role, caseCount: report.caseCount, reportFile }, null, 2));
}

module.exports = { main };
if (require.main === module) {
  try { main(); } catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
}
