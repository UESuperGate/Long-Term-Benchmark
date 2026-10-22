'use strict';

// Prospective hint-profile-v4 successor; live producer and public route remain unchanged.
// Versioned executable observations; no retained report is loaded by this module.

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

const DISABLED_POLICY = 'arkts.task12.merged-disabled-action.v4';

function closedDisabledForm(nodes) {
  const actual = nodes.filter(node => node.type);
  const allowed = new Set(['room_details_title', 'room_details_id', 'room_details_name', 'room_member_count',
    'open_report_room', 'leave_room', 'report_room_title', 'report_room_id', 'report_room_reason',
    'report_room_leave_checkbox', 'report_room_close', 'report_room_submit']);
  assertFact(actual.length === 24, 'disabled-action complete form inventory differs');
  const counts = {};
  for (const node of actual) {
    counts[node.type] = (counts[node.type] || 0) + 1;
    assertFact(node.visible === 'true' && node.scrollable === 'false', 'unbound hidden/overflow form control');
    if (node.id) assertFact(allowed.has(node.id) && actual.filter(item => item.id === node.id).length === 1,
      'additional/renamed unbound form control');
    else if (node.type === 'Text') assertFact(['Reason', 'Also leave this room after reporting'].includes(node.text) &&
      node.clickable === 'false' && node.longClickable === 'false', 'unbound text action');
    else assertFact(['root', 'Stack', 'Column', 'Scroll', 'Row'].includes(node.type) && !node.text &&
      node.clickable === 'false' && node.longClickable === 'false', 'unbound container action');
    if (node.type === 'Button') assertFact(['open_report_room', 'leave_room', 'report_room_close', 'report_room_submit'].includes(node.id),
      'unbound alternate command');
  }
  assertFact(counts.root === 1 && counts.Stack === 1 && counts.Column === 4 && counts.Scroll === 2 &&
    counts.Row === 2 && counts.Text === 8 && counts.Button === 4 && counts.TextArea === 1 && counts.Checkbox === 1,
    'complete form/native type inventory differs');
  const submit = one(actual, 'submit');
  assertFact(submit.id === 'report_room_submit' && submit.text === 'Report' && submit.enabled === 'false' &&
    submit.clickable === 'false' && one(actual, 'reason').enabled === 'true' && one(actual, 'toggle').enabled === 'true',
    'actual report command is not stably disabled on an otherwise interactive form');
  return { complete: true, nodeCount: actual.length, unboundControls: 0 };
}

function verifyBlocked(spec, row, requests, readLayout, bundle) {
  const evidence = row.entryFailureEvidence;
  assertFact(evidence?.policyId === DISABLED_POLICY && row.status === 'fail' && row.transitionExecuted === false &&
    row.observed === null && row.invariantChecks.length === 0 &&
    JSON.stringify(row.unevaluatedInvariants) === JSON.stringify(spec.invariants) &&
    JSON.stringify(row.unobservedExpectedFields) === JSON.stringify(Object.keys(spec.expected)),
    'blocked action projected downstream state/invariants');
  const expectedIndex = spec.setup.actions.findIndex(action => action.name === 'report');
  const expectedBoundary = expectedIndex >= 0 ? 'setup.actions[' + expectedIndex + ']' : 'event';
  assertFact((expectedIndex >= 0 || spec.event.name === 'report') && evidence.failedAt === expectedBoundary &&
    evidence.requestedAction.name === 'report' && evidence.forceClicked === false,
    'blocked canonical operation boundary differs');
  const names = ['blocked_before', 'blocked_positive_toggle', 'blocked_positive_restored'];
  const facts = names.map(name => {
    const points = row.checkpoints.filter(point => point.name === name);
    assertFact(points.length === 1, 'disabled action positive/native samples incomplete');
    const point = points[0], nodes = [];
    const visit = tree => { if (tree.attributes) nodes.push(tree.attributes); for (const child of tree.children || []) visit(child); };
    visit(readLayout(point.layout));
    closedDisabledForm(nodes);
    const roots = nodes.filter(node => node.type === 'root');
    assertFact(roots[0].bundleName === bundle && roots[0].pagePath === 'pages/Index' && roots[0].focused === 'true',
      'disabled prefix not in original focused window');
    const out = state({ nodes, sequence: point.sequence }, requests.filter(item => item.requestSequence < point.sequence));
    assertFact(equal(out, point.state) && equal(point.state, out), 'blocked prefix state differs from actual layout/effects');
    assertFact(out.reportCalls === 0 && out.leaveCalls === 0 && out.reportAction === 'uninitialized' &&
      out.submitEnabled === false && typeof out.reason === 'string' && out.reason.trim().length > 0,
      'disabled prefix lacks nonblank ready-form input or emitted an effect');
    return { state: out, sequence: point.sequence };
  });
  assertFact(facts[0].sequence < facts[1].sequence && facts[1].sequence < facts[2].sequence &&
    facts[0].state.leaveRoom !== facts[1].state.leaveRoom && equal(facts[0].state, facts[2].state),
    'actual same-form toggle/restore positive control missing');
  const operations = row.operationTrace.map(item => item.name);
  const expectedPrefix = spec.setup.actions.slice(0, expectedIndex >= 0 ? expectedIndex + 1 : spec.setup.actions.length).map(action => action.name);
  if (expectedIndex < 0) expectedPrefix.push(spec.event.name);
  assertFact(JSON.stringify(operations) === JSON.stringify(expectedPrefix), 'actual blocked action prefix differs');
  const priorActions = spec.setup.actions.slice(0, expectedIndex >= 0 ? expectedIndex : spec.setup.actions.length);
  const reasonActions = priorActions.filter(action => action.name === 'update_reason');
  assertFact(reasonActions.length > 0 && facts[0].state.reason === reasonActions.at(-1).reason &&
    facts[0].state.leaveRoom === (priorActions.filter(action => action.name === 'toggle_leave_room').length % 2 === 1),
    'actual reachable prefix does not match required input operations');
  return { validated: true, actualDisabledAction: true, sameFormPositiveControl: true,
    originalGivenReached: evidence.originalGivenReached, unobservedOriginalAssertionsRetained: true };
}

