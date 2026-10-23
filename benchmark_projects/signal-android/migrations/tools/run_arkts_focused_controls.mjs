import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';

const value = flag => process.argv[process.argv.indexOf(flag) + 1];
const migration = path.resolve(value('--migration'));
const target = value('--target');
const tools = path.dirname(new URL(import.meta.url).pathname);
const taskId = path.basename(migration);
const controlsDir = path.join(migration, 'results', 'arkts-controls');
const runtimeDir = path.join(migration, 'provenance', 'runtime-logs');
const auditPath = path.join(migration, 'provenance', 'arkts-control-audit.json');
const lockTool = path.join(tools, 'with_device_lock.py');
const buildTool = path.join(tools, 'build_arkts_focused_candidate.sh');
const runTool = path.join(tools, 'run_arkts_focused_candidate.mjs');
const scorer = path.join(tools, 'score_arkts_focused_candidate.mjs');
const deviceHash = crypto.createHash('sha256').update(target).digest('hex').slice(0, 16);
const deviceLock = `/tmp/ltb-arkts-device-${deviceHash}`;
const buildLock = '/tmp/long-term-benchmark-full-build.lock';
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), `ltb-${taskId}-arkts-controls-`));
const commands = [];
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const freeKiB = targetPath => Number.parseInt(spawnSync('df', ['-Pk', targetPath], { encoding: 'utf8' }).stdout.trim().split(/\n/).at(-1).split(/\s+/)[3], 10);
const run = (command, args, options = {}) => {
  const result = spawnSync(command, args, { encoding: 'utf8', timeout: options.timeout ?? 1200000, env: { ...process.env, HDC_TARGET: target, ...(options.env ?? {}) } });
  commands.push({ command: [command, ...args], exitCode: result.status, signal: result.signal, stdoutTail: result.stdout?.slice(-2500) ?? '', stderrTail: result.stderr?.slice(-2500) ?? '' });
  if (options.check !== false && result.status !== 0) throw new Error(`${command} failed\n${result.stderr || result.stdout}`);
  return result;
};
const assertDisk = () => {
  const available = freeKiB(migration);
  if (available < 8388608) throw new Error(`refusing calibration below 8 GiB free (${available} KiB)`);
  return available;
};
const copyCandidate = label => {
  const role = label === 'no-change-agent' ? 'base' : 'final';
  const destination = path.join(tempRoot, `${label}-${crypto.randomUUID()}`);
  fs.cpSync(path.join(migration, 'arkts', role), destination, {
    recursive: true,
    filter: source => !['build', '.hvigor', 'oh_modules'].includes(path.basename(source))
  });
  return destination;
};
const semantic = report => JSON.parse(fs.readFileSync(report, 'utf8')).semantic;
const expectMatrix = (report, expected) => {
  const actual = semantic(report);
  for (const [key, count] of Object.entries(expected)) if (actual[key] !== count) throw new Error(`${path.basename(report)} ${key}: expected ${count}, got ${actual[key]}`);
};

