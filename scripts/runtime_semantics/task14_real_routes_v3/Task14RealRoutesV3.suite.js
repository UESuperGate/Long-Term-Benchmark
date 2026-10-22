import { installTask14JoinOwnerV3 } from './Task14JoinOwnerV3';
import { installTask14RealFlowV2Observer } from './Task14RealFlowV2Observer';
import { acquireTask14RealFlowFrame } from './Task14RealFlowV2Frame';

export const TASK14_REAL_ROUTES_PROTOCOL = 'task14.arkts.actual-navigation-routes.v3';
const supported = new Set(['jr_state_005_found_then_continue_navigates',
  'jr_state_006_continue_waits_for_resolution', 'jr_state_009_dismiss_closes_flow']);
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const need = (value, reason) => { if (!value) throw Error(reason); };
const target = control => control?.actionAncestor || control;
const rootSelectors = { title: [{ text: 'Start a chat', type: 'Text' }], search: [{ id: 'people_search_input' }],
  join: [{ id: 'join_room_by_address' }], create: [{ id: 'create_room_action' }] };
const addressSelectors = { input: [{ id: 'room_address_input' }, { id: 'join_address_input' }],
  continue: [{ id: 'join_room_continue' }, { id: 'join_address_continue' }],
  cancel: [{ id: 'join_room_cancel' }, { id: 'join_address_cancel' }] };
const postSelectors = { search: rootSelectors.search, input: addressSelectors.input,
  roomBack: [{ id: 'room_back' }], roomId: [{ id: 'room_id' }], roomError: [{ id: 'room_error' }] };

async function stableActualPost(session, read, deadline) {
  // Stabilize transport, NEVER poll for the expected route/success value.
  for (let attempt = 0; attempt < 8 && Date.now() < deadline; attempt++) {
    const frame = await session.observeBracketed('after:event', postSelectors, read);
    const end = frame.bracketEnd;
    if (frame.windowId === end?.windowId && frame.routeName === end?.routeName &&
        JSON.stringify(frame.tree) === JSON.stringify(end?.tree)) return frame;
    await session.delay(50);
  }
  throw Error('Post-event native route/window remained mixed; NS');
}

