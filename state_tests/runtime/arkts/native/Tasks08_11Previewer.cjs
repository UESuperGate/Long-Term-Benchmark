'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { install } = require('./Tasks08_11NativeUi.install.cjs');
const root = path.resolve(__dirname, '../../../..');
const studio = '/Applications/DevEco-Studio.app/Contents';
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

// Bounded, serialized LOCAL Previewer validation. Never invokes hdc or a device.
function run(role = 'final', output = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks08_11-proof-'))) {
  if (!['base', 'final', 'agent'].includes(role)) throw new Error('Unknown candidate role');
  const processes = spawnSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).stdout;
  if (processes.split('\n').some(line => /\/bin\/Previewer |hvigor.js (test|assemble)/.test(line)))
    throw new Error('Another native Previewer/build is active. Retry after its owner finishes.');
  fs.mkdirSync(output, { recursive: true });
  const prepare = spawnSync(process.execPath, [path.join(root, 'scripts/runtime_semantics/arkts_native_smoke.cjs'),
    '--bundle', '11_room_upgrade_navigation', '--role', role, '--native-ui', '--prepare-only', '--output-dir', output],
  { cwd: root, encoding: 'utf8', timeout: 60000, maxBuffer: 4 * 1024 * 1024 });
  if (prepare.status !== 0) throw new Error(prepare.stderr || prepare.stdout);
  const setup = JSON.parse(prepare.stdout);
  const work = setup.work;
  const report = { role, work, output, runtime: 'native_previewer_arkui', rows: [],
    limitations: 'Local native keyed click events, not physical device touches. Compilation/transport success is separate from canonical semantic verdicts.' };
  report.fixtureSources = ['Tasks08_11Previewer.cjs', 'Tasks08_11NativeUi.install.cjs', 'Tasks08_11RoomObserver.js', 'Tasks08_11RoomObserver.d.ts']
    .map(name => ({ file: path.join(__dirname, name), sha256: hash(path.join(__dirname, name)) }));
  report.adapterSha256 = hash(path.join(__dirname, '../tasks08_11.cjs'));
  report.contractSha256 = hash(path.join(root, 'benchmark_tasks/11_room_upgrade_navigation/transitions.json'));
  try {
    const before = new Map();
    function collect(directory) {
      for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        const file = path.join(directory, entry.name);
        if (entry.isDirectory()) collect(file);
        else before.set(file, hash(file));
      }
    }
    collect(path.join(work, 'entry/src/main'));
    report.observer = install(work);
    const result = spawnSync(setup.command[0], setup.command.slice(1), { cwd: work, encoding: 'utf8',
      timeout: 240000, detached: true, maxBuffer: 16 * 1024 * 1024, env: { ...process.env,
        DEVECO_SDK_HOME: path.join(studio, 'sdk'), OHOS_SDK_HOME: path.join(os.homedir(), 'Library/OpenHarmony/Sdk'),
        NODE_PATH: path.join(work, 'node_modules'),
        NODE_OPTIONS: `--require=${path.join(work, 'native-diagnostics.cjs')} --require=${path.join(work, 'native-ui-preload.cjs')}`,
        LTB_NATIVE_UI_PAGES: path.join(work, 'entry/src/main/resources/base/profile/main_pages.json') } });
    if (result.error && result.pid) {
      try { process.kill(-result.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    }
    fs.writeFileSync(path.join(output, 'Tasks08_11-build.log'), result.stdout + result.stderr);
    report.exitCode = result.status;
    report.error = result.error && String(result.error);
    const bytecode = path.join(work, 'entry/.test/default/intermediates/assets/default/ets/modules.abc');
    report.compiled = fs.existsSync(bytecode);
    if (report.compiled) report.bytecodeSha256 = hash(bytecode);
    report.productionUnchanged = [...before].every(([file, digest]) => hash(file) === digest);
    const coverage = path.join(work, 'entry/.test/default/intermediates/test/coverage_data');
    const logFile = path.join(coverage, 'coverage.log');
    const chunks = new Map();
    if (fs.existsSync(logFile)) {
      fs.copyFileSync(logFile, path.join(output, 'Tasks08_11-previewer.log'));
      for (const line of fs.readFileSync(logFile, 'utf8').split('\n')) {
        const marker = 'ARKTS_NATIVE_ROW ';
        const index = line.indexOf(marker);
        if (index < 0) continue;
        const part = JSON.parse(line.slice(index + marker.length));
        if (!chunks.has(part.caseId)) chunks.set(part.caseId, { count: part.chunks, parts: [] });
        chunks.get(part.caseId).parts[part.index] = part.text;
      }
      for (const fragment of chunks.values()) {
        if (fragment.parts.filter(part => part !== undefined).length !== fragment.count) throw new Error('Incomplete native case evidence');
        report.rows.push(JSON.parse(fragment.parts.join('')));
      }
    }
    if (fs.existsSync(path.join(coverage, 'test_result.txt')))
      report.hypium = fs.readFileSync(path.join(coverage, 'test_result.txt'), 'utf8');
    report.nativeExecutedCaseIds = report.rows.map(row => row.caseId);
    const canonical = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/11_room_upgrade_navigation/transitions.json'), 'utf8'));
    for (const spec of canonical.cases) {
      if (!report.rows.some(row => row.caseId === spec.caseId)) report.rows.push({
        taskId: canonical.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'not_scored',
        reason: 'Native compile/transport did not return a complete case record; inspect Tasks08_11-build.log',
        nativeRuntimeExecuted: false, invariantChecks: [],
        unsupportedInvariants: spec.invariants.map(description => ({ description, reason: 'Native case did not execute' })) });
    }
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
    report.temporaryProjectRemoved = true;
    fs.writeFileSync(path.join(output, 'Tasks08_11-report.json'), JSON.stringify(report, null, 2));
  }
  return { output, compiled: report.compiled, exitCode: report.exitCode, productionUnchanged: report.productionUnchanged,
    cases: report.rows.map(row => ({ caseId: row.caseId, status: row.status, reason: row.reason })) };
}

module.exports = { run };
if (require.main === module) console.log(JSON.stringify(run(process.argv[2], process.argv[3]), null, 2));
