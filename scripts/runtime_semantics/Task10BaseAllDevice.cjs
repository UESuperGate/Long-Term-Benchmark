'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const bundleName = 'com.qingyu.elementx.mediaquality.base';
const buildDir = path.join(root,
  'experiment_results/runtime_transition_20261020/task10_repair/arkts-base-build-v1');
const buildReport = path.join(buildDir, 'device-build-report.json');
const hap = path.join(buildDir, 'entry-default-unsigned.hap');
const contractFile = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_4_task10_v2/after/transitions.json');

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const record = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) };
};

function parseBounds(value) {
  const match = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(value || '');
  if (!match) throw new Error('Invalid UI bounds: ' + value);
  return { left: Number(match[1]), top: Number(match[2]), right: Number(match[3]), bottom: Number(match[4]) };
}

function flatten(node, result = []) {
  if (node?.attributes) {
    result.push({ ...node.attributes, boundsObject: parseBounds(node.attributes.bounds || '[0,0][0,0]') });
  }
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
  return {
    x: Math.round((node.boundsObject.left + node.boundsObject.right) / 2),
    y: Math.round((node.boundsObject.top + node.boundsObject.bottom) / 2),
  };
}

const requiredEntrypoints = {
  mq_state_001_async_loading: ['media_slow_info', 'media_information_loading'],
  mq_state_002_limit_fallback: ['media_limit_failure', 'media_fallback_status'],
  mq_state_003_image_optimization: ['media_open_image', 'image_optimization_toggle'],
  mq_state_004_estimate_video_presets: ['video_quality_selector', 'media_safety_overhead'],
  mq_state_005_choose_best_preset: ['video_quality_selector', 'video_preset_high'],
  mq_state_006_dismiss_preserves_selection: ['video_quality_selector', 'video_quality_dismiss'],
  mq_state_007_reject_oversized_preset: ['video_quality_selector', 'video_preset_high'],
  mq_state_008_block_when_all_oversized: ['media_tiny_limit', 'media_too_large_modal'],
  mq_state_009_failure_cancel_retry: ['media_prepare', 'media_fail_upload', 'media_background_result'],
};

