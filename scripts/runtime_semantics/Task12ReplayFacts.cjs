'use strict';

const assertFact = (value, reason) => { if (!value) throw Error('Unbound Task12 observation: ' + reason); };
const ids = {
  entry: ['report_room_entry', 'open_report_room'], reason: ['report_room_reason'],
  toggle: ['report_room_leave_toggle', 'report_room_leave_checkbox'],
  submit: ['submit_report_room', 'report_room_submit'],
  reportError: ['report_room_error', 'report_room_report_failure'], partialError: ['report_room_partial_failure'],
  retryLeave: ['retry_leave_room', 'report_room_retry_leave'],
  clearError: ['dismiss_report_error', 'report_room_clear_failure', 'report_room_clear_partial'],
  success: ['report_room_success']
};

function matches(nodes, concept) {
  assertFact(ids[concept], 'unknown control concept');
  return nodes.filter(node => node.visible === 'true' && (ids[concept].includes(node.id) ||
    (concept === 'entry' && node.type === 'Button' && node.text === 'Report room')));
}

function one(nodes, concept, required = true) {
  const found = matches(nodes, concept);
  assertFact(found.length <= 1, 'ambiguous ' + concept);
  assertFact(!required || found.length === 1, 'missing ' + concept);
  return found[0];
}

function boolean(node, key) {
  assertFact(node && ['true', 'false'].includes(node[key]), 'missing native boolean: ' + key);
  return node[key] === 'true';
}

function prefixRequests(requests, roomId) {
  const paths = ['/_matrix/client/v3/joined_rooms', '/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/state'];
  assertFact(requests.length >= 2 && requests.length <= 3 && requests.slice(0, 2).every((item, i) => item.url === paths[i]) &&
    (requests.length === 2 || requests[2].url === '/_matrix/client/versions') &&
    requests.every(item => item.method === 'GET' && item.authorization === 'Bearer runtime-token' && !item.body),
    'common-start method/path/authentication/effect ledger differs');
  return { mandatoryRoomRequests: 2, capabilityRequestObserved: requests.length === 3 };
}

function closedBase(nodes) {
  const actual = nodes.filter(node => node.type), roots = actual.filter(node => node.type === 'root');
  assertFact(actual.length === 9 && roots.length === 1, 'incomplete/additional base UI inventory');
  const known = { room_details_title: 'Room details', room_details_id: '!room:example.org',
    room_details_name: 'Runtime room', room_member_count: '1 members', leave_room: 'Leave room' };
  const counts = {};
  for (const node of actual) {
    counts[node.type] = (counts[node.type] || 0) + 1;
    assertFact(node.visible === 'true' && node.longClickable === 'false' && node.scrollable === 'false' &&
      node.checkable === 'false', 'hidden/overflow/extra base interaction');
    if (node.id) assertFact(known[node.id] === node.text && node.enabled === 'true' &&
      node.type === (node.id === 'leave_room' ? 'Button' : 'Text') &&
      node.clickable === (node.id === 'leave_room' ? 'true' : 'false'), 'unbound renamed base control');
    else assertFact(['root', 'Column', 'Scroll'].includes(node.type) && node.clickable === 'false' && !node.text,
      'unbound base container/action');
  }
  assertFact(Object.keys(known).every(id => actual.filter(node => node.id === id).length === 1) &&
    counts.root === 1 && counts.Column === 2 && counts.Scroll === 1 && counts.Text === 4 && counts.Button === 1,
    'base UI closure incomplete');
  return { complete: true, nodes: actual.length, unboundControls: 0 };
}

function state(sample, requests) {
  const nodes = sample.nodes, effects = requests.filter(item => item.effect);
  const reason = one(nodes, 'reason', false), toggle = one(nodes, 'toggle', false), submit = one(nodes, 'submit', false);
  const error = one(nodes, 'reportError', false), partial = one(nodes, 'partialError', false);
  const success = one(nodes, 'success', false);
  const details = nodes.some(node => node.id === 'room_details_id' && node.visible === 'true');
  const out = { reportCalls: effects.filter(item => item.effect === 'report_room').length,
    leaveCalls: effects.filter(item => item.effect === 'leave_room').length, effects: effects.map(item => item.effect) };
  if (reason) {
    assertFact(typeof reason.text === 'string', 'native reason text missing');
    out.reason = reason.text;
  }
  if (toggle) out.leaveRoom = boolean(toggle, 'checked');
  if (submit) out.canReport = out.submitEnabled = boolean(submit, 'enabled');
  if (error) out.reportAction = 'report_failed';
  else if (partial) out.reportAction = 'leave_failed';
  else if (success || (!reason && details && effects.some(item => item.effect === 'report_room'))) out.reportAction = 'success';
  else if (reason && submit) out.reportAction = 'uninitialized';
  if (partial) out.retryEnabled = boolean(one(nodes, 'retryLeave'), 'enabled');
  const report = effects.find(item => item.effect === 'report_room');
  if (report) {
    const payload = JSON.parse(report.body);
    assertFact(typeof payload.reason === 'string', 'report payload reason missing');
    out.reportReason = payload.reason;
  }
  out.retryShouldReport = out.reportCalls > 1;
  return out;
}

function equal(expected, observed) {
  if (Array.isArray(expected)) return Array.isArray(observed) && expected.length === observed.length && expected.every((v, i) => equal(v, observed[i]));
  if (expected !== null && typeof expected === 'object') return observed !== null && typeof observed === 'object' &&
    Object.entries(expected).every(([key, value]) => Object.hasOwn(observed, key) && equal(value, observed[key]));
  return typeof expected === typeof observed && expected === observed;
}

