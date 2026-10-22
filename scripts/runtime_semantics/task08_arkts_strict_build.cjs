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
const installer = path.join(root, 'state_tests/runtime/arkts/native/task08_strict/Task08StrictNativeUi.install.cjs');
const contract = path.join(root, 'benchmark_tasks/08_threads/transitions.json');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const record = file => { const bytes = fs.readFileSync(file); return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) }; };

function value(args, flag) {
  const index = args.indexOf(flag);
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
  return args[index + 1];
}

function main() {
  const args = process.argv.slice(2);
  const output = path.resolve(value(args, '--output-dir'));
  const source = path.resolve(value(args, '--source'));
  const role = value(args, '--role');
  const requestedCase = args.includes('--case') ? value(args, '--case') : 'all';
  const timeoutSeconds = args.includes('--timeout-seconds') ? Number(value(args, '--timeout-seconds')) : 3600;
  if (!Number.isInteger(timeoutSeconds) || timeoutSeconds < 1 || timeoutSeconds > 3600) {
    throw new Error('Task08 strict build timeout must be an integer from 1 to 3600 seconds');
  }
  if (!['base', 'final', 'agent'].includes(role)) throw new Error('Task08 strict accepts base/final/agent only');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task08 build evidence: ' + output);
  const canonical = JSON.parse(fs.readFileSync(contract));
  if (canonical.taskId !== '08_threads' || canonical.cases.length !== 9) throw new Error('Invalid Task08 canonical contract');
  if (requestedCase !== 'all' && !canonical.cases.some(item => item.caseId === requestedCase)) {
    throw new Error('Unknown Task08 case: ' + requestedCase);
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
    .replace("if (nativeUI && taskId === '11_room_upgrade_navigation') {",
      "if (nativeUI && taskId === '08_threads') {\n          report.nativeUIObserver = require(" + JSON.stringify(installer) + ").install(work);\n        }\n        if (nativeUI && taskId === '11_room_upgrade_navigation') {");
  if (derived === original || !derived.includes(JSON.stringify(installer))) {
    throw new Error('Shared builder shape changed; refusing Task08 derivation');
  }
  const derivedBuilder = path.join(output, 'task08-strict-builder.generated.cjs');
  fs.writeFileSync(derivedBuilder, derived);
  const command = [derivedBuilder, '--source', source, '--task', '08_threads', '--fixture', 'bundle',
    '--role', role, '--case', requestedCase, '--native-ui', '--output-dir', output];
  const run = spawnSync(process.execPath, command, { cwd: root, encoding: 'utf8', timeout: timeoutSeconds * 1000,
    maxBuffer: 12 * 1024 * 1024, env: { ...process.env, LTB_TASK08_ROLE: role } });
  fs.writeFileSync(path.join(output, 'build-command.log'), (run.stdout || '') + (run.stderr || ''));
  if (run.error || run.status !== 0) throw new Error('Task08 strict build failed: ' + (run.error || run.status));
  const reportFile = path.join(output, 'device-build-report.json');
  const report = JSON.parse(fs.readFileSync(reportFile));
  const manifest = JSON.parse(fs.readFileSync(path.join(output, 'bundle-manifest.json')));
  const contractRecord = manifest.contracts.find(item => item.taskId === '08_threads');
  const expectedCaseCount = requestedCase === 'all' ? 9 : 1;
  const expectedCaseId = requestedCase === 'all' ? null : requestedCase;
  if (report.status !== 'built_not_executed' || report.runtimeCompile?.passed !== true ||
    report.productionUnchanged !== true || report.copiedProductionUnchanged !== true ||
    report.temporaryProjectRemoved !== true || report.caseCount !== expectedCaseCount || report.caseId !== expectedCaseId ||
    report.nativeUIObserver?.role !== role || report.nativeUIObserver?.productionUnchanged !== true ||
    contractRecord?.sha256 !== record(contract).sha256) throw new Error('Task08 build provenance incomplete');
  const appHap = report.haps.find(item => item.path.endsWith('entry-default-unsigned.hap'));
  const testHap = report.haps.find(item => item.path.endsWith('entry-ohosTest-unsigned.hap'));
  if (!appHap || !testHap) throw new Error('Task08 standalone app or ohosTest HAP missing');
  report.standaloneAppCompile = { passed: true, artifact: appHap };
  report.ohosTestCompile = { passed: true, artifact: testHap };
  report.task08Strict = { schemaVersion: 1, role, caseCount: expectedCaseCount, timeoutSeconds,
    caseSelection: requestedCase, canonicalContract: record(contract), wrapper: record(__filename),
    sharedBuilder: record(sharedBuilder), generatedBuilder: record(derivedBuilder), installer: record(installer) };
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: report.status, role, caseCount: report.caseCount, reportFile }, null, 2));
}

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
}
