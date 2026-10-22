#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { classifyEntry } = require('./task10_arkts_entry_binding.cjs');
const { assessBaseEntry } = require('./task10_arkts_closure_guard.cjs');

const root = path.resolve(__dirname, '../..');
const builder = path.join(__dirname, 'arkts_native_device.cjs');
const baseDevice = path.join(__dirname, 'Task10BaseAllDevice.cjs');
const finalDevice = path.join(__dirname, 'Task10FinalAllDevice.cjs');
const contractFile = path.join(root, 'benchmark_tasks/10_media_upload_quality/transitions.json');
const studio = '/Applications/DevEco-Studio.app/Contents';
const json5 = require(path.join(studio, 'tools/hvigor/hvigor-ohos-plugin/node_modules/json5'));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => { const bytes = fs.readFileSync(file); return {
  path: path.resolve(file), bytes: bytes.length, sha256: sha(bytes) }; };
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function value(args, flag, fallback) {
  const index = args.indexOf(flag);
  if (index < 0) return fallback;
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' requires a value');
  return args[index + 1];
}

function files(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? files(file) : entry.isFile() ? [file] : [];
  });
}

function sourceInventory(source) {
  const digest = crypto.createHash('sha256');
  const ignored = new Set(['.git', '.hvigor', 'build', 'oh_modules', 'node_modules']);
  let count = 0;
  for (const file of files(source).sort()) {
    const relative = path.relative(source, file);
    if (relative.split(path.sep).some(part => ignored.has(part))) continue;
    const name = Buffer.from(relative.split(path.sep).join('/'));
    const bytes = fs.readFileSync(file);
    digest.update(Buffer.from(String(name.length) + ':')); digest.update(name);
    digest.update(Buffer.from(String(bytes.length) + ':')); digest.update(bytes); count++;
  }
  return { root: path.resolve(source), files: count, sha256: digest.digest('hex') };
}

function exact(expected, observed) {
  if (expected && typeof expected === 'object' && !Array.isArray(expected))
    return observed && typeof observed === 'object' && !Array.isArray(observed) &&
      Object.entries(expected).every(([key, item]) => key in observed && exact(item, observed[key]));
  if (Array.isArray(expected)) return Array.isArray(observed) && expected.length === observed.length &&
    expected.every((item, index) => exact(item, observed[index]));
  return typeof expected === typeof observed && expected === observed;
}

function normalizeRow(row, spec, role) {
  if (row.caseId !== spec.caseId || row.traceDigest !== spec.traceDigest || !['pass', 'fail'].includes(row.status))
    throw new Error('Task10 device row identity/verdict mismatch: ' + spec.caseId);
  const raw = row.checkpoints || [];
  if (raw.length < 2) throw new Error(spec.caseId + ' lacks real runtime checkpoints');
  const checkpoints = [
    { name: 'before:event', sourceName: raw[0].name || raw[0].label,
      evidenceSha256: sha(Buffer.from(JSON.stringify(raw[0]))) },
    { name: 'after:event', sourceName: raw[raw.length - 1].name || raw[raw.length - 1].label,
      evidenceSha256: sha(Buffer.from(JSON.stringify(raw[raw.length - 1]))) },
  ];
  const checks = new Map((row.invariantChecks || []).map(check => [check.description || check.invariant || check.text,
    check.passed === undefined ? check.status === 'pass' : check.passed]));
  if (row.failureKind === 'semantic_missing_feature_entry') {
    const positive = row.observed?.originalMediaSendCompleted === true || row.observed?.positiveControl;
    if (row.status !== 'fail' || !positive) throw new Error(spec.caseId + ' base positive control was not completed');
    return { ...row, key: spec.key, role, transitionExecuted: false,
      entryFailureEvidence: { positiveControlCompleted: true,
        kind: 'reachable_common_preview_then_missing_version_bounded_entry' },
      invariantChecks: spec.invariants.map(description => ({ description, passed: false,
        evidence: 'Final transition entry absent after real common preview/send positive control.' })) };
  }
  for (const invariant of spec.invariants || []) if (typeof checks.get(invariant) !== 'boolean')
    throw new Error(spec.caseId + ' missing executable invariant: ' + invariant);
  const matches = exact(spec.expected, row.observed || {});
  const invariantsPass = spec.invariants.every(item => checks.get(item) === true);
  if (row.status === 'pass' && (!matches || !invariantsPass))
    throw new Error(spec.caseId + ' PASS differs from the canonical state/invariants');
  return { ...row, key: spec.key, role, transitionExecuted: true, checkpoints };
}

