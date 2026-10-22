#!/usr/bin/env node
'use strict';

// Task18 archived-candidate packaging diagnostics only. No device execution,
// baseline bypass, new agent generation, or report promotion is implemented.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const TASK = '18_custom_notification_sounds';
const ARCHIVE = 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair';
const REPORTS = 'experiment_results/runtime_transition_20261019/reports';
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const json = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
const record = file => ({ path: file, bytes: fs.statSync(file).size, sha256: sha(fs.readFileSync(file)) });
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const inside = (parent, file) => file === parent || file.startsWith(parent + path.sep);
function requireThat(value, message) { if (!value) throw new Error(message); }
function canonicalDestination(value) {
  const destination = path.resolve(value);
  let ancestor = destination;
  while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor);
  return path.join(fs.realpathSync(ancestor), path.relative(ancestor, destination));
}
function safeRelative(name) {
  requireThat(typeof name === 'string' && name.length && !path.isAbsolute(name) &&
    !name.split('/').some(part => !part || part === '.' || part === '..') && !name.includes('\\'), 'Unsafe relative source path');
  return name;
}

function manifest(directory) {
  const entries = [];
  let bytes = 0;
  function visit(dir) {
    for (const item of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name < b.name ? -1 : 1)) {
      if (dir === directory && item.name === '.git') continue;
      const file = path.join(dir, item.name);
      requireThat(!item.isSymbolicLink(), 'Candidate symlink is unsupported: ' + file);
      if (item.isDirectory()) visit(file);
      else {
        requireThat(item.isFile(), 'Non-file candidate entry: ' + file);
        const stat = fs.statSync(file);
        bytes += stat.size;
        requireThat(bytes <= 32 * 1024 * 1024 && entries.length < 2048, 'Candidate exceeds bounded diagnostic source budget');
        entries.push({ path: path.relative(directory, file), mode: stat.mode & 0o111 ? '100755' : '100644',
          bytes: stat.size, sha256: sha(fs.readFileSync(file)) });
      }
    }
  }
  visit(directory);
  return { entries, bytes, sha256: sha(JSON.stringify(entries)) };
}

function git(cwd, args, commands) {
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('GIT_')));
  Object.assign(env, { GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: os.devNull, GIT_TERMINAL_PROMPT: '0' });
  const actual = ['-c', 'core.autocrlf=false', '-c', 'core.filemode=true', ...args];
  const result = spawnSync('git', actual, { cwd, env, encoding: 'utf8', timeout: 15000, maxBuffer: 8 * 1024 * 1024 });
  commands.push({ executable: 'git', args: actual, cwd, exitCode: result.status,
    stdout: result.stdout || '', stderr: result.stderr || '', error: result.error ? String(result.error) : undefined });
  requireThat(!result.error && result.status === 0, 'Git diagnostic failed: ' + args.join(' ') + ': ' + (result.stderr || result.error));
  return result.stdout;
}

function featureHashes(entries) {
  return entries.filter(item => item.path.startsWith('entry/src/main/ets/features/') && /\.(ets|ts)$/.test(item.path))
    .map(item => ({ path: item.path, sha256: item.sha256 })).sort((a, b) => a.path.localeCompare(b.path));
}

function verifyPackage(build, bundle, candidate, candidatePath, caseId) {
  requireThat(build.taskId === TASK && build.role === 'agent' && build.caseId === caseId &&
    build.source === candidatePath && build.productionUnchanged && build.temporaryProjectRemoved,
  'Packager identity, candidate preservation, or cleanup mismatch');
  requireThat(bundle.taskSelection === TASK && same(bundle.roles, ['agent']) && bundle.caseCount === 1 &&
    bundle.candidates.length === 1 && bundle.candidates[0].taskId === TASK && bundle.candidates[0].role === 'agent' &&
    bundle.candidates[0].original === candidatePath && bundle.candidates[0].sourceOverride === true &&
    !bundle.candidates[0].patch, 'Bundle must use the reconstructed agent sourceOverride without applying another patch');
  requireThat(same(featureHashes(bundle.production), featureHashes(candidate.entries)), 'Bundled feature hashes differ from reconstructed candidate');
  const main = candidate.entries.filter(item => item.path.startsWith('entry/src/main/'));
  const actual = new Map(build.production.map(item => [item.path, item.sha256]));
  requireThat(build.production.length === main.length && actual.size === main.length && main.every(item => actual.get(item.path) === item.sha256),
    'Packaged full main source inventory differs from reconstructed candidate');
  if (bundle.candidateUI) requireThat(bundle.candidateUI.role === 'agent' &&
    main.some(item => item.path === bundle.candidateUI.productionSource.path && item.sha256 === bundle.candidateUI.productionSource.sha256),
  'Native UI page is not the archived agent page');
}

