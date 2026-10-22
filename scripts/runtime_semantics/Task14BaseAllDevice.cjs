'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const bundleName = 'com.qingyu.elementx.joinaddress.base';
const buildReport = path.join(root,
  'experiment_results/runtime_transition_20261020/task14_repair/real_flow_v2/builds/base-attempt3/report.json');
const hap = path.join(path.dirname(buildReport), 'entry-default-unsigned.hap');
const contractFile = path.join(root, 'benchmark_tasks/14_join_room_by_address/transitions.json');

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
  if (node?.attributes) result.push({ ...node.attributes,
    boundsObject: parseBounds(node.attributes.bounds || '[0,0][0,0]') });
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

const finalControls = {
  jr_state_001_entry_opens_address_flow: ['join_room_by_address', 'room_address_input'],
  jr_state_002_update_trims_and_debounces: ['join_room_by_address', 'room_address_input'],
  jr_state_003_invalid_after_continue: ['room_address_input', 'join_room_continue'],
  jr_state_004_valid_address_resolves: ['room_address_input', 'join_room_continue'],
  jr_state_005_found_then_continue_navigates: ['room_address_input', 'join_room_continue'],
  jr_state_006_continue_waits_for_resolution: ['room_address_input', 'join_room_continue'],
  jr_state_007_not_found_recovers: ['room_address_input', 'join_room_continue'],
  jr_state_008_timeout_recovers: ['room_address_input', 'join_room_continue'],
  jr_state_009_dismiss_closes_flow: ['room_address_input', 'join_room_cancel'],
};

