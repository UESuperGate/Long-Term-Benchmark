#!/usr/bin/env node
'use strict';

// Device diagnostics: one canonical case per fresh install, never a score-promotion shortcut.
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const [taskId, rolesArg, serial, outputArg] = process.argv.slice(2);
if (!/^\d\d_[a-z_]+$/.test(taskId || '') || !rolesArg || !serial || !outputArg) {
  throw new Error('Usage: run_arkts_device_matrix.cjs TASK base,final SERIAL OUTPUT');
}
const roles = rolesArg.split(',');
if (roles.some(role => !['base', 'final'].includes(role))) throw new Error('Calibrate base/final before agent execution');
const output = path.resolve(outputArg);
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks', taskId, 'task.json')));
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks', taskId, 'transitions.json')));
fs.mkdirSync(output, { recursive: true });
const summary = { taskId, startedAt: new Date().toISOString(), rows: [], benchmarkSemanticMetric: null };
for (const role of roles) {
  for (const spec of contract.cases) {
    const destination = path.join(output, role, spec.caseId);
    if (fs.existsSync(destination)) throw new Error('Refusing existing output: ' + destination);
    const source = path.join(root, manifest.arkts[role + 'Path']);
    const command = [path.join(__dirname, 'arkts_native_device.cjs'), '--source', source, '--task', taskId,
      '--fixture', 'bundle', '--role', role, '--case', spec.caseId, '--output-dir', destination];
    const build = spawnSync(process.execPath, command, { cwd: root, encoding: 'utf8', timeout: 540000, maxBuffer: 4 * 1024 * 1024 });
    const row = { role, caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'not_scored' };
    if (build.status === 0) {
      const buildFile = path.join(destination, 'device-build-report.json');
      const executed = spawnSync(process.execPath, [path.join(__dirname, 'arkts_device_execute.cjs'), buildFile, serial],
        { cwd: root, encoding: 'utf8', timeout: 210000, maxBuffer: 4 * 1024 * 1024 });
      row.executionExitCode = executed.status;
      row.report = path.join(destination, 'device-execution.json');
      if (fs.existsSync(row.report)) {
        const report = JSON.parse(fs.readFileSync(row.report));
        const observed = report.rows.find(item => item.caseId === spec.caseId);
        if (report.transportCompleted && observed && observed.traceDigest === spec.traceDigest) row.status = observed.status;
        row.error = report.error || (observed && observed.reason);
      } else row.error = executed.error ? String(executed.error) : executed.stderr;
    } else row.error = build.error ? String(build.error) : (build.stdout + build.stderr).slice(-1500);
    summary.rows.push(row);
    summary.updatedAt = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'device-matrix.json'), JSON.stringify(summary, null, 2) + '\n');
    console.log(JSON.stringify(row));
  }
}
summary.finishedAt = new Date().toISOString();
fs.writeFileSync(path.join(output, 'device-matrix.json'), JSON.stringify(summary, null, 2) + '\n');