async function run(options) {
  const root = fs.realpathSync(options.root || path.resolve(__dirname, '../..'));
  const mode = options.mode || 'audit';
  requireThat(['audit', 'prepare', 'build'].includes(mode), 'Unknown diagnostic mode');
  const taskFile = path.join(root, 'benchmark_tasks', TASK, 'task.json');
  const contractFile = path.join(root, 'benchmark_tasks', TASK, 'transitions.json');
  const task = json(taskFile), contract = json(contractFile);
  const caseSpec = options.caseId && contract.cases.find(item => item.caseId === options.caseId);
  requireThat(!options.caseId || caseSpec, 'Unknown canonical task18 case');
  requireThat(mode === 'audit' || caseSpec, '--case is required for one-case prepare/build');
  requireThat(task.taskId === TASK, 'Task identity mismatch');
  const baseRelative = safeRelative(task.arkts.basePath);
  const base = path.join(root, baseRelative);
  requireThat(fs.realpathSync(base) === base, 'Symlinked base path is unsupported');
  const output = canonicalDestination(options.output);
  for (const protectedPath of [base, path.join(root, ARCHIVE), path.join(root, REPORTS),
    path.join(root, 'benchmark_tasks'), path.join(root, 'final_dev_nodes'), path.join(root, 'scripts'), path.join(root, 'state_tests')]) {
    requireThat(!inside(protectedPath, output), 'Diagnostic output cannot write source/archive/contracts/main reports');
  }
  requireThat(!fs.existsSync(output), 'Refusing existing diagnostic output');
  fs.mkdirSync(output, { recursive: true });
  const report = { schemaVersion: 1, taskId: TASK, role: 'agent', mode,
    scope: 'archived_agent_context_repair_diagnostic', freshAgent: false, calibrationPassed: false,
    benchmarkSemanticMetric: null, reportMergeAllowed: false, nativeRuntimeExecuted: false,
    startedAt: new Date().toISOString(), status: 'preparing', commands: [],
    limitations: ['The archival evaluation does not contain a full historical base manifest. This audit freezes the current tracked base, checks patch reconstruction and matches all retained agent feature hashes.',
      'Device execution is deliberately external and requires parent authorization. Existing matrix and strict apply agent rejection remain unchanged.',
      'Canonical OS channel recreation evidence is under independent audit. Executing production classes or writing a channel ledger does not establish an actual OS channel effect. Current adapter outcomes are not calibration or promotion proof.'] };
  let temp, initialBase;
  try {
    const patch = path.join(root, ARCHIVE, 'provenance/patches', 'arkts_' + TASK + '.patch');
    const indexFile = path.join(root, ARCHIVE, 'provenance/evidence_index.json');
    const evalFile = path.join(root, ARCHIVE, 'provenance/eval_manifest.json');
    const primaryFile = path.join(root, REPORTS, 'arkts_' + TASK + '_agent.json');
    const primary = json(primaryFile), oldManifestFile = primary.nativeEvidence.manifest;
    const oldManifest = json(oldManifestFile);
    const patchRecord = record(patch);
    const archived = json(indexFile).artifacts.filter(item => item.kind === 'agent_patch' && item.name === path.basename(patch));
    requireThat(archived.length === 1 && archived[0].sha256 === patchRecord.sha256 && archived[0].bytes === patchRecord.bytes,
      'Original patch does not match published archive digest and byte count');
    requireThat(patchRecord.bytes <= 8 * 1024 * 1024, 'Patch exceeds bounded diagnostic budget');
    requireThat(primary.taskId === TASK && primary.role === 'agent' && primary.platform === 'arkts' &&
      primary.provenance.patchSha256 === patchRecord.sha256, 'Prior agent report does not bind this archived patch');
    requireThat(same(primary.semantic.cases.map(item => [item.caseId, item.traceDigest]).sort(),
      contract.cases.map(item => [item.caseId, item.traceDigest]).sort()), 'Prior agent report canonical case identities changed');
    const oldCandidate = oldManifest.candidates.filter(item => item.taskId === TASK && item.role === 'agent');
    requireThat(oldCandidate.length === 1 && oldCandidate[0].patchSha256 === patchRecord.sha256 &&
      oldCandidate[0].sourceOverride === false, 'Prior native bundle does not bind base-plus-original-patch reconstruction');
    const evaluations = json(evalFile).tasks.filter(item => item.taskId === TASK && item.platform === 'arkts');
    requireThat(evaluations.length === 1, 'Archived evaluation identity is ambiguous');
    report.inputs = [taskFile, contractFile, patch, indexFile, evalFile, primaryFile, oldManifestFile].map(record);
    report.archive = { patch: patchRecord, evaluation: evaluations[0], priorReport: record(primaryFile),
      priorCaseReasons: primary.semantic.cases.map(item => ({ caseId: item.caseId, status: item.status, reason: item.reason })) };
    report.contract = { ...record(contractFile), cases: contract.cases.map(item => ({ caseId: item.caseId, traceDigest: item.traceDigest })) };
    const head = git(root, ['rev-parse', 'HEAD'], report.commands).trim();
    const baseTree = git(root, ['rev-parse', head + ':' + baseRelative], report.commands).trim();
    requireThat(!git(root, ['status', '--porcelain', '--untracked-files=all', '--', baseRelative], report.commands).trim(),
      'Base has local changes; refusing to reconstruct a different candidate');
    initialBase = manifest(base);
    report.base = { path: base, repositoryCommit: head, gitTree: baseTree, ...initialBase };
    write(path.join(output, 'base-source-manifest.json'), report.base);
    fs.copyFileSync(patch, path.join(output, 'archived-agent.patch'), fs.constants.COPYFILE_EXCL);
    report.archive.retainedPatch = record(path.join(output, 'archived-agent.patch'));
    temp = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks16_18_archived_'));
    report.temporaryCandidate = path.join(temp, 'candidate');
    fs.cpSync(base, report.temporaryCandidate, { recursive: true });
    const command = args => git(report.temporaryCandidate, args, report.commands);
    command(['init', '-q']);
    command(['add', '--all', '--force']);
    requireThat(command(['write-tree']).trim() === baseTree, 'Full base inventory differs from the tracked base tree');
    command(['apply', '--check', '--index', '--binary', patch]);
    command(['apply', '--index', '--binary', patch]);
    command(['apply', '--reverse', '--check', '--index', '--binary', patch]);
    const tree = command(['write-tree']).trim();
    const candidate = manifest(report.temporaryCandidate);
    const changed = command(['diff-tree', '--no-commit-id', '--name-only', '-r', '-z', baseTree, tree]).split('\0').filter(Boolean).sort();
    requireThat(same(changed, evaluations[0].generatedCodeFiles.slice().sort()), 'Patch changed paths differ from archived generated-file inventory');
    const oldSources = oldManifest.production.filter(item => item.taskId === TASK && item.role === 'agent');
    requireThat(oldSources.length > 0 && same(featureHashes(oldSources), featureHashes(candidate.entries)),
      'Reconstructed feature inventory differs from prior archived native candidate');
    report.candidate = { gitTree: tree, ...candidate, changedPaths: changed,
      priorFeatureHashesMatched: oldSources.length, patchAppliedExactlyOnce: true };
    write(path.join(output, 'candidate-source-manifest.json'), report.candidate);
    report.tools = ['scripts/runtime_semantics/Tasks16_18ArchivedDiagnostic.cjs',
      'scripts/runtime_semantics/arkts_native_device.cjs', 'scripts/runtime_semantics/arkts_native_bundle.cjs',
      'state_tests/runtime/arkts/native/native-device-platform.js', 'state_tests/runtime/arkts/tasks16_18.cjs']
      .map(file => record(path.join(root, file)));
    if (mode !== 'audit') {
      const destination = path.join(output, 'package');
      const args = [path.join(root, 'scripts/runtime_semantics/arkts_native_device.cjs'),
        '--source', report.temporaryCandidate, '--task', TASK, '--fixture', 'bundle', '--role', 'agent',
        '--case', caseSpec.caseId, '--output-dir', destination,
        ...(options.nativeUI ? ['--native-ui'] : []), ...(mode === 'prepare' ? ['--prepare-only'] : []),
        ...(options.signingConfig ? ['--signing-config', path.resolve(options.signingConfig)] : []),
        ...(options.signingName ? ['--signing-name', options.signingName] : [])];
      const result = spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8', timeout: 540000, maxBuffer: 4 * 1024 * 1024 });
      fs.writeFileSync(path.join(output, 'packager.log'), (result.stdout || '') + (result.stderr || ''), { flag: 'wx' });
      report.commands.push({ executable: process.execPath, args, exitCode: result.status,
        error: result.error ? String(result.error) : undefined, log: record(path.join(output, 'packager.log')) });
      requireThat(!result.error && result.status === 0, 'Diagnostic packaging failed; see packager.log');
      const buildFile = path.join(destination, 'device-build-report.json');
      const build = json(buildFile), bundle = json(build.bundleManifest);
      verifyPackage(build, bundle, candidate, report.temporaryCandidate, caseSpec.caseId);
      requireThat(mode === 'prepare' ? build.status === 'prepared_only' :
        build.status === 'built_not_executed' && build.runtimeCompile.passed && build.copiedProductionUnchanged,
      'Packaging did not complete the requested diagnostic mode');
      report.package = { build: record(buildFile), bundle: record(build.bundleManifest),
        artifacts: [buildFile, build.bundleManifest, ...build.haps.map(item => item.path)].map(record),
        role: 'agent', sourceOverride: true, reconstructionVerified: true };
    }
    requireThat(same(manifest(report.temporaryCandidate), candidate), 'Candidate changed during diagnostic packaging');
    report.status = mode === 'audit' ? 'reconstructed_not_executed' : mode === 'prepare' ? 'prepared_not_executed' : 'built_not_executed';
  } catch (error) { report.status = 'blocked'; report.error = String(error); }
  finally {
    if (temp) fs.rmSync(temp, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
    report.temporaryCandidateRemoved = !temp || !fs.existsSync(temp);
    try {
      report.inputsUnchanged = [...(report.inputs || []), ...(report.tools || [])].every(item => same(record(item.path), item));
      report.baseUnchanged = !initialBase || same(manifest(base), initialBase);
    } catch (error) {
      report.inputsUnchanged = false; report.baseUnchanged = false;
      report.preservationError = String(error);
    }
    if (!report.inputsUnchanged || !report.baseUnchanged || !report.temporaryCandidateRemoved) {
      report.status = 'blocked'; report.error = 'Source preservation or temporary candidate cleanup failed';
    }
    report.finishedAt = new Date().toISOString();
    write(path.join(output, 'archived-diagnostic.json'), report);
  }
  return report;
}

function parse(args) {
  const result = { mode: 'audit' };
  const flags = { '--output-dir': 'output', '--case': 'caseId', '--signing-config': 'signingConfig', '--signing-name': 'signingName' };
  let mode;
  for (let i = 0; i < args.length; i++) {
    const flag = args[i];
    if (['--audit-only', '--prepare-only', '--build'].includes(flag)) {
      requireThat(!mode, 'Choose one diagnostic mode'); mode = flag;
      result.mode = flag === '--build' ? 'build' : flag === '--prepare-only' ? 'prepare' : 'audit';
    } else if (flag === '--native-ui') result.nativeUI = true;
    else {
      requireThat(flags[flag] && args[i + 1] && !args[i + 1].startsWith('--') && !result[flags[flag]], 'Unknown, missing or duplicate option: ' + flag);
      result[flags[flag]] = args[++i];
    }
  }
  requireThat(result.output, '--output-dir is required');
  return result;
}

module.exports = { run, manifest, verifyPackage, parse };
if (require.main === module) {
  if (process.argv.includes('--help')) console.log('Tasks16_18ArchivedDiagnostic.cjs --output-dir NEW_DIR [--audit-only | --prepare-only --case ID | --build --case ID] [--native-ui] [--signing-config FILE --signing-name NAME]\nTask18 archived agent only; no device execution or report merge.');
  else Promise.resolve().then(() => run(parse(process.argv.slice(2)))).then(report => {
    console.log(JSON.stringify({ status: report.status, error: report.error, nativeRuntimeExecuted: false,
      candidateManifestSha256: report.candidate?.sha256, temporaryCandidateRemoved: report.temporaryCandidateRemoved }, null, 2));
    if (report.status === 'blocked') process.exitCode = 1;
  }).catch(error => { console.error(String(error)); process.exitCode = 1; });
}
