#!/usr/bin/env node
'use strict';
// Independent prospective fixture; does not change formal/public admission.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const record = file => ({ path: file, bytes: fs.statSync(file).size, sha256: hash(file) });
function main() {
  const args = process.argv.slice(2);
  const value = flag => {
    const index = args.indexOf(flag);
    if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' required');
    return args[index + 1];
  };
  const source = path.resolve(value('--source')), task = value('--task'), caseId = value('--case');
  const output = path.resolve(value('--output-dir'));
  if (!['16_identity_reset', '17_pinned_messages'].includes(task)) throw new Error('Wrong task');
  if (fs.existsSync(output)) throw new Error('Evidence exists');
  const contract = path.join(root, 'benchmark_tasks', task, 'transitions.json');
  if (!JSON.parse(fs.readFileSync(contract)).cases.some(row => row.caseId === caseId)) throw new Error('Unknown case');
  const baseFile = path.join(__dirname, 'arkts_native_device.cjs');
  const deriveFile = path.join(__dirname, task.startsWith('16') ? 'task16_arkts_revision5_build.cjs' : 'task17_arkts_strict_build.cjs');
  let generated = require(deriveFile).deriveBuilder(fs.readFileSync(baseFile, 'utf8'));
  const previous = task.startsWith('16') ? 'Task16Revision5.install.cjs' : 'Task17StrictNativeUi.install.cjs';
  if (generated.split(previous).length !== 2) throw new Error('Unbound installer derivation');
  generated = generated.replace(previous, 'Tasks16_17PagePorts.install.cjs');
  if (task.startsWith('17')) {
    const token = '{ device: true, caseId });';
    if (generated.split(token).length !== 2) throw new Error('Unbound active contract');
    generated = generated.replace(token, '{ device: true, caseId, contractOverride: ' + JSON.stringify(contract) + ' });');
  }
  fs.mkdirSync(output, { recursive: true });
  const derived = path.join(output, 'page-ports-builder.generated.cjs');
  fs.writeFileSync(derived, generated);
  const deadline = Number(process.env.LTB_PAGE_PORTS_DEADLINE_MS);
  if (!Number.isFinite(deadline) || deadline <= Date.now()) throw new Error('Trusted remaining overall deadline required');
  const execution = spawnSync(process.execPath, [derived, '--source', source, '--task', task, '--fixture', 'bundle',
    '--role', 'agent', '--case', caseId, '--native-ui', '--output-dir', output], {
    cwd: root, env: { ...process.env, LTB_PAGE_PORTS_TASK: task }, encoding: 'utf8',
    timeout: deadline - Date.now(), maxBuffer: 16 * 1024 * 1024
  });
  fs.writeFileSync(path.join(output, 'build-command.log'), (execution.stdout || '') + (execution.stderr || ''));
  if (execution.error || execution.status !== 0) throw new Error('Native build failed: ' + (execution.error || execution.status));
  const reportFile = path.join(output, 'device-build-report.json'), report = JSON.parse(fs.readFileSync(reportFile));
  if (!report.productionUnchanged || !report.copiedProductionUnchanged || !report.temporaryProjectRemoved ||
      !report.nativeUIObserver?.productionUnchanged || !report.runtimeCompile?.passed) throw new Error('Incomplete native packaging provenance');
  report.prospectivePagePorts = { wrapper: record(__filename), derived: record(derived), derivation: record(deriveFile),
    originalBuilder: record(baseFile), canonicalContract: record(contract),
    integrationTier: 'actual_page_controlled_external_sdk', liveMatrixSdkOrServerVerified: false,
    publicAdmissionUnchanged: true };
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ reportFile, status: report.status }));
}
if (require.main === module) { try { main(); } catch (error) { console.error(error.stack); process.exitCode = 1; } }
