import { acquireTask14RealFlowFrame } from './Task14RealFlowV2Frame';

const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const need = (value, reason) => { if (!value) throw Error(reason); };
const target = control => control?.actionAncestor || control;
const supported = new Set([
  'jr_state_005_found_then_continue_navigates', 'jr_state_006_continue_waits_for_resolution',
  'jr_state_007_not_found_recovers', 'jr_state_009_dismiss_closes_flow'
]);
const rootSelectors = { search: [{ id: 'people_search_input' }],
  join: [{ id: 'join_room_by_address' }], create: [{ id: 'create_room_action' }] };
const addressSelectors = { input: [{ id: 'room_address_input' }],
  continue: [{ id: 'join_room_continue' }], cancel: [{ id: 'join_room_cancel' }],
  state: [{ id: 'room_address_state' }] };
const postSelectors = { search: rootSelectors.search, input: addressSelectors.input,
  state: addressSelectors.state, roomId: [{ id: 'room_id' }], roomBack: [{ id: 'room_back' }],
  error: [{ id: 'join_navigation_error' }] };

async function jointlyHeld(spec, session, owner, providerStatus, alias) {
  for (let attempt = 0; attempt < 160; attempt++) {
    const state = owner.read();
    const requests = state.resolverRequests?.filter(row => row.alias === alias && row.samePageResolver && !row.settled) || [];
    const external = await providerStatus();
    const held = external.held?.filter(row => row.caseId === spec.caseId && row.alias === alias) || [];
    if (state.available && requests.length === 1 && held.length === 1) {
      return { state, request: requests[0], held: held[0] };
    }
    await session.delay(50);
  }
  throw Error('Own configured resolver and nonce-bound provider request were not jointly held; NS');
}

async function stablePost(session, read, deadline) {
  for (let attempt = 0; attempt < 12 && Date.now() < deadline; attempt++) {
    const frame = await session.observeBracketed('after:event', postSelectors, read);
    const end = frame.bracketEnd;
    if (frame.windowId === end?.windowId && frame.routeName === end?.routeName &&
        JSON.stringify(frame.tree) === JSON.stringify(end?.tree)) return frame;
    await session.delay(50);
  }
  throw Error('Post-event native route/window remained mixed; NS');
}

export async function runTask14ConfiguredRoutesV16(spec, config, session, owner, providerStatus, emit = () => {}, trace = () => {}) {
  const result = { protocol: 'task14.configured-routes.v16', taskId: spec.taskId,
    caseId: spec.caseId, traceDigest: spec.traceDigest, observed: {}, invariantChecks: [],
    evidence: [], actions: [], eventExecuted: false, failure: null };
  const record = value => { result.evidence.push(clone(value)); emit(value); };
  try {
    need(supported.has(spec.caseId), 'Unsupported configured route case');
    const root = await acquireTask14RealFlowFrame(session, 'common:root', rootSelectors,
      { routeName: config.entryRoute, anchor: 'search', required: ['search', 'join', 'create'] }, record);
    await session.action('click', target(root.controls.join));
    const form = await acquireTask14RealFlowFrame(session, 'setup:form', addressSelectors,
      { routeName: config.addressRoute, anchor: 'input', required: ['input', 'continue', 'cancel'] }, record);
    const alias = spec.given.address || '#team:example.org';
    await session.action('input', form.controls.input, alias);
    await session.dismissKeyboard();
    const pending = await jointlyHeld(spec, session, owner, providerStatus, alias);
    const ownerId = pending.state.instanceId;

    if (spec.caseId === 'jr_state_005_found_then_continue_navigates') {
      await owner.resolveExternal(pending.request.id, { roomId: spec.given.roomId, servers: spec.given.servers });
      for (let attempt = 0; attempt < 80; attempt++) {
        const state = owner.read();
        if (state.addressState === 'room_found') break;
        await session.delay(50);
      }
      need(owner.read().addressState === 'room_found', 'Resolved-room given was not established');
    }
    const before = await session.observeBracketed('before:event', addressSelectors, () => owner.read());
    trace('before:event', clone(before));
    const requestCount = owner.read().resolverRequests.length;
    const control = spec.caseId === 'jr_state_009_dismiss_closes_flow' ? before.controls.cancel : before.controls.continue;
    await session.action('click', target(control));
    if (spec.caseId === 'jr_state_006_continue_waits_for_resolution') {
      need(owner.read().validationRequested === true, 'Continue did not request validation while resolving');
      await owner.resolveExternal(pending.request.id, { roomId: spec.event.roomId, servers: spec.event.servers });
    } else if (spec.caseId === 'jr_state_007_not_found_recovers') {
      await owner.settle(pending.request.id);
    }
    await session.delay(500);
    const after = await stablePost(session, () => owner.read(), config.deadlineEpochMs);
    const state = owner.read();
    need(state.instanceId === ownerId && state.instanceCount === 1, 'Event lost the original presenter owner');
    trace('after:event', clone(after));

    if (spec.caseId === 'jr_state_005_found_then_continue_navigates') {
      const opens = state.navigationCalls.filter(call => call.method === 'openRoom');
      result.observed = { dismissAddressFlow: state.addressFlowVisible === false,
        openRoom: { roomIdOrAlias: opens[0]?.args?.[0] ?? null, serverNames: opens[0]?.args?.[1] ?? null } };
      result.invariantChecks.push({ description: 'room navigation happens once', passed: opens.length === 1,
        observed: { openCalls: opens, routeName: after.routeName, renderedRoomId: after.controls.roomId?.text || null } });
    } else if (spec.caseId === 'jr_state_006_continue_waits_for_resolution') {
      result.observed = { validationRequested: state.validationRequested === true,
        dismissAddressFlow: state.addressFlowVisible === false, navigationCount: state.navigationCount };
      result.invariantChecks.push({ description: 'continue does not issue a second alias-resolution request',
        passed: state.resolverRequests.length === requestCount,
        observed: { before: requestCount, after: state.resolverRequests.length } });
    } else if (spec.caseId === 'jr_state_007_not_found_recovers') {
      result.observed = { addressState: state.addressState,
        errorVisible: after.controls.input.visible === true && after.controls.state?.text?.length > 0,
        navigationCount: state.navigationCount, editingEnabled: after.controls.input.enabled === true };
      result.invariantChecks.push({ description: 'resolution failures do not close the flow',
        passed: state.addressFlowVisible === true && after.controls.input.visible === true,
        observed: { addressFlowVisible: state.addressFlowVisible, routeName: after.routeName } });
    } else {
      result.observed = { addressFlowVisible: state.addressFlowVisible === true,
        openRoomCount: state.navigationCount };
      result.invariantChecks.push({ description: 'dismissing never joins a room',
        passed: state.navigationCount === 0,
        observed: { navigationCalls: state.navigationCalls, routeName: after.routeName } });
      // Canonical value is false after dismiss. Preserve the measured value directly.
      result.observed.addressFlowVisible = state.addressFlowVisible;
    }
    result.eventExecuted = true;
  } catch (error) {
    result.failure = String(error);
  }
  emit({ method: 'Task14.configuredRoutesEpisodeV16', ...clone(result) });
  return result;
}