function closedLeftRoom(sample, requests) {
  const actual = sample.nodes.filter(node => node.type);
  const known = { room_details_title: ['Text', 'Room details'], room_details_id: ['Text', '!room:example.org'],
    room_details_name: ['Text', 'Runtime room'], room_member_count: ['Text', '1 members'],
    leave_room_success: ['Text', 'Left room'], leave_room: ['Button', 'Leave room'] };
  const counts = {};
  assertFact(actual.length === 10, 'left-room complete native inventory differs');
  for (const node of actual) {
    counts[node.type] = (counts[node.type] || 0) + 1;
    assertFact(node.visible === 'true' && node.longClickable === 'false' && node.scrollable === 'false' &&
      node.clickable === 'false' && node.checkable === 'false', 'unbound terminal room interaction');
    if (node.id) assertFact(known[node.id] && node.type === known[node.id][0] && node.text === known[node.id][1] &&
      node.enabled === (node.id === 'leave_room' ? 'false' : 'true'), 'unbound terminal room control');
    else assertFact(['root', 'Column', 'Scroll'].includes(node.type) && !node.text && node.enabled === 'true',
      'unbound terminal room container');
  }
  assertFact(Object.keys(known).every(id => actual.filter(node => node.id === id).length === 1) &&
    counts.root === 1 && counts.Column === 2 && counts.Scroll === 1 && counts.Text === 5 && counts.Button === 1,
    'left-room native closure incomplete');
  const effects = requests.filter(item => item.effect);
  const report = effects.filter(item => item.effect === 'report_room').at(-1);
  const leave = effects.filter(item => item.effect === 'leave_room').at(-1);
  for (const item of [report, leave]) assertFact(item && item.responseStatus === 200 &&
    Number.isSafeInteger(item.requestSequence) && Number.isSafeInteger(item.responseSequence) &&
    item.responseSequence > item.requestSequence && Number.isSafeInteger(sample.sequence) &&
    item.responseSequence < sample.sequence, 'terminal native UI lacks completed real SDK success');
  // Canonical invariants still judge report/leave ordering and duplicate effects.
  return { complete: true, reportResponse: report.responseSequence, leaveRequest: leave.requestSequence,
    leaveResponse: leave.responseSequence, nativeSequence: sample.sequence };
}

function state(sample, requests) {
  const nodes = sample.nodes, effects = requests.filter(item => item.effect);
  if (nodes.some(node => node.id === 'leave_room_success')) closedLeftRoom(sample, requests);
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

function invariants(spec, before, after, requests, sample, retentionProbe) {
  const names = {
    initial_form: 'no report or leave effect is emitted',
    reason_enables_report: 'editing the reason does not toggle leave',
    toggle_leave: 'the reason remains unchanged',
    report_only_success: 'reporting completes before the success result',
    report_then_leave: 'leave is attempted only after reporting succeeds',
    blank_reason_disabled: 'leave preference remains selected',
    report_failure_stops_leave: 'form values survive the failure',
    leave_failure_is_partial: 'the successful report is remembered',
    retry_leave_only: 'the report is never submitted twice',
    clear_failure_keeps_form: 'clearing the error emits no network effect'
  };
  assertFact(spec.invariants.length === 1 && names[spec.key] === spec.invariants[0], 'canonical invariant mapping differs');
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
    report_failure_stops_leave: () => typeof before.reason === 'string' && typeof before.leaveRoom === 'boolean' &&
      before.reason === after.reason && before.leaveRoom === after.leaveRoom,
    leave_failure_is_partial: () => {
      assertFact(retentionProbe && retentionProbe.sample && retentionProbe.observed && Array.isArray(retentionProbe.requests),
        'actual post-assertion retry retention probe missing');
      const state = retentionProbe.observed;
      return state.reportCalls === after.reportCalls && state.reportCalls === 1 &&
        state.leaveCalls === after.leaveCalls + 1 && state.reportAction === 'success' &&
        retentionProbe.requests.length === 1 && retentionProbe.requests[0].effect === 'leave_room' &&
        retentionProbe.requests[0].responseStatus === 200 &&
        retentionProbe.requests[0].requestSequence > sample.sequence &&
        Number.isInteger(retentionProbe.requests[0].responseSequence) &&
        retentionProbe.requests[0].responseSequence < retentionProbe.sample.sequence;
    },
    retry_leave_only: () => before.reportCalls === 1 && after.reportCalls === before.reportCalls &&
      after.leaveCalls === before.leaveCalls + 1,
    clear_failure_keeps_form: () => before.reportCalls === after.reportCalls && before.leaveCalls === after.leaveCalls
  };
  assertFact(tests[spec.key] && spec.invariants.length === 1, 'unsupported complete invariant mapping');
  const passed = tests[spec.key]();
  assertFact(typeof passed === 'boolean', 'invariant has no executable observation');
  return [{ text: spec.invariants[0], description: spec.invariants[0], passed,
    evidence: { before, after, requestSequences: effects.map(item => ({ request: item.requestSequence,
      response: item.responseSequence, status: item.responseStatus })), nativeSampleSequence: sample.sequence,
      ...(retentionProbe ? { retentionProbe } : {}) } }];
}

