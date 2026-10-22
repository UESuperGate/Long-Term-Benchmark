#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const sharedBuilder = path.join(__dirname, 'arkts_native_device.cjs');
const strictInstaller = path.join(root, 'state_tests/runtime/arkts/native/task09_strict/Task09Strict.install.cjs');
const contractFile = path.join(root, 'benchmark_tasks/09_spaces_lifecycle/transitions.json');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => { const bytes = fs.readFileSync(file); return {
  path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) }; };

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
  const caseId = value(args, '--case');
  const timeoutSeconds = Number(args.includes('--timeout') ? value(args, '--timeout') : '3600');
  if (!['base', 'final', 'agent'].includes(role) || !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0)
    throw new Error('Invalid role or timeout');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task09 build evidence: ' + output);
  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '09_spaces_lifecycle' || contract.cases.length !== 9 ||
      !contract.cases.some(item => item.caseId === caseId)) throw new Error('Invalid Task09 canonical case');
  fs.mkdirSync(output, { recursive: true });
  const original = fs.readFileSync(sharedBuilder, 'utf8');
  const anchor = "        if (nativeUI && taskId === '11_room_upgrade_navigation') {";
  const injected = `        if (nativeUI && taskId === '09_spaces_lifecycle') {
          report.nativeUIObserver = require(${JSON.stringify(strictInstaller)}).install(work, role);
        }
${anchor}`;
  if (original.split(anchor).length !== 2) throw new Error('Shared device builder hook changed');
  const derived = original
    .replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';')
    .replace("require('./arkts_native_smoke.cjs')", 'require(' + JSON.stringify(path.join(__dirname, 'arkts_native_smoke.cjs')) + ')')
    .replace("require('./arkts_native_bundle.cjs')", 'require(' + JSON.stringify(path.join(__dirname, 'arkts_native_bundle.cjs')) + ')')
    .replace(anchor, injected);
  const generated = path.join(output, 'task09-strict-builder.generated.cjs');
  fs.writeFileSync(generated, derived);
  const command = [generated, '--source', source, '--task', '09_spaces_lifecycle', '--fixture', 'bundle',
    '--role', role, '--case', caseId, '--native-ui', '--output-dir', output];
  const result = spawnSync(process.execPath, command, { cwd: root, encoding: 'utf8',
    timeout: Math.min(timeoutSeconds * 1000, 600000), maxBuffer: 12 * 1024 * 1024 });
  fs.writeFileSync(path.join(output, 'build-command.log'), (result.stdout || '') + (result.stderr || ''));
  if (result.error || result.status !== 0) throw new Error('Task09 strict build failed: ' + (result.error || result.status));
  const reportFile = path.join(output, 'device-build-report.json');
  const report = JSON.parse(fs.readFileSync(reportFile));
  const manifest = JSON.parse(fs.readFileSync(path.join(output, 'bundle-manifest.json')));
  const manifestContract = manifest.contracts.find(item => item.taskId === '09_spaces_lifecycle');
  if (report.status !== 'built_not_executed' || report.runtimeCompile?.passed !== true ||
      report.productionUnchanged !== true || report.copiedProductionUnchanged !== true ||
      report.temporaryProjectRemoved !== true || report.caseId !== caseId || report.role !== role ||
      report.nativeUIObserver?.role !== role || report.nativeUIObserver?.productionUnchanged !== true ||
      path.resolve(manifestContract?.file || '') !== contractFile ||
      manifestContract?.sha256 !== fileRecord(contractFile).sha256)
    throw new Error('Task09 strict build provenance is incomplete');
  report.task09Strict = { schemaVersion: 1, role, caseId, activeCanonicalModified: false,
    contract: fileRecord(contractFile), wrapper: fileRecord(__filename), sharedBuilder: fileRecord(sharedBuilder),
    strictInstaller: fileRecord(strictInstaller), generatedBuilder: fileRecord(generated) };
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: report.status, role, caseId, reportFile }, null, 2));
}

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
}
