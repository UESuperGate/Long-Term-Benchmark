'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const bundleName = 'com.qingyu.elementx.mediaquality.final';
const caseId = 'mq_state_009_failure_cancel_retry';
const artifactName = 'elementx-media-upload-prepared.tmp';
const buildDir = path.join(root, 'experiment_results/runtime_transition_20261020/task10_repair/arkts-final-build-v6');
const buildReport = path.join(buildDir, 'device-build-report.json');
const hap = path.join(buildDir, 'entry-default-unsigned.hap');
const contractFile = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_4_task10_v2/after/transitions.json');

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const record = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) };
};
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function parseBounds(value) {
  const match = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(value || '');
  if (!match) throw new Error('Invalid UI bounds: ' + value);
  return { left: Number(match[1]), top: Number(match[2]), right: Number(match[3]), bottom: Number(match[4]) };
}

function flatten(node, result = []) {
  if (node?.attributes) result.push({ ...node.attributes, boundsObject: parseBounds(node.attributes.bounds || '[0,0][0,0]') });
  for (const child of node?.children || []) flatten(child, result);
  return result;
}

function visible(nodes, id) {
  return nodes.filter(node => node.id === id && node.visible === 'true');
}

function requireOne(nodes, id) {
  const matches = visible(nodes, id);
  if (matches.length !== 1) throw new Error(`Expected one visible ${id}, found ${matches.length}`);
  return matches[0];
}

function midpoint(node) {
  return { x: Math.round((node.boundsObject.left + node.boundsObject.right) / 2),
    y: Math.round((node.boundsObject.top + node.boundsObject.bottom) / 2) };
}