function assess(spec, before, after, requests, sample, retentionProbe) {
  for (const key of Object.keys(spec.expected)) assertFact(Object.hasOwn(after, key), 'expected field was not observed: ' + key);
  const checks = invariants(spec, before, after, requests, sample, retentionProbe);
  const pass = equal(spec.expected, after) && checks.every(check => check.passed);
  return { status: pass ? 'pass' : 'fail', observed: after, invariantChecks: checks,
    mismatchedFields: Object.keys(spec.expected).filter(key => !equal(spec.expected[key], after[key])) };
}

function verifyBody(raw, contract, readLayout, bundle) {
  assertFact(raw.nativeProtocol === 'task12.merged-native.v4' &&
    raw.semantic.cases.length === contract.cases.length && /^[0-9a-f]{32}$/.test(raw.nativeNonce),
    'incomplete native cases/nonce');
  const used = new Set();
  const facts = [];
  for (const [index, spec] of contract.cases.entries()) {
    const row = raw.semantic.cases[index];
    assertFact(row.caseId === spec.caseId && row.traceDigest === spec.traceDigest && row.nativeNonce === raw.nativeNonce &&
      !used.has(row.caseRunId), 'native identity/source session mismatch');
    used.add(row.caseRunId);
    assertFact(['pass', 'fail'].includes(row.status), 'native case remains unscored');
    const requests = raw.diagnostics.serverRequests.filter(item => item.caseRunId === row.caseRunId);
    if (row.entryFailureEvidence) {
      facts.push({ caseId: row.caseId, ...verifyBlocked(spec, row, requests, readLayout, bundle) });
      continue;
    }
    assertFact(row.transitionExecuted === true, 'production transition was not executed');
    const sample = name => {
      const points = row.checkpoints.filter(point => point.name === name);
      assertFact(points.length === 1, 'before/after native checkpoint missing/duplicated');
      const point = points[0], nodes = [];
      const visit = tree => { if (tree.attributes) nodes.push(tree.attributes); for (const child of tree.children || []) visit(child); };
      visit(readLayout(point.layout));
      const roots = nodes.filter(node => node.type === 'root');
      assertFact(roots.length === 1 && roots[0].bundleName === bundle && roots[0].pagePath === 'pages/Index' &&
        roots[0].focused === 'true', 'checkpoint is not the original focused production window');
      const observed = state({ nodes, sequence: point.sequence }, requests.filter(item => item.requestSequence < point.sequence));
      assertFact(equal(point.state, observed) && equal(observed, point.state), 'checkpoint state differs from actual native layout/effects');
      return { ...point, nodes, observed };
    };
    const before = sample('before_event'), after = sample('after_event');
    const roomNodes = before.nodes.filter(node => ['room_details_id', 'report_room_id'].includes(node.id) && node.visible === 'true');
    assertFact(roomNodes.length > 0 && roomNodes.every(node => node.text === '!room:example.org'), 'actual before-event room identity missing');
    const given = { ...before.observed, roomId: roomNodes[0].text };
    for (const [key, effect] of [['reportResult', 'report_room'], ['leaveResult', 'leave_room']]) {
      if (Object.hasOwn(spec.given, key)) given[key] = spec.setup.externalResponses[effect][0];
    }
    assertFact(equal(spec.setup.requiredBeforeEvent, given), 'runtime given does not match canonical operation prefix');
    let retention;
    if (spec.key === 'leave_failure_is_partial') {
      const actual = sample('post_assertion_retention');
      const later = requests.filter(item => item.effect && item.requestSequence > after.sequence && item.requestSequence < actual.sequence);
      retention = { sample: { layout: actual.layout, sequence: actual.sequence }, observed: actual.observed, requests: later };
      assertFact(JSON.stringify(retention) === JSON.stringify(row.postAssertionRetention), 'retention observation differs from actual native retry');
    }
    const result = assess(spec, before.observed, after.observed,
      requests.filter(item => item.requestSequence < after.sequence), after, retention);
    assertFact(result.status === row.status && equal(result.observed, row.observed) && equal(row.observed, result.observed) &&
      JSON.stringify(result.invariantChecks) === JSON.stringify(row.invariantChecks), 'native verdict/invariants cannot be recomputed');
    facts.push({ caseId: row.caseId, status: row.status, actualNativeFields: Object.keys(result.observed),
      completeInvariants: result.invariantChecks.length });
  }
  return { validated: true, cases: facts, nativeUiAndHttpRecomputed: true };
}

