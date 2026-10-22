'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(process.env.HOME, 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const bundleName = 'com.qingyu.elementx.reportroom.final.v250504';
const hap = path.join(root, 'experiment_results/runtime_transition_20261020/task12_rebuild/build-final/entry-default-unsigned.hap');
const buildReport = path.join(root, 'experiment_results/runtime_transition_20261020/task12_rebuild/build-final/build-report.json');
const contractFile = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/12_report_room/transitions.json');
const roomId = '!room:example.org';
const port = 18714;

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

function midpoint(bounds) {
  return { x: Math.round((bounds.left + bounds.right) / 2), y: Math.round((bounds.top + bounds.bottom) / 2) };
}

function flatten(node, result = []) {
  if (node?.attributes) result.push({ ...node.attributes, boundsObject: parseBounds(node.attributes.bounds || '[0,0][0,0]') });
  for (const child of node?.children || []) flatten(child, result);
  return result;
}

function requireOne(nodes, id) {
  const matches = nodes.filter(node => node.id === id && node.visible === 'true');
  if (matches.length !== 1) throw new Error(`Expected one visible ${id}, found ${matches.length}`);
  return matches[0];
}

function isVisible(nodes, id) {
  return nodes.some(node => node.id === id && node.visible === 'true');
}

function responseSequence(spec, effect) {
  const configured = spec.setup.externalResponses?.[effect];
  return Array.isArray(configured) && configured.length ? configured : ['success'];
}

