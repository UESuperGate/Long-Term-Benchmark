'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { normalizeRow, sourceInventory, cleanupArtifacts, lockRace, retryablePreflight } = require('./task11_arkts_strict_runtime.cjs');
const { removeCopiedHaps } = require('./task09_hap_cleanup.cjs');
const root = path.resolve(__dirname, '../..');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const rec = file => { const bytes = fs.readFileSync(file); return { path: path.resolve(file), bytes: bytes.length, sha256: sha(bytes) }; };
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const write = (file, data) => fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
function value(args, key, fallback) { const i = args.indexOf(key); return i < 0 ? fallback : args[i + 1]; }

async function main() {
  const args = process.argv.slice(2), role = value(args, '--role');
  const source = path.resolve(value(args, '--source')), output = path.resolve(value(args, '--output'));
  const artifacts = path.resolve(value(args, '--artifact-root'));
  const timeout = Number(value(args, '--timeout', '3600'));
  if (!['base', 'final', 'agent'].includes(role) || timeout <= 0 || timeout > 3600 || fs.existsSync(output)) throw new Error('Invalid repository runtime args');
  fs.mkdirSync(artifacts, { recursive: true }); fs.mkdirSync(path.dirname(output), { recursive: true });
  const started = Date.now(), inventory = sourceInventory(source), records = [], rows = [], hapCleanup = [];
  const contractFile = path.join(root, 'benchmark_tasks/10_media_upload_quality/transitions.json');
  const contract = JSON.parse(fs.readFileSync(contractFile));
  const selected = value(args, '--case');
  const specs = contract.cases.filter(spec => !selected || spec.caseId === selected);
  const remaining = () => { const ms = timeout * 1000 - (Date.now() - started); if (ms <= 0) throw new Error('Unified Task10 runtime deadline exhausted'); return ms; };
  const run = (name, command, argv, cap) => {
    const result = spawnSync(command, argv, { cwd: root, timeout: Math.min(remaining(), cap), encoding: 'utf8', maxBuffer: 12 * 1024 * 1024 });
    const log = path.join(artifacts, name + '.log'); fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''));
    records.push({ name, command: [command, ...argv], exitCode: result.status, log: rec(log) });
    if (result.error || result.status !== 0) throw new Error(name + ': ' + (result.error || result.status));
  };
  const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
  const targets = (spawnSync(hdc, ['list', 'targets'], { encoding: 'utf8', timeout: 30000 }).stdout || '').trim().split(/\s+/).filter(Boolean);
  if (targets.length !== 1) throw new Error('Expected exactly one API23 device');
  const serial = targets[0], lock = '/tmp/ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16);
  const sharedExecutor = path.join(__dirname, 'arkts_device_execute.cjs');
  let executor = fs.readFileSync(sharedExecutor, 'utf8');
  executor = executor.replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';')
    .replace("const providerHostFile = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');",
      'const providerHostFile = ' + JSON.stringify(path.join(root, 'state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs')) + ';');
  const executeFile = path.join(artifacts, 'task10-repository-execute.generated.cjs'); fs.writeFileSync(executeFile, executor);
  try {
    for (const spec of specs) {
      const directory = path.join(artifacts, spec.caseId), build = path.join(directory, 'device-build-report.json');
      let executionDirectory;
      try {
        run('build-' + spec.caseId, process.execPath, [path.join(__dirname, 'task10_arkts_repository_build.cjs'),
          '--source', source, '--role', role, '--case', spec.caseId, '--output-dir', directory], 600000);
        for (let attempt = 1; attempt <= 3; attempt++) {
          while (fs.existsSync(lock)) { remaining(); await pause(1000); }
          executionDirectory = path.join(directory, 'execution-' + attempt);
          try { run('device-' + spec.caseId + '-' + attempt, process.execPath, [executeFile, build, serial, executionDirectory], 300000); break; }
          catch (error) {
            const log = fs.readFileSync(path.join(artifacts, 'device-' + spec.caseId + '-' + attempt + '.log'), 'utf8');
            if (attempt === 3 || !(lockRace(log) || retryablePreflight(executionDirectory))) throw error;
          }
        }
        const executionFile = path.join(executionDirectory, 'device-execution.json');
        const execution = JSON.parse(fs.readFileSync(executionFile));
        const native = execution.rows.find(row => row.caseId === spec.caseId);
        if (!native || !execution.transportCompleted || !execution.cleanup?.ownedAppUninstalled || !execution.candidateAbsentBeforeInstall)
          throw new Error('Actual cold production device execution incomplete');
        let normalized;
        if (native.status === 'not_scored') normalized = { ...native, key: spec.key, transitionExecuted: false };
        else normalized = normalizeRow(native, spec, role, path.join(directory, 'snapshots'));
        rows.push({ ...normalized, freshInstall: true, build: rec(build), execution: rec(executionFile) });
      } finally { if (fs.existsSync(build)) hapCleanup.push({ caseId: spec.caseId, ...removeCopiedHaps(build) }); }
    }
    if (sourceInventory(source).sha256 !== inventory.sha256) throw new Error('Production source changed');
    const semantic = { total: rows.length, passed: rows.filter(row => row.status === 'pass').length,
      failed: rows.filter(row => row.status === 'fail').length, notScored: rows.filter(row => row.status === 'not_scored').length, cases: rows };
    const report = { schemaVersion: 2, taskId: contract.taskId, platform: 'arkts', role, target: source,
      observationMode: 'runtime_state_transition', compile: { passed: null, status: 'not_run', scope: 'standalone_candidate_application_build' },
      runtimeCompile: { passed: true, status: 'passed', scope: 'actual_original_application_and_native_test_packages' }, semantic,
      provenance: { productionSourceRoot: source, sourceInventory: inventory, contract: rec(contractFile), runner: rec(__filename),
        runtimeBinding: 'task10.original-page.repository.v2', commands: records, hapCleanup },
      diagnostics: { adapter: semantic.notScored ? 'partial' : 'ready', serial, strictRuntime: { sourceParameterized: true,
        entryEvaluator: true, runtimeOrDeviceEvaluator: true, sourceObserverUsed: false, fallbackUsed: false,
        candidateSmoke: { passed: true, source }, cleanup: cleanupArtifacts(artifacts) } }, elapsedSeconds: (Date.now() - started) / 1000 };
    write(output, report);
    console.log(JSON.stringify({ semantic: { ...semantic, cases: undefined }, output }));
  } finally { write(path.join(artifacts, 'binary-cleanup.json'), cleanupArtifacts(artifacts)); }
}
module.exports = { main };
if (require.main === module) main().catch(error => { console.error(error.stack || String(error)); process.exitCode = 1; });
