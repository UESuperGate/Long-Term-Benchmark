'use strict';

const page = 'entry/src/main/ets/pages/Index.ets';

const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
const requireEvidence = (condition, message) => { if (!condition) throw new Error(message); };
const visible = (frame, name) => !!frame?.controls?.find(control => control.name === name && control.visible);

function validateOwnerInventory(inventory) {
  requireEvidence(inventory?.complete === true && Array.isArray(inventory.nodes) &&
    inventory.nodeCount === inventory.nodes.length && inventory.nodes.length > 0, 'Incomplete actual UI inventory');
  const ids = new Set(['open_profile', 'open_timeline', 'open_members', 'profile_display_name', 'profile_user_id',
    'profile_verified_badge', 'profile_verification_violation', 'withdraw_verification_action', 'verify_user_action',
    'verification_unavailable', 'start_direct_message', 'toggle_block_user', 'verification_target_user',
    'verification_step', 'request_user_verification', 'start_sas_verification', 'verification_reply_loading',
    'accept_sas_challenge', 'decline_sas_challenge', 'reset_verification', 'verification_error',
    'cancel_verification', 'timeline_identity_warning', 'timeline_acknowledge_identity', 'room_member_identity_warning']);
  for (const node of inventory.nodes) {
    requireEvidence(!node.id || ids.has(node.id), 'Unknown/renamed production UI control: ' + node.id);
    if (!node.id && (node.clickable || node.longClickable || node.checkable || node.scrollable)) {
      requireEvidence((node.type === 'Button' && ['Alice', 'Bob'].includes(node.text)) || node.type === 'TextInput',
        'Unreviewed anonymous actionable production UI');
    }
    if (node.type === 'TextInput') requireEvidence(node.text === '' || ['Alice', 'Bob'].includes(node.text), 'Unknown native input binding');
  }
  return true;
}

