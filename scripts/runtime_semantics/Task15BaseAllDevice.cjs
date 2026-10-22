'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const bundleName = 'com.qingyu.elementx.deactivation.base';
const buildReport = path.join(root,
  'experiment_results/runtime_transition_20261020/task15_repair/v3/build-base-eexist-repair/report.json');
const contractFile = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/15_account_deactivation/transitions.json');

const digest = value => crypto.createHash('sha256').update(value).digest('hex');
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const artifact = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: digest(bytes) };
};

function parseBounds(value) {
  const match = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(value || '');
  if (!match) throw new Error('Invalid UI bounds: ' + value);
  return { left: Number(match[1]), top: Number(match[2]), right: Number(match[3]), bottom: Number(match[4]) };
}

function flatten(node, result = []) {
  if (node?.attributes) result.push({ ...node.attributes,
    boundsObject: parseBounds(node.attributes.bounds || '[0,0][0,0]') });
  for (const child of node?.children || []) flatten(child, result);
  return result;
}

const shown = node => node.visible === 'true' && node.boundsObject.right > node.boundsObject.left &&
  node.boundsObject.bottom > node.boundsObject.top;
const byId = (nodes, id) => nodes.filter(node => node.id === id && shown(node));
const byText = (nodes, text) => nodes.filter(node => node.text === text && shown(node));

function requireOne(nodes, predicate, description) {
  const matches = nodes.filter(predicate);
  if (matches.length !== 1) throw new Error(`Expected one visible ${description}, found ${matches.length}`);
  return matches[0];
}

function midpoint(node) {
  return { x: Math.round((node.boundsObject.left + node.boundsObject.right) / 2),
    y: Math.round((node.boundsObject.top + node.boundsObject.bottom) / 2) };
}

const finalIds = ['deactivate_account_entry', 'deactivation_password', 'deactivate_submit',
  'deactivation_loading_dialog', 'deactivation_loading_message'];
const finalTexts = ['Deactivate account', 'Are you sure you want to deactivate this account?',
  'Confirm deactivation', 'Account deactivated'];

