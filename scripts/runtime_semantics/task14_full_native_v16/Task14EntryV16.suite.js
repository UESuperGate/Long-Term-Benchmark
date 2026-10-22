import { acquireTask14RealFlowFrame } from './Task14RealFlowV2Frame';

const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const need = (value, reason) => { if (!value) throw Error(reason); };
const target = control => control?.actionAncestor || control;
const rootSelectors = { search: [{ id: 'people_search_input' }],
  join: [{ id: 'join_room_by_address' }], create: [{ id: 'create_room_action' }] };
const addressSelectors = { input: [{ id: 'room_address_input' }],
  cancel: [{ id: 'join_room_cancel' }], continue: [{ id: 'join_room_continue' }],
  state: [{ id: 'room_address_state' }] };

export async function runTask14EntryV16(spec, config, session, _importModule, emit = () => {}, trace = () => {}) {
  const result = { protocol: 'task14.configured-entry.v16', taskId: spec.taskId,
    caseId: spec.caseId, traceDigest: spec.traceDigest, observed: {}, invariantChecks: [],
    evidence: [], eventExecuted: false, failure: null };
  const record = value => { result.evidence.push(clone(value)); emit(value); };
  try {
    need(spec.caseId === 'jr_state_001_entry_opens_address_flow', 'Entry suite accepts only case001');
    const root = await acquireTask14RealFlowFrame(session, 'setup:root', rootSelectors,
      { routeName: config.entryRoute, anchor: 'search', required: ['search', 'join', 'create'] }, record);
    need(root.controls.search.text === '' && root.controls.search.enabled === true &&
      root.controls.create.visible === true && root.controls.create.enabled === true &&
      root.controls.join.visible === true && root.controls.join.enabled === true,
      'Configured root actions are not available');
    trace('before:event', clone(root));
    await session.action('click', target(root.controls.join));
    await session.delay(50);
    const address = await acquireTask14RealFlowFrame(session, 'after:event', addressSelectors,
      { routeName: config.addressRoute, anchor: 'input', required: ['input', 'cancel', 'continue'] }, record);
    const state = address.pageOwner;
    need(state?.available === true, 'Actual page-owned address presenter was not observed');
    result.observed = { addressFlowVisible: address.controls.input.visible === true,
      address: state.address, addressState: state.visibleAddressState ?? state.addressState };
    trace('after:event', clone(address));
    await session.action('click', target(address.controls.cancel));
    await session.delay(50);
    const returned = await acquireTask14RealFlowFrame(session, 'invariant:returned-root', rootSelectors,
      { routeName: config.entryRoute, anchor: 'search', required: ['search', 'join', 'create'] }, record);
    const actionsAvailable = returned.controls.search.visible === true && returned.controls.search.enabled === true &&
      returned.controls.create.visible === true && returned.controls.create.enabled === true;
    result.invariantChecks.push({ description: 'existing create-room and direct-message actions remain available',
      passed: actionsAvailable, observed: {
        directMessageAction: { id: returned.controls.search.id, visible: returned.controls.search.visible,
          enabled: returned.controls.search.enabled, clickable: returned.controls.search.clickable },
        createRoomAction: { id: returned.controls.create.id, visible: returned.controls.create.visible,
          enabled: returned.controls.create.enabled, clickable: returned.controls.create.clickable }
      } });
    result.eventExecuted = true;
  } catch (error) {
    result.failure = String(error);
  }
  emit({ method: 'Task14.configuredEntryEpisodeV16', ...clone(result) });
  return result;
}