export async function runTask14RealRoutesV3(spec, config, session, importModule, emit = () => {}, trace = () => {}) {
  const result = { protocol: TASK14_REAL_ROUTES_PROTOCOL, taskId: spec.taskId, caseId: spec.caseId,
    traceDigest: spec.traceDigest, evidence: [], observed: {}, invariantChecks: [], frames: [], actions: [],
    outcome: 'not_scored', eventExecuted: false, pendingIndependentAdmission: true,
    limitations: ['Controlled external alias response; original native page, presenter, navigator, router and RoomPresenter remain unchanged.'] };
  const record = item => { result.evidence.push(clone(item)); emit(item); };
  const capture = (label, frame, state) => {
    const value = { label, frame: clone(frame), samePageOwnerState: clone(state) };
    result.frames.push(value); trace(label, value); return value;
  };
  let observer;
  const deadline = config.deadlineEpochMs;
  const budget = () => need(Number.isFinite(deadline) && Date.now() < deadline, 'Original scorer deadline exhausted');
  try {
    budget(); need(supported.has(spec.caseId) && spec.taskId === '14_join_room_by_address' &&
      config.mode === 'after-page-ready', 'Explicit source-bound actual-route case required');
    const root = await acquireTask14RealFlowFrame(session, 'common:root', rootSelectors,
      { routeName: config.entryRoute, anchor: 'search', required: ['search', 'join', 'create'] }, record);
    // Only postload original production modules after the original native page
    // is ready. No presenter/navigator is constructed here.
    const join = await importModule(config.productionModuleUrl);
    const chat = await importModule(config.chatFeatureModuleUrl);
    const routes = await importModule(config.chatRoutesModuleUrl);
    const runtime = await importModule(config.chatRuntimeModuleUrl);
    const joinOwner = installTask14JoinOwnerV3(join, record);
    observer = installTask14RealFlowV2Observer({ chat, routes, runtime, joinObserver: joinOwner }, record);
    joinOwner.bindExternalResolver(config.resolverModuleUrl ? await importModule(config.resolverModuleUrl) : join);
    capture('common:root', root, null);
    await session.action('click', target(root.controls.join));
    const form = await acquireTask14RealFlowFrame(session, 'setup:form', addressSelectors,
      { routeName: config.addressRoute || config.entryRoute, anchor: 'input', required: ['input', 'continue', 'cancel'] }, record);
    const alias = spec.given.address || '#team:example.org';
    await session.action('input', form.controls.input, alias);
    await session.dismissKeyboard();
    let state, pending;
    // Canonical setup may wait for this actual page's pending external request.
    // Post-event verdicts never use expected-state readiness polling.
    for (let attempt = 0; attempt < 160; attempt++) {
      budget(); state = joinOwner.read();
      pending = state.resolverRequests?.filter(request => request.alias === alias && !request.settled && request.samePageResolver);
      if (state.available && state.instanceCount === 1 && state.addressState === 'resolving' && pending?.length === 1) break;
      await session.delay(50);
    }
    need(state.available && state.instanceCount === 1 && pending?.length === 1 && state.addressState === 'resolving',
      'Own original page pending request given not established');
    const ownRequest = pending[0], ownerId = state.instanceId;
    if (spec.caseId === 'jr_state_005_found_then_continue_navigates') {
      joinOwner.resolveExternal(ownRequest.id, { roomId: spec.given.roomId, servers: spec.given.servers });
      for (let attempt = 0; attempt < 80; attempt++) {
        budget(); state = joinOwner.read(); if (state.addressState === 'room_found') break; await session.delay(50);
      }
      need(state.addressState === 'room_found' && state.resolvedRoom?.roomId === spec.given.roomId &&
        JSON.stringify(state.resolvedRoom.servers) === JSON.stringify(spec.given.servers), 'Own resolved-room given not established');
    }
    const before = await session.observeBracketed('before:event', addressSelectors, () => joinOwner.read());
    state = joinOwner.read();
    need(state.instanceId === ownerId && before.routeName === (config.addressRoute || config.entryRoute) &&
      before.controls.input.text === state.address, 'Wrong original owner/rendered given');
    if (spec.caseId === 'jr_state_006_continue_waits_for_resolution')
      need(state.address === spec.given.address && state.addressState === 'resolving' && state.validationRequested === false,
        'Complete pending-continue given missing');
    if (spec.caseId === 'jr_state_009_dismiss_closes_flow')
      need(state.addressState === 'resolving' && before.controls.input.visible === true, 'Complete dismiss given missing');
    capture('before:event', before, state);
    const start = observer.checkpoint(), joinCallStart = state.calls.length;
    const control = spec.caseId === 'jr_state_009_dismiss_closes_flow' ? before.controls.cancel : before.controls.continue;
    const action = { kind: 'click', target: spec.caseId.endsWith('dismiss_closes_flow') ? 'cancel' : 'continue',
      nativeControl: clone(control), originalOwnerId: ownerId, executed: false };
    result.actions.push(action);
    await session.action('click', target(control)); action.executed = true;
    if (spec.caseId === 'jr_state_006_continue_waits_for_resolution') {
      capture('after:continue-before-resolution', await session.observeBracketed('pending:continue', addressSelectors,
        () => joinOwner.read()), joinOwner.read());
      joinOwner.resolveExternal(ownRequest.id, { roomId: spec.event.roomId, servers: spec.event.servers });
      record({ method: 'Task14.ownCompoundEventExternalResolution', requestId: ownRequest.id, ownerId });
    }
    await session.delay(500);
    const after = await stableActualPost(session, () => joinOwner.read(), deadline);
    const current = joinOwner.read(), calls = observer.calls().filter(call => call.sequence > start);
    need(current.instanceId === ownerId && current.instanceCount === 1 && before.windowId === after.windowId,
      'Event lost original page owner/window');
    const method = spec.caseId.endsWith('dismiss_closes_flow') ? 'dismiss' : 'continue';
    need(current.calls.slice(joinCallStart).some(call => call.instanceId === ownerId && call.method === method && call.returned),
      'Physical event did not invoke original page owner');
    capture('after:event', after, current);
    const navigations = current.navigationCalls.filter(call => call.method === 'openRoom');
    const routedCalls = calls.filter(call => call.owner === 'HarmonyRoutePort' && call.method === 'replace' && call.phase === 'call');
    const roomLoads = calls.filter(call => call.owner === 'RoomPresenter' && call.method === 'load' && call.phase === 'call');
    const physicalRoom = after.routeName === 'pages/Room' && after.controls.roomBack?.present === true && after.controls.roomBack.visible === true;
    const physicalRoot = after.routeName === config.entryRoute && after.controls.search?.present === true && after.controls.search.visible === true &&
      after.controls.input?.present === false;
    const physicalAddress = after.routeName === (config.addressRoute || config.entryRoute) && after.controls.input?.present === true;
    need(physicalRoom || physicalRoot || physicalAddress, 'Unknown native post-event surface; NS');
    const expectedRoom = spec.given.roomId || spec.event.roomId;
    if (physicalRoom) need(after.routeParams?.roomId && routedCalls.length >= 1 && roomLoads.some(call =>
      call.args[0] === after.routeParams.roomId), 'Actual Room route lacks production router/RoomPresenter lineage');
    const routeProof = { nativeRoute: after.routeName, routeParams: after.routeParams, windowId: after.windowId,
      originalNavigatorCalls: clone(navigations), productionRoutePortCalls: clone(routedCalls), actualRoomPresenterLoads: clone(roomLoads),
      physicalRoot, physicalRoom, physicalAddress, expectedRoomIsOnlyComparisonNotSetup: expectedRoom };
    record({ method: 'Task14.actualRouteOutcomeV3', ...routeProof });
    if (spec.caseId === 'jr_state_005_found_then_continue_navigates') {
      result.observed = { dismissAddressFlow: physicalRoom, openRoom: physicalRoom && navigations.length ?
        { roomIdOrAlias: after.routeParams.roomId, serverNames: navigations.at(-1).args[1] ?? null } : null };
      result.invariantChecks = [{ description: spec.invariants[0], passed: navigations.length === 1 && routedCalls.length === 1,
        observed: routeProof }];
    } else if (spec.caseId === 'jr_state_006_continue_waits_for_resolution') {
      result.observed = { validationRequested: current.validationRequested, dismissAddressFlow: physicalRoom, navigationCount: routedCalls.length };
      result.invariantChecks = [{ description: spec.invariants[0], passed: current.resolverRequests.length === state.resolverRequests.length,
        observed: { before: state.resolverRequests, after: current.resolverRequests, routeProof } }];
    } else {
      result.observed = { addressFlowVisible: !physicalRoot, openRoomCount: routedCalls.length };
      result.invariantChecks = [{ description: spec.invariants[0], passed: !navigations.length && !routedCalls.length && !roomLoads.length,
        observed: routeProof }];
    }
    result.eventExecuted = true; result.outcome = 'native_transition_observed_pending_independent_admission';
  } catch (error) { result.failure = String(error); result.outcome = 'not_scored'; }
  finally { observer?.dispose(); }
  return result;
}