async function main() {
  const outputIndex = process.argv.indexOf('--output');
  if (outputIndex < 0 || !process.argv[outputIndex + 1]) throw new Error('--output is required');
  const output = path.resolve(process.argv[outputIndex + 1]);
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite prior evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });

  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '15_account_deactivation' || contract.cases.length !== 10) {
    throw new Error('Expected Task15 revision-3 ten-case contract');
  }
  const build = JSON.parse(fs.readFileSync(buildReport));
  const hapRecord = build.haps?.[0];
  const hap = hapRecord?.path;
  if (build.role !== 'base' || build.compile?.passed !== true || build.productionUnchanged !== true ||
      build.productionCopyUnchanged !== true || build.temporaryWorkspaceRemoved !== true ||
      !hap || !fs.existsSync(hap) || hapRecord.sha256 !== digest(fs.readFileSync(hap))) {
    throw new Error('Task15 base application build evidence is invalid');
  }
  for (const source of build.production) {
    const file = path.join(build.source, source.path);
    if (!fs.existsSync(file) || digest(fs.readFileSync(file)) !== source.sha256) {
      throw new Error('Task15 base source changed after build: ' + source.path);
    }
  }

  const targets = (spawnSync(hdc, ['list', 'targets'], { encoding: 'utf8' }).stdout || '')
    .trim().split(/\s+/).filter(Boolean);
  if (targets.length !== 1) throw new Error('Expected one OpenHarmony target');
  const serial = targets[0];
  const lock = path.join('/tmp', 'ltb-arkts-device-' + digest(Buffer.from(serial)).slice(0, 16));
  const lockWaitStartedAt = Date.now();
  const lockDeadline = lockWaitStartedAt + 3600 * 1000;
  while (true) {
    try { fs.mkdirSync(lock); break; }
    catch (error) {
      if (error.code !== 'EEXIST' || Date.now() >= lockDeadline) throw error;
      await sleep(1000);
    }
  }

  const startedAt = new Date();
  const commands = [];
  const remoteLayouts = [];
  let sequence = 0;
  let currentCase = null;
  let appOwned = false;

  const run = (args, allowed = [0], timeout = 30000) => {
    const result = spawnSync(hdc, ['-t', serial, ...args], {
      encoding: 'utf8', timeout, maxBuffer: 8 * 1024 * 1024,
    });
    const text = (result.stdout || '') + (result.stderr || '');
    const label = args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_');
    const log = path.join(output, String(++sequence).padStart(3, '0') + '-' + label + '.log');
    fs.writeFileSync(log, text, { flag: 'wx' });
    commands.push({ caseId: currentCase, args, exitCode: result.status, log: artifact(log) });
    if (result.error || !allowed.includes(result.status)) {
      throw new Error(`hdc ${args.join(' ')} failed: ${result.error || text}`);
    }
    return text;
  };

  const dump = label => {
    const remote = `/data/local/tmp/task15-base-${Date.now()}-${sequence}.json`;
    remoteLayouts.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundleName], [0], 60000);
    const tree = JSON.parse(run(['shell', 'cat', remote]));
    const local = path.join(output, `${currentCase}-${label}.layout.json`);
    fs.writeFileSync(local, JSON.stringify(tree, null, 2) + '\n', { flag: 'wx' });
    return { nodes: flatten(tree), artifact: artifact(local) };
  };

  const waitFor = async (label, predicate) => {
    let sample;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      sample = dump(label + '-' + String(attempt + 1).padStart(2, '0'));
      if (predicate(sample.nodes)) return { ...sample, attempts: attempt + 1 };
      await sleep(200);
    }
    throw new Error('UI condition timed out: ' + label);
  };

  const missingFinalFeature = nodes => finalIds.every(id => !nodes.some(node => node.id === id)) &&
    finalTexts.every(text => !nodes.some(node => node.text === text));
  const commonSettingsReady = nodes => byText(nodes, 'Settings').length === 1 &&
    byText(nodes, 'Notifications').length === 1 && byText(nodes, 'Chat backup').length === 1 &&
    byText(nodes, 'Blocked users').length === 1 && byId(nodes, 'account_homeserver').length === 1 &&
    byId(nodes, 'account_user').length === 1 && byId(nodes, 'account_password').length === 1 &&
    missingFinalFeature(nodes);

  const report = {
    schemaVersion: 1, taskId: contract.taskId, platform: 'arkts', role: 'base',
    runtime: 'openharmony_api23_device_uitest', observationMode: 'runtime_state_transition',
    status: 'incomplete', startedAt: startedAt.toISOString(),
    compile: { passed: true, scope: 'application_hap', build: artifact(buildReport), hap: artifact(hap) },
    semantic: { total: 10, passed: 0, failed: 0, notScored: 10, cases: [] },
    provenance: { contract: artifact(contractFile), runner: artifact(__filename),
      production: build.production, source: path.relative(root, build.source) },
    diagnostics: { adapter: 'ready', transport: 'ready', serial, commands,
      deviceLockWaitSeconds: (Date.now() - lockWaitStartedAt) / 1000,
      cleanup: { ownedAppUninstalled: false, remoteLayoutsRemoved: 0, deviceLockRemoved: false } },
  };

  try {
    const apps = run(['shell', 'bm', 'dump', '-a']);
    if (apps.split('\n').some(line => line.trim() === bundleName)) {
      throw new Error('Task15 base candidate already installed before evaluator-owned execution');
    }
    for (const spec of contract.cases) {
      currentCase = spec.caseId;
      if (!run(['install', '-r', hap], [0], 120000).includes('install bundle successfully')) {
        throw new Error('Install rejected');
      }
      appOwned = true;
      run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);
      const ready = await waitFor('common-settings', commonSettingsReady);
      await sleep(150);
      const stable = dump('common-settings-stable');
      if (!commonSettingsReady(stable.nodes)) throw new Error('Common settings start was not stable');

      const notifications = requireOne(stable.nodes, node => node.text === 'Notifications' && shown(node), 'Notifications');
      const point = midpoint(notifications);
      run(['shell', 'uitest', 'uiInput', 'click', String(point.x), String(point.y)]);
      const positive = await waitFor('notification-positive-control', nodes =>
        byText(nodes, 'Notification settings opened').length === 1 && missingFinalFeature(nodes));

      report.semantic.cases.push({
        caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'fail', transitionExecuted: false,
        failureKind: 'semantic_missing_feature_entry',
        reason: 'The common production settings transition executes, but the final account-deactivation entry and state machine are absent.',
        expected: spec.expected,
        observed: { commonSettingsMounted: true, notificationSettingsEventExecuted: true,
          finalFeatureIdsAbsent: finalIds, finalFeatureTextsAbsent: finalTexts },
        invariantChecks: spec.invariants.map(text => ({ text, passed: false,
          reason: 'The final-version deactivation transition cannot execute from this base settings UI.' })),
        checkpoints: [
          { name: 'common_settings_ready', layout: ready.artifact },
          { name: 'common_settings_stable', layout: stable.artifact },
          { name: 'notification_settings_positive_control', layout: positive.artifact },
        ],
      });
      report.semantic.failed += 1;
      report.semantic.notScored -= 1;
      run(['uninstall', bundleName], [0], 120000);
      appOwned = false;
    }
    report.status = 'passed';
  } catch (error) {
    report.status = 'blocked';
    report.error = String(error);
    throw error;
  } finally {
    for (const remote of remoteLayouts) {
      try { run(['shell', 'rm', '-f', remote]); report.diagnostics.cleanup.remoteLayoutsRemoved += 1; } catch (_) {}
    }
    if (appOwned) {
      try { run(['uninstall', bundleName], [0], 120000); report.diagnostics.cleanup.ownedAppUninstalled = true; } catch (_) {}
    } else report.diagnostics.cleanup.ownedAppUninstalled = true;
    try { fs.rmdirSync(lock); report.diagnostics.cleanup.deviceLockRemoved = true; } catch (_) {}
    report.finishedAt = new Date().toISOString();
    report.elapsedSeconds = (Date.parse(report.finishedAt) - startedAt.getTime()) / 1000;
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
