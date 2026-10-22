import { startTask14Page } from './Task14DeviceUi.core';

const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const need = (value, reason) => { if (!value) throw Error(reason); };
const rootSelectors = {
  search: [{ id: 'people_search_input' }],
  create: [{ id: 'create_room_action' }],
  join: [{ id: 'join_room_by_address' }]
};
const createSelectors = {
  title: [{ id: 'create_room_title' }],
  cancel: [{ id: 'create_room_cancel' }]
};

async function stableFrame(session, label, selectors, accept, deadline) {
  let last;
  for (let attempt = 0; attempt < 80 && Date.now() < deadline; attempt++) {
    try {
      last = await session.observeBracketed(label, selectors, () => ({}));
      const end = last.bracketEnd;
      if (last.windowId === end?.windowId && last.routeName === end?.routeName && accept(last)) return last;
    } catch (_) {}
    await session.delay(50);
  }
  throw Error('Stable base UI frame unavailable: ' + label + ': ' + JSON.stringify(last?.routeName));
}

export async function evaluateTask14BaseV1(args, config, ports, record) {
  const raw = { protocol: 'task14.base-entry-absence.v1', taskId: args.taskId,
    caseId: args.caseSpec.caseId, traceDigest: args.caseSpec.traceDigest,
    entryExecuted: false, eventExecuted: false, released: false, failure: null, frames: [] };
  let session;
  try {
    if (Date.now() >= config.deadlineEpochMs) throw Error('Fresh base deadline missing');
    args.load(config.productionSourcePath);
    session = await startTask14Page(ports, config, event => record(event));
    raw.entryExecuted = true;
    const before = await stableFrame(session, 'before:event', rootSelectors, frame =>
      frame.routeName === config.entryRoute && frame.controls.search.visible === true &&
      frame.controls.search.enabled === true && frame.controls.create.visible === true &&
      frame.controls.create.enabled === true && frame.controls.join.present === false,
      config.deadlineEpochMs);
    raw.frames.push(clone(before));
    args.trace('before:event', clone(before));

    await session.action('click', before.controls.create.actionAncestor || before.controls.create);
    const create = await stableFrame(session, 'positive:create-room', createSelectors, frame =>
      frame.routeName === 'pages/CreateRoom' && frame.controls.title.visible === true &&
      frame.controls.cancel.visible === true && frame.controls.cancel.enabled === true,
      config.deadlineEpochMs);
    raw.frames.push(clone(create));
    await session.action('click', create.controls.cancel.actionAncestor || create.controls.cancel);

    const after = await stableFrame(session, 'after:event', rootSelectors, frame =>
      frame.routeName === config.entryRoute && frame.controls.search.visible === true &&
      frame.controls.search.enabled === true && frame.controls.create.visible === true &&
      frame.controls.create.enabled === true && frame.controls.join.present === false,
      config.deadlineEpochMs);
    raw.frames.push(clone(after));
    args.trace('after:event', clone(after));
    raw.eventExecuted = true;
    record({ method: 'Task14.baseEntryAbsenceV1', caseId: raw.caseId,
      commonStartChatReady: true, createRoomRoundTrip: true, joinAddressEntryAbsent: true });
  } catch (error) {
    raw.failure = String(error);
  } finally {
    try { if (session) { await session.release(); raw.released = true; } }
    catch (error) { raw.failure = 'Owned base runtime cleanup: ' + String(error); }
    raw.finishedAt = Date.now();
  }
  if (raw.failure !== null || raw.entryExecuted !== true || raw.eventExecuted !== true || raw.released !== true) {
    return { observed: {}, invariantChecks: [], evidence: [{ task14BaseV1: raw }],
      unsupported: 'Base feature-entry absence lacks complete runtime evidence',
      observationLevel: 'native_candidate_ui' };
  }
  return { observed: {}, invariantChecks: [], evidence: [{ task14BaseV1: raw }],
    semanticFailure: 'semantic_missing_feature_entry',
    semanticFailureReason: 'Common StartChat and CreateRoom transitions execute, but join-by-address is absent from the base UI.',
    observationLevel: 'native_candidate_ui' };
}