async function main() {
  const outputIndex = process.argv.indexOf('--output');
  if (outputIndex < 0 || !process.argv[outputIndex + 1]) throw new Error('--output is required');
  const output = path.resolve(process.argv[outputIndex + 1]);
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite prior evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });

  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '10_media_upload_quality' || contract.revision !== 4 || contract.cases.length !== 9) {
    throw new Error('Expected staged Task10 revision-4 contract with nine cases');
  }
  const build = JSON.parse(fs.readFileSync(buildReport));
  const builtHap = build.haps.find(item => path.basename(item.path) === path.basename(hap));
  if (build.status !== 'built_not_executed' || build.runtimeCompile?.passed !== true ||
      build.productionUnchanged !== true || build.copiedProductionUnchanged !== true ||
      build.temporaryProjectRemoved !== true || builtHap?.sha256 !== sha(fs.readFileSync(hap))) {
    throw new Error('Application build evidence is invalid');
  }

  const targetText = spawnSync(hdc, ['list', 'targets'], { encoding: 'utf8' }).stdout || '';
  const targets = targetText.trim().split(/\s+/).filter(Boolean);
  if (targets.length !== 1) throw new Error('Expected one OpenHarmony target');
  const serial = targets[0];
  const lock = path.join('/tmp', 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16));
  fs.mkdirSync(lock);

  const startedAt = new Date();
  const commands = [];
  const remoteLayouts = [];
  let sequence = 0;
  let appOwned = false;
  let currentCase = null;

  const run = (args, allowed = [0], timeout = 30000) => {
    const result = spawnSync(hdc, ['-t', serial, ...args], {
      encoding: 'utf8', timeout, maxBuffer: 8 * 1024 * 1024,
    });
    const text = (result.stdout || '') + (result.stderr || '');
    const label = args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_');
    const log = path.join(output, String(++sequence).padStart(3, '0') + '-' + label + '.log');
    fs.writeFileSync(log, text, { flag: 'wx' });
    commands.push({ caseId: currentCase, args, exitCode: result.status, log: record(log) });
    if (result.error || !allowed.includes(result.status)) {
      throw new Error(`hdc ${args.join(' ')} failed: ${result.error || text}`);
    }
    return { text, status: result.status };
  };

  const dump = label => {
    const remote = `/data/local/tmp/task10-base-${Date.now()}-${sequence}.json`;
    remoteLayouts.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundleName], [0], 60000);
    const tree = JSON.parse(run(['shell', 'cat', remote]).text);
    const local = path.join(output, `${currentCase}-${label}.layout.json`);
    fs.writeFileSync(local, JSON.stringify(tree, null, 2) + '\n', { flag: 'wx' });
    return { nodes: flatten(tree), artifact: record(local) };
  };

  const waitFor = async (label, predicate) => {
    let sample;
    let lastError;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      try {
        sample = dump(label + '-' + String(attempt + 1).padStart(2, '0'));
        if (predicate(sample.nodes)) return { ...sample, attempts: attempt + 1 };
      } catch (error) {
        lastError = error;
      }
      await sleep(200);
    }
    if (lastError) throw new Error(`UI condition timed out: ${label}; last observation: ${lastError.message}`);
    throw new Error('UI condition timed out: ' + label);
  };

  const click = (sample, id) => {
    const point = midpoint(requireOne(sample.nodes, id));
    run(['shell', 'uitest', 'uiInput', 'click', String(point.x), String(point.y)]);
  };
  const input = async (sample, id, value) => {
    const point = midpoint(requireOne(sample.nodes, id));
    run(['shell', 'uitest', 'uiInput', 'inputText', String(point.x), String(point.y), value]);
    let entered = await waitFor(`input-${id}`, nodes => requireOne(nodes, id).text === value);
    if (requireOne(entered.nodes, id).focused === 'true') {
      run(['shell', 'uitest', 'uiInput', 'keyEvent', 'Back']);
      entered = await waitFor(`input-${id}-keyboard-dismissed`, nodes =>
        requireOne(nodes, id).text === value);
    }
    return entered;
  };

  const report = {
    schemaVersion: 1,
    taskId: contract.taskId,
    platform: 'arkts',
    role: 'base',
    runtime: 'openharmony_api23_device_uitest',
    observationMode: 'runtime_state_transition',
    status: 'incomplete',
    startedAt: startedAt.toISOString(),
    compile: { passed: true, scope: 'application_hap', build: record(buildReport), hap: record(hap) },
    semantic: { total: 9, passed: 0, failed: 0, notScored: 9, cases: [] },
    provenance: {
      contract: record(contractFile), runner: record(__filename), activeCanonicalModified: false,
      buildProduction: build.production,
    },
    diagnostics: {
      adapter: 'ready', transport: 'ready', serial, commands,
      cleanup: { ownedAppUninstalled: false, remoteLayoutsRemoved: 0, deviceLockRemoved: false },
    },
  };

  try {
    const apps = run(['shell', 'bm', 'dump', '-a']).text;
    if (apps.split('\n').some(line => line.trim() === bundleName)) {
      throw new Error('Candidate already installed before evaluator-owned execution');
    }

    for (const spec of contract.cases) {
      currentCase = spec.caseId;
      const installed = run(['install', '-r', hap]).text;
      if (!installed.includes('install bundle successfully')) throw new Error('Install rejected');
      appOwned = true;
      run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);
      const ready = await waitFor('base-ready', nodes =>
        visible(nodes, 'attachment_caption').length === 1 && visible(nodes, 'attachment_send').length === 1);

      const missingBefore = requiredEntrypoints[spec.caseId]
        .filter(id => visible(ready.nodes, id).length === 0);
      if (missingBefore.length === 0) {
        throw new Error(`Base unexpectedly exposes every final entrypoint for ${spec.caseId}`);
      }

      const positiveCaption = 'base-positive-' + spec.caseId.slice(-3);
      await input(ready, 'attachment_caption', positiveCaption);
      const captioned = await waitFor('base-captioned', nodes =>
        requireOne(nodes, 'attachment_caption').text === positiveCaption);
      click(captioned, 'attachment_send');
      const sent = await waitFor('base-sent', nodes => nodes.some(node =>
        node.visible === 'true' && node.text === 'Send state: done'));
      const missingAfter = requiredEntrypoints[spec.caseId]
        .filter(id => visible(sent.nodes, id).length === 0);
      if (missingAfter.length === 0) {
        throw new Error(`Base unexpectedly acquired every final entrypoint for ${spec.caseId}`);
      }

      report.semantic.cases.push({
        caseId: spec.caseId,
        traceDigest: spec.traceDigest,
        status: 'fail',
        transitionExecuted: false,
        failureKind: 'semantic_missing_feature_entry',
        reason: 'The common base preview and original-media send are reachable, but the version-bounded final transition is absent.',
        expected: spec.expected,
        observed: {
          commonPreviewVisible: true,
          originalMediaSendCompleted: true,
          caption: positiveCaption,
          missingEntrypointsBeforePositiveControl: missingBefore,
          missingEntrypointsAfterPositiveControl: missingAfter,
        },
        invariantChecks: spec.invariants.map(text => ({
          text, passed: false, reason: 'Required final-version transition cannot be executed from the reachable base UI.',
        })),
        checkpoints: [
          { name: 'reachable_common_base', layout: ready.artifact },
          { name: 'caption_entered', layout: captioned.artifact },
          { name: 'original_media_positive_control_done', layout: sent.artifact },
        ],
      });
      report.semantic.failed += 1;
      report.semantic.notScored -= 1;
      run(['uninstall', bundleName]);
      appOwned = false;
    }

    report.status = 'passed';
  } catch (error) {
    report.status = 'blocked';
    report.error = String(error);
    throw error;
  } finally {
    for (const remote of remoteLayouts) {
      try {
        run(['shell', 'rm', '-f', remote]);
        report.diagnostics.cleanup.remoteLayoutsRemoved += 1;
      } catch (_) {}
    }
    if (appOwned) {
      try {
        run(['uninstall', bundleName]);
        report.diagnostics.cleanup.ownedAppUninstalled = true;
      } catch (_) {}
    } else {
      report.diagnostics.cleanup.ownedAppUninstalled = true;
    }
    try {
      fs.rmdirSync(lock);
      report.diagnostics.cleanup.deviceLockRemoved = true;
    } catch (_) {}
    report.finishedAt = new Date().toISOString();
    report.elapsedSeconds = (Date.parse(report.finishedAt) - startedAt.getTime()) / 1000;
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