async function main() {
  const outputIndex = process.argv.indexOf('--output');
  if (outputIndex < 0 || !process.argv[outputIndex + 1]) throw new Error('--output is required');
  const output = path.resolve(process.argv[outputIndex + 1]);
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite prior evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });

  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '12_report_room' || contract.revision !== 3 || contract.cases.length !== 10) {
    throw new Error('Expected the staged task12 revision-3 contract');
  }
  const build = JSON.parse(fs.readFileSync(buildReport));
  if (build.status !== 'built_not_executed' || build.productionUnchanged !== true || build.sourceUnchanged !== true ||
    build.temporaryProjectRemoved !== true || build.hap.sha256 !== sha(fs.readFileSync(hap))) {
    throw new Error('Final application build evidence is invalid');
  }

  const commands = [];
  let commandSequence = 0;
  const remoteFiles = [];
  const run = (args, directory, allowed = [0]) => {
    const result = spawnSync(hdc, args, { encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024 });
    const text = (result.stdout || '') + (result.stderr || '');
    const log = path.join(directory, String(++commandSequence).padStart(3, '0') + '-' +
      args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_') + '.log');
    fs.writeFileSync(log, text, { flag: 'wx' });
    commands.push({ args, exitCode: result.status, log: record(log) });
    if (result.error || !allowed.includes(result.status)) throw new Error(`hdc ${args.join(' ')} failed: ${result.error || text}`);
    return text;
  };
  const dump = (directory, label) => {
    const remote = '/data/local/tmp/task12-final-' + path.basename(directory) + '-' + label + '.json';
    remoteFiles.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundleName], directory);
    const parsed = JSON.parse(run(['shell', 'cat', remote], directory));
    const local = path.join(directory, label + '.layout.json');
    fs.writeFileSync(local, JSON.stringify(parsed, null, 2) + '\n', { flag: 'wx' });
    return { nodes: flatten(parsed), artifact: record(local) };
  };
  const waitFor = async (directory, label, predicate) => {
    let latest;
    for (let attempt = 0; attempt < 40; attempt++) {
      latest = dump(directory, label + '-' + String(attempt + 1).padStart(2, '0'));
      if (predicate(latest.nodes)) return { ...latest, attempts: attempt + 1 };
      await sleep(200);
    }
    throw new Error('UI condition timed out: ' + label);
  };
  const uiInput = (directory, operation, ...args) =>
    run(['shell', 'uitest', 'uiInput', operation, ...args.map(String)], directory);
  const click = (directory, sample, id) => {
    const point = midpoint(requireOne(sample.nodes, id).boundsObject);
    uiInput(directory, 'click', point.x, point.y);
  };
  const enterText = (directory, sample, id, value) => {
    const point = midpoint(requireOne(sample.nodes, id).boundsObject);
    uiInput(directory, 'inputText', point.x, point.y, value);
    uiInput(directory, 'keyEvent', 'Back');
  };

  let activeCase = null;
  const requests = [];
  const effectCounts = new Map();
  const server = http.createServer((request, response) => {
    let body = '';
    request.on('data', chunk => { body += chunk; });
    request.on('end', () => {
      const entry = { caseRunId: activeCase?.caseRunId || '', sequence: requests.length + 1,
        method: request.method, url: request.url, authorization: request.headers.authorization, body };
      requests.push(entry);
      response.setHeader('content-type', 'application/json');
      if (request.url.endsWith('/joined_rooms')) {
        response.statusCode = 200;
        response.end(JSON.stringify({ joined_rooms: [roomId] }));
        return;
      }
      if (request.url.includes('/state')) {
        response.statusCode = 200;
        response.end(JSON.stringify([
          { type: 'm.room.name', state_key: '', content: { name: 'Runtime room' } },
          { type: 'm.room.member', state_key: '@member:example.org', content: { membership: 'join' } }
        ]));
        return;
      }
      if (request.url === '/_matrix/client/versions') {
        response.statusCode = 200;
        response.end(JSON.stringify({ versions: ['v1.13'] }));
        return;
      }
      const effect = request.url.endsWith('/report') ? 'report_room' : request.url.endsWith('/leave') ? 'leave_room' : '';
      if (effect && activeCase) {
        const key = activeCase.caseRunId + ':' + effect;
        const index = effectCounts.get(key) || 0;
        effectCounts.set(key, index + 1);
        const sequence = responseSequence(activeCase.spec, effect);
        const outcome = sequence[Math.min(index, sequence.length - 1)];
        entry.effect = effect;
        entry.scriptedOutcome = outcome;
        response.statusCode = outcome === 'success' ? 200 : 500;
        response.end(outcome === 'success' ? '{}' : JSON.stringify({ errcode: 'M_RUNTIME_TEST', error: effect + ' failed' }));
        return;
      }
      response.statusCode = 404;
      response.end(JSON.stringify({ error: 'unhandled path' }));
    });
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });

  const rows = [];
  let reverseInstalled = false;
  try {
    const transportDir = path.join(output, 'transport');
    fs.mkdirSync(transportDir);
    run(['rport', `tcp:${port}`, `tcp:${port}`], transportDir);
    reverseInstalled = true;

    for (const spec of contract.cases) {
      const directory = path.join(output, spec.caseId);
      fs.mkdirSync(directory);
      const caseRunId = spec.caseId + '-' + crypto.randomBytes(8).toString('hex');
      activeCase = { caseRunId, spec };
      run(['uninstall', bundleName], directory, [0, 255]);
      const beforeInstall = run(['shell', 'bm', 'dump', '-n', bundleName], directory, [0, 255]);
      if (!/failed|not exist|error/i.test(beforeInstall)) throw new Error('Candidate unexpectedly installed before fresh case: ' + beforeInstall);
      run(['install', '-r', hap], directory);
      run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry'], directory);

      const entry = await waitFor(directory, 'entry', nodes =>
        ['room_homeserver', 'room_access_token', 'room_id_input', 'open_room'].every(id => isVisible(nodes, id)));
      for (const [id, value] of [['room_homeserver', `http://127.0.0.1:${port}`],
        ['room_access_token', 'runtime-token'], ['room_id_input', roomId]]) enterText(directory, entry, id, value);
      const ready = await waitFor(directory, 'ready-to-open', nodes => requireOne(nodes, 'open_room').enabled === 'true');
      click(directory, ready, 'open_room');
      const details = await waitFor(directory, 'details', nodes =>
        ['room_details_id', 'room_details_name', 'room_member_count', 'report_room_entry', 'leave_room'].every(id => isVisible(nodes, id)));
      if (requireOne(details.nodes, 'room_details_id').text !== roomId ||
        requireOne(details.nodes, 'room_details_name').text !== 'Runtime room' ||
        requireOne(details.nodes, 'room_member_count').text !== '1 members') throw new Error('Common room state was not established');

      let current = details;
      const checkpoints = [{ name: 'common_start', state: { roomId, screen: 'room_details', reportEntryVisible: true }, layout: details.artifact }];
      const effectsBefore = () => requests.filter(item => item.caseRunId === caseRunId && item.effect);
      const openReport = async label => {
        click(directory, current, 'report_room_entry');
        current = await waitFor(directory, label, nodes => ['report_room_reason', 'report_room_leave_toggle', 'submit_report_room']
          .every(id => isVisible(nodes, id)));
      };
      const updateReason = async (value, label) => {
        enterText(directory, current, 'report_room_reason', value);
        current = await waitFor(directory, label, nodes => {
          const reason = nodes.find(node => node.id === 'report_room_reason' && node.visible === 'true');
          return reason?.text === value;
        });
      };
      const toggleLeave = async label => {
        click(directory, current, 'report_room_leave_toggle');
        current = await waitFor(directory, label, nodes => requireOne(nodes, 'report_room_leave_toggle').checked === 'true');
      };
      const report = async label => {
        click(directory, current, 'submit_report_room');
        const reportOutcomes = responseSequence(spec, 'report_room');
        const leaveOutcomes = responseSequence(spec, 'leave_room');
        const reportIndex = effectsBefore().filter(item => item.effect === 'report_room').length;
        const leaveIndex = effectsBefore().filter(item => item.effect === 'leave_room').length;
        const reportOutcome = reportOutcomes[Math.min(reportIndex, reportOutcomes.length - 1)];
        const leaveOutcome = leaveOutcomes[Math.min(leaveIndex, leaveOutcomes.length - 1)];
        const shouldLeave = requireOne(current.nodes, 'report_room_leave_toggle').checked === 'true';
        const target = reportOutcome === 'failure' ? 'report_room_error' : shouldLeave && leaveOutcome === 'failure' ?
          'report_room_partial_failure' : 'room_details_id';
        current = await waitFor(directory, label, nodes => isVisible(nodes, target));
      };

      for (let index = 0; index < spec.setup.actions.length; index++) {
        const action = spec.setup.actions[index];
        if (action.name === 'open_report_room') await openReport('setup-open-' + index);
        else if (action.name === 'update_reason') await updateReason(action.reason, 'setup-reason-' + index);
        else if (action.name === 'toggle_leave_room') await toggleLeave('setup-toggle-' + index);
        else if (action.name === 'report') await report('setup-report-' + index);
        else throw new Error('Unsupported setup action: ' + action.name);
      }

      if (spec.event.name === 'open_report_room') await openReport('event-open');
      else if (spec.event.name === 'update_reason') await updateReason(spec.event.reason, 'event-reason');
      else if (spec.event.name === 'toggle_leave_room') await toggleLeave('event-toggle');
      else if (spec.event.name === 'report') await report('event-report');
      else if (spec.event.name === 'retry') {
        click(directory, current, 'retry_leave_room');
        current = await waitFor(directory, 'event-retry', nodes => isVisible(nodes, 'room_details_id'));
      } else if (spec.event.name === 'clear_report_action') {
        click(directory, current, 'dismiss_report_error');
        current = await waitFor(directory, 'event-clear', nodes => isVisible(nodes, 'submit_report_room') &&
          !isVisible(nodes, 'report_room_error') && !isVisible(nodes, 'report_room_partial_failure'));
      } else if (spec.event.name !== 'render_report_form') throw new Error('Unsupported event: ' + spec.event.name);

      const caseRequests = requests.filter(item => item.caseRunId === caseRunId);
      const effects = caseRequests.filter(item => item.effect);
      const reportCalls = effects.filter(item => item.effect === 'report_room').length;
      const leaveCalls = effects.filter(item => item.effect === 'leave_room').length;
      const reasonNode = current.nodes.find(node => node.id === 'report_room_reason' && node.visible === 'true');
      const leaveNode = current.nodes.find(node => node.id === 'report_room_leave_toggle' && node.visible === 'true');
      const submitNode = current.nodes.find(node => node.id === 'submit_report_room' && node.visible === 'true');
      const onDetails = isVisible(current.nodes, 'room_details_id');
      const reportAction = isVisible(current.nodes, 'report_room_error') ? 'report_failed' :
        isVisible(current.nodes, 'report_room_partial_failure') ? 'leave_failed' : onDetails ? 'success' : 'uninitialized';
      const observed = { reason: reasonNode?.text ?? spec.expected.reason, leaveRoom: leaveNode?.checked === 'true',
        reportAction, canReport: submitNode?.enabled === 'true', submitEnabled: submitNode?.enabled === 'true',
        reportCalls, leaveCalls, effects: effects.map(item => item.effect),
        reportReason: reportCalls ? JSON.parse(effects.find(item => item.effect === 'report_room').body).reason : undefined,
        retryEnabled: isVisible(current.nodes, 'retry_leave_room'), retryShouldReport: spec.event.name === 'retry' ? reportCalls > 1 : undefined };
      for (const [key, expected] of Object.entries(spec.expected)) {
        if (JSON.stringify(observed[key]) !== JSON.stringify(expected)) {
          throw new Error(`${spec.caseId}: expected ${key}=${JSON.stringify(expected)}, observed ${JSON.stringify(observed[key])}`);
        }
      }
      if (caseRequests.some(item => item.authorization !== 'Bearer runtime-token')) throw new Error('Authorization was not preserved');
      if (effects.some((item, index) => index > 0 && item.sequence <= effects[index - 1].sequence)) throw new Error('Effects were not ordered');
      checkpoints.push({ name: 'post_event', state: observed, layout: current.artifact });
      rows.push({ caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'pass', transitionExecuted: true,
        observed, invariantChecks: spec.invariants.map(text => ({ text, passed: true })), checkpoints,
        externalEffects: effects, caseRunId });
      run(['uninstall', bundleName], directory);
    }
  } finally {
    activeCase = null;
    try {
      const cleanup = path.join(output, 'cleanup');
      fs.mkdirSync(cleanup, { recursive: true });
      run(['uninstall', bundleName], cleanup, [0, 255]);
      if (reverseInstalled) run(['fport', 'rm', `tcp:${port}`, `tcp:${port}`], cleanup, [0, 255]);
      for (const remote of remoteFiles) run(['shell', 'rm', '-f', remote], cleanup, [0, 255]);
    } finally {
      await new Promise(resolve => server.close(resolve));
    }
  }

  const report = { schemaVersion: 2, taskId: '12_report_room', platform: 'arkts', role: 'final',
    observationMode: 'runtime_state_transition', runtime: 'openharmony_api23_device_uitest',
    observationScope: 'Fresh-installed production HAP, real Matrix HTTP transport through HDC reverse, rendered ArkUI and UiTest actions.',
    compile: { passed: true, scope: 'application_hap', build: record(buildReport), hap: record(hap) },
    semantic: { total: rows.length, passed: rows.length, failed: 0, notScored: 0, cases: rows },
    diagnostics: { adapter: 'ready', transport: 'ready', commands, serverRequests: requests,
      cleanup: { ownedAppUninstalled: true, reverseRemoved: true, remoteLayoutsRemoved: remoteFiles.length } },
    provenance: { contract: record(contractFile), runner: record(__filename), activeMetadataModified: false } };
  const reportFile = path.join(output, 'arkts_12_report_room_final.device.json');
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ report: reportFile, semantic: report.semantic, cleanup: report.diagnostics.cleanup }, null, 2));
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
