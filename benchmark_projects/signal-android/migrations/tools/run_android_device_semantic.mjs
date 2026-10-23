import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const value = flag => process.argv[process.argv.indexOf(flag) + 1];
const optional = flag => process.argv.includes(flag) ? value(flag) : null;
const project = path.resolve(value('--project'));
const role = value('--role');
const output = path.resolve(value('--output'));
const migration = path.resolve(optional('--migration') ?? path.resolve(project, '..', '..'));
const taskId = optional('--task-id') ?? path.basename(migration);
const adb = process.env.ADB ?? path.join(process.env.HOME, 'Library/Android/sdk/platform-tools/adb');
const serial = process.env.ANDROID_SERIAL ?? 'emulator-5554';
const apk = path.join(project, 'build', 'harness.apk');

const definitions = {
  '01_media_keyboard': {
    base: ['org.signal.benchmark.mediakeyboard.base', 'benchmark.evaluator.ImmutableMediaProbeKt'],
    final: ['org.signal.benchmark.mediakeyboard.finalapp', 'benchmark.evaluator.ImmutableMediaProbeKt']
  },
  '02_sticker_management': {
    base: ['org.signal.benchmark.stickers.base', 'org.thoughtcrime.securesms.stickers.ImmutableStickerBaseProbeKt'],
    final: ['org.signal.benchmark.stickers.finalapp', 'benchmark.evaluator.ImmutableStickerProbeKt']
  }
};
const sourceManifest = fs.readFileSync(path.join(project, 'src', 'main', 'AndroidManifest.xml'), 'utf8');
const manifestBundle = sourceManifest.match(/package="([^"]+)"/)?.[1];
const preparedPath = path.join(project, '.benchmark-evaluator', 'PREPARED');
const prepared = role === 'agent' && fs.existsSync(preparedPath) ? JSON.parse(fs.readFileSync(preparedPath, 'utf8')) : null;
const agentProbe = prepared?.probeMainClass;
const [bundle, probeClass] = role === 'agent' ? [manifestBundle, agentProbe] : (definitions[taskId]?.[role] ?? []);
if (!bundle || !probeClass) throw new Error(`unsupported task/role: ${taskId}/${role}`);
if (!fs.existsSync(apk)) throw new Error(`harness APK is missing: ${apk}`);

const run = (args, options = {}) => {
  const result = spawnSync(adb, ['-s', serial, ...args], { encoding: 'utf8', timeout: options.timeout ?? 120000 });
  if (options.check !== false && result.status !== 0) {
    throw new Error(`adb ${args.join(' ')} failed: ${result.stderr || result.stdout}`);
  }
  return result;
};

run(['uninstall', bundle], { check: false });
run(['install', '-r', '-t', apk]);
run(['shell', 'pm', 'clear', bundle]);
run(['logcat', '-c']);
const launch = run(['shell', 'am', 'start', '-W', '-n', `${bundle}/evaluator.harness.HarnessActivity`, '--es', 'probeClass', probeClass]);

let status = '';
for (let attempt = 0; attempt < 120; attempt += 1) {
  const check = run(['shell', 'run-as', bundle, 'cat', 'files/runtime.status'], { check: false, timeout: 5000 });
  status = check.stdout;
  if (status.startsWith('ok\n') || status.startsWith('error\n')) break;
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 250);
}
if (!status.startsWith('ok\n')) {
  const logcat = run(['logcat', '-d', '-s', 'BenchmarkObserver:*'], { check: false }).stdout;
  throw new Error(`device harness did not complete successfully: ${status || logcat}`);
}

const observed = run(['shell', 'run-as', bundle, 'cat', 'files/runtime.jsonl']).stdout.trim();
const lines = observed.split(/\r?\n/).filter(Boolean);
if (lines.length !== 10) throw new Error(`expected 10 device observations, got ${lines.length}`);
for (const line of lines) JSON.parse(line);

const logs = path.join(migration, 'provenance', 'runtime-logs');
fs.mkdirSync(logs, { recursive: true });
const outputStem = output.replace(/\.json$/, '');
const rawLog = role === 'agent' ? `${outputStem}.observations.jsonl` : path.join(logs, `android-${role}.jsonl`);
const transportLog = role === 'agent' ? `${outputStem}.transport.json` : path.join(logs, `android-${role}-transport.json`);
fs.mkdirSync(path.dirname(rawLog), { recursive: true });
fs.writeFileSync(rawLog, `${observed}\n`);
fs.writeFileSync(transportLog, `${JSON.stringify({
  deviceLock: process.env.BENCHMARK_DEVICE_LOCK_PATH ?? null,
  deviceLockImplementation: process.env.BENCHMARK_DEVICE_LOCK_IMPLEMENTATION ?? null,
  serial,
  apiLevel: run(['shell', 'getprop', 'ro.build.version.sdk']).stdout.trim(),
  abi: run(['shell', 'getprop', 'ro.product.cpu.abi']).stdout.trim(),
  bundle,
  probeClass,
  installableApk: path.relative(migration, apk),
  launchStdout: launch.stdout.trim(),
  status: 'completed'
}, null, 2)}\n`);

const scorer = path.join(migration, 'android', 'evaluator', 'run-semantic.mjs');
const scored = spawnSync(process.execPath, [scorer, '--project', project, '--role', role, '--output', output, '--observations', rawLog, '--native-device', serial, '--apk', apk], { encoding: 'utf8' });
process.stdout.write(scored.stdout);
process.stderr.write(scored.stderr);
process.exit(scored.status ?? 1);