function cleanupArtifacts(directory) {
  const suffixes = new Set(['.apk', '.hap', '.aab', '.apks', '.abc', '.dex', '.so', '.jar', '.class', '.har']);
  const binaryHashes = [];
  for (const file of files(directory)) if (suffixes.has(path.extname(file).toLowerCase())) {
    binaryHashes.push(fileRecord(file)); fs.unlinkSync(file);
  }
  const disposable = new Set(['build', '.hvigor', 'oh_modules', 'node_modules']);
  const directories = [];
  const visit = current => {
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) if (entry.isDirectory()) {
      const child = path.join(current, entry.name);
      if (disposable.has(entry.name)) directories.push(child); else visit(child);
    }
  };
  visit(directory);
  directories.sort((a, b) => b.split(path.sep).length - a.split(path.sep).length)
    .forEach(item => fs.rmSync(item, { recursive: true, force: true }));
  const remaining = files(directory).filter(file => suffixes.has(path.extname(file).toLowerCase()));
  return { performed: true, binaryHashes, binaryArtifactsRetained: remaining.length > 0,
    retainedEvidenceExcludesBinaries: remaining.length === 0, temporaryBuildRemoved: true,
    temporaryArtifactRootRemoved: true, remainingBinaries: remaining };
}

function deriveDeviceScript(templateFile, destination, options) {
  let source = fs.readFileSync(templateFile, 'utf8');
  source = source.replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';');
  source = source.replace(/const bundleName = '[^']+';/, 'const bundleName = ' + JSON.stringify(options.bundleName) + ';');
  source = source.replace(/const buildDir = path\.join\(root,\n\s*'[^']+'\);/, 'const buildDir = ' + JSON.stringify(options.buildDir) + ';');
  source = source.replace("const buildReport = path.join(buildDir, 'device-build-report.json');",
    'const buildReport = ' + JSON.stringify(options.buildReport) + ';');
  source = source.replace("const hap = path.join(buildDir, 'entry-default-unsigned.hap');",
    'const hap = ' + JSON.stringify(options.hap) + ';');
  source = source.replace(/const contractFile = path\.join\(root,\n\s*'[^']+'\);/,
    'const contractFile = ' + JSON.stringify(contractFile) + ';');
  source = source.replace('  fs.mkdirSync(lock);',
    "  if (process.env.LTB_DEVICE_LOCK_PREACQUIRED !== '1') fs.mkdirSync(lock);");
  source = source.replace("role: 'base',", 'role: ' + JSON.stringify(options.role) + ',');
  source = source.replace("role: 'final',", 'role: ' + JSON.stringify(options.role) + ',');
  if (!source.includes('const bundleName = ' + JSON.stringify(options.bundleName)) ||
      !source.includes('const buildReport = ' + JSON.stringify(options.buildReport)) ||
      !source.includes('const contractFile = ' + JSON.stringify(contractFile)) ||
      !source.includes("process.env.LTB_DEVICE_LOCK_PREACQUIRED !== '1'"))
    throw new Error('Task10 device runner template shape changed');
  fs.writeFileSync(destination, source);
}