function evaluatePageOwner(spec, raw) {
  raw.frames.forEach(frame => validateOwnerInventory(frame.uiInventory));
  const frame = label => {
    const matches = raw.frames.filter(item => item.label === label);
    requireEvidence(matches.length === 1, 'Actual checkpoint missing/duplicated: ' + label);
    return matches[0];
  };
  const first = frame('before_event'), last = frame('after_event');
  const initial = frame('initial_profile');
  requireEvidence(visible(initial, 'profile') && visible(initial, 'verify') && visible(initial, 'dm'),
    'Real common unverified profile prefix missing');
  const prefixes = raw.actions.filter(action => action.kind === 'canonical_prefix');
  requireEvidence(same(prefixes.map(action => action.name), (spec.setup?.actions || []).map(action => action.name)),
    'Original canonical operation prefix missing or reordered');
  const physical = { open_room_member_profile: 'openProfile', select_verify_user: 'verify',
    request_verification: 'request', start_sas_verification: 'start', accept_challenge: 'accept' };
  for (const prefix of prefixes) {
    const checkpoint = frame(prefix.frameLabel);
    requireEvidence(prefix.executed && prefix.sequence < checkpoint.sequence && prefix.sessionId === raw.sessionId,
      'Prefix receipt not bound to the actual native frame');
    if (physical[prefix.name]) requireEvidence(raw.actions.some(action => action.kind === 'click' &&
      action.target === physical[prefix.name] && action.executed && action.sequence > prefix.sequence &&
      action.sequence < checkpoint.sequence), 'Canonical prefix lacks its real production UI operation');
  }
  const input = item => item.pageObserver.sdkState;
  const ledger = last.pageObserver.ledger;
  requireEvidence(raw.semanticTier === 'android_equivalent_controlled_external_sdk' &&
    Array.isArray(ledger) && first.uiInventory?.complete && last.uiInventory?.complete,
    'Actual SDK ledger/full native tree missing');
  let before = first.pageObserver.state, after = last.pageObserver.state;
  if (spec.key === 'identity_violation_surfaces') {
    const profile = last, timeline = frame('after_identity_change_timeline'), members = frame('after_identity_change_members');
    const initialIdentity = input(first).identities.filter(item => item.userId !== '@alice:example.org');
    const finalIdentity = input(last).identities.filter(item => item.userId !== '@alice:example.org');
    requireEvidence(input(last).encryptedRoom === true && input(last).identities.some(item =>
      item.userId === spec.given.userId && item.identityState === spec.given.identityState),
    'Encrypted identity SDK given not established');
    const pending = frame('post_assertion_withdraw_pending_sdk');
    const restored = frame('post_assertion_withdraw_sdk_update');
    const withdrawal = pending.pageObserver.ledger.filter(item => item.kind === 'call' && item.method === 'withdrawVerification');
    requireEvidence(withdrawal.length === 1 && withdrawal[0].completed && same(withdrawal[0].args, ['@alice:example.org']) &&
      visible(pending, 'profileViolation') && !visible(restored, 'profileViolation') && visible(restored, 'verify') &&
      raw.withdrawPositiveControl?.effectDelegated && raw.withdrawPositiveControl.warningHeldUntilSdkUpdate,
    'Actual external withdrawal and independently delivered identity stream not verified');
    const observed = {
      profileBadge: visible(profile, 'profileViolation') ? 'verification_violation' :
        visible(profile, 'verifiedBadge') ? 'verified' : 'none',
      timelineWarning: visible(timeline, 'timelineWarning'), roomMemberWarning: visible(members, 'roomMemberWarning'),
      verifyActionVisible: visible(profile, 'verify'), withdrawVerificationActionVisible: visible(profile, 'withdraw'),
      profileWarningVisible: visible(profile, 'profileViolation')
    };
    const checks = spec.invariants.map(description => ({ description,
      passed: description === 'unrelated member identities are unchanged' ?
        initialIdentity.length === 1 && same(initialIdentity, finalIdentity) :
        description === 'verification-violation UI offers withdrawal instead of starting a new verification request' ?
          observed.withdrawVerificationActionVisible && !observed.verifyActionVisible : false,
      observed: { before: input(first), after: input(last), profile: profile.controls, timeline: timeline.controls, members: members.controls }
    }));
    // Keep exact canonical descriptions; no unknown invariant is treated as true.
    requireEvidence(spec.invariants.length === checks.length && checks.every(item =>
      ['unrelated member identities are unchanged', 'verification-violation UI offers withdrawal instead of starting a new verification request'].includes(item.description)),
    'Unbound canonical identity invariant');
    return { observed, invariantChecks: checks, before: input(first), after: input(last) };
  }
  requireEvidence(last.pageObserver.available && last.pageObserver.instanceCount === 1 &&
    after && after.sameService && after.sameRoom &&
    last.pageObserver.calls.some(call => call.method === 'attach' && call.presenterId === after.presenterId) &&
    ledger.some(item => item.kind === 'production_subscribe' && item.presenterId === after.presenterId &&
      item.serviceId === after.serviceId),
    'Not the actual attached page-owned presenter/service/identity');
  requireEvidence(raw.ownerCleanup?.calls?.some(call => call.method === 'dispose' && call.presenterId === after.presenterId) &&
    raw.ownerCleanup.ledger.some(item => item.kind === 'production_unsubscribe'), 'Original route-owner disposal/unsubscription missing');
  if (spec.key === 'profile_routes_user_request') {
    requireEvidence(visible(first, 'verify') && !visible(last, 'verify') && visible(last, 'request') &&
      visible(last, 'target') && visible(last, 'step'), 'Physical profile -> Verify page route absent');
    const observed = { route: 'verify_user', request: after.request };
    return { observed, before: { sdk: input(first), controls: first.controls }, after,
      invariantChecks: spec.invariants.map(description => ({ description,
        passed: description === 'self-session verification remains a distinct request type' &&
          last.pageObserver.requestTypes.user === 'user' && last.pageObserver.requestTypes.currentSession === 'current_session' &&
          after.request.type === 'user' && after.request.userId === spec.given.profileUserId &&
          after.currentSessionCalls === 0 && after.requestCalls === 0 && after.step === 'initial',
        observed: { request: after.request, profile: first.controls, route: last.controls, sdkLedger: ledger } })) };
  }
  requireEvidence(before && before.presenterId === after.presenterId && before.gatewayId === after.gatewayId &&
    before.identityId === after.identityId && before.serviceId === after.serviceId &&
    before.sameService && before.sameRoom, 'Page owner changed across canonical event');
  const given = { ...before,
    requestAccepted: first.pageObserver.ledger.some(item => item.kind === 'production_callback' && item.event.kind === 'accepted'),
    failure: first.pageObserver.ledger.some(item => item.kind === 'production_callback' && item.event.kind === 'failed') ? 'sdk_failure' : undefined };
  if (spec.key === 'challenge_is_stable') {
    requireEvidence(before.sas.length === 0 && same(raw.pendingSdkPayload?.sas, spec.given.sas),
      'Pending SAS fixture must not assign presenter state before SDK data callback');
    requireEvidence(first.pageObserver.ledger.some(item => item.kind === 'sdk_pending_data' &&
      same(item, raw.pendingSdkPayload)), 'Pending SDK payload not bound to its actual external ledger');
    given.sas = raw.pendingSdkPayload.sas;
  }
  for (const [key, value] of Object.entries(spec.given)) requireEvidence(same(given[key], value), 'Actual canonical given differs: ' + key);
  requireEvidence(first.controls.find(item => item.name === 'step')?.text === before.step &&
    last.controls.find(item => item.name === 'step')?.text === after.step,
    'Rendered step not bound to observed owner');
  const effectMethods = { request_verification: ['requestUserVerification', 'request_user_verification'],
    start_sas_verification: ['startVerification', 'start_verification'],
    accept_challenge: ['approveVerification', 'approve_verification'],
    decline_challenge: ['declineVerification', 'decline_verification'],
    cancel: ['cancelVerification', 'cancel_verification'], reset: ['resetVerification', 'reset_verification'] };
  const observed = { ...after };
  if (after.sas.length > 0) observed.sas = last.uiInventory.nodes.filter(node => node.type === 'Text' &&
    after.sas.includes(node.text)).map(node => node.text);
  if (after.replyState === 'loading' && !visible(last, 'loading')) observed.replyState = 'unrendered';
  const effect = effectMethods[spec.event.name];
  if (effect) {
    const delta = ledger.filter(item => item.kind === 'call' && item.sequence >
      Math.max(0, ...first.pageObserver.ledger.map(item => item.sequence)) && item.method === effect[0]);
    requireEvidence(delta.length === 1 && delta[0].completed, 'Original external SDK effect missing or duplicated');
    requireEvidence(last.pageObserver.calls.some(call => call.owner === 'gateway' && call.method === effect[0] &&
      call.presenterId === after.presenterId && call.gatewayId === after.gatewayId &&
      call.serviceId === after.serviceId && call.sameGatewayReceiver && call.sameService && call.completed),
      'Original page presenter -> actual gateway -> same service receiver chain missing');
    observed.effect = effect[1];
  }
  const checks = spec.invariants.map(description => {
    let passed = false;
    if (description === 'current-session verification is not requested') passed = after.currentSessionCalls === 0;
    else if (description === 'the active request is type user for @alice:example.org throughout the transition') {
      passed = raw.frames.filter(item => item.pageObserver?.state).every(item =>
        item.pageObserver.state.request.type === 'user' && item.pageObserver.state.request.userId === '@alice:example.org');
    } else if (description === 'the target user request remains active') passed =
      after.request.userId === '@alice:example.org' && !['canceled', 'completed', 'exit'].includes(after.step);
    else if (description === 'the challenge data is preserved until a response is sent') passed =
      same(observed.sas, spec.given.sas) && same(observed.sas, after.sas) && after.replyState === 'uninitialized';
    else if (description === 'the SAS challenge is unchanged') passed = same(before.sas, after.sas) && same(observed.sas, after.sas);
    else if (description === 'the user is not marked verified') passed = after.identityState !== 'verified';
    else if (description === 'the warning clears only after successful completion') {
      const guard = frame('finish_rejected_without_sdk_verified_status').pageObserver.state;
      passed = before.identityState === 'verification_violation' && before.warningVisible &&
        guard.step === 'verifying' && guard.warningVisible && guard.identityState === 'verification_violation' &&
        after.step === 'completed' && after.identityState === 'verified' && !after.warningVisible;
    } else if (description === 'cancellation never marks the user verified') passed =
      before.identityState === after.identityState && after.identityState !== 'verified';
    else if (description === 'reset creates no false success') passed = after.step !== 'completed' && after.identityState !== 'verified';
    return { description, passed, observed: { before, after, actualSdkLedger: ledger } };
  });
  return { observed, invariantChecks: checks, before, after };
}

