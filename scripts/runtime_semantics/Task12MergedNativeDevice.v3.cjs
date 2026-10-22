'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const { spawnSync } = require('node:child_process');
const { performance } = require('node:perf_hooks');
const F = require('./Task12MergedNativeFacts.v3.cjs');
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

async function execute(configPath) {
  configPath = path.resolve(configPath);
  const config = JSON.parse(fs.readFileSync(configPath));
  requireFact(Number.isFinite(config.remainingSeconds) && config.remainingSeconds > 0 && config.remainingSeconds <= 3600,
    'Invalid remaining local budget');
  const output = config.output;
  requireFact(!fs.existsSync(output), 'Refusing existing native execution evidence');
  fs.mkdirSync(output, { recursive: true });
  const deadline = performance.now() + config.remainingSeconds * 1000;
  const cleanupReserveMs = Math.min(60000, config.remainingSeconds * 100);
  const workRemaining = () => { requireFact(deadline - performance.now() > cleanupReserveMs, 'Work budget exhausted; cleanup reserved'); };
  const hashRecord = file => { workRemaining(); return record(file); };
  const remaining = () => { const value = Math.floor(deadline - performance.now()); requireFact(value > 0, 'Single replay deadline exhausted'); return value; };
  const contract = JSON.parse(fs.readFileSync(config.contract));
  const build = JSON.parse(fs.readFileSync(config.buildReport));
  requireFact(build.source === config.source && build.productionUnchanged && build.temporaryProjectRemoved &&
    build.hap.sha256 === record(config.hap).sha256, 'Source-specific compiled production HAP differs');
  const nonce = crypto.randomBytes(16).toString('hex');
  let sequence = 0, commandSequence = 0, activeCase;
  const commands = [], requests = [], rows = [], remoteFiles = [], layouts = [], effectCounts = new Map();
  const mark = () => ++sequence;
  const run = (args, directory, allowed = [0]) => {
    const startedMs = performance.now();
    const result = spawnSync(config.hdc, ['-t', config.serial, ...args], { encoding: 'utf8',
      timeout: Math.min(30000, remaining()), maxBuffer: 16 * 1024 * 1024 });
    const log = path.join(directory, String(++commandSequence).padStart(6, '0') + '.log');
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''), { flag: 'wx' });
    commands.push({ args, exitCode: result.status, log: record(log), sequence: mark(), caseRunId: activeCase?.id || '',
      elapsedMs: performance.now() - startedMs });
    requireFact(!result.error && allowed.includes(result.status), 'HDC transport failed: ' + log);
    return fs.readFileSync(log, 'utf8');
  };
  const dump = (directory, label) => {
    const remote = '/data/local/tmp/task12-replay-' + nonce + '-' + commandSequence + '.json';
    remoteFiles.push(remote);
    workRemaining();
    run(['shell', 'uitest', 'dumpLayout', '-p', remote, '-b', config.bundle], directory);
    const dumpCommand = commands.at(-1).sequence;
    let tree, catCommand;
    for (let attempt = 0; attempt < 5; attempt++) {
      try { tree = JSON.parse(run(['shell', 'cat', remote], directory)); catCommand = commands.at(-1).sequence; break; }
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
    const observedOwner = F.owner(nodes, config.bundle);
    if (activeCase.owner) requireFact(F.exact(activeCase.owner, observedOwner), 'Original native page owner changed');
    else activeCase.owner = observedOwner;
    const sample = { nodes, layout: hashRecord(local), sequence: mark() };
    layouts.push({ layout: sample.layout, sequence: sample.sequence, remote, dumpCommand, catCommand,
      caseRunId: activeCase.id, owner: observedOwner });
    return sample;
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
    // The canonical failing leave is already observed. The independent memory
    // probe retries against a recovered external server, as the Android probe.
    if (activeCase?.postAssertionRetention && spec.key === 'leave_failure_is_partial' &&
        effect === 'leave_room' && index === 1) return 'success';
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
  let reverseInstalled = false, cleanupComplete = false, executionError;
  const cleanupErrors = [];
  try {
    const transport = path.join(output, 'transport'); fs.mkdirSync(transport);
    run(['rport', `tcp:${config.port}`, `tcp:${config.port}`], transport); reverseInstalled = true;
    for (const spec of contract.cases) {
      workRemaining();
      const directory = path.join(output, spec.caseId); fs.mkdirSync(directory);
      const id = spec.caseId + '-' + crypto.randomBytes(8).toString('hex');
      activeCase = { id, spec };
      const checkpoints = [], operationTrace = [];
      let blockedAction, common;
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
        const caseRequests = () => requests.filter(item => item.caseRunId === id);
        const checkpoint = (name, sample) => checkpoints.push({ name, layout: sample.layout, sequence: sample.sequence });
        checkpoint('common_start', current);
        const original = F.closedDetails(current.nodes);
        await sleep(250); workRemaining();
        current = dump(directory, 'details-stable');
        requireFact(F.closedDetails(current.nodes).entryAvailable === original.entryAvailable, 'Unstable entry discovery');
        checkpoint('entry_stable', current);
        clickNode(directory, rawOne(current.nodes, 'leave_room'));
        current = await waitFor(directory, 'leave-confirmation', nodes => nodes.some(node =>
          node.id === 'leave_room_confirmation' && node.visible === 'true') && nodes.some(node =>
          node.id === 'cancel_leave_room' && node.enabled === 'true'));
        requireFact(F.closedDetails(current.nodes, true).entryAvailable === original.entryAvailable, 'Unbound leave positive control');
        checkpoint('positive_leave_control', current);
        clickNode(directory, rawOne(current.nodes, 'cancel_leave_room'));
        current = await waitFor(directory, 'details-restored', nodes => !nodes.some(node =>
          node.id === 'leave_room_confirmation' && node.visible === 'true') && nodes.some(node =>
          node.id === 'leave_room' && node.enabled === 'true'));
        requireFact(F.closedDetails(current.nodes).entryAvailable === original.entryAvailable, 'Unbound restored entry');
        checkpoint('common_start_restored', current);
        F.prefixRequests(caseRequests(), '!room:example.org');
        common = { session: id, start: checkpoints[0].sequence, end: mark(),
          owner: activeCase.owner, entryAvailable: original.entryAvailable };
        if (!original.entryAvailable) {
          rows.push(F.absence(spec, common, checkpoints, id, nonce));
          continue;
        }
        const capture = label => {
          current = dump(directory, label);
          F.boundUi(current.nodes);
          const state = F.state(current, caseRequests());
          checkpoints.push({ name: label, state, layout: current.layout, sequence: current.sequence });
          return state;
        };
        const settled = nodes => !!(F.one(nodes, 'reportError', false) || F.one(nodes, 'partialError', false) ||
          F.one(nodes, 'success', false) || (!F.one(nodes, 'reason', false) &&
          nodes.some(node => node.id === 'room_details_id' && node.visible === 'true')));
        const performAction = async (value, label) => {
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
            const target = F.one(current.nodes, value.name === 'retry' ? 'retryLeave' : 'submit');
            if (value.name === 'report' && target.enabled === 'false') {
              F.closedDisabledForm(current.nodes);
              const first = capture('blocked_before');
              clickNode(directory, F.one(current.nodes, 'toggle'));
              current = await waitFor(directory, 'blocked-toggle', nodes => F.boolean(F.one(nodes, 'toggle'), 'checked') !== first.leaveRoom);
              capture('blocked_positive_toggle');
              clickNode(directory, F.one(current.nodes, 'toggle'));
              current = await waitFor(directory, 'blocked-restored', nodes => F.boolean(F.one(nodes, 'toggle'), 'checked') === first.leaveRoom);
              capture('blocked_positive_restored');
              blockedAction = { requestedAction: value, failedAt: label === 'event' ? 'event' : 'setup.actions[' + label.split('-')[1] + ']',
                forceClicked: false, originalGivenReached: label === 'event' };
              throw Error('ACTUAL_DISABLED_REPORT_ACTION');
            }
            const count = caseRequests().filter(item => item.effect).length;
            clickNode(directory, target);
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
        const action = async (value, label) => {
          workRemaining(); F.boundUi(current.nodes);
          const operation = { name: value.name, action: value, sequence: mark(), caseRunId: id, before: current.layout };
          operationTrace.push(operation);
          try { await performAction(value, label); }
          finally { operation.end = mark(); }
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
        const afterSample = current;
        let retention;
        if (spec.key === 'leave_failure_is_partial') {
          activeCase.postAssertionRetention = true;
          await action({ name: 'retry' }, 'post_assertion_retry');
          const observed = capture('post_assertion_retention');
          retention = { sample: { layout: current.layout, sequence: current.sequence }, observed,
            requests: caseRequests().filter(item => item.effect && item.requestSequence > afterSample.sequence && item.requestSequence < current.sequence) };
        }
        const result = F.assess(spec, before, after,
          caseRequests().filter(item => item.requestSequence < afterSample.sequence), afterSample, retention);
        rows.push({ caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, ...result,
          given: spec.given, event: spec.event, transitionExecuted: true, checkpoints, caseRunId: id,
          common, operationTrace, externalEffects: caseRequests().filter(item => item.effect && item.requestSequence < afterSample.sequence),
          ...(retention ? { postAssertionRetention: retention } : {}), nativeNonce: nonce });
      } catch (error) {
        if (error.message === 'ACTUAL_DISABLED_REPORT_ACTION' && blockedAction) {
          const row = { caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, status: 'fail',
            transitionExecuted: false, observed: null, invariantChecks: [], given: spec.given, event: spec.event,
            unevaluatedInvariants: spec.invariants, unobservedExpectedFields: Object.keys(spec.expected),
            common, checkpoints, operationTrace, caseRunId: id, nativeNonce: nonce,
            entryFailureEvidence: { policyId: F.DISABLED_POLICY, canonicalGivenEstablished: true,
              commonStartEstablished: true, positiveControlCompleted: true,
              givenScope: 'audited common-start operation prefix; original final-only given may remain unreached', ...blockedAction } };
          try {
            F.verifyBlocked(spec, row, requests.filter(item => item.caseRunId === id), artifact => JSON.parse(fs.readFileSync(artifact.path)), config.bundle);
            rows.push(row);
          } catch (bindingError) {
            rows.push({ caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, status: 'not_scored',
              reason: String(bindingError.stack || bindingError), transitionExecuted: false, observed: null,
              invariantChecks: [], checkpoints, operationTrace, caseRunId: id, nativeNonce: nonce });
          }
        } else rows.push({ caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, status: 'not_scored',
          reason: String(error.stack || error), transitionExecuted: false, observed: null,
          invariantChecks: [], checkpoints, operationTrace, caseRunId: id, nativeNonce: nonce });
      } finally {
        try {
          run(['uninstall', config.bundle], directory, [0, 255]);
          requireFact(/failed|not exist|error/i.test(run(['shell', 'bm', 'dump', '-n', config.bundle], directory, [0, 255])),
            'Owned case app uninstall not verified');
        } catch (error) {
          rows[rows.length - 1] = { caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest,
            status: 'not_scored', reason: String(error.stack || error), transitionExecuted: false, observed: null,
            invariantChecks: [], checkpoints, operationTrace, caseRunId: id, nativeNonce: nonce };
        }
        fs.writeFileSync(path.join(directory, 'case.json'), JSON.stringify(rows.at(-1), null, 2) + '\n', { flag: 'wx' });
      }
    }
  } catch (error) {
    executionError = String(error.stack || error);
  } finally {
    activeCase = null;
    fs.writeFileSync(path.join(output, 'server-requests.audit.json'), JSON.stringify(requests, null, 2) + '\n', { flag: 'wx' });
    const cleanup = path.join(output, 'cleanup'); fs.mkdirSync(cleanup);
    const attempt = operation => { try { operation(); } catch (error) { cleanupErrors.push(String(error.stack || error)); } };
    attempt(() => {
      run(['uninstall', config.bundle], cleanup, [0, 255]);
      requireFact(/failed|not exist|error/i.test(run(['shell', 'bm', 'dump', '-n', config.bundle], cleanup, [0, 255])),
        'Final owned app uninstall not verified');
    });
    if (reverseInstalled) attempt(() => run(['fport', 'rm', `tcp:${config.port}`, `tcp:${config.port}`], cleanup));
    for (let index = 0; index < remoteFiles.length; index += 30)
      attempt(() => run(['shell', 'rm', '-f', ...remoteFiles.slice(index, index + 30)], cleanup));
    await new Promise(resolve => server.close(resolve));
    cleanupComplete = cleanupErrors.length === 0;
  }
  for (const spec of contract.cases.slice(rows.length)) rows.push({ caseId: spec.caseId, key: spec.key,
    traceDigest: spec.traceDigest, status: 'not_scored', reason: executionError || 'Incomplete episode',
    observed: null, invariantChecks: [], transitionExecuted: false,
    caseRunId: spec.caseId + '-' + crypto.randomBytes(8).toString('hex'), nativeNonce: nonce });
  const report = { nativeProtocol: F.PROTOCOL, taskId: contract.taskId, platform: 'arkts', runtime: 'openharmony_api23_device_uitest',
    observationMode: 'runtime_state_transition', nativeNonce: nonce, source: config.source, bundle: config.bundle,
    compile: { build: record(config.buildReport), hap: record(config.hap) }, executionConfig: { port: config.port },
    semantic: { total: rows.length, passed: rows.filter(row => row.status === 'pass').length,
      failed: rows.filter(row => row.status === 'fail').length, notScored: rows.filter(row => row.status === 'not_scored').length, cases: rows },
    diagnostics: { commands, layouts, remoteFiles, serverRequests: requests, executionError, cleanupErrors,
      performance: { scope: 'debug_only_not_benchmark_metrics', clock: 'node_process.performance.now', pid: process.pid,
        commandCount: commands.length, commandElapsedMs: commands.reduce((total, item) => total + item.elapsedMs, 0) },
      cleanup: { ownedAppUninstalled: cleanupComplete,
      reverseRemoved: cleanupComplete && reverseInstalled, remoteFilesRemoved: cleanupComplete, remoteLayoutsRemoved: remoteFiles.length } },
    provenance: { config: record(configPath), contract: record(config.contract), runner: record(__filename),
      facts: record(path.join(__dirname, 'Task12MergedNativeFacts.v3.cjs')) } };
  fs.writeFileSync(path.join(output, 'runtime.native.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  return { semantic: { passed: report.semantic.passed, failed: report.semantic.failed,
    notScored: report.semantic.notScored }, report: path.join(output, 'runtime.native.json') };
}

if (require.main === module) execute(process.argv[2]).then(result => console.log(JSON.stringify(result)))
  .catch(error => { console.error(error.stack || error); process.exitCode = 1; });
module.exports = { execute, flatten, midpoint };
