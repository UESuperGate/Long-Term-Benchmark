import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';

const value = flag => process.argv[process.argv.indexOf(flag) + 1];
const migration = path.resolve(value('--migration'));
const tools = path.dirname(new URL(import.meta.url).pathname);
const taskId = path.basename(migration);
const controlsDir = path.join(migration, 'results', 'android-controls');
const runtimeDir = path.join(migration, 'provenance', 'runtime-logs');
const scorer = path.join(migration, 'android', 'evaluator', 'run-semantic.mjs');
const calibrationPath = path.join(migration, 'provenance', 'calibration-summary.json');
const auditPath = path.join(migration, 'provenance', 'android-control-audit.json');
const lockTool = path.join(tools, 'with_device_lock.py');
const buildTool = path.join(tools, 'build_android_focused_candidate.sh');
const runTool = path.join(tools, 'run_android_focused_candidate.mjs');
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), `ltb-${taskId}-android-controls-`));
const commands = [];

const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const freeKiB = target => Number.parseInt(spawnSync('df', ['-Pk', target], { encoding: 'utf8' }).stdout.trim().split(/\n/).at(-1).split(/\s+/)[3], 10);
const run = (command, args, options = {}) => {
  const startedAt = new Date().toISOString();
  const result = spawnSync(command, args, { encoding: 'utf8', timeout: options.timeout ?? 600000, env: { ...process.env, ...(options.env ?? {}) } });
  commands.push({ command: [command, ...args], startedAt, exitCode: result.status, signal: result.signal, stdoutTail: result.stdout?.slice(-2000) ?? '', stderrTail: result.stderr?.slice(-2000) ?? '' });
  if (options.expect !== undefined && result.status !== options.expect) {
    throw new Error(`${command} exited ${result.status}; expected ${options.expect}\n${result.stderr || result.stdout}`);
  }
  if (options.check !== false && result.status !== 0) throw new Error(`${command} failed\n${result.stderr || result.stdout}`);
  return result;
};
const assertDisk = () => {
  const available = freeKiB(migration);
  if (available < 8388608) throw new Error(`refusing calibration below 8 GiB free (${available} KiB)`);
  return available;
};
const copyCandidate = label => {
  const sourceRole = label === 'no-change-agent' ? 'base' : 'final';
  const destination = path.join(tempRoot, `${label}-${crypto.randomUUID()}`);
  fs.cpSync(path.join(migration, 'android', sourceRole), destination, { recursive: true });
  return destination;
};
const semantic = reportPath => JSON.parse(fs.readFileSync(reportPath, 'utf8')).semantic;
const expectMatrix = (reportPath, expected) => {
  const actual = semantic(reportPath);
  for (const [key, count] of Object.entries(expected)) {
    if (actual[key] !== count) throw new Error(`${path.basename(reportPath)} ${key}: expected ${count}, got ${actual[key]}`);
  }
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
    run('python3', [lockTool, '--lock', '/tmp/long-term-benchmark-android-full-build.lock', '--', 'bash', buildTool, candidate, migration]);
    const report = path.join(controlsDir, `${label}.json`);
    run('python3', [lockTool, '--lock', '/tmp/long-term-benchmark-android-device.lock', '--', process.execPath, runTool,
      '--project', candidate, '--migration', migration, '--role', 'agent', '--run-id', label, '--output', report]);
    reports[label] = report;
  }
  expectMatrix(reports['no-change-agent'], { passed: 0, failed: 10, notScored: 0, total: 10 });
  expectMatrix(reports['known-final-agent'], { passed: 10, failed: 0, notScored: 0, total: 10 });

  const knownFinalObservations = path.join(runtimeDir, 'android-known-final-agent.jsonl');
  const knownFinalApk = path.join(candidates['known-final-agent'], 'build', 'harness.apk');
  const failures = [
    {
      label: 'fail-closed-missing-manifest',
      mutate(candidate) { fs.rmSync(path.join(candidate, 'IMMUTABLE_SOURCES.json')); },
      reason: 'candidate_source_manifest_missing'
    },
    {
      label: 'fail-closed-source-hash-tamper',
      mutate(candidate) {
        const manifest = JSON.parse(fs.readFileSync(path.join(candidate, 'IMMUTABLE_SOURCES.json'), 'utf8'));
        fs.appendFileSync(path.join(candidate, 'immutable-src', manifest.files[0].path), '\n// provenance control tamper\n');
      },
      reason: 'candidate_source_provenance_mismatch'
    },
    {
      label: 'fail-closed-candidate-identity-missing',
      mutate(candidate) { fs.rmSync(path.join(candidate, 'src', 'main', 'AndroidManifest.xml')); },
      reason: 'candidate_identity_missing'
    }
  ];

  for (const control of failures) {
    const candidate = copyCandidate(control.label);
    candidates[control.label] = candidate;
    control.mutate(candidate);
    const report = path.join(controlsDir, `${control.label}.json`);
    const result = run(process.execPath, [scorer, '--project', candidate, '--role', 'agent', '--output', report,
      '--observations', knownFinalObservations, '--native-device', process.env.ANDROID_SERIAL ?? 'emulator-5554',
      '--apk', knownFinalApk, '--probe-candidate', 'known-final-control'], { check: false });
    if (result.status === 0) throw new Error(`${control.label} did not fail closed`);
    expectMatrix(report, { passed: 0, failed: 0, notScored: 10, total: 10 });
    const reasons = new Set(JSON.parse(fs.readFileSync(report, 'utf8')).semantic.cases.map(item => item.reason));
    if (reasons.size !== 1 || !reasons.has(control.reason)) throw new Error(`${control.label} emitted unexpected reasons: ${[...reasons]}`);
    reports[control.label] = report;
  }

  const matrix = Object.fromEntries(Object.entries(reports).map(([label, report]) => [label, {
    ...Object.fromEntries(Object.entries(semantic(report)).filter(([key]) => key !== 'cases')),
    report: path.relative(migration, report),
    sha256: sha256(report),
    scorerExitCode: label.startsWith('fail-closed-') ? commands.filter(item => item.command.includes(report)).at(-1)?.exitCode ?? null : 0
  }]));
  const audit = {
    schemaVersion: 1,
    taskId,
    status: 'passed',
    startedAt,
    completedAt: new Date().toISOString(),
    invariant: 'all controls use the same scorer with role=agent; role and candidate path do not select semantics',
    randomIndependentRoot: tempRoot,
    randomCandidateDirectories: candidates,
    sourceObserver: false,
    minimumObservedFreeKiB: minimumFreeKiB,
    locks: {
      build: '/tmp/long-term-benchmark-android-full-build.lock',
      device: '/tmp/long-term-benchmark-android-device.lock',
      implementation: 'python_fcntl.flock'
    },
    expected: {
      'no-change-agent': { passed: 0, failed: 10, notScored: 0 },
      'known-final-agent': { passed: 10, failed: 0, notScored: 0 },
      failClosed: { exitCode: 'nonzero', passed: 0, failed: 0, notScored: 10 }
    },
    matrix,
    rawObservations: {
      'no-change-agent': 'provenance/runtime-logs/android-no-change-agent.jsonl',
      'known-final-agent': 'provenance/runtime-logs/android-known-final-agent.jsonl'
    },
    commands
  };
  fs.writeFileSync(auditPath, `${JSON.stringify(audit, null, 2)}\n`);

  const calibration = JSON.parse(fs.readFileSync(calibrationPath, 'utf8'));
  calibration.matrix = { ...calibration.matrix, ...Object.fromEntries(Object.entries(matrix).map(([key, value]) => [key, {
    passed: value.passed, failed: value.failed, notScored: value.notScored, total: value.total
  }])) };
  calibration.controls = { status: 'passed', audit: 'android-control-audit.json', sourceObserver: false, identicalRole: 'agent' };
  fs.writeFileSync(calibrationPath, `${JSON.stringify(calibration, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify({ taskId, status: 'passed', matrix }, null, 2)}\n`);
} finally {
  fs.rmSync(tempRoot, { recursive: true, force: true });
}
