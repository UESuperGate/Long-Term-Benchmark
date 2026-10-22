'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { evaluateCase } = require('../../../scripts/runtime_semantics/arkts_runtime.cjs');
const adapter = require('./tasks08_11.cjs');

const ROOT = path.resolve(__dirname, '../../..');
const SPACES = '09_spaces_lifecycle';
const MEDIA = '10_media_upload_quality';
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const task = taskId => readJson(path.join(ROOT, 'benchmark_tasks', taskId, 'task.json'));
const spec = (taskId, key) => readJson(path.join(ROOT, 'benchmark_tasks', taskId, 'transitions.json'))
  .cases.find(item => item.key === key);
const finalProject = taskId => path.join(ROOT, task(taskId).arkts.finalPath);
const run = (taskId, caseSpec, project = finalProject(taskId)) => evaluateCase(taskId, caseSpec, project, adapter);

function assertScored(row, status) {
  assert.equal(row.status, status, row.reason || JSON.stringify(row.assertionFailures));
  assert.deepEqual(row.missingObservations, []);
  assert.deepEqual(row.missingInvariants, []);
  assert.ok(row.checkpoints.some(item => item.label === 'before:event'));
  assert.ok(row.checkpoints.some(item => item.label === 'after:event'));
  assert.ok(row.productionSources.length);
  assert.equal(row.observationLevel, 'production_domain');
}

function assertUploadBoundaries(row) {
  const invariant = row.invariantChecks[0];
  assert.equal(invariant.passed, true);
  const boundary = invariant.observed.boundary;
  assert.equal(boundary.length, 6);
  for (const preset of ['high', 'standard', 'low']) {
    const probes = boundary.filter(item => item.preset === preset);
    assert.deepEqual(probes.map(item => item.offset), [0, -1]);
    assert.deepEqual(probes.map(item => item.canUpload), [true, false]);
    for (const probe of probes) {
      assert.equal(probe.maxUploadSize, row.observed.sizes[preset] + probe.offset);
      assert.equal(probe.actualMaxUploadSize, probe.maxUploadSize);
      assert.equal(probe.sizeInBytes ?? probe.estimatedSize, row.observed.sizes[preset]);
    }
  }
  assert.equal(row.checkpoints.filter(item => item.label === 'media:boundary-before-request').length, 6);
  assert.equal(row.checkpoints.filter(item => item.label === 'media:boundary-after-request').length, 6);
}

function archivedFeatures(t, taskId) {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'arkts09-10-adapter-'));
  t.after(() => fs.rmSync(project, { recursive: true, force: true }));
  const relative = 'entry/src/main/ets/features';
  fs.mkdirSync(path.dirname(path.join(project, relative)), { recursive: true });
  fs.cpSync(path.join(ROOT, task(taskId).arkts.basePath, relative), path.join(project, relative), { recursive: true });
  const patch = path.join(ROOT, 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/provenance/patches',
    `arkts_${taskId}.patch`);
  // Reconstruct only original feature sources in a disposable directory. No business-code substitutes.
  execFileSync('git', ['apply', '--include=entry/src/main/ets/features/*', patch], { cwd: project, stdio: 'pipe' });
  return project;
}

test('09 acceptance observes mark-as-unseen semantics and the unchanged membership/effect assertions', async () => {
  const row = await run(SPACES, spec(SPACES, 'accept_invite'));
  assertScored(row, 'pass');
  assert.deepEqual(row.observed, { effect: 'accept_invite', membership: 'joined', seenInvites: [] });
  assert.ok(row.invariantChecks.every(item => item.passed));
  assert.ok(row.calls.some(item => item.class === 'SpacesPresenter' && item.method === 'acceptInvite'));
});

test('09 an unestablished seen-invite given stays unscored', async () => {
  const caseSpec = spec(SPACES, 'accept_invite');
  caseSpec.given.seenInvites = ['!unrepresented'];
  const row = await run(SPACES, caseSpec);
  assert.equal(row.status, 'not_scored');
  assert.match(row.reason, /seen-invite state.*canonical given/);
});

test('09 archived implementation retaining the seen ID is a genuine mismatch', async t => {
  const row = await run(SPACES, spec(SPACES, 'accept_invite'), archivedFeatures(t, SPACES));
  assertScored(row, 'fail');
  assert.deepEqual(row.observed.seenInvites, ['!invited']);
  assert.ok(row.invariantChecks.some(item => !item.passed));
});

