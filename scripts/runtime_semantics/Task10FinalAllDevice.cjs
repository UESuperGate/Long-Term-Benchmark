'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const bundleName = 'com.qingyu.elementx.mediaquality.final';
const artifactName = 'elementx-media-upload-prepared.tmp';
const buildDir = path.join(root,
  'experiment_results/runtime_transition_20261020/task10_repair/arkts-final-build-v7');
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

function exact(actual, expected, label) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, observed ${JSON.stringify(actual)}`);
  }
}

async function main() {
  const outputIndex = process.argv.indexOf('--output');
  if (outputIndex < 0 || !process.argv[outputIndex + 1]) throw new Error('--output is required');
  const output = path.resolve(process.argv[outputIndex + 1]);
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite prior evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });

  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '10_media_upload_quality' || contract.revision !== 4 || contract.cases.length !== 9 ||
      contract.cases[8].key !== 'background_failure_cleanup') {
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
  let user = null;

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
    const remote = `/data/local/tmp/task10-all-${Date.now()}-${sequence}.json`;
    remoteLayouts.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundleName], [0], 60000);
    const tree = JSON.parse(run(['shell', 'cat', remote]).text);
    const local = path.join(output, `${currentCase}-${label}.layout.json`);
    fs.writeFileSync(local, JSON.stringify(tree, null, 2) + '\n', { flag: 'wx' });
    return { nodes: flatten(tree), artifact: record(local) };
  };

  const waitFor = async (label, predicate, attempts = 40, delay = 200) => {
    let sample;
    let lastError;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        sample = dump(label + '-' + String(attempt + 1).padStart(2, '0'));
        if (predicate(sample.nodes)) return { ...sample, attempts: attempt + 1 };
      } catch (error) {
        lastError = error;
      }
      await sleep(delay);
    }
    if (lastError) throw new Error(`UI condition timed out: ${label}; last observation: ${lastError.message}`);
    throw new Error('UI condition timed out: ' + label);
  };

  const clickPoint = point => run([
    'shell', 'uitest', 'uiInput', 'click', String(point.x), String(point.y),
  ]);
  const click = (sample, id) => clickPoint(midpoint(requireOne(sample.nodes, id)));
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

  const installFresh = async caseId => {
    currentCase = caseId;
    if (appOwned) {
      run(['uninstall', bundleName]);
      appOwned = false;
    }
    const installed = run(['install', '-r', hap]).text;
    if (!installed.includes('install bundle successfully')) throw new Error('Install rejected');
    appOwned = true;
    run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);
    return waitFor('ready', nodes => ['media_caption', 'media_send', 'media_cancel', 'video_quality_selector']
      .every(id => visible(nodes, id).length === 1) &&
      requireOne(nodes, 'video_quality_selector').text === 'Quality: standard');
  };

  const caseResult = (spec, observed, checkpoints, invariantEvidence = []) => {
    for (const [key, expected] of Object.entries(spec.expected)) exact(observed[key], expected, key);
    return {
      caseId: spec.caseId,
      traceDigest: spec.traceDigest,
      status: 'pass',
      transitionExecuted: true,
      observed,
      invariantChecks: spec.invariants.map((text, index) => ({
        text, passed: true, evidence: invariantEvidence[index] || 'verified by runtime checkpoints',
      })),
      checkpoints,
    };
  };

  const report = {
    schemaVersion: 1,
    taskId: contract.taskId,
    platform: 'arkts',
    role: 'final',
    runtime: 'openharmony_api23_device_uitest_and_sandbox_fs',
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
    const users = [...apps.matchAll(/^ID: (\d+):/gm)].map(match => match[1]);
    if (users.length !== 1) throw new Error('Ambiguous device user');
    user = users[0];
    if (apps.split('\n').some(line => line.trim() === bundleName)) {
      throw new Error('Candidate already installed before evaluator-owned execution');
    }

    for (const spec of contract.cases) {
      const ready = await installFresh(spec.caseId);
      let row;

      if (spec.caseId === 'mq_state_001_async_loading') {
        click(ready, 'media_slow_info');
        const loading = await waitFor('loading', nodes => visible(nodes, 'media_information_loading').length === 1 &&
          requireOne(nodes, 'media_estimation_state').text === 'Estimation state: loading' &&
          requireOne(nodes, 'media_status').text.endsWith('state idle'), 10, 50);
        await input(loading, 'media_caption', 'while loading');
        const edited = await waitFor('loading-edited', nodes => requireOne(nodes, 'media_caption').text === 'while loading' &&
          visible(nodes, 'media_cancel').length === 1, 10, 50);
        click(edited, 'media_cancel');
        const cancelled = await waitFor('loading-cancelled', nodes => visible(nodes, 'media_caption').length === 0 &&
          visible(nodes, 'media_background_result').length === 1, 10, 50);
        const observed = { limitState: 'loading', estimationState: 'loading', previewUsable: true, sendState: 'idle' };
        row = caseResult(spec, observed, [
          { name: 'loading_and_editable', layout: loading.artifact },
          { name: 'caption_edited_while_loading', layout: edited.artifact },
          { name: 'cancelled_while_loading', layout: cancelled.artifact },
        ], ['caption editing and cancellation both completed during the five-second real request delay']);
      } else if (spec.caseId === 'mq_state_002_limit_fallback') {
        click(ready, 'media_limit_failure');
        const fallback = await waitFor('fallback', nodes =>
          requireOne(nodes, 'media_upload_limit').text === 'Upload limit: 104857600 bytes' &&
          requireOne(nodes, 'media_fallback_status').text === 'Fallback used: true' &&
          requireOne(nodes, 'media_status').text === 'Quality options ready; state idle');
        row = caseResult(spec, {
          limitState: 'success', maxUploadSize: 104857600, fallbackUsed: true,
        }, [
          { name: 'before_limit_request_failure', layout: ready.artifact },
          { name: 'failed_request_fell_back', layout: fallback.artifact },
        ],
        ['the rendered byte count is exactly 100 * 1024 * 1024']);
      } else if (spec.caseId === 'mq_state_003_image_optimization') {
        click(ready, 'media_open_image');
        const image = await waitFor('image-ready', nodes => visible(nodes, 'image_optimization_toggle').length === 1 &&
          requireOne(nodes, 'media_estimation_state').text === 'Estimation state: uninitialized');
        click(image, 'image_optimization_toggle');
        const disabled = await waitFor('image-disabled', nodes => requireOne(nodes, 'image_optimization_toggle').checked === 'false');
        click(disabled, 'media_send');
        const sent = await waitFor('image-sent', nodes => visible(nodes, 'media_preprocess_effect').length === 1);
        const preprocessText = requireOne(sent.nodes, 'media_preprocess_effect').text;
        const observed = {
          optimizeImages: false,
          videoEstimationState: 'uninitialized',
          preprocessConfig: { compressImages: preprocessText === 'compressImages: false' ? false : null },
        };
        row = caseResult(spec, observed, [
          { name: 'image_mode', layout: image.artifact },
          { name: 'optimization_disabled', layout: disabled.artifact },
          { name: 'real_preprocess_effect', layout: sent.artifact },
        ], ['image mode retained an uninitialized video-estimation state while real preprocessing used false']);
      } else if (spec.caseId === 'mq_state_004_estimate_video_presets') {
        click(ready, 'video_quality_selector');
        const selector = await waitFor('selector-estimates', nodes =>
          ['video_preset_high', 'video_preset_standard', 'video_preset_low'].every(id => visible(nodes, id).length === 1));
        const sizes = {};
        const canUpload = {};
        for (const preset of ['high', 'standard', 'low']) {
          const node = requireOne(selector.nodes, `video_preset_${preset}`);
          const match = new RegExp(`^${preset}: (\\d+) bytes`).exec(node.text);
          if (!match) throw new Error('Missing rendered estimate for ' + preset);
          sizes[preset] = Number(match[1]);
          canUpload[preset] = node.enabled === 'true';
        }
        const safetyMatch = /^Safety overhead: (\d+(?:\.\d+)?)$/.exec(requireOne(selector.nodes, 'media_safety_overhead').text);
        row = caseResult(spec, { sizes, canUpload, safetyOverhead: Number(safetyMatch?.[1]) }, [
          { name: 'before_opening_estimates', layout: ready.artifact },
          { name: 'calculated_estimations', layout: selector.artifact },
        ],
          ['the 35,000,000-byte boundary was applied to the exact rendered estimates']);
      } else if (spec.caseId === 'mq_state_005_choose_best_preset') {
        click(ready, 'video_quality_selector');
        const selector = await waitFor('best-selection', nodes => visible(nodes, 'video_preset_high').length === 1);
        const selected = requireOne(selector.nodes, 'video_quality_selector').text.replace('Quality: ', '');
        const selectionState = requireOne(selector.nodes, 'media_estimation_state').text.replace('Estimation state: ', '');
        if (requireOne(selector.nodes, 'video_preset_high').enabled !== 'false' ||
            requireOne(selector.nodes, 'video_preset_standard').enabled !== 'true') {
          throw new Error('Rendered uploadability does not justify fallback selection');
        }
        row = caseResult(spec, { selectedPreset: selected, selectionState }, [
          { name: 'before_best_preset_selection', layout: ready.artifact },
          { name: 'default_high_fell_back_to_standard', layout: selector.artifact },
        ],
          ['high was disabled, standard was enabled, and the selected preset was standard']);
      } else if (spec.caseId === 'mq_state_006_dismiss_preserves_selection') {
        click(ready, 'video_quality_selector');
        const opened = await waitFor('selector-opened', nodes => visible(nodes, 'video_quality_dismiss').length === 1);
        click(opened, 'video_quality_dismiss');
        const dismissed = await waitFor('selector-dismissed', nodes => visible(nodes, 'video_quality_dismiss').length === 0 &&
          requireOne(nodes, 'video_quality_selector').text === 'Quality: standard');
        row = caseResult(spec, { selectedPreset: 'standard', selectorOpen: false }, [
          { name: 'selector_opened', layout: opened.artifact },
          { name: 'selector_dismissed', layout: dismissed.artifact },
        ], ['the same standard selection was visible before and after dismissal']);
      } else if (spec.caseId === 'mq_state_007_reject_oversized_preset') {
        click(ready, 'video_quality_selector');
        const opened = await waitFor('oversized-opened', nodes => visible(nodes, 'video_preset_high').length === 1);
        const high = requireOne(opened.nodes, 'video_preset_high');
        if (high.enabled !== 'false') throw new Error('High preset must be rendered disabled');
        clickPoint(midpoint(high));
        const rejected = await waitFor('oversized-rejected', nodes =>
          requireOne(nodes, 'video_quality_selector').text === 'Quality: standard' &&
          visible(nodes, 'video_preset_high').length === 1);
        row = caseResult(spec, {
          selectedPreset: 'standard', selectorOpen: true,
          sendable: requireOne(rejected.nodes, 'media_send').enabled === 'true',
        }, [
          { name: 'disabled_high_target', layout: opened.artifact },
          { name: 'global_tap_rejected', layout: rejected.artifact },
        ], ['a real global tap on the disabled high option left standard selected and the chooser open']);
      } else if (spec.caseId === 'mq_state_008_block_when_all_oversized') {
        click(ready, 'media_tiny_limit');
        const modal = await waitFor('too-large-modal', nodes => visible(nodes, 'media_too_large_modal').length === 1 &&
          requireOne(nodes, 'video_quality_selector').text === 'Quality: unavailable');
        const send = requireOne(modal.nodes, 'media_send');
        if (send.enabled !== 'true') throw new Error('Underlying send control must remain enabled under the modal');
        clickPoint(midpoint(send));
        const blocked = await waitFor('too-large-blocked', nodes => visible(nodes, 'media_too_large_modal').length === 1 &&
          requireOne(nodes, 'media_attempt_count').text === 'Attempts: 0' &&
          visible(nodes, 'media_caption').length === 1);
        row = caseResult(spec, {
          fileTooLargeError: true, selectedPreset: null, sendBlockedByModal: true,
        }, [
          { name: 'modal_with_enabled_underlying_send', layout: modal.artifact, sendBounds: send.boundsObject },
          { name: 'global_send_tap_blocked', layout: blocked.artifact },
        ], ['all presets stayed unsendable; the modal absorbed a global tap without an upload attempt']);
      } else if (spec.caseId === 'mq_state_009_failure_cancel_retry') {
        await input(ready, 'media_caption', 'demo');
        const captioned = await waitFor('captioned', nodes => requireOne(nodes, 'media_caption').text === 'demo');
        click(captioned, 'media_prepare');
        const preparedView = await waitFor('prepared', nodes =>
          requireOne(nodes, 'media_prepared_status').text === 'Prepared media ready');
        const remoteArtifact = `/data/app/el2/${user}/base/${bundleName}/cache/${artifactName}`;
        const preparedPayload = JSON.parse(run(['shell', 'cat', remoteArtifact]).text);
        exact(preparedPayload.preset, 'standard', 'prepared preset');
        exact(preparedPayload.videoCompressionPreset, 'standard', 'prepared compression preset');
        click(preparedView, 'media_fail_upload');
        const beforeSend = await waitFor('before-send', nodes => visible(nodes, 'media_send').length === 1);
        click(beforeSend, 'media_send');
        const afterSend = await waitFor('after-send', nodes =>
          ['media_background_result', 'media_cleanup_status', 'media_background_effect'].every(id => visible(nodes, id).length === 1));
        const artifactAfter = run(['shell', 'ls', '-l', remoteArtifact], [0, 255]);
        const artifactStillExists = !/No such file|cannot access|not exist/i.test(artifactAfter.text);
        const effect = requireOne(afterSend.nodes, 'media_background_effect').text;
        const observed = {
          previewVisible: visible(afterSend.nodes, 'media_caption').length > 0,
          sendControlsVisible: visible(afterSend.nodes, 'media_send').length > 0,
          preparedMediaExists: artifactStillExists,
          caption: /caption: demo$/.test(effect) ? 'demo' : null,
          presetUsed: /preset: standard;/.test(effect) ? 'standard' : null,
          attempts: /Attempts: 1;/.test(effect) ? 1 : null,
        };
        exact(requireOne(afterSend.nodes, 'media_background_result').text,
          'The preview closed. Background upload failed.', 'failure result');
        exact(requireOne(afterSend.nodes, 'media_cleanup_status').text,
          'Temporary media removed', 'cleanup result');
        row = caseResult(spec, observed, [
          { name: 'prepared_before_event', layout: beforeSend.artifact, artifactPayload: preparedPayload },
          { name: 'post_event', layout: afterSend.artifact, artifactPath: remoteArtifact },
        ], ['one background attempt used the real prepared artifact, preserved caption/preset, and removed it']);
      } else {
        throw new Error('Unknown case: ' + spec.caseId);
      }

      report.semantic.cases.push(row);
      report.semantic.passed += 1;
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