function invariants(spec, before, after, requests, sample) {
  const effects = requests.filter(item => item.effect);
  const report = effects.find(item => item.effect === 'report_room');
  const leave = effects.find(item => item.effect === 'leave_room');
  const completed = item => !!(item && Number.isInteger(item.responseSequence) && Number.isInteger(item.requestSequence) &&
    item.responseSequence > item.requestSequence && item.responseSequence < sample.sequence);
  const tests = {
    initial_form: () => effects.length === 0,
    reason_enables_report: () => Object.hasOwn(before, 'leaveRoom') && after.leaveRoom === before.leaveRoom,
    toggle_leave: () => typeof before.reason === 'string' && after.reason === before.reason,
    report_only_success: () => completed(report) && report.responseStatus === 200 && after.reportAction === 'success',
    report_then_leave: () => completed(report) && completed(leave) && report.responseStatus === 200 &&
      leave.requestSequence > report.responseSequence,
    blank_reason_disabled: () => before.leaveRoom === true && after.leaveRoom === true,
    report_failure_stops_leave: () => completed(report) && report.responseStatus === 500 && !leave,
    leave_failure_is_partial: () => completed(report) && completed(leave) && report.responseStatus === 200 &&
      leave.responseStatus === 500 && before.reason === after.reason && before.leaveRoom === after.leaveRoom,
    retry_leave_only: () => before.reportCalls === 1 && after.reportCalls === before.reportCalls &&
      after.leaveCalls === before.leaveCalls + 1,
    clear_failure_keeps_form: () => before.reportCalls === after.reportCalls && before.leaveCalls === after.leaveCalls
  };
  assertFact(tests[spec.key] && spec.invariants.length === 1, 'unsupported complete invariant mapping');
  const passed = tests[spec.key]();
  assertFact(typeof passed === 'boolean', 'invariant has no executable observation');
  return [{ text: spec.invariants[0], passed,
    evidence: { before, after, requestSequences: effects.map(item => ({ request: item.requestSequence,
      response: item.responseSequence, status: item.responseStatus })), nativeSampleSequence: sample.sequence } }];
}

function assess(spec, before, after, requests, sample) {
  for (const key of Object.keys(spec.expected)) assertFact(Object.hasOwn(after, key), 'expected field was not observed: ' + key);
  const checks = invariants(spec, before, after, requests, sample);
  const pass = equal(spec.expected, after) && checks.every(check => check.passed);
  return { status: pass ? 'pass' : 'fail', observed: after, invariantChecks: checks,
    mismatchedFields: Object.keys(spec.expected).filter(key => !equal(spec.expected[key], after[key])) };
}

function verifyNative(raw, contract, readLayout, bundle) {
  assertFact(raw.semantic.cases.length === contract.cases.length && /^[0-9a-f]{32}$/.test(raw.nativeNonce),
    'incomplete native cases/nonce');
  const used = new Set();
  const facts = [];
  for (const [index, spec] of contract.cases.entries()) {
    const row = raw.semantic.cases[index];
    assertFact(row.caseId === spec.caseId && row.traceDigest === spec.traceDigest && row.nativeNonce === raw.nativeNonce &&
      !used.has(row.caseRunId), 'native identity/source session mismatch');
    used.add(row.caseRunId);
    assertFact(['pass', 'fail'].includes(row.status) && row.transitionExecuted === true, 'native case remains unscored');
    const requests = raw.diagnostics.serverRequests.filter(item => item.caseRunId === row.caseRunId);
    const sample = name => {
      const points = row.checkpoints.filter(point => point.name === name);
      assertFact(points.length === 1, 'before/after native checkpoint missing/duplicated');
      const point = points[0], nodes = [];
      const visit = tree => { if (tree.attributes) nodes.push(tree.attributes); for (const child of tree.children || []) visit(child); };
      visit(readLayout(point.layout));
      const roots = nodes.filter(node => node.type === 'root');
      assertFact(roots.length === 1 && roots[0].bundleName === bundle && roots[0].pagePath === 'pages/Index' &&
        roots[0].focused === 'true', 'checkpoint is not the original focused production window');
      const observed = state({ nodes }, requests.filter(item => item.requestSequence < point.sequence));
      assertFact(equal(point.state, observed) && equal(observed, point.state), 'checkpoint state differs from actual native layout/effects');
      return { ...point, nodes, observed };
    };
    const before = sample('before_event'), after = sample('after_event');
    const given = { ...before.observed, roomId: '!room:example.org' };
    for (const [key, effect] of [['reportResult', 'report_room'], ['leaveResult', 'leave_room']]) {
      if (Object.hasOwn(spec.given, key)) given[key] = spec.setup.externalResponses[effect][0];
    }
    assertFact(equal(spec.setup.requiredBeforeEvent, given), 'runtime given does not match canonical operation prefix');
    const result = assess(spec, before.observed, after.observed, requests, after);
    assertFact(result.status === row.status && equal(result.observed, row.observed) && equal(row.observed, result.observed) &&
      JSON.stringify(result.invariantChecks) === JSON.stringify(row.invariantChecks), 'native verdict/invariants cannot be recomputed');
    facts.push({ caseId: row.caseId, status: row.status, actualNativeFields: Object.keys(result.observed),
      completeInvariants: result.invariantChecks.length });
  }
  return { validated: true, cases: facts, nativeUiAndHttpRecomputed: true };
}

module.exports = { one, matches, boolean, prefixRequests, closedBase, state, equal, invariants, assess, verifyNative };