const PROTOCOL = 'task12.merged-native.v4';
const ABSENT_POLICY = 'arkts.task12.merged-closed-entry.v4';
const ROOM = '!room:example.org';
const integer = value => Number.isSafeInteger(value) && value > 0;
const exact = (a, b) => equal(a, b) && equal(b, a);
function flatten(tree) {
  return [...(tree.attributes ? [tree.attributes] : []), ...(tree.children || []).flatMap(flatten)];
}

function owner(nodes, bundle) {
  const roots = nodes.filter(node => node.type === 'root');
  assertFact(roots.length === 1, 'missing/ambiguous native owner');
  const root = roots[0];
  assertFact(root.bundleName === bundle && root.pagePath === 'pages/Index' && root.abilityName === 'EntryAbility' &&
    root.focused === 'true' && /^[1-9][0-9]*$/.test(root.hostWindowId) &&
    Number.isSafeInteger(Number(root.hostWindowId)) && root.hashcode === root.hostWindowId + ':0',
    'native owner/window/ability binding unavailable');
  assertFact(nodes.filter(node => node.type).every(node => node.hostWindowId === root.hostWindowId),
    'cross-window native inventory');
  return { bundle: root.bundleName, ability: root.abilityName, page: root.pagePath,
    window: root.hostWindowId, root: root.hashcode };
}

function rawOne(nodes, id) {
  const found = nodes.filter(node => node.id === id && node.visible === 'true');
  assertFact(found.length === 1, 'missing/ambiguous room control ' + id);
  return found[0];
}

// Closed room inventory is checked on both capability branches, not only base.
function closedDetails(nodes, confirmation = false) {
  const entry = one(nodes, 'entry', false);
  const known = {
    room_details_title: ['Text', 'Room details'], room_details_id: ['Text', ROOM],
    room_details_name: ['Text', 'Runtime room'], room_member_count: ['Text', '1 members'],
    leave_room: ['Button', 'Leave room']
  };
  if (entry) known[entry.id] = ['Button', 'Report room'];
  if (confirmation) Object.assign(known, {
    leave_room_confirmation: ['Text', 'Leave this room?'],
    cancel_leave_room: ['Button', 'Cancel'], confirm_leave_room: ['Button', 'Confirm leave']
  });
  const actual = nodes.filter(node => node.type), counts = {};
  for (const node of actual) {
    counts[node.type] = (counts[node.type] || 0) + 1;
    assertFact(node.visible === 'true' && node.enabled === 'true' && node.scrollable === 'false' &&
      node.longClickable === 'false' && node.checkable === 'false', 'unbound hidden/overflow details interaction');
    if (node.id) assertFact(known[node.id] && node.type === known[node.id][0] && node.text === known[node.id][1] &&
      node.clickable === (node.type === 'Button' ? 'true' : 'false'), 'unbound/renamed details control');
    else assertFact(['root', 'Column', 'Scroll', ...(entry ? ['Stack', 'Row'] : confirmation ? ['Row'] : [])].includes(node.type) &&
      node.clickable === 'false' && !node.text, 'unbound details container/action');
  }
  assertFact(Object.keys(known).every(id => actual.filter(node => node.id === id).length === 1) &&
    counts.root === 1 && counts.Text === 4 + Number(confirmation) &&
    counts.Button === 1 + Number(!!entry) + (confirmation ? 2 : 0), 'details UI closure incomplete');
  if (!entry) assertFact(actual.length === 9 + (confirmation ? 4 : 0) && counts.Column === 2 &&
    counts.Scroll === 1 && (counts.Row || 0) === Number(confirmation), 'absence UI closure incomplete');
  if (!entry && !confirmation) closedBase(nodes);
  return { entryAvailable: !!entry, complete: true, unboundControls: 0 };
}

