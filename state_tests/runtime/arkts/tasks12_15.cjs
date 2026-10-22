'use strict';

const { setTimeout: delay } = require('node:timers/promises');
const { isDeepStrictEqual: same } = require('node:util');

const FEATURES = 'entry/src/main/ets/features/';
const UI_LIMIT = 'Native ArkUI was not executed; only exported production domain state and getters are observable.';

class Unsupported extends Error {}

function copy(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function last(items, predicate = () => true) {
  for (let i = items.length - 1; i >= 0; i -= 1) {
    if (predicate(items[i])) return items[i];
  }
  return undefined;
}

function whenObserved(values, predicate) {
  return values.every((value) => value !== undefined) ? predicate() : undefined;
}

function read(target, ...names) {
  for (const name of names) {
    if (target && name in target) {
      return typeof target[name] === 'function' ? target[name]() : target[name];
    }
  }
  return undefined;
}

function call(target, names, ...args) {
  const name = names.find((candidate) => typeof target?.[candidate] === 'function');
  if (!name) throw new Unsupported(`Production API unavailable: ${names.join(' or ')}`);
  return target[name](...args);
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

async function flush() {
  for (let i = 0; i < 12; i += 1) await Promise.resolve();
}

function context(args) {
  const evidence = [];
  const checks = new Map();
  const limitations = [];
  let beforeRecorded = false;
  let afterRecorded = false;
  return {
    ...args,
    observed: {},
    snapshot: () => ({}),
    record(label, data) {
      const checkpoint = copy(data);
      evidence.push({ label, data: checkpoint });
      if (typeof args.trace === 'function') args.trace(label, checkpoint);
    },
    checkpointState() {
      try { return this.snapshot(); }
      catch (error) {
        const reason = `Production observation failed: ${error.message || error}`;
        this.missing(reason);
        return { unavailableObservation: reason };
      }
    },
    before() {
      beforeRecorded = true;
      this.record('before_event', { event: args.caseSpec.event, state: this.checkpointState() });
    },
    after() {
      afterRecorded = true;
      this.record('after_event', { event: args.caseSpec.event, state: this.checkpointState() });
    },
    check(description, passed, observed) {
      if (typeof passed !== 'boolean') {
        this.missing(`Invariant has incomplete runtime evidence: ${description}`);
        return;
      }
      checks.set(description, { description, passed, observed: copy(observed) });
    },
    missing(reason) {
      if (!limitations.includes(reason)) limitations.push(reason);
    },
    async module(candidates, exportName) {
      const errors = [];
      for (const relative of candidates) {
        const path = FEATURES + relative + '.ets';
        try {
          const exports = await args.load(path);
          if (typeof exports?.[exportName] !== 'function') {
            errors.push({ path, error: `Missing export ${exportName}` });
            continue;
          }
          this.record('production_module', { path, exportName });
          return exports;
        } catch (error) {
          errors.push({ path, error: String(error.message || error) });
        }
      }
      this.record('unavailable_modules', errors);
      throw new Unsupported(`Cannot load executable ${exportName}: ${errors.map((item) => `${item.path}: ${item.error}`).join('; ')}`);
    },
    finish(error) {
      if (error) this.missing(String(error.message || error));
      if (!beforeRecorded) this.before();
      if (!afterRecorded) this.after();
      const invariantChecks = [];
      const unsupportedInvariants = [];
      for (const description of args.caseSpec.invariants || []) {
        if (checks.has(description)) invariantChecks.push(checks.get(description));
        else unsupportedInvariants.push({ description, reason: limitations.join('; ') || 'No executable observation for this invariant.' });
      }
      return {
        observed: copy(this.observed),
        evidence,
        invariantChecks,
        unsupportedInvariants,
        observationLevel: 'production_domain',
        integrationBoundary: {
          entry: 'exported production presenter APIs',
          appEntryExecuted: false,
          externalServicesExecuted: false,
          gatewayEvidence: 'calls from production code to injected external dependencies; not SDK/network integration'
        },
        nativeUI: this.nativeUIProof || { observed: false, reason: UI_LIMIT },
        prerequisiteChecks: this.prerequisiteChecks || [],
        ...(limitations.length ? { unsupported: limitations.join('; ') } : {})
      };
    }
  };
}

async function reportRoom(c) {
  let m;
  try { m = await c.module(['ReportRoomFeature'], 'ReportRoomPresenter'); }
  catch (error) {
    await legacySurface(c, ['RoomDetailsFeature'], 'RoomDetailsPresenter', (exports) => [new exports.RoomDetailsGateway()]);
    throw error;
  }
  if (typeof m.RoomFlow === 'function') return reportRoomWithClient(c, m);
  const g = c.caseSpec.given;
  const event = c.caseSpec.event;
  const key = c.caseSpec.key;
  let reportFails = g.reportResult === 'failure';
  let leaveFails = g.leaveResult === 'failure';
  const calls = [];
  let p;
  const gateway = typeof m.ReportRoomGateway === 'function' ? new m.ReportRoomGateway() : {};
  gateway.roomExists = true;
  gateway.reportRoom = (...args) => {
    const result = !reportFails;
    const item = { effect: 'report_room', reason: last(args), args, result, actionDuringCall: action() };
    calls.push(item);
    c.record('gateway_report_return', item);
    return result;
  };
  gateway.leaveRoom = (...args) => {
    const result = !leaveFails;
    const item = { effect: 'leave_room', args, result, actionDuringCall: action() };
    calls.push(item);
    c.record('gateway_leave_return', item);
    return result;
  };
  p = new m.ReportRoomPresenter(typeof m.ReportRoomService === 'function' ? new m.ReportRoomService(gateway) : gateway);
  function action() {
    const state = p?.reportAction ?? p?.phase;
    return ({ idle: 'uninitialized', editing: 'uninitialized', submitting_report: 'loading', submitting_leave: 'loading' })[state] ?? state;
  }
  const count = (effect) => calls.filter((item) => item.effect === effect).length;
  const snapshot = () => copy({
    reason: p.reason, leaveRoom: p.leaveRoom, reportAction: action(),
    canReport: read(p, 'canReport', 'canSubmit'),
    submitEnabled: read(p, 'submitEnabled'),
    domainCanSubmit: read(p, 'canSubmit'),
    retryEnabled: read(p, 'canRetry', 'retryEnabled'),
    reportCalls: count('report_room'), leaveCalls: count('leave_room'),
    reportReason: last(calls, (item) => item.effect === 'report_room')?.reason,
    effects: calls.map((item) => item.effect), lastOutcome: p.lastOutcome
  });
  c.snapshot = snapshot;
  if (event.name !== 'open_report_room' && typeof p.openReportRoom === 'function') p.openReportRoom(g.roomId || '!room:example.org');
  if (g.reason !== undefined) await call(p, ['updateReason'], g.reason);
  if (g.leaveRoom !== undefined && p.leaveRoom !== g.leaveRoom) {
    if (typeof p.setLeaveRoom === 'function') p.setLeaveRoom(g.leaveRoom);
    else await call(p, ['toggleLeaveRoom']);
  }
  if (g.reportAction === 'leave_failed' || g.reportAction === 'report_failed') {
    reportFails = g.reportAction === 'report_failed';
    leaveFails = g.reportAction === 'leave_failed';
    await call(p, ['submit', 'submitReport']);
    c.record('fixture_failure', snapshot());
    reportFails = false;
    leaveFails = false;
  }
  const before = snapshot();
  c.before();
  switch (event.name) {
    case 'open_report_room':
      if (typeof p.openReportRoom === 'function') p.openReportRoom(g.roomId || '!room:example.org');
      break;
    case 'render_report_form': break;
    case 'update_reason': await call(p, ['updateReason'], event.reason); break;
    case 'toggle_leave_room': await call(p, ['toggleLeaveRoom']); break;
    case 'report': await call(p, ['submit', 'submitReport']); break;
    case 'retry': await call(p, ['retry']); break;
    case 'clear_report_action': await call(p, ['clearReportAction']); break;
    default: throw new Unsupported(`Unknown report event: ${event.name}`);
  }
  c.observed = snapshot();
  if (event.name === 'retry') c.observed.retryShouldReport = c.observed.reportCalls > before.reportCalls;
  c.after();
  const after = c.observed;
  if (key === 'initial_form' && 'canReport' in p) {
    c.record('production_getter_observation', { owner: 'ReportRoomPresenter', getter: 'canReport', value: read(p, 'canReport'), observationLevel: 'production_domain' });
  }
  const detail = { before, after, calls };
  switch (key) {
    case 'initial_form': c.check('no report or leave effect is emitted', calls.length === 0, detail); break;
    case 'reason_enables_report': c.check('editing the reason does not toggle leave', whenObserved([before.leaveRoom, after.leaveRoom], () => before.leaveRoom === after.leaveRoom), detail); break;
    case 'toggle_leave': c.check('the reason remains unchanged', whenObserved([before.reason, after.reason], () => before.reason === after.reason), detail); break;
    case 'report_only_success':
      c.check('reporting completes before the success result', calls.some((item) => item.effect === 'report_room' && item.result && item.actionDuringCall !== 'success') && after.reportAction === 'success', detail);
      break;
    case 'report_then_leave':
      c.check('leave is attempted only after reporting succeeds', calls.some((item) => item.effect === 'leave_room') && calls.every((item, index) => item.effect !== 'leave_room' || calls.slice(0, index).some((prior) => prior.effect === 'report_room' && prior.result)), detail);
      break;
    case 'blank_reason_disabled':
      c.check('leave preference remains selected', before.leaveRoom === true && after.leaveRoom === true, detail);
      if (after.submitEnabled === undefined) c.missing('submitEnabled has no executable production getter; the native report button was not observed.');
      break;
    case 'report_failure_stops_leave': c.check('form values survive the failure', whenObserved([before.reason, after.reason, before.leaveRoom, after.leaveRoom], () => before.reason === after.reason && before.leaveRoom === after.leaveRoom), detail); break;
    case 'leave_failure_is_partial': {
      if (after.retryEnabled === undefined) c.missing('retryEnabled is only available in the native report UI.');
      // Probe retry on this same instance to observe remembered report success.
      leaveFails = false;
      await call(p, ['retry']);
      const retried = snapshot();
      c.record('invariant_retry_probe', retried);
      c.check('the successful report is remembered', after.reportCalls === 1 && retried.reportCalls === after.reportCalls && retried.leaveCalls === after.leaveCalls + 1, { after, retried });
      break;
    }
    case 'retry_leave_only': c.check('the report is never submitted twice', before.reportCalls === 1 && after.reportCalls === before.reportCalls, detail); break;
    case 'clear_failure_keeps_form': c.check('clearing the error emits no network effect', same(before.effects, after.effects), detail); break;
  }
}

async function reportRoomWithClient(c, m) {
  const spec = c.caseSpec;
  const setup = spec.setup || {};
  const initial = setup.initialState || {};
  const roomId = initial.roomId || spec.given.roomId || '!room:example.org';
  const scripted = Object.fromEntries(Object.entries(setup.externalResponses || {})
    .map(([name, values]) => [name, values.slice()]));
  const requests = [];
  const reportReasons = [];
  const resultFor = (name) => scripted[name]?.shift() || 'success';
  const client = {
    async getRoom(requestedRoomId) {
      requests.push({ effect: 'get_room', roomId: requestedRoomId, result: 'success' });
      return { roomId: requestedRoomId, name: 'Runtime room', topic: '', memberCount: 2 };
    },
    async leaveRoom(requestedRoomId) {
      const result = resultFor('leave_room');
      requests.push({ effect: 'leave_room', roomId: requestedRoomId, result });
      if (result === 'failure') throw new Error('Scripted leave failure');
    },
    async canReportRoom() {
      requests.push({ effect: 'can_report_room', result: true });
      return true;
    },
    async reportRoom(requestedRoomId, reason) {
      const result = resultFor('report_room');
      reportReasons.push(reason);
      requests.push({ effect: 'report_room', roomId: requestedRoomId, reason, result });
      if (result === 'failure') throw new Error('Scripted report failure');
    }
  };
  const flow = new m.RoomFlow(roomId, client);
  await flow.details.load();
  const effects = () => requests.filter(item => item.effect === 'report_room' || item.effect === 'leave_room');
  const presenter = () => flow.report;
  const projection = () => {
    const p = presenter();
    const reportCalls = effects().filter(item => item.effect === 'report_room').length;
    const leaveCalls = effects().filter(item => item.effect === 'leave_room').length;
    return {
      roomId,
      screen: flow.screen === 'details' ? 'room_details' : flow.screen,
      reason: p?.reason,
      leaveRoom: p?.leaveRoom,
      reportAction: p?.reportAction,
      canReport: p?.canReport,
      submitEnabled: p ? p.canReport && p.reportAction !== 'loading' : undefined,
      retryEnabled: p?.reportAction === 'leave_failed',
      reportResult: scripted.report_room?.[0] || 'success',
      leaveResult: scripted.leave_room?.[0] || 'success',
      reportCalls,
      leaveCalls,
      reportReason: reportReasons.at(-1),
      effects: effects().map(item => item.effect)
    };
  };
  c.snapshot = projection;
  c.record('common_start', { state: projection(), room: copy(flow.details.room),
    clientCapability: flow.details.canReportRoom, requests: copy(requests) });

  async function action(event) {
    const p = presenter();
    switch (event.name) {
      case 'open_report_room':
        if (!flow.openReport()) throw new Unsupported('The production report entry rejected the canonical action.');
        break;
      case 'update_reason': call(p, ['updateReason'], event.reason); break;
      case 'toggle_leave_room': call(p, ['toggleLeaveRoom']); break;
      case 'report': await call(flow, ['submitReport']); break;
      case 'retry': await call(flow, ['submitReport']); break;
      case 'clear_report_action': call(p, ['clearReportAction']); break;
      case 'render_report_form': break;
      default: throw new Unsupported(`Unknown report event: ${event.name}`);
    }
    c.record('production_action', { action: copy(event), state: projection(), requests: copy(requests) });
  }

  for (const actionSpec of setup.actions || []) await action(actionSpec);
  const before = projection();
  for (const [name, expected] of Object.entries(spec.given || {})) {
    if (!same(before[name], expected)) c.missing(`Canonical given not established: ${name}`);
  }
  for (const [name, expected] of Object.entries(setup.requiredBeforeEvent || {})) {
    if (!same(before[name], expected)) c.missing(`Required action-prefix state not established: ${name}`);
  }
  c.record('canonical_given_validated', { given: copy(before), remainingResponses: copy(scripted) });
  c.before();
  const reportCallsBefore = before.reportCalls;
  await action(spec.event);
  const after = projection();
  if (spec.event.name === 'retry') after.retryShouldReport = after.reportCalls > reportCallsBefore;
  c.observed = after;
  c.after();
  const detail = { before, after, requests: copy(requests) };
  switch (spec.key) {
    case 'initial_form': c.check('no report or leave effect is emitted', effects().length === 0, detail); break;
    case 'reason_enables_report': c.check('editing the reason does not toggle leave', before.leaveRoom === after.leaveRoom, detail); break;
    case 'toggle_leave': c.check('the reason remains unchanged', before.reason === after.reason, detail); break;
    case 'report_only_success':
      c.check('reporting completes before the success result', after.reportAction === 'success' &&
        effects().length === 1 && effects()[0].effect === 'report_room' && effects()[0].result === 'success', detail);
      break;
    case 'report_then_leave':
      c.check('leave is attempted only after reporting succeeds', same(after.effects, ['report_room', 'leave_room']) &&
        effects()[0].result === 'success', detail);
      break;
    case 'blank_reason_disabled': c.check('leave preference remains selected', before.leaveRoom === true && after.leaveRoom === true, detail); break;
    case 'report_failure_stops_leave': c.check('form values survive the failure', before.reason === after.reason && before.leaveRoom === after.leaveRoom, detail); break;
    case 'leave_failure_is_partial': {
      const reportCalls = after.reportCalls;
      const leaveCalls = after.leaveCalls;
      await action({ name: 'retry' });
      const retried = projection();
      c.record('invariant_retry_probe', { state: retried, requests: copy(requests) });
      c.check('the successful report is remembered', retried.reportCalls === reportCalls &&
        retried.leaveCalls === leaveCalls + 1 && retried.reportAction === 'success', { after, retried, requests: copy(requests) });
      break;
    }
    case 'retry_leave_only': c.check('the report is never submitted twice', before.reportCalls === 1 && after.reportCalls === before.reportCalls, detail); break;
    case 'clear_failure_keeps_form': c.check('clearing the error emits no network effect', same(before.effects, after.effects), detail); break;
  }
  c.record('external_client_boundary', { requests: copy(requests),
    note: 'Only the ReportingRoomClient boundary is scripted; RoomFlow, presenters and service are production code.' });
}

async function verification(c) {
  const g = c.caseSpec.given;
  const key = c.caseSpec.key;
  const event = c.caseSpec.event;
  const userId = g.request?.userId || g.profileUserId || g.userId || '@alice:example.org';
  const roomId = '!room:example.org';
  const words = g.sas || ['Dog', 'Tree', 'Rocket'];
  let m;
  try { m = await c.module(['UserVerificationFeature'], 'UserVerificationPresenter'); }
  catch (error) {
    if (!(error instanceof Unsupported)) throw error;
    m = await c.module(['UserProfileFeature'], 'UserProfilePresenter');
  }
  const effects = [];
  const recordEffect = (effect, args) => {
    const item = { effect, args: copy(args) };
    effects.push(item);
    c.record('verification_gateway', item);
  };
  let p;
  let profile;
  let service;
  let identity;
  let alternate = false;
  let request;
  const normalizeIdentity = (value) => value === 'trusted' ? 'verified' : value;
  let identitySnapshot;
  let dispatch;
  if (typeof m.UserVerificationPresenter === 'function') {
    const gateway = new m.VerificationGateway();
    for (const [method, effect] of Object.entries({
      requestUserVerification: 'request_user_verification', requestCurrentSessionVerification: 'request_current_session_verification',
      startVerification: 'start_verification', approveVerification: 'approve_verification', declineVerification: 'decline_verification',
      cancelVerification: 'cancel_verification', resetVerification: 'reset_verification'
    })) {
      if (typeof gateway[method] === 'function') gateway[method] = (...args) => recordEffect(effect, args);
    }
    request = new m.VerificationRequest(g.request?.type || 'user', userId);
    identity = new m.IdentityStateStore(userId, g.identityState || 'unverified');
    p = new m.UserVerificationPresenter(request, gateway, identity);
    identitySnapshot = () => ({ identityState: identity.identityState, warningVisible: read(identity, 'warningVisible') });
    dispatch = (name) => {
      const methods = {
        request_verification: 'requestVerification', mark_accepted: 'remoteAcceptedRequest', start_sas_verification: 'startSasVerification',
        receive_challenge: 'receiveChallenge', accept_challenge: 'acceptChallenge', decline_challenge: 'declineChallenge',
        verification_finished: 'verificationFinished', cancel: 'cancel', reset: 'reset', sdk_failure: 'verificationFailed'
      };
      if (!methods[name]) throw new Unsupported(`No verification API for ${name}`);
      return call(p, [methods[name]], ...(name === 'receive_challenge' ? [words.slice()] : []));
    };
  } else {
    alternate = true;
    if (typeof m.VerificationService !== 'function' || typeof m.IdentityService !== 'function') {
      const legacy = new m.UserProfilePresenter(new m.UserProfileGateway());
      c.snapshot = () => copy({ userId: legacy.userId, displayName: legacy.displayName, blocked: legacy.blocked, gateway: legacy.gateway });
      c.record('legacy_surface', { exportName: 'UserProfilePresenter', state: c.snapshot() });
      throw new Unsupported('Profile presenter has no executable verification service or identity store.');
    }
    service = new m.VerificationService();
    identity = new m.IdentityService();
    const gateway = new m.UserProfileGateway();
    for (const [method, effect] of Object.entries({
      startUserVerification: 'request_user_verification', startSelfSessionVerification: 'request_current_session_verification',
      dispatchSasApprove: 'approve_verification', dispatchSasDecline: 'decline_verification', dispatchCancel: 'cancel_verification', dispatchReset: 'reset_verification'
    })) {
      if (typeof gateway[method] === 'function') gateway[method] = (...args) => recordEffect(effect, args);
    }
    profile = new m.UserProfilePresenter(gateway, service, identity);
    if (profile.userId !== userId) throw new Unsupported('Profile target cannot be configured through its public API.');
    call(identity, ['observeIdentityChange'], userId, 'Alice', roomId, g.identityState || 'unknown');
    identitySnapshot = () => ({
      identityState: normalizeIdentity(identity.getIdentityState(userId, roomId)),
      warningVisible: identity.hasViolation(userId, roomId)
    });
    dispatch = (name) => {
      if (name === 'request_verification' || name === 'verify_user_from_profile') {
        p = call(profile, ['startUserVerification']);
        return;
      }
      if (!p) throw new Unsupported('No active production verification session.');
      return call(profile, ['applyEvent'], p, name, { emojis: words.slice(), numbers: [1, 2, 3], otherDeviceId: 'remote-device' });
    };
  }
  const count = (effect) => effects.filter((item) => item.effect === effect).length;
  // VerificationSession calls the idle pre-request stage "idle" and the
  // post-request, pre-acceptance stage "initial". Bind those protocol stages,
  // retaining the raw state in evidence; do not normalize its reset failure.
  const sessionStep = () => ({ idle: 'initial', initial: 'awaiting_other_device_response' })[p?.state] ?? p?.state;
  const snapshot = () => copy({
    step: p?.step ?? sessionStep(),
    rawStep: p?.step ?? p?.state,
    replyState: p?.replyState,
    sas: Array.isArray(p?.sas) ? p.sas : p?.sas?.emojis,
    request: p?.request || (p ? { type: p.requestType, userId: p.targetUserId } : undefined),
    ...identitySnapshot(),
    requestCalls: count('request_user_verification'), currentSessionCalls: count('request_current_session_verification'),
    startCalls: count('start_verification'), approveCalls: count('approve_verification'), declineCalls: count('decline_verification'), cancelCalls: count('cancel_verification'),
    effects: effects.map((item) => item.effect)
  });
  c.snapshot = snapshot;
  if (key === 'identity_violation_surfaces') {
    if (!alternate) {
      c.before();
      c.observed = snapshot();
      c.after();
      c.missing('Cross-surface identity rendering and unrelated-member observations require native UI or a multi-member production store.');
      return;
    }
    const other = '@bob:example.org';
    call(identity, ['observeIdentityChange'], other, 'Bob', roomId, 'trusted');
    const beforeOther = identity.getIdentityState(other, roomId);
    c.before();
    call(identity, ['observeIdentityChange'], userId, 'Alice', roomId, g.identityState);
    c.observed = snapshot();
    c.after();
    const afterOther = identity.getIdentityState(other, roomId);
    c.check('unrelated member identities are unchanged', whenObserved([beforeOther, afterOther], () => beforeOther === afterOther), { beforeOther, afterOther });
    c.missing('Profile badge, timeline warning, member warning and verify-action visibility have no exported UI projection.');
    return;
  }
  if (key === 'profile_routes_user_request') {
    c.before();
    if (alternate) {
      await dispatch(event.name);
      c.observed = snapshot();
      const self = call(service, ['createSelfSessionVerification']);
      c.check('self-session verification remains a distinct request type', whenObserved([p.requestType, self.requestType], () => p.requestType !== self.requestType && self.targetUserId !== userId), { user: c.observed.request, self: { type: self.requestType, userId: self.targetUserId } });
    }
    c.after();
    c.missing('The profile navigation route is not exposed by an executable production navigation API.');
    return;
  }
  if (event.name !== 'request_verification') {
    await dispatch('request_verification');
    if (g.step === 'ready' || g.step === 'verifying' || key === 'challenge_is_stable') {
      await dispatch('mark_accepted');
      if (g.step !== 'ready') await dispatch('start_sas_verification');
    }
    if (g.step === 'verifying') {
      await dispatch('receive_challenge');
      // The alternate API names the pre-reply stage awaiting_other_device_response.
      // Only completion fixtures need a real accepted reply first.
      if (event.name === 'verification_finished') await dispatch('accept_challenge');
    }
    if (g.step === 'canceled') await dispatch('sdk_failure');
  }
  const before = snapshot();
  const effectOffset = effects.length;
  c.before();
  await dispatch(event.name);
  c.observed = snapshot();
  const emitted = effects.slice(effectOffset);
  if (emitted.length) c.observed.effect = last(emitted).effect;
  const userRequest = last(effects, (item) => item.effect === 'request_user_verification');
  if (userRequest) c.observed.userId = userRequest.args[0];
  const reset = emitted.find((item) => item.effect === 'reset_verification');
  if (reset?.args.length) c.observed.cancelPending = reset.args[0];
  c.after();
  const after = c.observed;
  const detail = { before, after, emitted };
  switch (key) {
    case 'request_targets_user': c.check('current-session verification is not requested', after.currentSessionCalls === 0, detail); break;
    case 'start_sas_after_acceptance': {
      const active = alternate ? service.getActiveSession() === p && p.isActive() : same(before.request, after.request) && after.step !== 'canceled' && after.step !== 'completed';
      c.check('the target user request remains active', active && after.request?.userId === userId, detail);
      if (!emitted.some((item) => item.effect === 'start_verification')) c.missing('SAS-start state changed, but this API exposes no external start-verification dispatch.');
      break;
    }
    case 'challenge_is_stable': {
      await flush();
      const settled = snapshot();
      c.check('the challenge data is preserved until a response is sent', same(after.sas, words) && same(after.sas, settled.sas), { after, settled });
      break;
    }
    case 'accept_challenge_once': {
      await dispatch('accept_challenge');
      const duplicate = snapshot();
      c.record('duplicate_accept_probe', duplicate);
      c.check('the SAS challenge is unchanged', whenObserved([before.sas, after.sas, duplicate.sas], () => same(before.sas, after.sas) && same(after.sas, duplicate.sas) && duplicate.approveCalls === after.approveCalls), { before, after, duplicate });
      break;
    }
    case 'decline_challenge_once': {
      await dispatch('decline_challenge');
      const duplicate = snapshot();
      c.record('duplicate_decline_probe', duplicate);
      c.check('the user is not marked verified', whenObserved([after.identityState, duplicate.identityState], () => after.identityState !== 'verified' && duplicate.identityState !== 'verified' && duplicate.declineCalls === after.declineCalls), { before, after, duplicate });
      break;
    }
    case 'finish_clears_violation': c.check('the warning clears only after successful completion', before.warningVisible === true && before.identityState === 'verification_violation' && after.step === 'completed' && after.warningVisible === false, detail); break;
    case 'local_cancel': c.check('cancellation never marks the user verified', whenObserved([before.identityState, after.identityState], () => after.identityState !== 'verified' && before.identityState === after.identityState), detail); break;
    case 'failure_reset':
      c.check('reset creates no false success', whenObserved([after.step, after.identityState], () => after.step !== 'completed' && after.identityState !== 'verified'), detail);
      if (after.cancelPending === undefined) c.missing('Reset dispatch exposes no cancelPending argument or production projection.');
      break;
  }
  if (['challenge_is_stable', 'accept_challenge_once', 'decline_challenge_once'].includes(key) && after.replyState === undefined) {
    c.missing('The verification API exposes no replyState; response counters cannot substitute for a loading-state observation.');
  }
}

async function joinRoom(c) {
  let m;
  try { m = await c.module(['JoinRoomByAddressFeature', 'JoinRoomByAddress/JoinRoomByAddressPresenter', 'ChatFeature'], 'JoinRoomByAddressPresenter'); }
  catch (error) {
    await legacySurface(c, ['CreateRoomBase'], 'CreateRoomBasePresenter');
    throw error;
  }
  const g = c.caseSpec.given;
  const event = c.caseSpec.event;
  const key = c.caseSpec.key;
  const requests = [];
  const updates = [];
  const navigation = [];
  const gatewayScheduler = typeof m.TimerTaskScheduler === 'function';
  const navigator = typeof m.JoinRoomNavigator === 'function' ? new m.JoinRoomNavigator() :
    gatewayScheduler ? { addressFlowVisible: true, openRoomCount: 0, openedRoomId: null, openedServers: null,
      async openRoom(...args) {
        this.openRoomCount++;
        this.openedRoomId = args[0];
        this.openedServers = args.length > 1 ? args[1] : null;
        this.addressFlowVisible = false;
        navigation.push({ method: 'openRoom', args: copy(args) });
        c.record('external_navigation_requested', last(navigation));
      },
      async back() {
        this.addressFlowVisible = false;
        navigation.push({ method: 'back', args: [] });
        c.record('external_navigation_requested', last(navigation));
      }
    } : undefined;
  if (navigator && !gatewayScheduler) {
    for (const method of ['dismissJoinRoomByAddress', 'openRoom']) {
      const original = navigator[method].bind(navigator);
      navigator[method] = (...args) => {
        navigation.push({ method, args: copy(args) });
        c.record('production_navigation', last(navigation));
        return original(...args);
      };
    }
    if (key !== 'entry_opens_address_flow') call(navigator, ['showJoinRoomByAddress']);
  }
  function lookup(alias, ...args) {
    const pending = deferred();
    const request = { alias, args, pending, started: Date.now() };
    requests.push(request);
    c.record('resolver_requested', { alias, args: args.map((value) => typeof value === 'object' ? { cancelled: value?.cancelled } : value) });
    return pending.promise;
  }
  let resolver = { resolveRoomAlias: lookup, resolve: lookup,
    async getRoom(roomId) { return { roomId, name: '', topic: '', memberIds: [], direct: false }; } };
  // Preserve the alternate production resolver's timeout/cancellation policy.
  if (!navigator) {
    const rm = await c.module(['JoinRoomByAddress/DelegatingRoomAliasResolver'], 'DelegatingRoomAliasResolver');
    resolver = new rm.DelegatingRoomAliasResolver(lookup);
  }
  const p = gatewayScheduler ? new m.JoinRoomByAddressPresenter(resolver, navigator, new m.TimerTaskScheduler()) :
    new m.JoinRoomByAddressPresenter(resolver, navigator);
  const addressState = () => p.addressState ?? p.state;
  const snapshot = () => copy({
    address: p.address,
    addressState: addressState() === 'not_found' ? 'room_not_found' : addressState(),
    visibleAddressState: read(p, 'visibleAddressState'),
    validationRequested: p.validationRequested,
    resolvedRoom: p.resolvedRoom,
    pendingNavigation: p.pendingNavigation,
    addressFlowVisible: navigator?.addressFlowVisible,
    navigationCount: navigator?.openRoomCount,
    openRoomCount: navigator?.openRoomCount,
    ...(navigator ? { dismissAddressFlow: !navigator.addressFlowVisible } : {}),
    openRoom: navigator?.openRoomCount ? { roomIdOrAlias: navigator.openedRoomId, serverNames: navigator.openedServers } : undefined,
    errorVisible: read(p, 'errorVisible'), editingEnabled: read(p, 'editingEnabled', 'canEdit'),
    closed: p.closed ?? p.dismissed, resolveCalls: requests.length
  });
  c.snapshot = snapshot;
  function update(value) {
    const result = call(p, ['updateAddress'], value);
    if (result && typeof result.then === 'function') {
      // Attach rejection handling immediately, including work invalidated by a later edit.
      updates.push(Promise.resolve(result).catch((error) => {
        c.missing(`Asynchronous production update failed: ${error.message || error}`);
        c.record('production_update_error', { message: String(error.message || error) });
      }));
    }
    return result;
  }
  async function settle(value) {
    const request = last(requests);
    if (!request) throw new Unsupported('No alias-resolution request reached the external gateway.');
    request.pending.resolve(value);
    await flush();
  }
  async function waitForRequest() {
    await delay(330);
    await flush();
    if (!requests.length) throw new Unsupported('Alias resolution did not reach the external gateway after the debounce window.');
  }
  const continueFlow = () => call(p, ['continue', 'requestContinue']);
  try {
    if (key === 'entry_opens_address_flow') {
      c.before();
      if (navigator) call(navigator, ['showJoinRoomByAddress']);
      c.observed = snapshot();
      c.after();
      c.missing('Start-chat entry action and availability of create-room/direct-message controls require native UI observation.');
      return;
    }
    if (key === 'update_trims_and_debounces') {
      // Keep an older request pending, then exercise the canonical edit.
      update('#old:example.org');
      await waitForRequest();
      const stale = last(requests);
      c.before();
      const started = Date.now();
      update(event.value);
      const immediate = snapshot();
      c.observed = { ...immediate, addressStateBefore300ms: immediate.addressState };
      stale.pending.resolve({ roomId: '!old:example.org', servers: ['example.org'] });
      await flush();
      const afterStale = snapshot();
      c.record('stale_resolution_completed', afterStale);
      c.check('each address change invalidates the previous resolution', afterStale.address === immediate.address && !afterStale.resolvedRoom && afterStale.navigationCount !== 1 && !afterStale.pendingNavigation, { immediate, afterStale });
      await delay(330);
      const latest = last(requests);
      c.record('debounce_wall_clock', { elapsedMs: latest.started - started, requests: requests.length });
      c.after();
      c.missing('Exact resolveAfterMs is unavailable without a loader-provided controllable clock; wall-clock timing is recorded without rounding to the contract.');
      return;
    }
    update(g.address || '#team:example.org');
    let eventStarted = false;
    if (event.name === 'debounce_elapsed') {
      c.before();
      eventStarted = true;
      await waitForRequest();
    } else if (key === 'invalid_after_continue') {
      await delay(330);
    } else {
      await waitForRequest();
    }
    if (key === 'found_then_continue_navigates') {
      await settle({ roomId: g.roomId, servers: g.servers.slice() });
    }
    const before = snapshot();
    if (!eventStarted) c.before();
    switch (event.name) {
      case 'continue': continueFlow(); break;
      case 'debounce_elapsed': break;
      case 'continue_then_resolution_succeeds':
        continueFlow();
        c.record('continue_while_resolving', snapshot());
        await settle({ roomId: event.roomId, servers: event.servers.slice() });
        break;
      case 'resolve_returns_empty_or_error':
        last(requests).pending.reject(new Error('Directory lookup failed'));
        await flush();
        break;
      case 'resolve_timeout':
        await delay(event.elapsedSeconds * 1000 + 30);
        await flush();
        break;
      case 'dismiss': call(p, ['dismiss']); break;
      default: throw new Unsupported(`Unknown join event: ${event.name}`);
    }
    c.observed = snapshot();
    if (event.name === 'debounce_elapsed' && requests.length) {
      c.observed.effect = 'resolve_room_alias';
      c.observed.alias = last(requests).alias;
    }
    c.after();
    const after = c.observed;
    const detail = { before, after, navigation };
    switch (key) {
      case 'invalid_after_continue': {
        const visibleBefore = before.visibleAddressState ?? before.addressState;
        c.check('invalid feedback is suppressed before validation is requested', before.validationRequested === false && visibleBefore !== 'invalid', detail);
        if (after.errorVisible === undefined) c.missing('Invalid-error visibility is native UI state, with no exported errorVisible getter.');
        break;
      }
      case 'valid_address_resolves': {
        const validCalls = requests.length;
        update('not-a-room');
        await delay(330);
        const invalid = snapshot();
        c.record('invalid_alias_probe', invalid);
        c.check('only syntactically valid room aliases are resolved', validCalls === 1 && requests.length === validCalls, { valid: after, invalid });
        break;
      }
      case 'found_then_continue_navigates':
        if (navigator) c.check('room navigation happens once', after.navigationCount === 1 && navigation.filter((item) => item.method === 'openRoom').length === 1, detail);
        break;
      case 'continue_waits_for_resolution': {
        // A second request may be scheduled, rather than dispatched synchronously.
        await delay(330);
        const settled = snapshot();
        c.record('duplicate_resolution_probe', settled);
        c.check('continue does not issue a second alias-resolution request', after.resolveCalls === before.resolveCalls && settled.resolveCalls === before.resolveCalls, { ...detail, settled });
        break;
      }
      case 'not_found_recovers':
        if (navigator) c.check('resolution failures do not close the flow', after.addressFlowVisible === true && after.navigationCount === 0, detail);
        else c.check('resolution failures do not close the flow', before.closed === false && after.closed === false && !after.pendingNavigation, detail);
        if (after.errorVisible === undefined || after.editingEnabled === undefined) c.missing('Error visibility and editor enabled state require native UI observation.');
        break;
      case 'timeout_recovers': {
        c.check('the resolver cannot leave the UI loading indefinitely', whenObserved([before.addressState, after.addressState], () => before.addressState === 'resolving' && after.addressState !== 'resolving'), detail);
        const previousCalls = requests.length;
        update('#retry:example.org');
        await delay(330);
        c.observed.retryByEditing = requests.length > previousCalls && p.address === '#retry:example.org';
        c.record('retry_by_editing_probe', snapshot());
        break;
      }
      case 'dismiss_closes_flow':
        await settle({ roomId: '!late:example.org', servers: ['example.org'] });
        await delay(330);
        if (navigator) c.check('dismissing never joins a room', navigator.openRoomCount === 0, { after, afterLateResult: snapshot() });
        break;
    }
    if (!navigator && ['found_then_continue_navigates', 'continue_waits_for_resolution', 'dismiss_closes_flow'].includes(key)) {
      c.missing('The presenter exposes a pending navigation intent/closed flag, but actual flow dismissal and room navigation are performed only by native UI.');
    }
  } finally {
    // Invalidate callbacks before releasing pending external responses.
    c.record('fixture_cleanup', { operation: 'dismiss and release external alias responses', timerControl: 'real scheduler; no controllable production clock supplied' });
    if (typeof p.dismiss === 'function') p.dismiss();
    for (const request of requests) request.pending.resolve(undefined);
    await flush();
  }
}

async function deactivation(c) {
  const g = c.caseSpec.given;
  const event = c.caseSpec.event;
  const key = c.caseSpec.key;
  let m;
  try { m = await c.module(['AccountDeactivationFeature', 'AccountDeactivation'], 'AccountDeactivationPresenter'); }
  catch (error) {
    if (!(error instanceof Unsupported)) throw error;
    try { m = await c.module(['Deactivation'], 'DeactivationPresenter'); }
    catch (alternateError) {
      await legacySurface(c, ['PreferencesBase'], 'PreferencesBasePresenter');
      throw alternateError;
    }
  }
  const requests = [];
  const pendingMethods = [];
  let capability = g.serverCanDeactivateAccount ?? true;
  const external = {
    async restore() {},
    async canDeactivateAccount() { c.record('capability_response', { value: capability }); return capability; },
    deactivateAccount(password, eraseData) {
      const pending = deferred();
      requests.push({ payload: { password, eraseData }, pending });
      c.record('deactivation_gateway', { payload: last(requests).payload });
      return pending.promise;
    }
  };
  const serviceBacked = typeof m.AccountDeactivationPresenter === 'function';
  const clientBacked = serviceBacked && typeof m.AccountDeactivationPresenter.prototype.refreshAvailability === 'function' &&
    typeof m.AccountDeactivationPresenter.prototype.openForm === 'function';
  let completionCallbacks = 0;
  const p = serviceBacked ? new m.AccountDeactivationPresenter(external,
    clientBacked ? () => { completionCallbacks++; } : external) : new m.DeactivationPresenter();
  if (clientBacked) {
    await p.refreshAvailability();
    p.openForm();
    c.record('production_open_form_prefix', { action: p.action, formOpen: p.formOpen, available: p.available });
  }
  function submit(isRetry) {
    const pending = call(p, ['deactivateAccount', 'requestDeactivation'], isRetry);
    if (pending && typeof pending.then === 'function') pendingMethods.push(pending);
  }
  async function complete(success) {
    if (serviceBacked) {
      const pending = last(requests)?.pending;
      if (!pending) throw new Unsupported('No actual deactivation service request is pending.');
      if (success) pending.resolve();
      else pending.reject(new Error('Fixture gateway failure'));
      await flush();
    } else {
      await call(p, success ? ['reportSuccess'] : ['reportFailure'], ...(success ? [] : ['Fixture gateway failure']));
    }
  }
  const snapshot = () => copy({
    action: clientBacked && p.action === m.DEACTIVATION_SUCCEEDED ? 'success' : p.action,
    rawAction: p.action, completionCallbacks, password: p.password, eraseData: p.eraseData,
    submitEnabled: read(p, 'submitEnabled', 'canSubmit'),
    domainCanSubmit: read(p, 'canSubmit'),
    confirmationVisible: read(p, 'confirmationVisible', 'confirmationPromptVisible'),
    retryEnabled: read(p, 'retryEnabled', 'canRetry'),
    requestCount: serviceBacked ? requests.length : undefined,
    payload: serviceBacked ? last(requests)?.payload : undefined,
    requestIntentCount: !serviceBacked ? p.requestCount : undefined,
    requestIntentPayload: !serviceBacked ? read(p, 'getLastRequestPayload') : undefined,
    formControlsDisabled: read(p, 'formControlsDisabled'),
    canDeactivateAccount: read(p, 'canDeactivateAccount', 'serverCanDeactivateAccount'),
    deactivateEntryVisible: read(p, 'deactivateEntryVisible'), entryStyle: read(p, 'entryStyle'),
    signedOut: p.signedOut, sessionEnded: p.sessionEnded
  });
  c.snapshot = snapshot;
  try {
    if (key === 'capability_gates_entry') {
      c.before();
      if (typeof p.loadCapability === 'function') await p.loadCapability();
      else await call(p, ['setServerCapability'], capability);
      c.observed = snapshot();
      c.after();
      capability = false;
      if (typeof p.loadCapability === 'function') await p.loadCapability();
      else await call(p, ['setServerCapability'], capability);
      const disabled = snapshot();
      c.record('unsupported_capability_probe', disabled);
      if (disabled.deactivateEntryVisible !== undefined) c.check('the entry is hidden when the server reports unsupported', disabled.deactivateEntryVisible === false, disabled);
      if (c.observed.deactivateEntryVisible === undefined || c.observed.entryStyle === undefined) c.missing('Settings entry visibility and destructive styling exist only in native ArkUI; the capability value alone cannot prove them.');
      return;
    }
    // Opening the form must observe its constructor defaults, without fixing
    // them by replaying the contract's given values through setters first.
    if (event.name !== 'open_deactivation') {
      if (g.password !== undefined) await call(p, ['setPassword'], g.password);
      else if (['loading', 'confirming', 'failure'].includes(g.action)) await call(p, ['setPassword'], 'secret');
      if (g.eraseData !== undefined) await call(p, ['setEraseData'], g.eraseData);
    }
    if (['confirming', 'loading', 'failure'].includes(g.action)) {
      submit(false);
      if (g.action !== 'confirming') submit(false);
      if (g.action === 'failure') await complete(false);
      c.record('fixture_action', snapshot());
    }
    const before = snapshot();
    c.before();
    switch (event.name) {
      case 'open_deactivation': break;
      case 'set_password': await call(p, ['setPassword'], event.value); break;
      case 'set_erase_data': await call(p, ['setEraseData'], event.value); break;
      case 'deactivate_account': submit(event.isRetry); break;
      case 'deactivation_succeeds': await complete(true); break;
      case 'deactivation_fails': await complete(false); break;
      case 'close_dialogs': await call(p, ['closeDialogs']); break;
      default: throw new Unsupported(`Unknown deactivation event: ${event.name}`);
    }
    c.observed = snapshot();
    if (serviceBacked && c.observed.requestCount > before.requestCount) c.observed.effect = 'deactivate_account';
    c.after();
    const after = c.observed;
    const detail = { before, after };
    switch (key) {
      case 'default_form_blocks_submit': c.check('no deactivation request is sent on entry', whenObserved([after.requestCount], () => after.requestCount === 0), detail); break;
      case 'password_enables_submit': c.check('pasted newline characters are removed', typeof after.password === 'string' && !after.password.includes('\n') && !after.password.includes('\r'), detail); break;
      case 'erase_data_option': c.check('the password is unchanged', whenObserved([before.password, after.password], () => before.password === after.password), detail); break;
      case 'first_submit_confirms':
        c.check('a destructive request is never sent before confirmation', whenObserved([before.requestCount, after.requestCount], () => before.requestCount === 0 && after.requestCount === 0), detail);
        if (after.confirmationVisible === undefined) c.missing('Confirmation visibility has no exported production getter.');
        break;
      case 'confirm_sends_payload':
        if (after.formControlsDisabled !== undefined) c.check('form controls are disabled while loading', after.action === 'loading' && after.formControlsDisabled === true, detail);
        else c.missing('Loading-state form-control disabling is only observable in native ArkUI.');
        if (!serviceBacked) c.missing('The presenter records a request intent but exposes no external deactivation dispatch; effect is unobserved.');
        break;
      case 'success_completes': c.check('the request is not duplicated', whenObserved([before.requestCount, after.requestCount], () => before.requestCount === 1 && after.requestCount === before.requestCount), detail); break;
      case 'failure_preserves_form':
        c.check('failure does not report completion', whenObserved([after.action], () => after.action !== 'success' && after.signedOut !== true && after.sessionEnded !== true), detail);
        if (after.retryEnabled === undefined) c.missing('Retry-enabled state has no exported production getter.');
        break;
      case 'retry_bypasses_confirmation':
        c.check('retry reuses the preserved form payload', whenObserved([before.payload, after.payload, before.requestCount, after.requestCount], () => same(before.payload, after.payload) && after.requestCount === before.requestCount + 1), detail);
        if (after.confirmationVisible === undefined) c.missing('Confirmation visibility has no exported production getter.');
        break;
      case 'close_dialog_resets_action': c.check('dismissing an error does not submit again', whenObserved([before.requestCount, after.requestCount], () => before.requestCount === after.requestCount), detail); break;
    }
    if (!serviceBacked) c.record('observation_boundary', { requestIntentCount: 'Production presenter intent counter; external requestCount is unobserved.', requestIntentPayload: 'Production getLastRequestPayload(); not an observed service payload.' });
  } finally {
    c.record('fixture_cleanup', { operation: 'release external deactivation responses' });
    for (const request of requests) request.pending.resolve();
    await flush();
    for (const pending of pendingMethods) pending.catch((error) => c.record('cleanup_deactivation_error', { message: String(error.message || error) }));
  }
}

async function legacySurface(c, candidates, exportName, argumentsFor = () => []) {
  try {
    const exports = await c.module(candidates, exportName);
    const presenter = new exports[exportName](...argumentsFor(exports));
    const state = copy(presenter);
    // Legacy constructors can be executed, but absent feature APIs cannot be
    // replaced by similarly named, semantically unrelated base actions.
    c.snapshot = () => state;
    c.record('legacy_surface', { exportName, state, eventUnavailable: c.caseSpec.event.name });
  } catch (error) {
    c.record('legacy_surface_unavailable', { exportName, reason: String(error.message || error) });
  }
}

async function probeNativeRoot(c) {
  const ui = c.native?.ui;
  if (typeof ui?.observe !== 'function') return;
  const surfaces = {
    '12_report_room': {
      anchors: ['report_room_reason', 'open_report_room', 'leave_room'],
      entries: ['report_room_reason', 'report_reason_input', 'open_report_room', 'submit_report_room', 'submit_report'],
      controls: ['report_room_leave_toggle', 'leave_room_toggle', 'retry_leave_room', 'retry_report_room', 'retry_leave_only']
    },
    '13_user_verification': {
      anchors: ['verify_user_action', 'start_user_verification', 'start_direct_message'],
      entries: ['verify_user_action', 'start_user_verification'],
      controls: ['profile_verification_violation', 'identity_violation_badge', 'timeline_identity_warning', 'room_member_identity_warning', 'accept_sas_challenge', 'decline_sas_challenge']
    },
    '14_join_room_by_address': {
      anchors: ['join_room_by_address', 'join_by_address_button', 'people_search_input', 'create_room_button'],
      entries: ['join_room_by_address', 'join_by_address_button'],
      controls: ['room_address_input', 'address_input', 'address_continue_button', 'join_room_continue']
    },
    '15_account_deactivation': {
      anchors: ['deactivate_account_entry', 'deactivation_password'],
      entries: ['deactivate_account_entry', 'deactivation_password'],
      controls: ['deactivate_submit']
    }
  };
  const surface = surfaces[c.taskId];
  if (!surface) return;
  const ids = [...surface.entries, ...surface.controls];
  try {
    let before;
    let anchor;
    for (const id of surface.anchors) {
      const candidate = await ui.observe(ids, id);
      if (candidate?.available === true && candidate.snapshot?.candidateRouteVerified === true) {
        before = candidate;
        anchor = id;
        break;
      }
    }
    if (!before) {
      c.record('native_root_unavailable', { reason: 'No verified candidate-route positive anchor. Unkeyed roots need the device UI suite; feature absence is not inferred.' });
      return;
    }
    function summarize(probe) {
      return {
        available: probe.available, route: probe.snapshot?.route, anchor: probe.anchor?.id,
        controls: probe.controls.map((control) => ({
          id: control.id, present: control.present, type: control.node?.$type,
          attributes: control.node?.$attrs ? {
            enabled: control.node.$attrs.enabled, visibility: control.node.$attrs.visibility,
            text: control.node.$attrs.text, label: control.node.$attrs.label,
            isOn: control.node.$attrs.isOn, content: control.node.$attrs.content
          } : undefined
        }))
      };
    }
    c.record('native_root_before_observation', summarize(before));
    const after = await ui.observe(ids, anchor);
    c.record('native_root_after_observation', summarize(after));
    if (after?.available !== true || after.snapshot?.candidateRouteVerified !== true) return;
    const hasEntry = (probe) => surface.entries.some((id) => probe.controls.some((control) => control.id === id && control.present === true));
    const absent = (probe) => surface.entries.every((id) => probe.controls.some((control) => control.id === id && control.present === false));
    const stablePresence = hasEntry(before) && hasEntry(after);
    const stableAbsence = absent(before) && absent(after);
    c.nativeUIProof = {
      observed: true, observationLevel: 'native_candidate_ui', scope: 'root controls only',
      transitionObserved: false, before: summarize(before), after: summarize(after),
      reason: 'The real candidate root was inspected. Domain fixtures below use a different presenter instance; these UI values do not fill canonical transition observations.'
    };
    if (stablePresence || stableAbsence) c.prerequisiteChecks = [{
      description: 'The feature is reachable from the rendered candidate root',
      passed: stablePresence ? true : null,
      status: stablePresence ? 'observed_present' : 'observed_absent_unscored',
      diagnosticOnly: true,
      canonicalGivensEstablished: false,
      canonicalEventExecuted: false,
      observed: { caseId: c.caseSpec.caseId, traceDigest: c.caseSpec.traceDigest,
        requestedEvent: c.caseSpec.event, anchor, before: summarize(before), after: summarize(after) },
      scope: 'native_root_feature_prerequisite',
      reason: stableAbsence ? 'Feature controls are absent on the confirmed production root; no downstream state or API failure is fabricated.' : 'Feature entry or form is rendered.'
    }];
  } catch (error) {
    c.record('native_root_unavailable', { reason: String(error.message || error) });
  }
}

async function reportRoomNativeBlank(args) {
  const native = args.native || args.context?.native;
  const evidence = [];
  const result = { observed: {}, evidence, invariantChecks: [], observationLevel: 'native_candidate_ui',
    integrationBoundary: { entry: 'original page native UI with same-module presenter prototype observer',
      appEntryExecuted: false, externalServicesExecuted: false } };
  try {
    const raw = await native.runTasks12To15UI(args.caseSpec);
    evidence.push({ nativePageTransition: copy(raw) });
    for (const frame of raw.frames || []) {
      args.trace?.(`native_ui_${frame.label}`, copy(frame));
    }
    const spec = args.caseSpec;
    const before = raw.frames?.find(frame => frame.label === 'before_event');
    const after = raw.frames?.find(frame => frame.label === 'after_event');
    const source = raw.productionSources?.find(item => item.path === FEATURES + 'ReportRoomFeature.ets');
    const page = raw.productionSources?.find(item => item.path === 'entry/src/main/ets/pages/Index.ets');
    if (raw.taskId !== args.taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest ||
      !source || !page || ![source, page].every(item => /^[a-f0-9]{64}$/.test(item.sha256)) ||
      raw.entryExecuted !== true || raw.eventExecuted !== true || !before || !after ||
      !raw.sessionId || before.sessionId !== raw.sessionId || after.sessionId !== raw.sessionId ||
      before.bundleName !== native.bundleName || after.bundleName !== native.bundleName ||
      !(before.sequence < after.sequence)) throw new Unsupported('Original native page identity, source provenance, or event frames are incomplete.' +
        (raw.failure ? ` Native collection failure at ${raw.failure.stage}: ${raw.failure.message}` :
          raw.unsupported ? ` Native diagnostic: ${raw.unsupported}` : ''));
    result.integrationBoundary.appEntryExecuted = true;
    const controls = frame => Object.fromEntries(frame.controls.map(control => [control.selector, control]));
    for (const frame of [before, after]) {
      const p = frame.presenterEvidence, ui = controls(frame);
      if (!p?.available || p.instanceCount !== 1 || typeof p.instanceId !== 'number' ||
        !['report reason', 'leave preference', 'report submit'].every(name => ui[name]?.present && ui[name].visible) ||
        p.reason !== ui['report reason'].text || p.leaveRoom !== ui['leave preference'].checked ||
        frame.observed.reason !== p.reason || frame.observed.leaveRoom !== p.leaveRoom ||
        typeof p.canReport !== 'boolean' || frame.observed.canReport !== p.canReport ||
        typeof ui['report submit'].enabled !== 'boolean' || frame.observed.submitEnabled !== ui['report submit'].enabled ||
        !p.calls?.some(call => call.completed && call.method === 'updateReason' && call.value === p.reason) ||
        !p.calls?.some(call => call.completed && call.method === 'toggleLeaveRoom')) {
        throw new Unsupported('Native controls and original same-page presenter evidence are incomplete or disagree.');
      }
    }
    if (before.presenterEvidence.instanceId !== after.presenterEvidence.instanceId ||
      !Object.entries(spec.given).every(([key, value]) => same(before.observed[key], value))) {
      throw new Unsupported('Canonical given or stable original presenter identity was not established.');
    }
    const setup = (raw.actions || []).filter(action => action.executed && action.sessionId === raw.sessionId && action.sequence < before.sequence);
    if (!setup.some(action => action.kind === 'input' && action.value === spec.given.reason) ||
      !setup.some(action => action.kind === 'click' && ['report_room_leave_toggle', 'leave_room_toggle'].includes(action.target))) {
      throw new Unsupported('Canonical blank/leave fixture was not established by actual UI actions.');
    }
    // Registers the immutable original feature's source hash with evaluateCase.
    // No exported constructor or method is invoked on a second instance.
    await args.load(FEATURES + 'ReportRoomFeature.ets');
    result.observed = copy(after.observed);
    result.invariantChecks.push({ description: 'leave preference remains selected',
      passed: before.observed.leaveRoom === true && after.observed.leaveRoom === true,
      observed: { before: copy(before), after: copy(after) } });
    result.nativeUI = { observed: true, transitionObserved: true, samePresenterInstance: true,
      productionSources: copy(raw.productionSources), sessionId: raw.sessionId };
  } catch (error) {
    result.unsupported = String(error.message || error);
  }
  return result;
}

async function runCase(args) {
  const native = args.native || args.context?.native;
  if (args.taskId === '13_user_verification' && args.caseSpec.key === 'profile_routes_user_request' &&
    typeof native?.evaluateTask13UI === 'function') return native.evaluateTask13UI(args);
  if (args.taskId === '12_report_room' && args.caseSpec.key === 'blank_reason_disabled' &&
    typeof native?.runTasks12To15UI === 'function') return reportRoomNativeBlank(args);
  const c = context(args);
  c.record('integration_boundary', {
    productionEntry: 'exported presenter constructor and methods',
    appEntryExecuted: false,
    nativeUIExecuted: false,
    externalServicesExecuted: false,
    gatewayCalls: 'production-to-injected-dependency calls only'
  });
  try {
    await probeNativeRoot(c);
    switch (args.taskId) {
      case '12_report_room': await reportRoom(c); break;
      case '13_user_verification': await verification(c); break;
      case '14_join_room_by_address': await joinRoom(c); break;
      case '15_account_deactivation': await deactivation(c); break;
      default: throw new Unsupported(`Task is outside this adapter: ${args.taskId}`);
    }
    return c.finish();
  } catch (error) {
    c.record('execution_unavailable', { name: error.name, message: String(error.message || error) });
    return c.finish(error);
  }
}

module.exports = { runCase };
