'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const { spawnSync } = require('node:child_process');
const { performance } = require('node:perf_hooks');
const F = require('./Task12ReplayFacts.cjs');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const record = file => { const data = fs.readFileSync(file); return { path: file, bytes: data.length, sha256: sha(data) }; };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const requireFact = (ok, message) => { if (!ok) throw Error(message); };

function flatten(tree, result = []) {
  if (tree.attributes) result.push(tree.attributes);
  for (const child of tree.children || []) flatten(child, result);
  return result;
}

function midpoint(node) {
  const bounds = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(node.bounds || '');
  requireFact(bounds, 'Native component bounds unavailable');
  return [Math.round((+bounds[1] + +bounds[3]) / 2), Math.round((+bounds[2] + +bounds[4]) / 2)];
}

async function main() {
  const configPath = path.resolve(process.argv[2]), config = JSON.parse(fs.readFileSync(configPath));
  const output = config.output;
  requireFact(!fs.existsSync(output), 'Refusing existing native execution evidence');
  fs.mkdirSync(output, { recursive: true });
  const deadline = performance.now() + config.remainingSeconds * 1000;
  const remaining = () => { const value = Math.floor(deadline - performance.now()); requireFact(value > 0, 'Single replay deadline exhausted'); return value; };
  const contract = JSON.parse(fs.readFileSync(config.contract));
  const build = JSON.parse(fs.readFileSync(config.buildReport));
  requireFact(build.source === config.source && build.productionUnchanged && build.temporaryProjectRemoved &&
    build.hap.sha256 === record(config.hap).sha256, 'Source-specific compiled production HAP differs');
  const nonce = crypto.randomBytes(16).toString('hex');
  let sequence = 0, commandSequence = 0, activeCase;
  const commands = [], requests = [], rows = [], remoteFiles = [], effectCounts = new Map();
  const mark = () => ++sequence;
  const run = (args, directory, allowed = [0]) => {
    const result = spawnSync(config.hdc, ['-t', config.serial, ...args], { encoding: 'utf8',
      timeout: Math.min(30000, remaining()), maxBuffer: 16 * 1024 * 1024 });
    const log = path.join(directory, String(++commandSequence).padStart(6, '0') + '.log');
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''), { flag: 'wx' });
    commands.push({ args, exitCode: result.status, log: record(log), sequence: mark() });
    requireFact(!result.error && allowed.includes(result.status), 'HDC transport failed: ' + log);
    return fs.readFileSync(log, 'utf8');
  };
  const dump = (directory, label) => {
    const remote = '/data/local/tmp/task12-replay-' + nonce + '-' + commandSequence + '.json';
    remoteFiles.push(remote);
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', config.bundle], directory);
    let tree;
    for (let attempt = 0; attempt < 5; attempt++) {
      try { tree = JSON.parse(run(['shell', 'cat', remote], directory)); break; }
      catch (error) {
        if (!(error instanceof SyntaxError) || !error.message.includes('Unexpected end of JSON') || attempt === 4) throw error;
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
      }
    }
    const nodes = flatten(tree), roots = nodes.filter(node => node.type === 'root');
    requireFact(roots.length === 1 && roots[0].bundleName === config.bundle && roots[0].pagePath === 'pages/Index' &&
      roots[0].focused === 'true', 'Not the focused original production page');
    const local = path.join(directory, label + '-' + commandSequence + '.layout.json');
    fs.writeFileSync(local, JSON.stringify(tree, null, 2) + '\n', { flag: 'wx' });
    return { nodes, layout: record(local), sequence: mark() };
  };
  const waitFor = async (directory, label, predicate) => {
    for (let attempt = 0; attempt < 40; attempt++) {
      const sample = dump(directory, label);
      try { if (predicate(sample.nodes)) return sample; }
      catch (error) { if (!error.message.startsWith('Unbound Task12 observation: missing ')) throw error; }
      await sleep(150);
    }
    throw Error('Unbound native UI condition timed out: ' + label);
  };
  const rawOne = (nodes, id) => {
    const found = nodes.filter(node => node.visible === 'true' && node.id === id);
    requireFact(found.length === 1, 'Unbound original room control: ' + id);
    return found[0];
  };
  const clickNode = (directory, node) => {
    requireFact(F.boolean(node, 'enabled'), 'Native control disabled: ' + node.id);
    run(['shell', 'uitest', 'uiInput', 'click', ...midpoint(node).map(String)], directory);
  };
  const enter = (directory, node, text) => {
    requireFact(F.boolean(node, 'enabled'), 'Native input disabled');
    run(['shell', 'uitest', 'uiInput', 'inputText', ...midpoint(node).map(String), text], directory);
    run(['shell', 'uitest', 'uiInput', 'keyEvent', 'Back'], directory);
  };
  const configuredOutcome = (spec, effect, index) => {
    const values = spec.setup.externalResponses?.[effect] || ['success'];
    return values[Math.min(index, values.length - 1)];
  };
  const server = http.createServer((request, response) => {
    let body = '';
    request.on('data', data => { body += data; });
    request.on('end', () => {
      const entry = { caseRunId: activeCase?.id || '', requestSequence: mark(), method: request.method,
        url: request.url, authorization: request.headers.authorization, body };
      requests.push(entry);
      const roomPath = '/_matrix/client/v3/rooms/' + encodeURIComponent('!room:example.org');
      let status = 200, data;
      if (request.url === '/_matrix/client/v3/joined_rooms') data = { joined_rooms: ['!room:example.org'] };
      else if (request.url === roomPath + '/state') data = [
        { type: 'm.room.name', state_key: '', content: { name: 'Runtime room' } },
        { type: 'm.room.member', state_key: '@member:example.org', content: { membership: 'join' } }];
      else if (request.url === '/_matrix/client/versions') data = { versions: ['v1.13'] };
      else if (activeCase && [roomPath + '/report', roomPath + '/leave'].includes(request.url)) {
        entry.effect = request.url.endsWith('/report') ? 'report_room' : 'leave_room';
        const key = activeCase.id + ':' + entry.effect, count = effectCounts.get(key) || 0;
        effectCounts.set(key, count + 1);
        entry.scriptedOutcome = configuredOutcome(activeCase.spec, entry.effect, count);
        status = entry.scriptedOutcome === 'success' ? 200 : 500;
        data = status === 200 ? {} : { errcode: 'M_RUNTIME_TEST', error: entry.effect + ' failed' };
        if (request.method !== 'POST') { status = 405; data = { error: 'wrong HTTP method' }; }
      } else { status = 404; data = { error: 'unhandled path' }; }
      if (request.url !== '/_matrix/client/versions' && entry.authorization !== 'Bearer runtime-token') {
        status = 401; data = { error: 'invalid authentication' };
      }
      response.setHeader('content-type', 'application/json');
      response.statusCode = status;
      response.once('finish', () => { entry.responseSequence = mark(); entry.responseStatus = status; });
      response.end(JSON.stringify(data));
    });
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(config.port, '127.0.0.1', resolve); });
  let reverseInstalled = false, cleanupComplete = false;
  try {
    const transport = path.join(output, 'transport'); fs.mkdirSync(transport);
    run(['rport', `tcp:${config.port}`, `tcp:${config.port}`], transport); reverseInstalled = true;
    for (const spec of contract.cases) {
      const directory = path.join(output, spec.caseId); fs.mkdirSync(directory);
      const id = spec.caseId + '-' + crypto.randomBytes(8).toString('hex');
      activeCase = { id, spec };
      const checkpoints = [], operationTrace = [];
      try {
        run(['uninstall', config.bundle], directory, [0, 255]);
        requireFact(/failed|not exist|error/i.test(run(['shell', 'bm', 'dump', '-n', config.bundle], directory, [0, 255])),
          'Candidate not absent before fresh install');
        run(['install', '-r', config.hap], directory);
        run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', config.bundle, '-m', 'entry'], directory);
        let current = await waitFor(directory, 'entry', nodes => ['room_homeserver', 'room_access_token', 'room_id_input', 'open_room']
          .every(id => nodes.some(node => node.id === id && node.visible === 'true')));
        for (const [id, value] of [['room_homeserver', `http://127.0.0.1:${config.port}`],
          ['room_access_token', 'runtime-token'], ['room_id_input', '!room:example.org']]) enter(directory, rawOne(current.nodes, id), value);
        current = await waitFor(directory, 'ready', nodes => rawOne(nodes, 'open_room').enabled === 'true');
        clickNode(directory, rawOne(current.nodes, 'open_room'));
        current = await waitFor(directory, 'room-details', nodes => ['room_details_id', 'room_details_name', 'room_member_count', 'leave_room']
          .every(id => nodes.some(node => node.id === id && node.visible === 'true')));
        requireFact(rawOne(current.nodes, 'room_details_id').text === '!room:example.org' &&
          rawOne(current.nodes, 'room_details_name').text === 'Runtime room' &&
          rawOne(current.nodes, 'room_member_count').text === '1 members', 'Canonical common room not established');
        await sleep(200);
        const caseRequests = () => requests.filter(item => item.caseRunId === id);
        F.prefixRequests(caseRequests(), '!room:example.org');
        checkpoints.push({ name: 'common_start', state: { roomId: '!room:example.org', screen: 'room_details' },
          layout: current.layout, sequence: current.sequence });
        const capture = label => {
          current = dump(directory, label);
          const state = F.state(current, caseRequests());
          checkpoints.push({ name: label, state, layout: current.layout, sequence: current.sequence });
          return state;
        };
        const settled = nodes => !!(F.one(nodes, 'reportError', false) || F.one(nodes, 'partialError', false) ||
          F.one(nodes, 'success', false) || (!F.one(nodes, 'reason', false) &&
          nodes.some(node => node.id === 'room_details_id' && node.visible === 'true')));
        const action = async (value, label) => {
          operationTrace.push({ name: value.name, sequence: mark(), caseRunId: id });
          if (value.name === 'open_report_room') {
            clickNode(directory, F.one(current.nodes, 'entry'));
            current = await waitFor(directory, label, nodes => !!(F.one(nodes, 'reason', false) &&
              F.one(nodes, 'toggle', false) && F.one(nodes, 'submit', false)));
          } else if (value.name === 'update_reason') {
            enter(directory, F.one(current.nodes, 'reason'), value.reason);
            current = await waitFor(directory, label, nodes => F.one(nodes, 'reason').text === value.reason);
          } else if (value.name === 'toggle_leave_room') {
            const before = F.boolean(F.one(current.nodes, 'toggle'), 'checked');
            clickNode(directory, F.one(current.nodes, 'toggle'));
            current = await waitFor(directory, label, nodes => F.boolean(F.one(nodes, 'toggle'), 'checked') !== before);
          } else if (value.name === 'report' || value.name === 'retry') {
            const count = caseRequests().filter(item => item.effect).length;
            clickNode(directory, F.one(current.nodes, value.name === 'retry' ? 'retryLeave' : 'submit'));
            current = await waitFor(directory, label, nodes => {
              const effects = caseRequests().filter(item => item.effect);
              const loading = nodes.some(node => node.visible === 'true' &&
                (node.id === 'report_room_in_flight' || (node.id === 'submit_report_room' && node.text === 'Reporting...')));
              return !loading && effects.length > count && effects.every(item => Number.isInteger(item.responseSequence)) && settled(nodes);
            });
          } else if (value.name === 'clear_report_action') {
            clickNode(directory, F.one(current.nodes, 'clearError'));
            current = await waitFor(directory, label, nodes => !!F.one(nodes, 'submit', false) &&
              !F.one(nodes, 'reportError', false) && !F.one(nodes, 'partialError', false));
          } else requireFact(value.name === 'render_report_form', 'Unsupported canonical operation');
          capture(label + '-settled');
        };
        for (let index = 0; index < spec.setup.actions.length; index++) await action(spec.setup.actions[index], 'setup-' + index);
        const before = capture('before_event');
        const given = { ...before, roomId: '!room:example.org' };
        if (spec.given.reportResult) given.reportResult = configuredOutcome(spec, 'report_room', 0);
        if (spec.given.leaveResult) given.leaveResult = configuredOutcome(spec, 'leave_room', 0);
        requireFact(F.equal(spec.setup.requiredBeforeEvent, given), 'Canonical given not reached by real operation prefix');
        await action(spec.event, 'event');
        const after = capture('after_event');
        requireFact(caseRequests().every(item => item.url === '/_matrix/client/versions' || item.authorization === 'Bearer runtime-token'),
          'Source authentication binding changed');
        const result = F.assess(spec, before, after, caseRequests(), current);
        rows.push({ caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, ...result,
          given: spec.given, event: spec.event, transitionExecuted: true, checkpoints, caseRunId: id,
          operationTrace, externalEffects: caseRequests().filter(item => item.effect), nativeNonce: nonce });
      } catch (error) {
        rows.push({ caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, status: 'not_scored',
          reason: String(error.stack || error), transitionExecuted: false, observed: null,
          invariantChecks: [], checkpoints, operationTrace, caseRunId: id, nativeNonce: nonce });
      } finally {
        run(['uninstall', config.bundle], directory, [0, 255]);
        fs.writeFileSync(path.join(directory, 'case.json'), JSON.stringify(rows.at(-1), null, 2) + '\n', { flag: 'wx' });
      }
    }
  } finally {
    activeCase = null;
    fs.writeFileSync(path.join(output, 'server-requests.audit.json'), JSON.stringify(requests, null, 2) + '\n', { flag: 'wx' });
    const cleanup = path.join(output, 'cleanup'); fs.mkdirSync(cleanup);
    try {
      run(['uninstall', config.bundle], cleanup, [0, 255]);
      if (reverseInstalled) run(['fport', 'rm', `tcp:${config.port}`, `tcp:${config.port}`], cleanup, [0, 255]);
      for (let index = 0; index < remoteFiles.length; index += 30) run(['shell', 'rm', '-f', ...remoteFiles.slice(index, index + 30)], cleanup, [0, 255]);
      cleanupComplete = true;
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
  const report = { taskId: contract.taskId, platform: 'arkts', runtime: 'openharmony_api23_device_uitest',
    observationMode: 'runtime_state_transition', nativeNonce: nonce, source: config.source,
    compile: { build: record(config.buildReport), hap: record(config.hap) },
    semantic: { total: rows.length, passed: rows.filter(row => row.status === 'pass').length,
      failed: rows.filter(row => row.status === 'fail').length, notScored: rows.filter(row => row.status === 'not_scored').length, cases: rows },
    diagnostics: { commands, serverRequests: requests, cleanup: { ownedAppUninstalled: cleanupComplete,
      reverseRemoved: cleanupComplete, remoteLayoutsRemoved: remoteFiles.length } },
    provenance: { config: record(configPath), contract: record(config.contract), runner: record(__filename),
      facts: record(path.join(__dirname, 'Task12ReplayFacts.cjs')) } };
  fs.writeFileSync(path.join(output, 'runtime.native.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ semantic: { passed: report.semantic.passed, failed: report.semantic.failed,
    notScored: report.semantic.notScored }, report: path.join(output, 'runtime.native.json') }));
}

if (require.main === module) main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
module.exports = { flatten, midpoint };