function boundUi(nodes) {
  const known = new Set([...Object.values(ids).flat(), 'room_details_title', 'room_details_id',
    'room_details_name', 'room_member_count', 'leave_room', 'report_room_title', 'report_room_id',
    'report_room_back', 'report_room_close', 'retry_report_room', 'report_room_in_flight', 'leave_room_success']);
  const seen = new Set();
  for (const node of nodes.filter(node => node.type)) {
    // Native editable reason text exposes platform selection/paste long press.
    // This binds only the known reason editor, never arbitrary clickable inputs.
    // Placeholder copy is not canonical semantics; retain the actual layout value.
    // Source/HAP/layout provenance remains the caller's unchanged admission boundary.
    const nativeReasonEditor = node.id === 'report_room_reason' && node.key === node.id &&
      ['TextArea', 'TextInput'].includes(node.type) && typeof node.hint === 'string' &&
      node.enabled === 'true' && node.clickable === 'true' && node.checkable === 'false' && typeof node.text === 'string';
    assertFact(node.visible === 'true' && node.scrollable === 'false' &&
      (node.longClickable === 'false' || (node.longClickable === 'true' && nativeReasonEditor)),
      'unbound hidden/overflow native interaction');
    if (node.id) {
      assertFact(known.has(node.id) && !seen.has(node.id), 'unbound/duplicate native control');
      seen.add(node.id);
      const concepts = Object.keys(ids).filter(concept => ids[concept].includes(node.id));
      let types = ['Text'];
      if (concepts.includes('reason')) types = ['TextArea', 'TextInput'];
      else if (concepts.includes('toggle')) types = ['Checkbox', 'Toggle'];
      else if (concepts.some(concept => ['entry', 'submit', 'retryLeave', 'clearError'].includes(concept)) ||
        ['leave_room', 'report_room_back', 'report_room_close', 'retry_report_room'].includes(node.id)) types = ['Button'];
      assertFact(types.includes(node.type), 'unbound native control type');
      if (node.type === 'Text') assertFact(node.clickable === 'false' && node.checkable === 'false',
        'unbound interactive native label');
    } else assertFact(['root', 'Stack', 'Column', 'Scroll', 'Row', 'Text'].includes(node.type) &&
      node.clickable === 'false' && node.checkable === 'false', 'unbound native action');
  }
}

function absence(spec, common, checkpoints, caseRunId, nativeNonce) {
  return { caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, caseRunId, nativeNonce,
    status: 'fail', transitionExecuted: false, observed: null, invariantChecks: [],
    unevaluatedInvariants: spec.invariants, unobservedExpectedFields: Object.keys(spec.expected),
    checkpoints, operationTrace: [], common,
    entryFailureEvidence: { policyId: ABSENT_POLICY, requestedAction: spec.setup.actions[0] || spec.event,
      failedAt: spec.setup.actions.length ? 'setup.actions[0]' : 'event',
      commonStartEstablished: true, positiveControlCompleted: true, originalGivenReached: false,
      givenScope: 'actual common start; downstream given and invariants remain unobserved' } };
}

function clickArgs(node) {
  const bounds = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(node.bounds || '');
  assertFact(bounds && node.enabled === 'true', 'missing bounds or disabled positive control');
  return ['shell', 'uitest', 'uiInput', 'click',
    String(Math.round((+bounds[1] + +bounds[3]) / 2)), String(Math.round((+bounds[2] + +bounds[4]) / 2))];
}