async function runCase(args) {
  const spec = args.caseSpec, native = args.native || args.context?.native;
  const result = { observed: {}, invariantChecks: [], evidence: [],
    observationLevel: 'openharmony_api23_original_profile_ui_and_production_runtime',
    integrationBoundary: { appEntryExecuted: false, externalServicesExecuted: false,
      boundary: 'Original ArkUI profile plus original production presenter/store/gateway in the API23 test process.' } };
  try {
    requireEvidence(args.taskId === '13_user_verification' && typeof native?.runTask13Revision5UI === 'function',
      'Task13 revision5 native bridge unavailable');
    const raw = await native.runTask13Revision5UI(spec);
    result.evidence.push({ nativePageTransition: raw });
    for (const frame of raw.frames || []) args.trace('task13_revision5_ui_' + frame.label, frame);
    requireEvidence(raw.entryExecuted && raw.eventExecuted && !raw.failure && raw.caseId === spec.caseId &&
      raw.traceDigest === spec.traceDigest && raw.sessionId && raw.frames?.some(frame => frame.label === 'before_event') &&
      raw.frames?.some(frame => frame.label === 'after_event') && raw.actions?.every(action => action.executed),
    'Original Task13 native replay incomplete: ' + JSON.stringify(raw.failure || {}));
    requireEvidence(raw.frames.every(frame => frame.sessionId === raw.sessionId && frame.bundleName === native.bundleName &&
      frame.windowIdentity?.focused && frame.windowIdentity.hostVerified), 'Original Task13 window identity differs');
    const sourcePaths = raw.productionSources?.map(item => item.path) || [];
    requireEvidence(sourcePaths.includes(page), 'Original Task13 page provenance missing');
    result.integrationBoundary.appEntryExecuted = true;

    if (raw.role === 'base') {
      requireEvidence(raw.basePositiveControl?.profileRendered && raw.basePositiveControl.directMessageExecuted,
        'Base profile positive control did not execute');
      requireEvidence(sourcePaths.includes(native.task13ProductionFeature), 'Actual page module/data-plane provenance missing');
      if (spec.key !== 'identity_violation_surfaces') {
        // No SAS post-state exists after a genuinely missing UI entry. An independent,
        // source-bound entry validator must review the actual native observations.
        result.observed = null;
        result.unsupported = 'Missing verification entry; requires independent live common-entry validation';
      } else {
        const before = raw.frames.find(frame => frame.label === 'before_event');
        const timeline = raw.frames.find(frame => frame.label === 'after_identity_change_timeline');
        const members = raw.frames.find(frame => frame.label === 'after_identity_change_members');
        const profile = raw.frames.find(frame => frame.label === 'after_identity_change_profile_restored');
        requireEvidence(before && timeline && members && profile, 'Identity transition surface replay incomplete');
        requireEvidence(raw.oldTimelinePositiveControl?.warningHeldUntilSdkUpdate &&
          raw.oldTimelinePositiveControl.warningCleared &&
          same(raw.oldTimelinePositiveControl.sdkEffects, [{ method: 'withdrawVerification', userId: '@alice:example.org' }]),
        'Old timeline production UI/encryption-service/SDK-stream positive control incomplete');
        requireEvidence(['verifiedBadgeUpdated', 'legacyRowUpdated', 'displayNameUpdated',
          'bothMembersRendered', 'memberProfileNavigated', 'searchFilteredAndRestored',
          'blockAndUnblockBound'].every(key => raw.baseStreamPositiveControl?.[key] === true),
        'Original base profile/member SDK stream positive control incomplete');
        const initial = before.pageObserver.sdkState, after = profile.pageObserver.sdkState;
        requireEvidence(initial.encryptedRoom && after.encryptedRoom &&
          initial.identities.find(item => item.userId === '@alice:example.org')?.identityState === 'pinned' &&
          after.identities.find(item => item.userId === '@alice:example.org')?.identityState === 'verification_violation',
        'Real encrypted room identity transition was not delivered');
        result.observed = {
          profileBadge: visible(profile, 'profileViolation') ? 'verification_violation' :
            visible(profile, 'verifiedBadge') ? 'verified' : 'none',
          timelineWarning: visible(timeline, 'timelineWarning'),
          roomMemberWarning: visible(members, 'roomMemberWarning'),
          verifyActionVisible: visible(profile, 'verify'),
          withdrawVerificationActionVisible: visible(profile, 'withdraw'),
          profileWarningVisible: visible(profile, 'profileViolation')
        };
        const unrelatedBefore = initial.identities.filter(item => item.userId !== '@alice:example.org');
        const unrelatedAfter = after.identities.filter(item => item.userId !== '@alice:example.org');
        result.invariantChecks = [
          { description: spec.invariants[0], passed: unrelatedBefore.length === 1 &&
            unrelatedBefore[0].userId === '@bob:example.org' && same(unrelatedBefore, unrelatedAfter),
            observed: { before: unrelatedBefore, after: unrelatedAfter, sameRuntimeReplay: raw.sessionId } },
          { description: spec.invariants[1], passed: visible(profile, 'withdraw') && !visible(profile, 'verify'),
            observed: { profile: profile.controls, timeline: timeline.controls, sameRuntimeReplay: raw.sessionId } }
        ];
        args.trace('task13_revision5_before_event', { frame: before, identityInput: initial });
        args.trace('task13_revision5_after_event', { frame: profile, observed: result.observed,
          timelineFrame: timeline, memberFrame: members, identityInput: after });
      }
    } else {
      requireEvidence(sourcePaths.includes(native.task13ProductionFeature), 'Actual production module provenance missing');
      const observed = evaluatePageOwner(spec, raw);
      result.observed = observed.observed; result.invariantChecks = observed.invariantChecks;
      result.integrationBoundary.externalServicesExecuted = true;
      args.trace('task13_revision5_before_event', observed.before);
      args.trace('task13_revision5_after_event', observed.after);
      result.evidence.push({ pageOwnerBefore: observed.before, pageOwnerAfter: observed.after });
    }
    result.nativeUI = { observed: true, transitionObserved: true, role: raw.role,
      sessionId: raw.sessionId, productionSources: raw.productionSources };
  } catch (error) {
    result.unsupported = String(error.message || error);
  }
  return result;
}

module.exports = { runCase, evaluatePageOwner, validateOwnerInventory };
