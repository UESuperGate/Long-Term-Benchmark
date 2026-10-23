import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const value = flag => process.argv[process.argv.indexOf(flag) + 1];
const project = path.resolve(value('--project'));
const migration = path.resolve(value('--migration'));
const output = path.resolve(value('--output'));
const role = value('--role');
const runId = process.argv.includes('--run-id') ? value('--run-id') : role;
const sourceManifest = process.argv.includes('--source-manifest') ? path.resolve(value('--source-manifest')) : null;
if (!/^[a-z0-9][a-z0-9-]*$/.test(runId)) throw new Error(`invalid run id: ${runId}`);
const contract = JSON.parse(fs.readFileSync(path.join(migration, 'canonical', 'transitions.json'), 'utf8'));
const app = JSON.parse(fs.readFileSync(path.join(project, 'AppScope', 'app.json5'), 'utf8'));
const hap = path.join(project, 'entry', 'build', 'default', 'outputs', 'default', 'entry-default-unsigned.hap');
const hdc = process.env.HDC ?? path.join(process.env.HOME, 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const target = process.env.HDC_TARGET;
if (!target) throw new Error('HDC_TARGET is required');
const command = (args, check = true) => {
  const result = spawnSync(hdc, ['-t', target, ...args], { encoding: 'utf8', timeout: 120000 });
  if (check && result.status !== 0) throw new Error(`hdc ${args.join(' ')} failed: ${result.stderr || result.stdout}`);
  return result;
};
const pause = milliseconds => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
if (!fs.existsSync(hap)) throw new Error(`HAP missing: ${hap}`);
const apiVersion = command(['shell', 'param', 'get', 'const.ohos.apiversion']).stdout.trim();
if (apiVersion !== '23') throw new Error(`expected API23 ArkVM target, got ${apiVersion}`);
const install = command(['install', '-r', hap]);
command(['shell', 'hilog', '-r']);
command(['shell', 'aa', 'force-stop', '-b', app.app.bundleName], false);
const launch = command(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', app.app.bundleName]);
let hilog = '';
for (let attempt = 0; attempt < 120; attempt += 1) {
  pause(250);
  hilog = command(['shell', 'hilog', '-x']).stdout;
  if (hilog.includes(`BENCHMARK_COMPLETE:${contract.taskId}`)) break;
}
if (!hilog.includes(`BENCHMARK_COMPLETE:${contract.taskId}`)) throw new Error('native_transition_observer_timeout');
const rows = [];
const ids = new Set();
const chunks = new Map();
for (const line of hilog.split(/\r?\n/)) {
  const marker = 'BENCHMARK_CASE:';
  const index = line.indexOf(marker);
  if (index >= 0) {
    const raw = line.slice(index + marker.length).trim();
    const row = JSON.parse(raw);
    if (ids.has(row.caseId)) throw new Error(`duplicate observation: ${row.caseId}`);
    ids.add(row.caseId);
    rows.push(raw);
    continue;
  }
  const chunkMarker = 'BENCHMARK_CHUNK:';
  const chunkAt = line.indexOf(chunkMarker);
  if (chunkAt < 0) continue;
  const encoded = line.slice(chunkAt + chunkMarker.length).trim();
  const match = encoded.match(/^([^:]+):(\d+):(\d+):([\s\S]*)$/);
  if (!match) throw new Error('malformed benchmark observation chunk');
  const [, caseId, chunkIndexText, chunkCountText, data] = match;
  const chunkIndex = Number(chunkIndexText);
  const chunkCount = Number(chunkCountText);
  const record = chunks.get(caseId) ?? { chunkCount, values: new Map() };
  if (record.chunkCount !== chunkCount || record.values.has(chunkIndex)) throw new Error(`invalid observation chunk sequence: ${caseId}`);
  record.values.set(chunkIndex, data);
  chunks.set(caseId, record);
}
for (const [caseId, record] of chunks) {
  if (record.values.size !== record.chunkCount) throw new Error(`incomplete observation chunks: ${caseId}`);
  let raw = '';
  for (let chunkIndex = 0; chunkIndex < record.chunkCount; chunkIndex += 1) raw += record.values.get(chunkIndex);
  const row = JSON.parse(raw);
  if (row.caseId !== caseId || ids.has(caseId)) throw new Error(`duplicate or mismatched observation: ${caseId}`);
  ids.add(caseId);
  rows.push(raw);
}
if (rows.length !== contract.cases.length) throw new Error(`expected ${contract.cases.length} observations, got ${rows.length}`);
const ownerIds = new Set(rows.map(raw => JSON.parse(raw).ownerId));
if (ownerIds.size !== 1 || ownerIds.has(null) || ownerIds.has(undefined)) throw new Error('native_page_owner_identity_mismatch');
const logs = path.join(migration, 'provenance', 'runtime-logs');
fs.mkdirSync(logs, { recursive: true });
const rawLog = path.join(logs, `arkts-${runId}.jsonl`);
const transportLog = path.join(logs, `arkts-${runId}-transport.json`);
fs.writeFileSync(rawLog, `${rows.join('\n')}\n`);
fs.writeFileSync(transportLog, `${JSON.stringify({
  deviceLock: process.env.BENCHMARK_DEVICE_LOCK_PATH ?? null,
  deviceLockImplementation: process.env.BENCHMARK_DEVICE_LOCK_IMPLEMENTATION ?? null,
  target, apiVersion, role, runId, bundleName: app.app.bundleName, candidateProject: project,
  installStdout: install.stdout.trim(), launchStdout: launch.stdout.trim(), ownerId: [...ownerIds][0], status: 'completed'
}, null, 2)}\n`);
const scorer = path.join(path.dirname(new URL(import.meta.url).pathname), 'score_arkts_focused_candidate.mjs');
const scored = spawnSync(process.execPath, [scorer, '--project', project, '--migration', migration, '--role', role,
  '--output', output, '--observations', rawLog, '--native-target', target, '--hap', hap,
  ...(sourceManifest ? ['--source-manifest', sourceManifest] : [])], { encoding: 'utf8' });
process.stdout.write(scored.stdout);
process.stderr.write(scored.stderr);
process.exit(scored.status ?? 1);
