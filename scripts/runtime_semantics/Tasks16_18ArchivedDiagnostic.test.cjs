'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { run, manifest, parse, verifyPackage } = require('./Tasks16_18ArchivedDiagnostic.cjs');
const TASK = '18_custom_notification_sounds';
const ARCHIVE = 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair';
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const feature = 'entry/src/main/ets/features/NotificationSettingsBase.ets';
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks16_18_archive_test_'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const write = (relative, value) => {
    const file = path.join(root, relative); fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, typeof value === 'string' || Buffer.isBuffer(value) ? value : JSON.stringify(value));
    return file;
  };
  const git = (cwd, ...args) => execFileSync('git', ['-c', 'user.name=Unit test', '-c', 'user.email=unit@invalid',
    '-c', 'commit.gpgsign=false', ...args], { cwd, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
  const base = path.join(root, 'base');
  write('base/' + feature, 'export const value = 0;\n');
  write('base/entry/src/main/ets/pages/Index.ets', 'export const page = 0;\n');
  git(root, 'init', '-q'); git(root, 'add', 'base'); git(root, 'commit', '-qm', 'unit base');
  const candidate = path.join(root, 'patch-work');
  fs.cpSync(base, candidate, { recursive: true });
  git(candidate, 'init', '-q'); git(candidate, 'add', '.'); git(candidate, 'commit', '-qm', 'unit base');
  fs.writeFileSync(path.join(candidate, feature), 'export const value = 1;\n');
  git(candidate, 'add', '.');
  const patch = git(candidate, 'diff', '--cached', '--binary');
  const patchFile = write(ARCHIVE + '/provenance/patches/arkts_' + TASK + '.patch', patch);
  const indexFile = write(ARCHIVE + '/provenance/evidence_index.json', { artifacts: [{ kind: 'agent_patch',
    name: path.basename(patchFile), bytes: Buffer.byteLength(patch), sha256: sha(patch) }] });
  write(ARCHIVE + '/provenance/eval_manifest.json', { tasks: [{ taskId: TASK, platform: 'arkts', generatedCodeFiles: [feature] }] });
  write('benchmark_tasks/' + TASK + '/task.json', { taskId: TASK, arkts: { basePath: 'base' } });
  write('benchmark_tasks/' + TASK + '/transitions.json', { cases: [{ caseId: 'canonical', traceDigest: 'digest' }] });
  const oldManifestFile = write('old-native-manifest.json', { candidates: [{ taskId: TASK, role: 'agent',
    patchSha256: sha(patch), sourceOverride: false }], production: [{ taskId: TASK, role: 'agent', path: feature,
    sha256: sha(fs.readFileSync(path.join(candidate, feature))) }] });
  write('experiment_results/runtime_transition_20261019/reports/arkts_' + TASK + '_agent.json', {
    taskId: TASK, role: 'agent', platform: 'arkts', provenance: { patchSha256: sha(patch) },
    nativeEvidence: { manifest: oldManifestFile }, semantic: { cases: [{ caseId: 'canonical', traceDigest: 'digest', status: 'not_scored' }] } });
  for (const name of ['scripts/runtime_semantics/Tasks16_18ArchivedDiagnostic.cjs', 'scripts/runtime_semantics/arkts_native_device.cjs',
    'scripts/runtime_semantics/arkts_native_bundle.cjs', 'state_tests/runtime/arkts/native/native-device-platform.js',
    'state_tests/runtime/arkts/tasks16_18.cjs']) write(name, '// unit provenance placeholder\n');
  fs.rmSync(candidate, { recursive: true });
  return { root, base, patchFile, indexFile, oldManifestFile, write, output: path.join(root, 'diagnostic') };
}

for (const mode of ['valid', 'patch_hash', 'base_dirty', 'base_ignored_extra', 'prior_feature_hash', 'changed_paths']) {
  test('bounded reconstruction fails closed and cleans owned temporary candidate: ' + mode, async t => {
    const f = fixture(t);
    if (mode === 'patch_hash') fs.appendFileSync(f.patchFile, '\n');
    if (mode === 'base_dirty') fs.appendFileSync(path.join(f.base, feature), '// modified\n');
    if (mode === 'base_ignored_extra') {
      f.write('.git/info/exclude', 'base/ignored.txt\n'); f.write('base/ignored.txt', 'unexpected');
    }
    if (mode === 'prior_feature_hash') {
      const value = JSON.parse(fs.readFileSync(f.oldManifestFile)); value.production[0].sha256 = '0'.repeat(64);
      f.write('old-native-manifest.json', value);
    }
    if (mode === 'changed_paths') f.write(ARCHIVE + '/provenance/eval_manifest.json', {
      tasks: [{ taskId: TASK, platform: 'arkts', generatedCodeFiles: [] }] });
    const report = await run(f);
    assert.equal(report.status, mode === 'valid' ? 'reconstructed_not_executed' : 'blocked', report.error);
    assert.equal(report.temporaryCandidateRemoved, true);
    if (report.temporaryCandidate) assert.equal(fs.existsSync(report.temporaryCandidate), false);
    assert.equal(report.nativeRuntimeExecuted, false);
    assert.equal(report.freshAgent, false);
    assert.equal(report.reportMergeAllowed, false);
    assert.equal(report.benchmarkSemanticMetric, null);
    assert.ok(report.limitations.some(item => item.includes('actual OS channel effect')));
    assert.ok(report.commands.every(command => command.executable === 'git'));
    if (mode === 'valid') {
      assert.equal(report.candidate.priorFeatureHashesMatched, 1);
      assert.equal(report.candidate.patchAppliedExactlyOnce, true);
      assert.equal(report.archive.retainedPatch.sha256, report.archive.patch.sha256);
      assert.notEqual(report.base.sha256, report.candidate.sha256);
      assert.equal(report.baseUnchanged, true);
      await assert.rejects(run(f), /Refusing existing/);
    }
  });
}

test('source symlinks, noncanonical case and report output are refused', async t => {
  const f = fixture(t);
  fs.symlinkSync(f.patchFile, path.join(f.base, 'unexpected-link'));
  assert.throws(() => manifest(f.base), /symlink/);
  await assert.rejects(run({ ...f, caseId: 'other-task' }), /Unknown canonical/);
  await assert.rejects(run({ ...f, mode: 'build' }), /--case is required/);
  await assert.rejects(run({ ...f, output: path.join(f.root, 'experiment_results/runtime_transition_20261019/reports/new') }), /cannot write/);
});

test('CLI has no device, role override, apply, or gate bypass options', () => {
  assert.deepEqual(parse(['--output-dir', 'new']), { mode: 'audit', output: 'new' });
  assert.equal(parse(['--output-dir', 'new', '--prepare-only', '--case', 'canonical']).mode, 'prepare');
  for (const flag of ['--serial', '--execute', '--role', '--merge', '--skip-calibration', '--source']) {
    assert.throws(() => parse(['--output-dir', 'new', flag, 'value']), /Unknown/);
  }
  assert.throws(() => parse(['--output-dir', 'new', '--build', '--audit-only']), /Choose one/);
});

test('packager failure retains diagnostic logs and still removes the exact candidate', async t => {
  const f = fixture(t);
  f.write('scripts/runtime_semantics/arkts_native_device.cjs', "console.error('unit package failure'); process.exitCode = 1;\n");
  const report = await run({ ...f, mode: 'prepare', caseId: 'canonical' });
  assert.equal(report.status, 'blocked');
  assert.match(report.error, /packaging failed/);
  assert.equal(report.temporaryCandidateRemoved, true);
  assert.equal(fs.existsSync(report.temporaryCandidate), false);
  assert.match(fs.readFileSync(path.join(f.output, 'packager.log'), 'utf8'), /unit package failure/);
  assert.equal(report.inputsUnchanged, true);
  assert.equal(report.baseUnchanged, true);
});

for (const change of ['none', 'role', 'override', 'double_patch', 'feature', 'extra_main', 'page', 'cleanup']) {
  test('packager sourceOverride evidence remains original role agent: ' + change, () => {
    const source = '/temporary/candidate';
    const entries = [{ path: feature, sha256: 'a' }, { path: 'entry/src/main/ets/pages/Index.ets', sha256: 'b' }];
    const build = { taskId: TASK, role: 'agent', caseId: 'canonical', source, productionUnchanged: true,
      temporaryProjectRemoved: true, production: structuredClone(entries) };
    const bundle = { taskSelection: TASK, roles: ['agent'], caseCount: 1,
      candidates: [{ taskId: TASK, role: 'agent', original: source, sourceOverride: true }],
      production: [structuredClone(entries[0])], candidateUI: { role: 'agent', productionSource: structuredClone(entries[1]) } };
    if (change === 'role') build.role = 'final';
    if (change === 'override') bundle.candidates[0].sourceOverride = false;
    if (change === 'double_patch') bundle.candidates[0].patch = '/original.patch';
    if (change === 'feature') bundle.production[0].sha256 = 'modified';
    if (change === 'extra_main') build.production.push({ path: 'entry/src/main/new.ets', sha256: 'extra' });
    if (change === 'page') bundle.candidateUI.productionSource.sha256 = 'wrong';
    if (change === 'cleanup') build.temporaryProjectRemoved = false;
    if (change === 'none') assert.doesNotThrow(() => verifyPackage(build, bundle, { entries }, source, 'canonical'));
    else assert.throws(() => verifyPackage(build, bundle, { entries }, source, 'canonical'));
  });
}