function verifyCommon(row, raw, readLayout, readLog, bundle) {
  const common = row.common;
  assertFact(common && common.session === row.caseRunId && integer(common.start) && integer(common.end) &&
    common.start < common.end, 'missing common episode');
  const commands = raw.diagnostics.commands.filter(item => item.caseRunId === row.caseRunId);
  const before = commands.filter(item => item.sequence < common.end);
  const starts = commands.filter(item => item.args.slice(0, 3).join(' ') === 'shell aa start');
  const installs = commands.filter(item => item.args[0] === 'install');
  assertFact(starts.length === 1 && installs.length === 1 && installs[0].args[2] === raw.compile.hap.path &&
    exact(starts[0].args, ['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundle, '-m', 'entry']) &&
    installs[0].sequence < starts[0].sequence && starts[0].sequence < common.start, 'not one fresh original-page episode');
  const absent = before.find(item => exact(item.args, ['shell', 'bm', 'dump', '-n', bundle]));
  assertFact(absent && absent.sequence < installs[0].sequence && /failed|not exist|error/i.test(readLog(absent.log)),
    'fresh installation absence not observed');
  assertFact(before.some(item => item.args[0] === 'uninstall' && item.sequence < absent.sequence), 'fresh uninstall missing');
  const points = ['common_start', 'entry_stable', 'positive_leave_control', 'common_start_restored'].map(name => {
    const found = row.checkpoints.filter(point => point.name === name);
    assertFact(found.length === 1, 'common checkpoint missing/duplicate ' + name);
    const point = found[0], nodes = flatten(readLayout(point.layout));
    assertFact(exact(owner(nodes, bundle), common.owner), 'page owner changed within common prefix');
    return { ...point, nodes };
  });
  assertFact(points.every(point => integer(point.sequence)) && common.start === points[0].sequence &&
    points.every((point, index) => index === 0 || points[index - 1].sequence < point.sequence) &&
    points[3].sequence < common.end, 'common checkpoint chronology differs');
  const capabilities = points.map((point, index) => closedDetails(point.nodes, index === 2).entryAvailable);
  assertFact(capabilities.every(value => value === capabilities[0]) && common.entryAvailable === capabilities[0],
    'unstable/ambiguous capability binding');
  const click = (sample, id, low, high) => {
    const expected = clickArgs(rawOne(sample.nodes, id));
    assertFact(commands.filter(item => item.sequence > low && item.sequence < high && exact(item.args, expected)).length === 1,
      'positive control was not actually clicked');
  };
  click(points[1], 'leave_room', points[1].sequence, points[2].sequence);
  click(points[2], 'cancel_leave_room', points[2].sequence, points[3].sequence);
  const requests = raw.diagnostics.serverRequests.filter(item => item.caseRunId === row.caseRunId);
  prefixRequests(requests.filter(item => item.requestSequence < common.end), ROOM);
  assertFact(requests.filter(item => item.requestSequence < common.end).every(item =>
    integer(item.responseSequence) && item.responseStatus === 200 && item.responseSequence < points[0].sequence),
    'common SDK response not completed before actual room');
  const last = Math.max(common.end, ...row.checkpoints.map(point => point.sequence));
  assertFact(commands.filter(item => item.sequence > starts[0].sequence && item.sequence < last).every(item =>
    !['install', 'uninstall'].includes(item.args[0]) && !['start', 'force-stop', 'stop-service'].includes(item.args[2])),
    'page lifecycle reset inside episode');
  for (const point of row.checkpoints) {
    assertFact(exact(owner(flatten(readLayout(point.layout)), bundle), common.owner), 'canonical transition owner changed');
    assertFact(point.sequence >= common.start, 'checkpoint from a prior episode');
  }
  const end = commands.find(item => item.sequence > last && exact(item.args, ['shell', 'bm', 'dump', '-n', bundle]));
  assertFact(end && /failed|not exist|error/i.test(readLog(end.log)) &&
    commands.some(item => item.sequence > last && item.sequence < end.sequence && item.args[0] === 'uninstall'),
    'case owned-app uninstall was not verified');
  return { requests, available: capabilities[0] };
}

function verifyOperations(spec, row, raw, readLayout) {
  const blocked = row.entryFailureEvidence?.policyId === DISABLED_POLICY;
  let expected = [...spec.setup.actions, spec.event];
  if (blocked) {
    const index = expected.findIndex(action => action.name === 'report');
    assertFact(index >= 0, 'unsupported disabled operation');
    expected = expected.slice(0, index + 1);
  } else if (spec.key === 'leave_failure_is_partial') expected.push({ name: 'retry' });
  assertFact(exact(row.operationTrace.map(op => op.action), expected), 'canonical operation values/order omitted or changed');
  let previous = row.common.end;
  for (const op of row.operationTrace) {
    assertFact(integer(op.sequence) && integer(op.end) && op.sequence > previous && op.end > op.sequence &&
      op.caseRunId === row.caseRunId && op.name === op.action.name, 'canonical operation sequence/identity differs');
    previous = op.end;
    const nodes = flatten(readLayout(op.before));
    assertFact(raw.diagnostics.layouts.some(entry => exact(entry.layout, op.before) &&
      entry.sequence < op.sequence && entry.caseRunId === row.caseRunId), 'operation before-layout is from the future');
    assertFact(exact(owner(nodes, raw.bundle), row.common.owner), 'operation uses detached owner');
    boundUi(nodes);
    const commands = raw.diagnostics.commands.filter(item => item.caseRunId === row.caseRunId &&
      item.sequence > op.sequence && item.sequence < op.end);
    let target;
    const concepts = { open_report_room: 'entry', toggle_leave_room: 'toggle', report: 'submit',
      retry: 'retryLeave', clear_report_action: 'clearError' };
    if (op.action.name === 'update_reason') {
      target = one(nodes, 'reason');
      const click = clickArgs(target);
      assertFact(commands.some(item => exact(item.args, ['shell', 'uitest', 'uiInput', 'inputText', ...click.slice(-2), op.action.reason])) &&
        commands.some(item => exact(item.args, ['shell', 'uitest', 'uiInput', 'keyEvent', 'Back'])), 'actual input operation missing');
    } else if (concepts[op.action.name]) {
      target = one(nodes, concepts[op.action.name]);
      if (!(blocked && op.action.name === 'report')) assertFact(commands.some(item => exact(item.args, clickArgs(target))),
        'actual canonical click missing');
      else assertFact(!commands.some(item => exact(item.args, clickArgs({ ...target, enabled: 'true' }))),
        'disabled command force-clicked');
    } else assertFact(op.action.name === 'render_report_form', 'unknown canonical operation');
  }
  const point = name => row.checkpoints.find(p => p.name === name);
  if (!blocked) {
    const before = point('before_event'), after = point('after_event');
    const event = row.operationTrace[spec.setup.actions.length];
    assertFact(before && after && before.sequence < event.sequence && event.end < after.sequence &&
      (spec.setup.actions.length === 0 ? row.common.end : row.operationTrace[spec.setup.actions.length - 1].end) < before.sequence,
      'canonical before/event/after chronology differs');
    if (spec.key === 'leave_failure_is_partial') assertFact(row.operationTrace.at(-1).sequence > after.sequence &&
      row.operationTrace.at(-1).end < point('post_assertion_retention').sequence, 'retention retry chronology differs');
  }
}

function verifyNative(raw, contract, readLayout, bundle, readLog) {
  assertFact(raw.nativeProtocol === PROTOCOL && raw.bundle === bundle && raw.taskId === contract.taskId &&
    /^[0-9a-f]{32}$/.test(raw.nativeNonce) && raw.semantic.cases.length === contract.cases.length,
    'not a complete merged-native protocol');
  assertFact(raw.diagnostics.cleanup.ownedAppUninstalled === true && raw.diagnostics.cleanup.reverseRemoved === true &&
    raw.diagnostics.cleanup.remoteFilesRemoved === true, 'remote cleanup incomplete');
  const used = new Set(), sequences = new Set();
  for (const command of raw.diagnostics.commands) {
    assertFact(integer(command.sequence) && !sequences.has(command.sequence) && [0, 255].includes(command.exitCode),
      'command transport/sequence incomplete');
    sequences.add(command.sequence); readLog(command.log);
    assertFact(command.exitCode === 0 || command.args[0] === 'uninstall' ||
      exact(command.args, ['shell', 'bm', 'dump', '-n', bundle]), 'non-cleanup transport failure');
  }
  verifyLayoutLedger(raw, readLayout, readLog, bundle);
  const facts = [];
  for (const [index, spec] of contract.cases.entries()) {
    const row = raw.semantic.cases[index];
    assertFact(row.caseId === spec.caseId && row.key === spec.key && row.traceDigest === spec.traceDigest &&
      row.nativeNonce === raw.nativeNonce && typeof row.caseRunId === 'string' &&
      row.caseRunId.startsWith(spec.caseId + '-') && /^[0-9a-f]{16}$/.test(row.caseRunId.slice(-16)) && !used.has(row.caseRunId),
      'case/nonce/digest duplicate or binding differs');
    used.add(row.caseRunId);
    if (row.status === 'not_scored') {
      assertFact(typeof row.reason === 'string' && row.reason.length > 0 && row.observed === null && row.invariantChecks.length === 0,
        'invalid unavailable row');
      facts.push({ caseId: row.caseId, status: 'not_scored' }); continue;
    }
    const common = verifyCommon(row, raw, readLayout, readLog, bundle);
    verifySdk(spec, row, common.requests);
    if (!common.available) {
      const expected = absence(spec, row.common, row.checkpoints, row.caseRunId, raw.nativeNonce);
      for (const field of ['status', 'transitionExecuted', 'observed', 'invariantChecks', 'unevaluatedInvariants',
        'unobservedExpectedFields', 'operationTrace', 'entryFailureEvidence']) assertFact(exact(row[field], expected[field]),
        'absent entry projected/modified downstream assertions');
      assertFact(common.requests.every(item => !item.effect) && common.requests.length <= 3, 'absent entry emitted SDK effects');
      facts.push({ caseId: row.caseId, status: 'fail', actualClosedEntry: true }); continue;
    }
    verifyOperations(spec, row, raw, readLayout);
    for (const point of row.checkpoints.filter(point => !['common_start', 'entry_stable', 'positive_leave_control',
      'common_start_restored'].includes(point.name))) boundUi(flatten(readLayout(point.layout)));
    const verified = verifyBody({ ...raw, semantic: { cases: [row] } }, { ...contract, cases: [spec] }, readLayout, bundle);
    facts.push({ ...verified.cases[0], status: row.status, sameOriginalPageEpisode: true });
  }
  const counts = { total: facts.length, passed: facts.filter(row => row.status === 'pass').length,
    failed: facts.filter(row => row.status === 'fail').length, notScored: facts.filter(row => row.status === 'not_scored').length };
  for (const [key, value] of Object.entries(counts)) assertFact(raw.semantic[key] === value, 'semantic aggregate differs');
  assertFact(raw.diagnostics.serverRequests.every(item => used.has(item.caseRunId)), 'unbound external callback');
  return { protocol: PROTOCOL, validated: true, cases: facts, counts,
    sameOriginalPageEpisodes: true, fullInvariantRecomputation: true, publicAdmitted: false };
}

function verifySdk(spec, row, requests) {
  let previous = 0;
  const counts = {};
  for (const request of requests) {
    assertFact(integer(request.requestSequence) && integer(request.responseSequence) &&
      request.requestSequence > previous && request.responseSequence > request.requestSequence &&
      request.authorization === 'Bearer runtime-token', 'SDK response/method/auth/order incomplete');
    previous = request.requestSequence;
    if (request.effect) {
      assertFact(['report_room', 'leave_room'].includes(request.effect) && request.method === 'POST' &&
        request.url === '/_matrix/client/v3/rooms/' + encodeURIComponent(ROOM) +
          (request.effect === 'report_room' ? '/report' : '/leave'), 'unbound SDK effect');
      assertFact(row.operationTrace.some(op => ['report', 'retry'].includes(op.action.name) &&
        op.sequence < request.requestSequence && request.responseSequence < op.end),
        'SDK effect outside actual canonical UI operation');
      const index = counts[request.effect] || 0;
      counts[request.effect] = index + 1;
      const outcomes = spec.setup.externalResponses[request.effect] || ['success'];
      const retention = spec.key === 'leave_failure_is_partial' && request.effect === 'leave_room' && index === 1;
      const outcome = retention ? 'success' : outcomes[Math.min(index, outcomes.length - 1)];
      assertFact(request.scriptedOutcome === outcome && request.responseStatus === (outcome === 'success' ? 200 : 500),
        'external SDK scripted outcome differs');
      const payload = JSON.parse(request.body);
      assertFact(payload && typeof payload === 'object' && !Array.isArray(payload) &&
        (request.effect !== 'report_room' || typeof payload.reason === 'string'), 'invalid SDK payload');
    } else assertFact(request.method === 'GET' && !request.body && request.responseStatus === 200 &&
      ['/_matrix/client/v3/joined_rooms', '/_matrix/client/v3/rooms/' + encodeURIComponent(ROOM) + '/state',
        '/_matrix/client/versions'].includes(request.url), 'unbound SDK request');
  }
}

function verifyLayoutLedger(raw, readLayout, readLog, bundle) {
  const command = sequence => {
    const found = raw.diagnostics.commands.filter(item => item.sequence === sequence);
    assertFact(found.length === 1, 'layout command binding incomplete');
    return found[0];
  };
  const paths = new Set(), samples = new Set(), cases = new Map();
  for (const entry of raw.diagnostics.layouts) {
    assertFact(typeof entry.remote === 'string' && entry.remote.startsWith('/data/local/tmp/task12-replay-' + raw.nativeNonce + '-') &&
      /^\d+\.json$/.test(entry.remote.split('-').at(-1)) && !paths.has(entry.remote) &&
      !samples.has(entry.sequence) && integer(entry.sequence), 'layout owned nonce/identity invalid');
    paths.add(entry.remote); samples.add(entry.sequence);
    const dump = command(entry.dumpCommand), cat = command(entry.catCommand);
    assertFact(exact(dump.args, ['shell', 'uitest', 'dumpLayout', '-p', entry.remote, '-b', bundle]) &&
      exact(cat.args, ['shell', 'cat', entry.remote]) && dump.caseRunId === entry.caseRunId && cat.caseRunId === entry.caseRunId &&
      dump.sequence < cat.sequence && cat.sequence < entry.sequence && dump.exitCode === 0 && cat.exitCode === 0,
      'layout not captured from this device episode');
    const layout = readLayout(entry.layout);
    assertFact(exact(layout, JSON.parse(readLog(cat.log))), 'retained layout differs from actual HDC output');
    const identity = owner(flatten(layout), bundle);
    assertFact(exact(identity, entry.owner) && (!cases.has(entry.caseRunId) || exact(identity, cases.get(entry.caseRunId))),
      'native owner changed between samples');
    cases.set(entry.caseRunId, identity);
  }
  for (const row of raw.semantic.cases.filter(row => row.status !== 'not_scored')) {
    for (const point of row.checkpoints) assertFact(raw.diagnostics.layouts.some(entry => entry.sequence === point.sequence &&
      entry.caseRunId === row.caseRunId && exact(entry.layout, point.layout)), 'checkpoint not in actual device layout ledger');
    for (const op of row.operationTrace) assertFact(raw.diagnostics.layouts.some(entry =>
      entry.caseRunId === row.caseRunId && exact(entry.layout, op.before)), 'operation uses foreign layout');
  }
  const expected = [...paths].sort(), removed = [];
  assertFact(exact([...raw.diagnostics.remoteFiles].sort(), expected), 'remote file manifest differs');
  for (const item of raw.diagnostics.commands.filter(item => item.args.slice(0, 3).join(' ') === 'shell rm -f')) {
    assertFact(item.exitCode === 0 && item.args.slice(3).every(file => paths.has(file)), 'remote cleanup touched unowned files');
    removed.push(...item.args.slice(3));
  }
  assertFact(exact(removed.sort(), expected) && raw.diagnostics.cleanup.remoteLayoutsRemoved === expected.length,
    'owned remote layouts not fully removed');
  const config = raw.executionConfig;
  assertFact(config && integer(config.port) && config.port <= 65535, 'reverse-port config missing');
  for (const [name, args] of [['rport', ['rport', 'tcp:' + config.port, 'tcp:' + config.port]],
    ['reverse removal', ['fport', 'rm', 'tcp:' + config.port, 'tcp:' + config.port]]]) {
    assertFact(raw.diagnostics.commands.filter(item => exact(item.args, args) && item.exitCode === 0).length === 1,
      name + ' actual command missing');
  }
}

module.exports = { PROTOCOL, ABSENT_POLICY, DISABLED_POLICY, one, matches, boolean, prefixRequests,
  closedBase, closedDetails, closedLeftRoom, boundUi, owner, rawOne, flatten, absence, closedDisabledForm, verifyBlocked,
  state, equal, exact, invariants, assess, verifyNative, verifyCommon, verifyOperations, verifySdk, verifyLayoutLedger };