async function main() {
  const args = process.argv.slice(2);
  const source = path.resolve(value(args, '--source'));
  const role = value(args, '--role');
  const output = path.resolve(value(args, '--output'));
  const artifactRoot = path.resolve(value(args, '--artifact-root'));
  const platform = value(args, '--platform');
  const timeoutSeconds = Number(value(args, '--timeout', '3600'));
  if (platform !== 'arkts' || !['base', 'final', 'agent'].includes(role) ||
      !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 3600)
    throw new Error('Invalid Task10 ArkTS strict arguments');
  if (!fs.statSync(source).isDirectory() || fs.existsSync(output)) throw new Error('Invalid source or existing output');
  fs.mkdirSync(artifactRoot, { recursive: true });
  const started = process.hrtime.bigint();
  const elapsed = () => Number(process.hrtime.bigint() - started) / 1e9;
  const remainingMs = () => {
    const budget = Math.floor((timeoutSeconds - elapsed()) * 1000);
    if (budget <= 0) throw new Error('Task10 ArkTS strict runner exhausted its unified deadline');
    return budget;
  };
  const sourceBefore = sourceInventory(source);
  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '10_media_upload_quality' || contract.revision !== 4 || contract.cases.length !== 9)
    throw new Error('Task10 canonical contract identity/count changed');
  const commands = [];
  const run = (name, command, commandArgs, capMs, extraEnvironment = {}) => {
    const budget = Math.min(remainingMs(), capMs);
    const result = spawnSync(command, commandArgs, { cwd: root, encoding: 'utf8', timeout: budget,
      env: { ...process.env, ...extraEnvironment },
      maxBuffer: 24 * 1024 * 1024 });
    const log = path.join(artifactRoot, name + '.log');
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''));
    commands.push({ name, command: [command, ...commandArgs], budgetMs: budget, exitCode: result.status,
      error: result.error && String(result.error), log: fileRecord(log) });
    if (result.error || result.status !== 0) throw new Error(name + ' failed: ' + (result.error || result.status));
  };

  // Keep original build JSON until the host retainer has copied its exact bytes.
  const buildDir = path.join(artifactRoot, 'application-artifacts');
  run('build', process.execPath, [builder, '--source', source, '--task', '10_media_upload_quality',
    '--fixture', 'bundle', '--role', role, '--case', contract.cases[8].caseId,
    '--output-dir', buildDir], Math.min(900000, remainingMs()));
  const buildReport = path.join(buildDir, 'device-build-report.json');
  const build = JSON.parse(fs.readFileSync(buildReport));
  if (build.status !== 'built_not_executed' || build.runtimeCompile?.passed !== true ||
      build.productionUnchanged !== true || build.copiedProductionUnchanged !== true ||
      build.temporaryProjectRemoved !== true || build.source !== source || build.role !== role)
    throw new Error('Task10 source-parameterized HAP build provenance is incomplete');
  const app = json5.parse(fs.readFileSync(path.join(source, 'AppScope/app.json5'), 'utf8')).app;
  if (!/^com\.[A-Za-z0-9_.]+$/.test(app.bundleName)) throw new Error('Invalid Task10 candidate bundle name');
  const appHaps = build.haps.filter(item => !String(item.path).includes('ohosTest'));
  if (appHaps.length !== 1 || appHaps[0].sha256 !== sha(fs.readFileSync(appHaps[0].path)))
    throw new Error('Task10 application HAP identity is ambiguous');
  const generated = path.join(artifactRoot, 'task10-device.generated.cjs');
  const targetText = spawnSync(path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc'),
    ['list', 'targets'], { encoding: 'utf8', timeout: 30000 }).stdout || '';
  const targets = targetText.trim().split(/\s+/).filter(Boolean);
  if (targets.length !== 1) throw new Error('Expected exactly one OpenHarmony target');
  const lock = path.join('/tmp', 'ltb-arkts-device-' + sha(Buffer.from(targets[0])).slice(0, 16));
  while (true) {
    remainingMs();
    try { fs.mkdirSync(lock); break; }
    catch (error) { if (error.code !== 'EEXIST') throw error; await sleep(2000); }
  }
  const deviceDir = path.join(artifactRoot, 'device');
  let entryCapability;
  try {
    const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
    const invoke = (name, args) => {
      const result = spawnSync(hdc, ['-t', targets[0], ...args], { encoding: 'utf8',
        timeout: Math.min(remainingMs(), 60000), maxBuffer: 8 * 1024 * 1024 });
      const log = path.join(artifactRoot, 'entry-' + name + '.log');
      fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''));
      if (result.error || result.status !== 0) throw new Error('Runtime entry probe transport failed: ' + name);
      return (result.stdout || '') + (result.stderr || '');
    };
    if (invoke('installed', ['shell', 'bm', 'dump', '-a']).split('\n').some(line => line.trim() === app.bundleName))
      throw new Error('Runtime entry probe requires an absent candidate app');
    let owned = false;
    try {
      if (!invoke('install', ['install', '-r', appHaps[0].path]).includes('install bundle successfully'))
        throw new Error('Runtime entry probe install failed');
      owned = true;
      invoke('launch', ['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', app.bundleName, '-m', 'entry']);
      for (let attempt = 0; attempt < 30 && !entryCapability; attempt++) {
        const remote = '/data/local/tmp/task10-entry-' + process.pid + '-' + attempt + '.json';
        try {
          invoke('dump-' + attempt, ['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', app.bundleName]);
          const tree = JSON.parse(invoke('read-' + attempt, ['shell', 'cat', remote]));
          const flatten = node => [node.attributes || {}, ...(node.children || []).flatMap(flatten)];
          const nodes = flatten(tree);
          const one = id => nodes.filter(node => node.id === id && node.visible === 'true').length === 1;
          let selected = classifyEntry(nodes);
          const originalMediaHint = nodes.some(node => node.type === 'Button' &&
            node.visible === 'true' && node.text === 'Send original');
          if (selected.commonPreview || (selected.binding === 'production_repository_probe_required' && originalMediaHint)) {
            const closureEligibility = assessBaseEntry(sourceBefore, tree);
            selected = { ...selected, closureEligibility };
            if (!closureEligibility.eligible) selected = { ...selected,
              binding: 'unknown_entry_not_scored', commonPreview: false, qualityPreview: false };
          }
          if (selected.binding === 'unbound' && nodes.some(node => node.type === 'root' &&
              node.pagePath === 'pages/Index' && node.visible === 'true') &&
              nodes.some(node => ['Button', 'TextInput', 'Toggle'].includes(node.type) && node.visible === 'true')) {
            selected = { ...selected, binding: 'unknown_entry_not_scored',
              closureEligibility: assessBaseEntry(sourceBefore, tree) };
          }
          if (selected.binding !== 'unbound') {
            const snapshot = path.join(artifactRoot, 'entry-capability.snapshot.json');
            fs.writeFileSync(snapshot, JSON.stringify(tree, null, 2) + '\n');
            entryCapability = { ...selected, snapshot: fileRecord(snapshot),
              source: 'actual initial production ArkUI controls; independent of role/source name' };
          }
        } catch (error) {
          fs.writeFileSync(path.join(artifactRoot, 'entry-observation-' + attempt + '.log'), String(error));
        } finally { invoke('remote-cleanup-' + attempt, ['shell', 'rm', '-f', remote]); }
        if (!entryCapability) await sleep(200);
      }
      if (!entryCapability) throw new Error('No unambiguous real production preview entry; unscored');
    } finally {
      if (owned && !invoke('uninstall', ['uninstall', app.bundleName]).includes('uninstall bundle successfully'))
        throw new Error('Runtime entry probe failed to uninstall owned app');
    }
    if (!['production_repository_probe_required', 'unknown_entry_not_scored'].includes(entryCapability.binding)) {
      const reviewedMissingEntry = entryCapability.binding === 'canonical_original_media_ui' &&
        entryCapability.closureEligibility?.eligible === true;
      if (entryCapability.commonPreview && !reviewedMissingEntry) throw new Error('Unreviewed common entry cannot produce semantic failures');
      deriveDeviceScript(reviewedMissingEntry ? baseDevice : finalDevice, generated, {
        bundleName: app.bundleName, buildDir, buildReport, hap: appHaps[0].path, role,
      });
      run('device', process.execPath, [generated, '--output', deviceDir], remainingMs(),
        { LTB_DEVICE_LOCK_PREACQUIRED: '1' });
    }
  } finally {
    try { fs.rmdirSync(lock); } catch (_) {}
  }
  if (entryCapability.binding === 'unknown_entry_not_scored') {
    const buildRecord = fileRecord(buildReport);
    const cleanup = cleanupArtifacts(artifactRoot);
    const reason = 'Unknown/extra/renamed entry or unreviewed production closure; canonical transitions were not dispatched.';
    const rows = contract.cases.map(spec => ({ taskId: contract.taskId, role, caseId: spec.caseId,
      key: spec.key, traceDigest: spec.traceDigest, status: 'not_scored', reason,
      transitionExecuted: false, observed: null, invariantChecks: [],
      unevaluatedInvariants: spec.invariants, checkpoints: [] }));
    const report = { schemaVersion: 2, taskId: contract.taskId, platform, role, target: source,
      observationMode: 'runtime_state_transition',
      compile: { passed: null, status: 'not_run', scope: 'standalone_candidate_application_build' },
      runtimeCompile: { passed: true, status: 'passed', scope: 'application_entry_probe_only_not_canonical_transitions' },
      semantic: { total: rows.length, passed: 0, failed: 0, notScored: rows.length, cases: rows },
      provenance: { productionSourceRoot: source, sourceInventory: sourceBefore, entryCapability,
        entryEligibilityRejected: true, buildReport: buildRecord, contract: fileRecord(contractFile),
        runtimeBinding: 'task10.arkts.unbound-entry.v1', runner: fileRecord(__filename), commands },
      diagnostics: { adapter: 'unbound_not_scored', transport: 'ready', serial: targets[0], strictRuntime: {
        sourceParameterized: true, entryEvaluator: true, runtimeOrDeviceEvaluator: true,
        sourceObserverUsed: false, fallbackUsed: false, candidateSmoke: { passed: true, source }, cleanup } },
      elapsedSeconds: Number(elapsed().toFixed(3)) };
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    return;
  }
  if (entryCapability.binding === 'production_repository_probe_required') {
    run('repository-runtime', process.execPath, [path.join(__dirname, 'task10_arkts_repository_runtime.cjs'),
      '--source', source, '--role', role, '--platform', platform, '--timeout', String(remainingMs() / 1000),
      '--output', output, '--artifact-root', path.join(artifactRoot, 'repository-runtime')], remainingMs());
    const repository = JSON.parse(fs.readFileSync(output));
    repository.provenance.entryCapability = entryCapability;
    repository.provenance.entryProbeCleanup = cleanupArtifacts(artifactRoot);
    repository.provenance.outerRunner = fileRecord(__filename);
    fs.writeFileSync(output, JSON.stringify(repository, null, 2) + '\n');
    return;
  }
  const deviceReport = path.join(deviceDir, 'report.json');
  const device = JSON.parse(fs.readFileSync(deviceReport));
  if (device.status !== 'passed' || device.compile?.passed !== true ||
      device.diagnostics?.cleanup?.ownedAppUninstalled !== true ||
      device.diagnostics?.cleanup?.deviceLockRemoved !== true)
    throw new Error('Task10 fresh device execution/cleanup is incomplete');
  const rows = contract.cases.map(spec => {
    const row = device.semantic.cases.find(item => item.caseId === spec.caseId);
    if (!row) throw new Error('Missing Task10 device row: ' + spec.caseId);
    return normalizeRow(row, spec, role);
  });
  if (sourceInventory(source).sha256 !== sourceBefore.sha256) throw new Error('Task10 evaluator mutated candidate source');
  const semantic = { total: 9, passed: rows.filter(row => row.status === 'pass').length,
    failed: rows.filter(row => row.status === 'fail').length, notScored: 0, cases: rows };
  const retainedProvenance = {
    generatedDeviceRunner: fileRecord(generated),
    buildReport: fileRecord(buildReport),
    deviceReport: fileRecord(deviceReport),
  };
  const cleanup = cleanupArtifacts(artifactRoot);
  if (cleanup.binaryArtifactsRetained || !cleanup.temporaryBuildRemoved) throw new Error('Task10 binary cleanup incomplete');
  const report = { schemaVersion: 2, taskId: '10_media_upload_quality', platform: 'arkts', role,
    target: source, source, observationMode: 'runtime_state_transition',
    compile: { passed: null, status: 'not_run', scope: 'standalone_candidate_application_build' },
    runtimeCompile: { passed: true, status: 'passed', scope: 'source_parameterized_application_hap_and_device_ui' },
    semantic, provenance: { productionSourceRoot: source, sourceInventory: sourceBefore,
      entryCapability,
      contract: fileRecord(contractFile), runner: fileRecord(__filename), ...retainedProvenance, commands },
    diagnostics: { adapter: 'ready', transport: 'ready', serial: targets[0], strictRuntime: {
      sourceParameterized: true, entryEvaluator: true, runtimeOrDeviceEvaluator: true,
      sourceObserverUsed: false, fallbackUsed: false, candidateSmoke: { passed: true, source }, cleanup } },
    elapsedSeconds: Number(elapsed().toFixed(3)) };
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ output, semantic: { passed: semantic.passed, failed: semantic.failed,
    notScored: semantic.notScored }, elapsedSeconds: report.elapsedSeconds }));
}

module.exports = { exact, normalizeRow, cleanupArtifacts, deriveDeviceScript, sourceInventory };

if (require.main === module) main().catch(error => {
  console.error(error.stack || String(error)); process.exitCode = 1;
});
