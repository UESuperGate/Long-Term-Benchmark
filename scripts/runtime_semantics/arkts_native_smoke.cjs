#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const { spawn, spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const studio = '/Applications/DevEco-Studio.app/Contents';
const sdk = path.join(os.homedir(), 'Library/OpenHarmony/Sdk');
const source = path.join(root, 'final_dev_nodes/12_report_room_final_25_05_0');
const fixtures = path.join(root, 'state_tests/runtime/arkts/native');
const production = 'entry/src/main/ets/features/ReportRoomFeature.ets';
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const writeJson = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');

async function withTemporaryWorkspace(action, { keepTemp = false, prepareOnly = false } = {}) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-arkts-native-'));
  let result;
  try {
    result = await action(work);
    return result;
  } finally {
    if (!keepTemp && !(prepareOnly && result?.prepared)) {
      fs.rmSync(work, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
      if (result?.report) result.report.temporaryProjectRemoved = true;
    }
  }
}

async function main() {
  if (process.argv.includes('--help')) {
    console.log('node scripts/runtime_semantics/arkts_native_smoke.cjs [--bundle TASK|all] [--role base|final|agent|all] [--source CANDIDATE] [--contract STAGED_CONTRACT] [--output-dir DIRECTORY] [--keep-temp] [--prepare-only] [--probe-platform] [--entry-policy JSON] [--native-ui]');
    return;
  }
  for (const flag of ['--bundle', '--role', '--source', '--contract', '--output-dir', '--entry-policy']) {
    const index = process.argv.indexOf(flag);
    if (index >= 0 && (!process.argv[index + 1] || process.argv[index + 1].startsWith('--'))) throw new Error(`${flag} requires a value`);
  }
  const bundleIndex = process.argv.indexOf('--bundle');
  const bundleTask = bundleIndex >= 0 ? (process.argv[bundleIndex + 1] || '12_report_room') : null;
  const roleIndex = process.argv.indexOf('--role');
  const role = roleIndex >= 0 ? process.argv[roleIndex + 1] : 'final';
  const sourceIndex = process.argv.indexOf('--source');
  const sourceOverride = sourceIndex >= 0 ? path.resolve(process.argv[sourceIndex + 1]) : null;
  const contractIndex = process.argv.indexOf('--contract');
  const contractOverride = contractIndex >= 0 ? path.resolve(process.argv[contractIndex + 1]) : null;
  const platformProbe = process.argv.includes('--probe-platform');
  const nativeUI = process.argv.includes('--native-ui');
  if (nativeUI && (!bundleTask || bundleTask === 'all' || role === 'all')) throw new Error('--native-ui requires one --bundle task and one --role');
  if (sourceOverride && !platformProbe && (!bundleTask || bundleTask === 'all' || role === 'all')) throw new Error('--source requires one --bundle task and one --role');
  if (contractOverride && (!bundleTask || bundleTask === 'all')) throw new Error('--contract requires one --bundle task');
  if (contractOverride && platformProbe) throw new Error('--contract cannot be combined with --probe-platform');
  const outputIndex = process.argv.indexOf('--output-dir');
  const outputDirectory = outputIndex >= 0 ? path.resolve(process.argv[outputIndex + 1]) : fixtures;
  if (platformProbe && bundleTask) throw new Error('--probe-platform cannot be combined with --bundle');
  const selectedSource = sourceOverride || source;
  const measuredProduction = platformProbe || nativeUI ? 'entry/src/main/ets/pages/Index.ets' : production;
  const entryPolicyIndex = process.argv.indexOf('--entry-policy');
  let entryRequest = null;
  if (entryPolicyIndex >= 0) {
    if (!platformProbe || !sourceOverride || !['base', 'final', 'agent'].includes(role)) {
      throw new Error('--entry-policy requires --probe-platform, --source and one --role');
    }
    const policyFile = path.resolve(process.argv[entryPolicyIndex + 1]);
    const policy = JSON.parse(fs.readFileSync(policyFile, 'utf8'));
    if (!/^\d\d_[a-z_]+$/.test(policy.taskId)) throw new Error('Invalid entry-policy task');
    const contractFile = path.join(root, 'benchmark_tasks', policy.taskId, 'transitions.json');
    const contract = JSON.parse(fs.readFileSync(contractFile, 'utf8'));
    const spec = contract.cases.find(item => item.caseId === policy.caseId);
    if (!spec) throw new Error('Entry policy names an unknown canonical case');
    entryRequest = { spec, policy, binding: { taskId: policy.taskId, role,
      policySha256: hash(policyFile), sourceSha256: hash(path.join(selectedSource, measuredProduction)) },
      provenance: { policyFile, contractFile, contractSha256: hash(contractFile) } };
  }
  const prefix = platformProbe ? 'platform' : bundleTask ? 'bundle' : 'smoke';
  const result = await withTemporaryWorkspace(async work => {
  const evidence = outputIndex >= 0 ? path.join(outputDirectory, 'native', `${bundleTask || 'smoke'}-${role}-${path.basename(work)}`) : fixtures;
  fs.mkdirSync(evidence, { recursive: true });
  fs.cpSync(selectedSource, work, { recursive: true, filter: name => !['build', '.hvigor', 'oh_modules', 'node_modules'].includes(path.basename(name)) });
  fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work, 'oh_modules'), { recursive: true, verbatimSymlinks: true });
  fs.mkdirSync(path.join(work, 'node_modules/@ohos'), { recursive: true });
  for (const name of ['hvigor', 'hvigor-ohos-plugin']) {
    fs.symlinkSync(path.join(studio, 'tools/hvigor', name), path.join(work, 'node_modules/@ohos', name));
  }
  fs.writeFileSync(path.join(work, 'local.properties'), `sdk.dir=${sdk}\nhwsdk.dir=${studio}/sdk\n`);
  const packageFile = path.join(work, 'oh-package.json5');
  const pkg = JSON.parse(fs.readFileSync(packageFile, 'utf8'));
  pkg.devDependencies = { '@ohos/hypium': '1.0.18' };
  writeJson(packageFile, pkg);
  fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true });
  if (!platformProbe) fs.copyFileSync(path.join(fixtures, 'ReportRoomNative.test.ets'), path.join(work, 'entry/src/test/ReportRoomNative.test.ets'));
  fs.writeFileSync(path.join(work, 'entry/src/test/List.test.ets'), "import nativeReportRoomTests from './ReportRoomNative.test';\nexport default function testsuite(): void { nativeReportRoomTests(); }\n");
  if (platformProbe) {
    fs.copyFileSync(path.join(__dirname, 'arkts_native_ui_preload.cjs'), path.join(work, 'native-ui-preload.cjs'));
    for (const name of ['native-platform.js', 'entry-assertion.js', 'NativePlatform.test.ets']) fs.copyFileSync(path.join(fixtures, name), path.join(work, 'entry/src/test', name));
    const sandboxRoot = path.join(work, 'native-platform-sandbox');
    fs.mkdirSync(sandboxRoot);
    fs.writeFileSync(path.join(work, 'entry/src/test/native-platform.d.ts'), 'export function probeNativePlatform(sandboxRoot: string, entryRequestJson: string): Promise<string>;\n');
    fs.writeFileSync(path.join(work, 'entry/src/test/native-platform-config.ets'), `export const sandboxRoot: string = ${JSON.stringify(sandboxRoot)};\nexport const entryRequestJson: string = ${JSON.stringify(entryRequest ? JSON.stringify(entryRequest) : '')};\n`);
    fs.writeFileSync(path.join(work, 'entry/src/test/List.test.ets'), "import suite from './NativePlatform.test';\nexport default function testsuite(): void { suite(); }\n");
  }
  const bundleManifest = bundleTask ? require('./arkts_native_bundle.cjs').generate(work, evidence, bundleTask, role, sourceOverride, nativeUI,
    { contractOverride }) : null;
  if (nativeUI) fs.copyFileSync(path.join(__dirname, 'arkts_native_ui_preload.cjs'), path.join(work, 'native-ui-preload.cjs'));
  fs.writeFileSync(path.join(work, 'native-diagnostics.cjs'), "process.on('uncaughtExceptionMonitor', error => require('node:fs').writeSync(2, '\\nARKTS_NATIVE_BUILD_ERROR ' + String(error.stack || error).slice(-12000) + '\\n'));\n");
  const command = [path.join(studio, 'tools/node/bin/node'), path.join(studio, 'tools/hvigor/hvigor/bin/hvigor.js'),
    'test', '--mode', 'module', '-p', 'module=entry@default', '-p', 'product=default',
    '-p', 'buildMode=debug', '-p', 'isLocalTest=true', '-p', 'unitTestMode=true',
    '-p', 'ohos-test-coverage=false', '--no-daemon', '--no-parallel'];
  const summaryCandidate = bundleManifest?.candidates.length === 1 ? bundleManifest.candidates[0] : null;
  const summaryProduction = summaryCandidate ? bundleManifest.production.find(item =>
    item.taskId === summaryCandidate.taskId && item.role === summaryCandidate.role) : null;
  const reportSource = summaryCandidate?.original || selectedSource;
  const reportProduction = nativeUI ? bundleManifest.candidateUI.productionSource.path :
    summaryProduction?.path || measuredProduction;
  const reportSourceSha256 = nativeUI ? bundleManifest.candidateUI.productionSource.sha256 :
    summaryProduction?.sha256 || hash(path.join(reportSource, reportProduction));
  const reportCopiedSha256 = summaryProduction?.sha256 || hash(path.join(work, reportProduction));
  const report = { schemaVersion: 1, taskId: bundleTask || entryRequest?.binding.taskId || '12_report_room', role, work, command, source: reportSource,
    productionFile: reportProduction, sourceSha256: reportSourceSha256,
    copiedSha256: reportCopiedSha256, nativeRuntimeExecuted: false, status: 'prepared',
    compile: { passed: null, scope: 'candidate application not compiled' } };
  if (entryRequest) {
    report.entryRequest = entryRequest;
    report.caseId = entryRequest.spec.caseId;
    report.statusMeaning = 'Native transport only; platform.entryAssertion.assessment controls early-failure eligibility';
  }
  if (bundleManifest) report.bundleManifest = path.join(evidence, 'bundle-manifest.json');
  writeJson(path.join(evidence, `${prefix}-report.json`), report);
  console.log(JSON.stringify({ work, command, bundleTask, role, cases: bundleManifest?.caseCount }, null, 2));
  if (process.argv.includes('--prepare-only')) return { report, evidence, prepared: true };
  const child = spawn(command[0], command.slice(1), { cwd: work, detached: true, env: {
    ...process.env, DEVECO_SDK_HOME: path.join(studio, 'sdk'), OHOS_SDK_HOME: sdk,
    NODE_PATH: path.join(work, 'node_modules'),
    NODE_OPTIONS: `--require=${path.join(work, 'native-diagnostics.cjs')}` + (platformProbe || nativeUI ? ` --require=${path.join(work, 'native-ui-preload.cjs')}` : ''),
    ...(platformProbe || nativeUI ? { LTB_NATIVE_UI_PAGES: path.join(work, 'entry/src/main/resources/base/profile/main_pages.json') } : {}),
    PATH: `${studio}/tools/node/bin:${studio}/tools/ohpm/bin:${process.env.PATH}`
  } });
  let output = '';
  for (const stream of [child.stdout, child.stderr]) stream.on('data', data => {
    output += data.toString(); process.stdout.write(data);
  });
  function terminateChild() {
    if (!child.pid) return;
    try { process.kill(-child.pid, 'SIGTERM'); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
  }
  const timer = setTimeout(() => { report.timedOut = true; terminateChild(); }, 240000);
  const monitor = setInterval(() => {
    const size = spawnSync('du', ['-sk', work], { encoding: 'utf8' }).stdout;
    report.workKiB = Number(size.split(/\s/)[0]);
    if (report.workKiB > 900 * 1024) {
      report.resourceLimit = 'Temporary project exceeded 900 MiB';
      terminateChild();
    }
    if (report.nativeProcess?.arkRuntimeLibraries.length) return;
    const processes = spawnSync('ps', ['-axo', 'pid=,command='], { encoding: 'utf8' }).stdout;
    const line = processes.split('\n').find(line => line.includes('/bin/Previewer ') && line.includes(path.basename(work)));
    if (line) {
      const pid = Number(line.trim().split(/\s/)[0]);
      const files = spawnSync('lsof', ['-p', String(pid), '-Fn'], { encoding: 'utf8' }).stdout;
      const libraries = files.split('\n').filter(line => line.includes('libark_jsruntime.dylib'));
      report.nativeProcess = { pid, command: line.trim(), arkRuntimeLibraries: libraries };
    }
  }, 150);
  let code;
  try {
    code = await new Promise((resolve, reject) => { child.on('error', reject); child.on('close', resolve); });
  } finally {
    clearTimeout(timer);
    clearInterval(monitor);
  }
  fs.writeFileSync(path.join(evidence, `${prefix}-build.log`), output.split('\n').map(line =>
    line.length > 4000 ? `[omitted SDK source dump: ${line.length} characters]` : line).join('\n'));
  const nativeLog = path.join(work, 'entry/.test/default/intermediates/test/coverage_data/coverage.log');
  const resultFile = path.join(path.dirname(nativeLog), 'test_result.txt');
  const nativeOutput = fs.existsSync(nativeLog) ? fs.readFileSync(nativeLog, 'utf8') : '';
  const nativeResult = fs.existsSync(resultFile) ? fs.readFileSync(resultFile, 'utf8') : '';
  const nativeLogPath = path.join(evidence, `${prefix}-previewer.log${bundleManifest ? '.gz' : ''}`);
  fs.writeFileSync(nativeLogPath, bundleManifest ? zlib.gzipSync(nativeOutput) : nativeOutput);
  report.nativeLogSha256 = hash(nativeLogPath);
  fs.writeFileSync(path.join(evidence, `${prefix}-hypium-result.txt`), nativeResult);
  report.exitCode = code;
  report.productionUnchanged = bundleManifest ? bundleManifest.production.every(item => hash(item.file) === item.sha256) :
    (nativeUI || report.sourceSha256 === hash(path.join(selectedSource, measuredProduction))) &&
      report.sourceSha256 === hash(path.join(work, measuredProduction));
  report.nativeRuntimeExecuted = nativeOutput.includes('ARKTS_NATIVE_BEFORE') && nativeOutput.includes('ARKTS_NATIVE_AFTER');
  report.runtime = 'native_previewer_arkvm_hypium';
  report.nativeLog = nativeLogPath;
  report.hypiumResultFile = path.join(evidence, `${prefix}-hypium-result.txt`);
  report.hypiumResult = nativeResult.split('\n').find(line => line.startsWith('Tests run:')) || '';
  report.status = code === 0 && nativeOutput.includes('ARKTS_NATIVE_SMOKE_PASS') &&
    nativeResult.includes('Tests run: 1, Failure: 0, Error: 0, Pass: 1, Ignore: 0') ? 'pass' : 'fail';
  report.compile = { passed: null, scope: 'candidate application not compiled' };
  report.runtimeCompile = { passed: output.includes('Finished :entry:default@UnitTestArkTS'), scope: 'generated test assets and Hypium ArkTS wrapper' };
  if (platformProbe) {
    const marker = 'ARKTS_NATIVE_PLATFORM_RESULT ';
    const line = nativeOutput.split('\n').find(line => line.includes(marker));
    if (line) report.platform = JSON.parse(line.slice(line.indexOf(marker) + marker.length));
    const parts = [];
    let expectedChunks = 0;
    for (const line of nativeOutput.split('\n')) {
      const marker = 'ARKTS_NATIVE_PLATFORM_CHUNK ';
      const start = line.indexOf(marker);
      if (start < 0) continue;
      const fragment = JSON.parse(line.slice(start + marker.length));
      parts[fragment.index] = fragment.text;
      expectedChunks = fragment.chunks;
    }
    if (expectedChunks && parts.filter(part => part !== undefined).length === expectedChunks) report.platform = JSON.parse(parts.join(''));
    report.nativeRuntimeExecuted = !!report.platform;
    report.status = code === 0 && report.platform && nativeResult.includes('Tests run: 1, Failure: 0, Error: 0, Pass: 1, Ignore: 0') ? 'pass' : 'fail';
    if (report.platform?.filesystem.available) {
      const file = report.platform.filesystem.source;
      report.platform.filesystem.hostVerified = file.startsWith(work + '/') && fs.existsSync(file) && fs.readFileSync(file, 'utf8') === 'native-filesystem-proof';
    }
    if (report.platform?.asyncCopy?.available) {
      const file = report.platform.asyncCopy.destination;
      report.platform.asyncCopy.hostVerified = file.startsWith(work + '/') && fs.existsSync(file) && fs.readFileSync(file, 'utf8') === 'native-filesystem-proof';
    }
    if (report.platform?.asyncFilesystem?.available) {
      const file = report.platform.asyncFilesystem.source;
      report.platform.asyncFilesystem.hostVerified = file.startsWith(work + '/') && fs.existsSync(file) &&
        fs.readFileSync(file, 'utf8') === 'native-async-filesystem-proof';
    }
  }
  const abc = path.join(work, 'entry/.test/default/intermediates/assets/default/ets/modules.abc');
  if (fs.existsSync(abc)) {
    fs.copyFileSync(abc, path.join(evidence, `${prefix}-modules.abc`));
    report.bytecode = { file: path.join(evidence, `${prefix}-modules.abc`), sha256: hash(abc), bytes: fs.statSync(abc).size };
  }
  if (bundleManifest) {
    const fragments = new Map();
    for (const line of nativeOutput.split('\n')) {
      const start = line.indexOf('ARKTS_NATIVE_ROW ');
      if (start < 0) continue;
      const fragment = JSON.parse(line.slice(start + 'ARKTS_NATIVE_ROW '.length));
      const key = fragment.taskId + ':' + fragment.role + ':' + fragment.caseId;
      if (!fragments.has(key)) fragments.set(key, { chunks: fragment.chunks, parts: [] });
      fragments.get(key).parts[fragment.index] = fragment.text;
    }
    const rows = [...fragments.values()].map(fragment => {
      if (fragment.parts.filter(part => part !== undefined).length !== fragment.chunks) throw new Error('Incomplete native evidence chunks');
      return JSON.parse(fragment.parts.join(''));
    });
    report.semantic = { total: bundleManifest.caseCount, executed: rows.length,
      passed: rows.filter(row => row.status === 'pass').length,
      failed: rows.filter(row => row.status === 'fail').length,
      notScored: rows.filter(row => row.status === 'not_scored').length };
    report.nativeRuntimeExecuted = rows.length > 0;
    report.runtime = 'native_previewer_arkvm_transpiled_production_and_unchanged_adapters';
    report.status = code === 0 && rows.length === bundleManifest.caseCount &&
      nativeResult.includes(`Tests run: ${rows.length}, Failure: 0, Error: 0, Pass: ${rows.length}, Ignore: 0`) ? 'pass' : 'fail';
    report.statusMeaning = 'Execution transport and Hypium completion only; semantic verdicts are in semantic.cases';
    report.productionUnchanged = report.productionUnchanged && bundleManifest.production.every(item => hash(item.file) === item.sha256);
    report.originalProductionUnchanged = bundleManifest.production.every(item => !item.originalFile || hash(item.originalFile) === item.sha256);
    report.observationMode = 'runtime_state_transition';
    report.observationScope = 'ArkVM executes production domain modules and evaluator adapters. Native ES-import filesystem bindings and per-case sandboxes are available. Candidate ArkUI keyed observations require --native-ui and a rendered positive anchor. Application context, preferences, media and network support must be established by per-case capability evidence; unavailable operations remain not_scored.';
    report.shims = { fs: 'existsSync over bundled module registry only', path: 'POSIX join/normalize',
      util: 'deep strict equality restricted to plain records, arrays and primitives',
      timers: 'real native timers', performance: 'Date.now elapsed wall-clock milliseconds',
      platformModules: 'real ES-import file.fs/data.preferences/router bindings with per-case capabilities; other imports remain unavailable sentinels except immutable SDK SlotType constants' };
    report.byTaskRole = [];
    const reportsDirectory = path.join(outputDirectory, 'reports');
    fs.mkdirSync(reportsDirectory, { recursive: true });
    for (const candidate of bundleManifest.candidates) {
      const cases = rows.filter(row => row.taskId === candidate.taskId && row.role === candidate.role);
      const semantic = { total: cases.length, passed: cases.filter(row => row.status === 'pass').length,
        failed: cases.filter(row => row.status === 'fail').length, notScored: cases.filter(row => row.status === 'not_scored').length, cases };
      const taskReport = { schemaVersion: 2, taskId: candidate.taskId, platform: 'arkts', role: candidate.role,
        observationMode: report.observationMode, observationScope: report.observationScope,
        runtime: report.runtime, compile: { passed: null, scope: 'candidate application not compiled' },
        runtimeCompile: { passed: output.includes('Finished :entry:default@UnitTestArkTS'), scope: 'generated JS bundle and Hypium ArkTS wrapper' },
        diagnostics: { nativeRuntimeExecuted: cases.length > 0,
          nativeProductionExecuted: cases.some(row => row.productionSources.length > 0 && row.calls.length > 0) }, provenance: candidate, semantic,
        nativeEvidence: { command, nativeProcess: report.nativeProcess, nativeLog: report.nativeLog,
          bundleSha256: bundleManifest.bundleSha256, manifest: report.bundleManifest,
          bytecode: report.bytecode, shims: report.shims } };
      const contractRecord = bundleManifest.contracts.find(item => item.taskId === candidate.taskId);
      const contract = JSON.parse(fs.readFileSync(contractRecord.file, 'utf8'));
      if (cases.length !== contract.cases.length || contract.cases.some(item => !cases.some(row => row.caseId === item.caseId && row.traceDigest === item.traceDigest))) {
        taskReport.diagnostics.incompleteCanonicalEvidence = true;
        report.status = 'fail';
      }
      writeJson(path.join(reportsDirectory, `arkts_${candidate.taskId}_${candidate.role}.json`), taskReport);
      report.byTaskRole.push({ taskId: candidate.taskId, role: candidate.role, ...semantic, cases: undefined });
    }
  }
  report.workKiB = Number(spawnSync('du', ['-sk', work], { encoding: 'utf8' }).stdout.split(/\s/)[0]);
  report.finishedAt = new Date().toISOString();
  return { report, evidence };
  }, { keepTemp: process.argv.includes('--keep-temp'), prepareOnly: process.argv.includes('--prepare-only') });
  const { report, evidence } = result;
  writeJson(path.join(evidence, `${prefix}-report.json`), report);
  if (result.prepared) return;
  if (bundleTask === 'all' && role === 'all') writeJson(path.join(outputDirectory, 'arkts_native_summary.json'), report);
  console.log(JSON.stringify({ status: report.status, nativeRuntimeExecuted: report.nativeRuntimeExecuted,
    nativeProcess: report.nativeProcess, semantic: report.semantic && { ...report.semantic, cases: undefined },
    report: path.join(evidence, `${prefix}-report.json`) }, null, 2));
  process.exitCode = report.status === 'pass' ? 0 : 1;
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });

module.exports = { withTemporaryWorkspace };