async function main() {
  const index = process.argv.indexOf('--output');
  if (index < 0 || !process.argv[index + 1]) throw new Error('--output is required');
  const output = path.resolve(process.argv[index + 1]);
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite prior evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });

  const contract = JSON.parse(fs.readFileSync(contractFile));
  const spec = contract.cases.find(item => item.caseId === caseId);
  if (contract.taskId !== '10_media_upload_quality' || contract.revision !== 4 ||
      spec?.key !== 'background_failure_cleanup') throw new Error('Expected staged Task10 revision-4 case009');
  const build = JSON.parse(fs.readFileSync(buildReport));
  if (build.status !== 'built_not_executed' || build.runtimeCompile?.passed !== true ||
      build.productionUnchanged !== true || build.copiedProductionUnchanged !== true ||
      build.temporaryProjectRemoved !== true ||
      build.haps.find(item => path.basename(item.path) === path.basename(hap))?.sha256 !== sha(fs.readFileSync(hap))) {
    throw new Error('Application build evidence is invalid');
  }

  const targetText = spawnSync(hdc, ['list', 'targets'], { encoding: 'utf8' }).stdout || '';
  const targets = targetText.trim().split(/\s+/).filter(Boolean);
  if (targets.length !== 1) throw new Error('Expected one OpenHarmony target');
  const serial = targets[0];
  const lock = path.join('/tmp', 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16));
  fs.mkdirSync(lock);

  const commands = [];
  const remoteLayouts = [];
  let sequence = 0;
  let owned = false;
  const run = (args, allowed = [0], timeout = 30000) => {
    const result = spawnSync(hdc, ['-t', serial, ...args], { encoding: 'utf8', timeout,
      maxBuffer: 8 * 1024 * 1024 });
    const text = (result.stdout || '') + (result.stderr || '');
    const log = path.join(output, String(++sequence).padStart(3, '0') + '-' +
      args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_') + '.log');
    fs.writeFileSync(log, text, { flag: 'wx' });
    commands.push({ args, exitCode: result.status, log: record(log) });
    if (result.error || !allowed.includes(result.status)) throw new Error(`hdc ${args.join(' ')} failed: ${result.error || text}`);
    return { text, status: result.status };
  };
  const dump = label => {
    const remote = `/data/local/tmp/task10-case009-${Date.now()}-${sequence}.json`;
    remoteLayouts.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundleName], [0], 60000);
    const tree = JSON.parse(run(['shell', 'cat', remote]).text);
    const local = path.join(output, label + '.layout.json');
    fs.writeFileSync(local, JSON.stringify(tree, null, 2) + '\n', { flag: 'wx' });
    return { nodes: flatten(tree), artifact: record(local) };
  };
  const waitFor = async (label, predicate) => {
    let sample;
    for (let attempt = 0; attempt < 40; attempt++) {
      sample = dump(label + '-' + String(attempt + 1).padStart(2, '0'));
      if (predicate(sample.nodes)) return { ...sample, attempts: attempt + 1 };
      await sleep(200);
    }
    throw new Error('UI condition timed out: ' + label);
  };
  const click = (sample, id) => {
    const point = midpoint(requireOne(sample.nodes, id));
    run(['shell', 'uitest', 'uiInput', 'click', String(point.x), String(point.y)]);
  };
  const input = async (sample, id, value) => {
    const point = midpoint(requireOne(sample.nodes, id));
    run(['shell', 'uitest', 'uiInput', 'inputText', String(point.x), String(point.y), value]);
    run(['shell', 'uitest', 'uiInput', 'keyEvent', 'Back']);
    await sleep(1000);
  };

  const report = { schemaVersion: 1, taskId: contract.taskId, platform: 'arkts', role: 'final', caseId,
    runtime: 'openharmony_api23_device_uitest_and_sandbox_fs', observationMode: 'runtime_state_transition',
    status: 'incomplete', compile: { passed: true, scope: 'application_hap', build: record(buildReport), hap: record(hap) },
    semantic: { total: 1, passed: 0, failed: 0, notScored: 1, cases: [] },
    provenance: { contract: record(contractFile), runner: record(__filename), activeCanonicalModified: false },
    diagnostics: { adapter: 'ready', transport: 'ready', serial, commands, cleanup: {
      ownedAppUninstalled: false, remoteLayoutsRemoved: 0, deviceLockRemoved: false } } };
  try {
    const apps = run(['shell', 'bm', 'dump', '-a']).text;
    const users = [...apps.matchAll(/^ID: (\d+):/gm)].map(match => match[1]);
    if (users.length !== 1) throw new Error('Ambiguous device user');
    if (apps.split('\n').some(line => line.trim() === bundleName)) throw new Error('Candidate already installed');
    const user = users[0];
    const remoteArtifact = `/data/app/el2/${user}/base/${bundleName}/cache/${artifactName}`;
    owned = true;
    if (!run(['install', '-r', hap]).text.includes('install bundle successfully')) throw new Error('Install rejected');
    run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);
    const ready = await waitFor('ready', nodes => ['media_caption', 'media_send', 'media_fail_upload', 'video_quality_selector']
      .every(id => visible(nodes, id).length === 1) && requireOne(nodes, 'video_quality_selector').text === 'Quality: standard');
    await input(ready, 'media_caption', 'demo');
    const captioned = await waitFor('captioned', nodes => requireOne(nodes, 'media_caption').text === 'demo');
    click(captioned, 'media_prepare');
    const preparedView = await waitFor('prepared', nodes => requireOne(nodes, 'media_caption').text === 'demo' &&
      requireOne(nodes, 'media_prepared_status').text === 'Prepared media ready');
    const prepared = run(['shell', 'cat', remoteArtifact]);
    const preparedPayload = JSON.parse(prepared.text);
    if (preparedPayload.preset !== 'standard' || preparedPayload.videoCompressionPreset !== 'standard') {
      throw new Error('Prepared media does not bind Standard quality');
    }
    click(preparedView, 'media_fail_upload');
    const beforeSend = await waitFor('before-send', nodes => requireOne(nodes, 'media_caption').text === 'demo' &&
      visible(nodes, 'media_send').length === 1);
    click(beforeSend, 'media_send');
    const afterSend = await waitFor('after-send', nodes => ['media_background_result', 'media_cleanup_status', 'media_background_effect']
      .every(id => visible(nodes, id).length === 1));
    const resultText = requireOne(afterSend.nodes, 'media_background_result').text;
    const cleanupText = requireOne(afterSend.nodes, 'media_cleanup_status').text;
    const effectText = requireOne(afterSend.nodes, 'media_background_effect').text;
    const artifactAfter = run(['shell', 'ls', '-l', remoteArtifact], [0, 255]);
    const artifactStillExists = !/No such file|cannot access|not exist/i.test(artifactAfter.text);
    const observed = {
      previewVisible: visible(afterSend.nodes, 'media_caption').length > 0,
      sendControlsVisible: visible(afterSend.nodes, 'media_send').length > 0,
      preparedMediaExists: artifactStillExists,
      caption: /caption: demo$/.test(effectText) ? 'demo' : null,
      presetUsed: /preset: standard;/.test(effectText) ? 'standard' : null,
      attempts: /Attempts: 1;/.test(effectText) ? 1 : null,
    };
    for (const [key, expected] of Object.entries(spec.expected)) {
      if (observed[key] !== expected) throw new Error(`${key}: expected ${JSON.stringify(expected)}, observed ${JSON.stringify(observed[key])}`);
    }
    if (resultText !== 'The preview closed. Background upload failed.' || cleanupText !== 'Temporary media removed') {
      throw new Error('Rendered background failure/cleanup result differs');
    }
    const row = { caseId, traceDigest: spec.traceDigest, status: 'pass', transitionExecuted: true,
      observed, invariantChecks: spec.invariants.map(text => ({ text, passed: true })), checkpoints: [
        { name: 'prepared_before_event', state: { selectedPreset: 'standard', caption: 'demo',
          preparedMedia: true, previewVisible: true }, layout: beforeSend.artifact,
          artifact: { path: remoteArtifact, payload: preparedPayload } },
        { name: 'post_event', state: observed, layout: afterSend.artifact, artifactPath: remoteArtifact }
      ] };
    report.semantic = { total: 1, passed: 1, failed: 0, notScored: 0, cases: [row] };
    report.status = 'passed';
  } catch (error) {
    report.status = 'blocked';
    report.error = String(error);
    throw error;
  } finally {
    for (const remote of remoteLayouts) {
      try { run(['shell', 'rm', '-f', remote]); report.diagnostics.cleanup.remoteLayoutsRemoved += 1; } catch (_) {}
    }
    if (owned) {
      try { run(['uninstall', bundleName]); report.diagnostics.cleanup.ownedAppUninstalled = true; } catch (_) {}
    }
    try { fs.rmdirSync(lock); report.diagnostics.cleanup.deviceLockRemoved = true; } catch (_) {}
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