async function main() {
  const outputIndex = process.argv.indexOf('--output');
  if (outputIndex < 0 || !process.argv[outputIndex + 1]) throw new Error('--output is required');
  const output = path.resolve(process.argv[outputIndex + 1]);
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite prior evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });

  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '14_join_room_by_address' || contract.cases.length !== 9) {
    throw new Error('Expected Task14 nine-case contract');
  }
  const build = JSON.parse(fs.readFileSync(buildReport));
  if (build.role !== 'base' || build.passed !== true || build.productionUnchanged !== true ||
      build.copiedProductionUnchanged !== true || build.temporaryProjectRemoved !== true ||
      build.hap?.sha256 !== sha(fs.readFileSync(hap))) {
    throw new Error('Base application build evidence is invalid');
  }
  for (const source of build.sources) {
    const file = path.join(build.source, source.path);
    if (!fs.existsSync(file) || sha(fs.readFileSync(file)) !== source.sha256) {
      throw new Error('Base source changed after application build: ' + source.path);
    }
  }

  const targets = (spawnSync(hdc, ['list', 'targets'], { encoding: 'utf8' }).stdout || '')
    .trim().split(/\s+/).filter(Boolean);
  if (targets.length !== 1) throw new Error('Expected one OpenHarmony target');
  const serial = targets[0];
  const lock = path.join('/tmp', 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16));
  const lockWaitStartedAt = Date.now();
  const lockDeadline = lockWaitStartedAt + 3600 * 1000;
  while (true) {
    try {
      fs.mkdirSync(lock);
      break;
    } catch (error) {
      if (error.code !== 'EEXIST' || Date.now() >= lockDeadline) throw error;
      await sleep(1000);
    }
  }
  const deviceLockWaitSeconds = (Date.now() - lockWaitStartedAt) / 1000;

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
    commands.push({ caseId: currentCase, args, exitCode: result.status, log: record(log) });
    if (result.error || !allowed.includes(result.status)) {
      throw new Error(`hdc ${args.join(' ')} failed: ${result.error || text}`);
    }
    return { text, status: result.status };
  };

  const dump = label => {
    const remote = `/data/local/tmp/task14-base-${Date.now()}-${sequence}.json`;
    remoteLayouts.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundleName], [0], 60000);
    const tree = JSON.parse(run(['shell', 'cat', remote]).text);
    const local = path.join(output, `${currentCase}-${label}.layout.json`);
    fs.writeFileSync(local, JSON.stringify(tree, null, 2) + '\n', { flag: 'wx' });
    return { nodes: flatten(tree), artifact: record(local) };
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
  const click = (sample, id) => {
    const point = midpoint(requireOne(sample.nodes, id));
    run(['shell', 'uitest', 'uiInput', 'click', String(point.x), String(point.y)]);
  };

  const report = {
    schemaVersion: 1, taskId: contract.taskId, platform: 'arkts', role: 'base',
    runtime: 'openharmony_api23_device_uitest', observationMode: 'runtime_state_transition',
    status: 'incomplete', startedAt: startedAt.toISOString(),
    compile: { passed: true, scope: 'application_hap', build: record(buildReport), hap: record(hap) },
    semantic: { total: 9, passed: 0, failed: 0, notScored: 9, cases: [] },
    provenance: { contract: record(contractFile), runner: record(__filename),
      production: build.sources, source: path.relative(root, build.source) },
    diagnostics: { adapter: 'ready', transport: 'ready', serial, commands,
      deviceLockWaitSeconds,
      cleanup: { ownedAppUninstalled: false, remoteLayoutsRemoved: 0, deviceLockRemoved: false } },
  };

  try {
    const apps = run(['shell', 'bm', 'dump', '-a']).text;
    if (apps.split('\n').some(line => line.trim() === bundleName)) {
      throw new Error('Candidate already installed before evaluator-owned execution');
    }
    for (const spec of contract.cases) {
      currentCase = spec.caseId;
      if (!run(['install', '-r', hap]).text.includes('install bundle successfully')) {
        throw new Error('Install rejected');
      }
      appOwned = true;
      run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);
      const ready = await waitFor('start-chat', nodes =>
        visible(nodes, 'create_room_action').length === 1 &&
        visible(nodes, 'person_@alice:demo.local').length === 1);
      const missingBefore = finalControls[spec.caseId].filter(id => visible(ready.nodes, id).length === 0);
      if (missingBefore.length === 0) throw new Error('Base unexpectedly exposes the final transition entry');

      click(ready, 'create_room_action');
      const create = await waitFor('create-route', nodes => visible(nodes, 'create_room_title').length === 1 &&
        visible(nodes, 'create_room_cancel').length === 1);
      click(create, 'create_room_cancel');
      const returned = await waitFor('returned-start-chat', nodes =>
        visible(nodes, 'create_room_action').length === 1 &&
        visible(nodes, 'person_@alice:demo.local').length === 1);
      click(returned, 'person_@alice:demo.local');
      const direct = await waitFor('direct-room', nodes => visible(nodes, 'room_id').length === 1 &&
        requireOne(nodes, 'room_members').text.includes('@alice:demo.local'));
      const roomId = requireOne(direct.nodes, 'room_id').text;
      if (!roomId.startsWith('!local-')) throw new Error('DM did not reach a stored room ID');
      const missingAfter = finalControls[spec.caseId].filter(id => visible(direct.nodes, id).length === 0);
      if (missingAfter.length === 0) throw new Error('Final controls unexpectedly appeared after positive controls');

      report.semantic.cases.push({
        caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'fail', transitionExecuted: false,
        failureKind: 'semantic_missing_feature_entry',
        reason: 'The common create-room and direct-message production routes work, but the final join-by-address transition is absent.',
        expected: spec.expected,
        observed: { createRoomRouteReached: true, directMessageRouteReached: true,
          storedDirectRoomId: roomId, missingEntrypointsBeforePositiveControl: missingBefore,
          missingEntrypointsAfterPositiveControl: missingAfter },
        invariantChecks: spec.invariants.map(text => ({ text, passed: false,
          reason: 'The final-version join-by-address transition cannot execute from this base UI.' })),
        checkpoints: [
          { name: 'reachable_common_start_chat', layout: ready.artifact },
          { name: 'create_room_route', layout: create.artifact },
          { name: 'returned_common_start_chat', layout: returned.artifact },
          { name: 'stored_direct_room_route', layout: direct.artifact },
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
      try { run(['shell', 'rm', '-f', remote]); report.diagnostics.cleanup.remoteLayoutsRemoved += 1; } catch (_) {}
    }
    if (appOwned) {
      try { run(['uninstall', bundleName]); report.diagnostics.cleanup.ownedAppUninstalled = true; } catch (_) {}
    } else {
      report.diagnostics.cleanup.ownedAppUninstalled = true;
    }
    try { fs.rmdirSync(lock); report.diagnostics.cleanup.deviceLockRemoved = true; } catch (_) {}
    report.finishedAt = new Date().toISOString();
    report.elapsedSeconds = (Date.parse(report.finishedAt) - startedAt.getTime()) / 1000;
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
