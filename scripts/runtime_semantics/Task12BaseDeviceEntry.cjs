'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(process.env.HOME, 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const bundleName = 'com.qingyu.elementx.reportroom.base.rebuilt';
const hap = path.join(root, 'experiment_results/runtime_transition_20261020/task12_rebuild/build-base/entry-default-unsigned.hap');
const buildReport = path.join(root, 'experiment_results/runtime_transition_20261020/task12_rebuild/build-base/build-report.json');
const contractFile = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/12_report_room/transitions.json');
const roomId = '!room:example.org';
const port = 18713;

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const record = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) };
};
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const midpoint = bounds => ({ x: Math.round((bounds.left + bounds.right) / 2), y: Math.round((bounds.top + bounds.bottom) / 2) });

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

function requireOne(nodes, id) {
  const matches = nodes.filter(node => node.id === id && node.visible === 'true');
  if (matches.length !== 1) throw new Error(`Expected one visible ${id}, found ${matches.length}`);
  return matches[0];
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
    throw new Error('Base application build evidence is invalid');
  }
  const commands = [];
  let commandSequence = 0;
  const run = (args, directory, allowed = [0]) => {
    const result = spawnSync(hdc, args, { encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024 });
    const text = (result.stdout || '') + (result.stderr || '');
    const log = path.join(directory, String(++commandSequence).padStart(3, '0') + '-' +
      args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_') + '.log');
    fs.writeFileSync(log, text, { flag: 'wx' });
    const item = { args, exitCode: result.status, log: record(log) };
    commands.push(item);
    if (result.error || !allowed.includes(result.status)) throw new Error(`hdc ${args.join(' ')} failed: ${result.error || text}`);
    return text;
  };
  const remoteFiles = [];
  const dump = (directory, label) => {
    const remote = '/data/local/tmp/task12-' + path.basename(directory) + '-' + label + '.json';
    remoteFiles.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', bundleName], directory);
    const data = run(['shell', 'cat', remote], directory);
    const parsed = JSON.parse(data);
    const local = path.join(directory, label + '.layout.json');
    fs.writeFileSync(local, JSON.stringify(parsed, null, 2) + '\n', { flag: 'wx' });
    return { parsed, nodes: flatten(parsed), artifact: record(local) };
  };
  const waitFor = async (directory, label, predicate) => {
    let latest;
    for (let attempt = 0; attempt < 30; attempt++) {
      latest = dump(directory, label + '-' + String(attempt + 1).padStart(2, '0'));
      if (predicate(latest.nodes)) return { ...latest, attempts: attempt + 1 };
      await sleep(200);
    }
    throw new Error('UI condition timed out: ' + label + '; latest=' + JSON.stringify(latest?.nodes));
  };
  const uiInput = (directory, operation, ...args) => run(['shell', 'uitest', 'uiInput', operation, ...args.map(String)], directory);
  let activeCase = '';
  const requests = [];
  const server = http.createServer((request, response) => {
    let body = '';
    request.on('data', chunk => { body += chunk; });
    request.on('end', () => {
      requests.push({ caseRunId: activeCase, method: request.method, url: request.url, authorization: request.headers.authorization, body });
      response.setHeader('content-type', 'application/json');
      if (request.url.endsWith('/joined_rooms')) response.end(JSON.stringify({ joined_rooms: [roomId] }));
      else if (request.url.includes('/state')) response.end(JSON.stringify([
        { type: 'm.room.name', state_key: '', content: { name: 'Runtime room' } },
        { type: 'm.room.member', state_key: '@member:example.org', content: { membership: 'join' } }
      ]));
      else response.end('{}');
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
    for (let index = 0; index < contract.cases.length; index++) {
      const spec = contract.cases[index];
      const caseRunId = spec.caseId + '-' + crypto.randomBytes(8).toString('hex');
      activeCase = caseRunId;
      const directory = path.join(output, spec.caseId);
      fs.mkdirSync(directory);
      run(['uninstall', bundleName], directory, [0, 255]);
      const beforeInstall = run(['shell', 'bm', 'dump', '-n', bundleName], directory, [0, 255]);
      if (!/failed|not exist|error/i.test(beforeInstall)) throw new Error('Candidate unexpectedly installed before fresh case: ' + beforeInstall);
      run(['install', '-r', hap], directory);
      run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry'], directory);
      const entry = await waitFor(directory, 'entry', nodes => ['room_homeserver', 'room_access_token', 'room_id_input', 'open_room']
        .every(id => nodes.some(node => node.id === id && node.visible === 'true')));
      for (const [id, value] of [['room_homeserver', `http://127.0.0.1:${port}`], ['room_access_token', 'runtime-token'], ['room_id_input', roomId]]) {
        const point = midpoint(requireOne(entry.nodes, id).boundsObject);
        uiInput(directory, 'inputText', point.x, point.y, value);
        uiInput(directory, 'keyEvent', 'Back');
      }
      const ready = await waitFor(directory, 'ready-to-open', nodes => {
        const button = nodes.find(node => node.id === 'open_room');
        return button?.enabled === 'true';
      });
      const openPoint = midpoint(requireOne(ready.nodes, 'open_room').boundsObject);
      uiInput(directory, 'click', openPoint.x, openPoint.y);
      const details = await waitFor(directory, 'details', nodes => ['room_details_title', 'room_details_id', 'room_details_name', 'room_member_count', 'leave_room']
        .every(id => nodes.some(node => node.id === id && node.visible === 'true')));
      await sleep(250);
      const stable = dump(directory, 'details-stable');
      const reportIds = ['report_room_entry', 'report_room_reason', 'submit_report_room'];
      const reportMatches = sample => sample.nodes.filter(node => reportIds.includes(node.id) || node.text === 'Report room');
      const detailsId = requireOne(details.nodes, 'room_details_id');
      const detailsName = requireOne(details.nodes, 'room_details_name');
      const memberCount = requireOne(details.nodes, 'room_member_count');
      if (detailsId.text !== roomId || detailsName.text !== 'Runtime room' || memberCount.text !== '1 members' ||
        reportMatches(details).length || reportMatches(stable).length) throw new Error('Common start or stable entry absence failed');
      const leavePoint = midpoint(requireOne(stable.nodes, 'leave_room').boundsObject);
      uiInput(directory, 'click', leavePoint.x, leavePoint.y);
      const confirmation = await waitFor(directory, 'leave-confirmation', nodes =>
        nodes.some(node => node.id === 'leave_room_confirmation' && node.visible === 'true') &&
        nodes.some(node => node.id === 'cancel_leave_room' && node.enabled === 'true'));
      const cancelPoint = midpoint(requireOne(confirmation.nodes, 'cancel_leave_room').boundsObject);
      uiInput(directory, 'click', cancelPoint.x, cancelPoint.y);
      const restored = await waitFor(directory, 'details-restored', nodes =>
        nodes.some(node => node.id === 'room_details_id' && node.text === roomId && node.visible === 'true') &&
        nodes.some(node => node.id === 'leave_room' && node.enabled === 'true'));
      const caseRequests = requests.filter(item => item.caseRunId === caseRunId);
      if (caseRequests.map(item => item.url).join('|') !==
        '/_matrix/client/v3/joined_rooms|/_matrix/client/v3/rooms/!room%3Aexample.org/state' ||
        caseRequests.some(item => item.authorization !== 'Bearer runtime-token')) throw new Error('Unexpected Matrix common-start requests');
      rows.push({ caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'fail', transitionExecuted: false,
        observed: null, invariantChecks: [], checkpoints: [
          { name: 'common_start', state: { roomId, screen: 'room_details', roomName: detailsName.text, memberCount: 1,
            leaveControlEnabled: true, reportEntryCount: 0 }, layout: details.artifact },
          { name: 'entry_absence_stable', state: { reportEntryCount: 0, samples: 2 }, layout: stable.artifact },
          { name: 'positive_leave_control', state: { confirmationVisible: true, cancelEnabled: true }, layout: confirmation.artifact },
          { name: 'common_start_restored', state: { roomId, leaveControlEnabled: true }, layout: restored.artifact }
        ], entryFailureEvidence: { schemaVersion: 1, caseRunId, canonicalGivenEstablished: true,
          requestedAction: spec.setup.actions[0] || spec.event, failedAt: spec.setup.actions.length ? 'setup.actions[0]' : 'event',
          reason: 'The actual rendered base room-details page has no report entry after a real Matrix room load.',
          candidateRoute: 'pages/Index', candidateBundle: bundleName, reportEntryCount: 0,
          positiveControl: 'leave_confirmation_and_cancel', requests: caseRequests },
        reason: 'Canonical report-room action is unavailable on the real base room-details page.' });
      run(['uninstall', bundleName], directory);
    }
  } finally {
    activeCase = '';
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
  const report = { schemaVersion: 2, taskId: '12_report_room', platform: 'arkts', role: 'base',
    observationMode: 'runtime_state_transition', runtime: 'openharmony_api23_device_uitest',
    observationScope: 'Fresh-installed production HAP, real Matrix HTTP transport through HDC reverse, rendered ArkUI and UiTest layout/actions.',
    compile: { passed: true, scope: 'application_hap', build: record(buildReport), hap: record(hap) },
    semantic: { total: rows.length, passed: 0, failed: rows.length, notScored: 0, cases: rows },
    diagnostics: { adapter: 'ready', transport: 'ready', commands, serverRequests: requests,
      cleanup: { ownedAppUninstalled: true, reverseRemoved: true, remoteLayoutsRemoved: remoteFiles.length } },
    provenance: { contract: record(contractFile), runner: record(__filename), activeMetadataModified: false } };
  const reportFile = path.join(output, 'arkts_12_report_room_base.device-entry.json');
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ report: reportFile, semantic: report.semantic, cleanup: report.diagnostics.cleanup }, null, 2));
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