fs.mkdirSync(controlsDir, { recursive: true });
fs.mkdirSync(runtimeDir, { recursive: true });
const startedAt = new Date().toISOString();
const candidates = {};
const reports = {};
let minimumFreeKiB = assertDisk();
try {
  for (const label of ['no-change-agent', 'known-final-agent']) {
    const candidate = copyCandidate(label);
    candidates[label] = candidate;
    minimumFreeKiB = Math.min(minimumFreeKiB, assertDisk());
    run('python3', [lockTool, '--lock', buildLock, '--', 'bash', buildTool, candidate, migration]);
    const report = path.join(controlsDir, `${label}.json`);
    run('python3', [lockTool, '--lock', deviceLock, '--', process.execPath, runTool,
      '--project', candidate, '--migration', migration, '--role', 'agent', '--run-id', label, '--output', report]);
    reports[label] = report;
  }
  expectMatrix(reports['no-change-agent'], { passed: 0, failed: 10, notScored: 0, total: 10 });
  expectMatrix(reports['known-final-agent'], { passed: 10, failed: 0, notScored: 0, total: 10 });
  const observations = path.join(runtimeDir, 'arkts-known-final-agent.jsonl');
  const knownFinalHap = path.join(candidates['known-final-agent'], 'entry', 'build', 'default', 'outputs', 'default', 'entry-default-unsigned.hap');
  const failures = [
    { label: 'fail-closed-missing-manifest', reason: 'candidate_source_manifest_missing', mutate(candidate) { fs.rmSync(path.join(candidate, 'SOURCE_MANIFEST.json')); } },
    { label: 'fail-closed-source-hash-tamper', reason: 'candidate_source_provenance_mismatch', mutate(candidate) {
      const manifest = JSON.parse(fs.readFileSync(path.join(candidate, 'SOURCE_MANIFEST.json'), 'utf8'));
      fs.appendFileSync(path.join(candidate, manifest.files[0].path), '\n// provenance control tamper\n');
    } },
    { label: 'fail-closed-candidate-identity-missing', reason: 'candidate_identity_missing', mutate(candidate) { fs.rmSync(path.join(candidate, 'AppScope', 'app.json5')); } }
  ];
  for (const control of failures) {
    const candidate = copyCandidate(control.label);
    candidates[control.label] = candidate;
    control.mutate(candidate);
    const report = path.join(controlsDir, `${control.label}.json`);
    const result = run(process.execPath, [scorer, '--project', candidate, '--migration', migration, '--role', 'agent', '--output', report,
      '--observations', observations, '--native-target', target, '--hap', knownFinalHap], { check: false });
    if (result.status === 0) throw new Error(`${control.label} did not fail closed`);
    expectMatrix(report, { passed: 0, failed: 0, notScored: 10, total: 10 });
    const reasons = new Set(JSON.parse(fs.readFileSync(report, 'utf8')).semantic.cases.map(item => item.reason));
    if (reasons.size !== 1 || !reasons.has(control.reason)) throw new Error(`${control.label}: unexpected reasons ${[...reasons]}`);
    reports[control.label] = report;
  }
  const matrix = Object.fromEntries(Object.entries(reports).map(([label, report]) => [label, {
    ...Object.fromEntries(Object.entries(semantic(report)).filter(([key]) => key !== 'cases')),
    report: path.relative(migration, report), sha256: sha256(report),
    scorerExitCode: label.startsWith('fail-closed-') ? commands.filter(item => item.command.includes(report)).at(-1)?.exitCode ?? null : 0
  }]));
  const audit = {
    schemaVersion: 1, taskId, status: 'passed', startedAt, completedAt: new Date().toISOString(),
    invariant: 'same API23 runtime scorer and role=agent for random base/final candidates; no role or path semantic selection',
    sourceObserver: false, roleUsedForScoring: false, randomIndependentRoot: tempRoot, randomCandidateDirectories: candidates,
    minimumObservedFreeKiB: minimumFreeKiB, locks: { build: buildLock, device: deviceLock, implementation: 'python_fcntl.flock' },
    target, apiVersion: 23,
    expected: { 'no-change-agent': { passed: 0, failed: 10, notScored: 0 }, 'known-final-agent': { passed: 10, failed: 0, notScored: 0 }, failClosed: { exitCode: 'nonzero', passed: 0, failed: 0, notScored: 10 } },
    matrix,
    rawObservations: { 'no-change-agent': 'provenance/runtime-logs/arkts-no-change-agent.jsonl', 'known-final-agent': 'provenance/runtime-logs/arkts-known-final-agent.jsonl' },
    commands
  };
  fs.writeFileSync(auditPath, `${JSON.stringify(audit, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify({ taskId, status: 'passed', matrix }, null, 2)}\n`);
} finally {
  fs.rmSync(tempRoot, { recursive: true, force: true });
}