test('10 canonical dimensions and milliseconds reach the unchanged production helper', async () => {
  const caseSpec = spec(MEDIA, 'estimate_video_presets');
  assert.deepEqual(caseSpec.given, { width: 1920, height: 1080, durationMs: 60000, maxUploadSize: 35000000 });
  const row = await run(MEDIA, caseSpec);
  assertScored(row, 'pass');
  assert.deepEqual(row.observed.sizes, { high: 51315000, standard: 22803000, low: 5700750 });
  assert.deepEqual(row.observed.canUpload, { high: false, standard: true, low: true });
  assert.equal(row.observed.safetyOverhead, 1.1);
  assert.equal(row.observed.metadata.durationSeconds, 60);
  assert.equal(row.observed.metadata.width, 1920);
  assert.equal(row.observed.metadata.height, 1080);
  assert.ok(row.calls.some(item => item.class === 'VideoCompressorHelper' && item.method === 'calculateOptimalBitrate' &&
    item.args[0].width === 1920 && item.args[0].height === 1080 && item.args[1] === 30));
  assertUploadBoundaries(row);
  assert.ok(!row.calls.some(item => item.method === 'setPresetBitrate'));
});

test('10 durationMs is converted rather than silently defaulted to sixty seconds', async () => {
  const caseSpec = spec(MEDIA, 'estimate_video_presets');
  caseSpec.given.durationMs = 12000;
  caseSpec.expected.sizes = { high: 10263000, standard: 4560600, low: 1140150 };
  caseSpec.expected.canUpload = { high: true, standard: true, low: true };
  const row = await run(MEDIA, caseSpec);
  assertScored(row, 'pass');
  assert.equal(row.observed.metadata.durationSeconds, 12);
  assertUploadBoundaries(row);
});

test('10 supplied dimensions, not fixed full-HD defaults, determine estimates', async () => {
  const caseSpec = spec(MEDIA, 'estimate_video_presets');
  Object.assign(caseSpec.given, { width: 640, height: 360 });
  caseSpec.expected.sizes = { high: 5700750, standard: 5700750, low: 5700750 };
  caseSpec.expected.canUpload = { high: true, standard: true, low: true };
  const row = await run(MEDIA, caseSpec);
  assertScored(row, 'pass');
  assert.equal(row.observed.metadata.width, 640);
  assert.equal(row.observed.metadata.height, 360);
  assertUploadBoundaries(row);
});

test('10 durationSeconds remains a compatible input alias, but conflicting units are unsupported', async () => {
  const caseSpec = spec(MEDIA, 'estimate_video_presets');
  delete caseSpec.given.durationMs;
  caseSpec.given.durationSeconds = 60;
  const compatible = await run(MEDIA, caseSpec);
  assertScored(compatible, 'pass');
  assertUploadBoundaries(compatible);
  caseSpec.given.durationMs = 12000;
  const row = await run(MEDIA, caseSpec);
  assert.equal(row.status, 'not_scored');
  assert.match(row.reason, /Conflicting durationMs and durationSeconds/);
});

test('10 expectations do not manufacture observations or loosen upload/overhead assertions', async () => {
  const caseSpec = spec(MEDIA, 'estimate_video_presets');
  caseSpec.expected.sizes.high = 1;
  caseSpec.expected.canUpload.high = true;
  caseSpec.expected.safetyOverhead = 1;
  const row = await run(MEDIA, caseSpec);
  assertScored(row, 'fail');
  assert.equal(row.observed.sizes.high, 51315000);
  assert.equal(row.observed.canUpload.high, false);
  assert.equal(row.observed.safetyOverhead, 1.1);
  assert.deepEqual(row.assertionFailures.map(item => item.path), ['sizes.high', 'canUpload.high', 'safetyOverhead']);
  assertUploadBoundaries(row);
});

test('10 archived constant-bitrate implementation executes and retains real mismatches', async t => {
  const row = await run(MEDIA, spec(MEDIA, 'estimate_video_presets'), archivedFeatures(t, MEDIA));
  assertScored(row, 'fail');
  assert.deepEqual(row.observed.sizes, { high: 60000000, standard: 30000000, low: 7500000 });
  assert.deepEqual(row.observed.canUpload, { high: false, standard: true, low: true });
  assert.equal(row.observed.safetyOverhead, 1);
  assert.ok(row.assertionFailures.some(item => item.path === 'safetyOverhead'));
  assert.ok(row.invariantChecks.every(item => item.passed));
  assertUploadBoundaries(row);
  assert.ok(!row.calls.some(item => item.method === 'setPresetBitrate'));
});

test('09/10 unrelated host-domain cases keep their existing assertions', async () => {
  for (const [taskId, key] of [[SPACES, 'join_failure_retry'], [SPACES, 'leave_failure_retry'],
    [MEDIA, 'async_loading'], [MEDIA, 'limit_fallback'], [MEDIA, 'failure_cancel_retry']]) {
    assertScored(await run(taskId, spec(taskId, key)), 'pass');
  }
});
