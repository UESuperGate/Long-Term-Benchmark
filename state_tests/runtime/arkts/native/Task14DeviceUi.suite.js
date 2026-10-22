import { installTask14Observer } from './Task14PageObserver';
import { observePeopleSelection } from './Task14AncestorObserver';
import { acquirePageFrame } from './Task14FrameAcquisition';

export const TASK14_CASES = {
  jr_state_001_entry_opens_address_flow: 'entry_opens_address_flow',
  jr_state_003_invalid_after_continue: 'invalid_after_continue',
  jr_state_007_not_found_recovers: 'not_found_recovers'
};

export const TASK14_SELECTORS = {
  root: [{ text: 'Start a chat', type: 'Text' }],
  search: [{ id: 'people_search_input' }, { type: 'TextInput' }],
  entry: [{ id: 'join_room_by_address' }, { id: 'join_by_address_button' }],
  create: [{ id: 'create_room_button' }, { type: 'Button', text: 'Create room' }],
  dmAlice: [{ text: 'Alice', type: 'Text', actionAncestor: true }],
  dmBob: [{ text: 'Bob', type: 'Text', actionAncestor: true }],
  dmCharlie: [{ text: 'Charlie', type: 'Text', actionAncestor: true }],
  input: [{ id: 'room_address_input' }, { id: 'address_input' }, { id: 'join_address_input' }],
  continue: [{ id: 'join_room_continue' }, { id: 'address_continue_button' }, { id: 'join_address_continue' }],
  cancel: [{ id: 'address_dismiss_button' }, { type: 'Button', text: 'Cancel' }],
  invalid: [{ id: 'address_validation_message' }, { type: 'Text', text: 'Enter a valid Matrix room address' }, { id: 'join_address_error' }],
  notFound: [{ id: 'address_notfound_label' }, { type: 'Text', text: 'Room not found. Check the address and retry.' }, { id: 'join_address_error' }],
  resolving: [{ id: 'address_loading' }, { type: 'Text', text: 'Looking up room...' }, { id: 'join_address_loading' }]
};
const copy = value => JSON.parse(JSON.stringify(value));
const rootSelectors = Object.fromEntries(['root', 'search', 'entry', 'create', 'dmAlice', 'dmBob', 'dmCharlie'].map(k => [k, TASK14_SELECTORS[k]]));
const formSelectors = Object.fromEntries(['input', 'continue', 'cancel', 'invalid', 'notFound', 'resolving'].map(k => [k, TASK14_SELECTORS[k]]));
const pageSelectors = { ...rootSelectors, ...formSelectors, search: [{ id: 'people_search_input' }] };
const requireObserved = (condition, reason) => { if (!condition) throw new Error(reason); };
const visibility = control => {
  requireObserved(typeof control?.visible === 'boolean', 'Native visibility is unobserved for ' + JSON.stringify(control?.selector));
  return control.visible;
};
const summary = frame => ({ label: frame.label, routeName: frame.routeName, windowId: frame.windowId,
  stackLength: frame.stackLength, controls: frame.controls, state: frame.state });

// The suite drives original controls only. Expected values never construct state.
export async function runTask14Transition(spec, config, session, importModule, emit, trace = () => {}) {
  const result = { taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest,
    observed: {}, invariantChecks: [], unsupportedInvariants: [], evidence: [], notes: [],
    observationLevel: 'native_candidate_ui_and_production_state',
    limitations: ['Original ArkUI + same original page receiver. Directory failure is an injected external resolver response; no real network request. Inspector/Driver visibility is not pixel occlusion proof.'] };
  let observer;
  let beforeRecorded = false, afterRecorded = false;
  const record = event => { result.evidence.push({ label: event.method, data: copy(event) }); emit(event); };
  const frame = async (label, selectors, stateRequired = true, acquired) => {
    const view = acquired || await session.observe(label, selectors);
    const state = acquired ? acquired.stateAfter : observer?.read();
    if (config.apiShape === 'gatewayScheduler' && state?.available &&
        state.visibleAddressState === undefined && typeof view.controls.invalid?.visible === 'boolean') {
      state.visibleAddressState = !state.validationRequested && !view.controls.invalid.visible ? 'unknown' : state.addressState;
    }
    if (stateRequired) requireObserved(state?.available && state.instanceId && state.instanceCount === 1,
      state?.reason || 'A single original page presenter receiver is not established');
    const value = { ...view, label, state };
    result.evidence.push({ label, data: copy(value) });
    emit({ method: 'Task14.originalPageFrame', available: true, frame: summary(value), productionSources: config.productionSources });
    if (label === 'before:event') beforeRecorded = true;
    if (label === 'after:event') afterRecorded = true;
    trace(label, summary(value));
    return value;
  };
  const invariant = (description, passed, observed) => {
    requireObserved(spec.invariants.includes(description), 'Unexpected canonical invariant identity');
    result.invariantChecks.push({ description, passed, observed: copy(observed) });
  };
  const stableFrame = async (label, identity, stateRequired = true, extraSelectors = {}) => {
    const selectors = { ...pageSelectors, ...extraSelectors };
    const acquired = await acquirePageFrame(session, selectors, () => observer?.read(),
      { routeName: config.entryRoute, ...identity, stateRequired }, record, { phase: label });
    return frame(label, selectors, stateRequired, acquired);
  };
  const bind = async readiness => {
    requireObserved(readiness.available && (readiness.controls.entry?.visible === true || readiness.controls.input?.visible === true),
      'Original page positive root/form evidence is required before import');
    requireObserved(config.productionModuleUrl?.startsWith('@bundle:' + config.bundleName + '/' + config.moduleName + '/ets/features/'),
      'Original app module URL is not bound to manifest');
    record({ method: 'Task14.beforeOriginalModuleImport', available: true, requestedModuleUrl: config.productionModuleUrl,
      readiness: summary(readiness), warning: 'Native cache miss can be fatal; task11 does not prove task14 loader support' });
    const namespace = await importModule(config.productionModuleUrl);
    observer = installTask14Observer(namespace, record);
    record({ method: 'Task14.originalModuleBound', available: true, requestedModuleUrl: config.productionModuleUrl,
      importCompleted: true, receiverObserved: false, ...observer.binding });
    return namespace;
  };
  const sameReceiver = (before, after) => requireObserved(before.state.instanceId === after.state.instanceId &&
    before.windowId === after.windowId && after.state.instanceCount === 1, 'Original receiver/window identity changed during event');
  const validateGiven = (given, actual) => {
    const checks = Object.entries(given).map(([field, value]) => ({ field, actual: actual[field], given: value,
      established: actual[field] !== undefined && JSON.stringify(actual[field]) === JSON.stringify(value) }));
    record({ method: 'Task14.givenChecks', available: true, checks });
    requireObserved(checks.every(check => check.established), 'Canonical given not established: ' +
      checks.filter(check => !check.established).map(check => check.field).join(', '));
  };
  const waitState = async predicate => {
    const until = Date.now() + 3000;
    do {
      const state = observer.read();
      if (state.available && predicate(state)) return state;
      await session.delay(25);
    } while (Date.now() < until);
    throw new Error('Original page state did not reach the required setup/event boundary');
  };
  try {
    requireObserved(spec.taskId === '14_join_room_by_address' && TASK14_CASES[spec.caseId] === spec.key,
      'Task14 independent suite supports only canonical cases001/003/007');
    const root = spec.key === 'entry_opens_address_flow' ? await stableFrame('setup:original-root', {}, false) :
      await frame('setup:original-root', rootSelectors, false);
    requireObserved(root.routeName === config.entryRoute && visibility(root.controls.root) &&
      visibility(root.controls.search), 'Original start-chat root/search is not positively observed');
    requireObserved(root.controls.entry.present === true && visibility(root.controls.entry),
      'Original join-by-address entry is absent/unobserved; no missing-symbol semantic verdict');
    if (spec.key === 'entry_opens_address_flow') {
      validateGiven(spec.given, { surface: 'start_chat', searchActive:
        typeof root.controls.search.focused === 'boolean' && typeof root.controls.search.text === 'string' ?
          root.controls.search.focused || root.controls.search.text.length > 0 : undefined });
      // If the class first loads on a separate destination page, pre-entry
      // import is unsafe, and an extra edit would overwrite canonical post-state.
      requireObserved(config.presenterLoadedByEntry === true,
        'Entry presenter is not in the already-loaded original entry module graph; post-entry receiver proof requires a separate binding');
      await bind(root);
      const before = await stableFrame('before:event', { windowId: root.windowId }, false);
      requireObserved(spec.event.name === 'select_join_by_address', 'Unexpected canonical entry event');
      await session.action('click', before.controls.entry);
      const after = await stableFrame('after:event', { windowId: root.windowId });
      requireObserved(after.state.calls.some(call => ['visibleAddressState', 'updateAddress', 'setOnStateChange', 'reset'].includes(call.method)),
        'No original page presenter callback was captured after entry');
      requireObserved(after.controls.input.text === after.state.address, 'Rendered address and original receiver disagree');
      result.observed = { addressFlowVisible: visibility(after.controls.input), address: after.state.address,
        addressState: after.state.visibleAddressState ?? after.state.addressState };
      // Availability belongs to the start-chat surface, not simultaneous modal
      // visibility. Return using the original Cancel/Dismiss control to inspect it.
      await session.action('click', after.controls.cancel);
      const returned = await stableFrame('invariant:returned-start-chat',
        { windowId: after.windowId, instanceId: after.state.instanceId });
      sameReceiver(after, returned);
      requireObserved(visibility(returned.controls.root) && visibility(returned.controls.search), 'Original start-chat did not return');
      const beforePeople = ['dmAlice', 'dmBob', 'dmCharlie'].filter(k => visibility(before.controls[k]));
      const afterPeople = ['dmAlice', 'dmBob', 'dmCharlie'].filter(k => visibility(returned.controls[k]));
      const actionFor = control => control.actionAncestor || control;
      requireObserved(beforePeople.every(k => actionFor(before.controls[k]).clickable === true && actionFor(before.controls[k]).enabled === true) &&
        afterPeople.every(k => actionFor(returned.controls[k]).clickable === true && actionFor(returned.controls[k]).enabled === true),
        'Visible people labels lack directly observed enabled/clickable action semantics; ancestor event binding is unobserved');
      const createAvailable = visibility(before.controls.create) && before.controls.create.enabled === true &&
        visibility(returned.controls.create) && returned.controls.create.enabled === true;
      // Known original base/agent people controls are scanned in the complete
      // original tree. No search widget alone is called a direct-message action.
      const controlsAvailable = createAvailable && beforePeople.length > 0 && afterPeople.length > 0;
      record({ method: 'Task14.partialActionAvailability', before: summary(before), returned: summary(returned),
        beforePeople, afterPeople, createAvailable, controlsAvailable,
        scope: 'Rendered controls only. Neither selection nor button presence establishes genuine create-room/DM actions.' });
      if (!controlsAvailable) invariant('existing create-room and direct-message actions remain available', false,
        { before: summary(before), returned: summary(returned), beforePeople, afterPeople, createAvailable });
      if (!beforePeople.length || !afterPeople.length) result.notes.push({ kind: 'actual_ui_invariant_mismatch',
        reason: 'Original start-chat tree has no existing Alice/Bob/Charlie people actions; search input presence does not prove DM availability.' });
      if (afterPeople.length && config.peopleModuleUrl) {
        requireObserved(config.peopleModuleUrl.startsWith('@bundle:' + config.bundleName + '/' + config.moduleName + '/ets/features/'),
          'Original people module URL is not candidate-owned');
        const people = observePeopleSelection(await importModule(config.peopleModuleUrl), record);
        try {
          const label = returned.controls[afterPeople[0]];
          await session.action('click', actionFor(label));
          const selected = await stableFrame('supplemental:people-selection',
            { windowId: returned.windowId, instanceId: returned.state.instanceId }, true,
            { selected: [{ text: 'Selected', type: 'Text' }] });
          const calls = people.read();
          requireObserved(calls.length === 1 && calls[0].receiverCount === 1 && calls[0].args[0] === label.text &&
            calls[0].after === label.text && visibility(selected.controls.selected),
            'Original people selection callback and rendered selection were not both observed');
          result.notes.push({ kind: 'supplemental_selection_only', reason: 'Real original row click and selectPerson receiver; not DM navigation.' });
        } finally { people.dispose(); }
      }
      if (controlsAvailable) {
        result.notes.push({ kind: 'actual_feature_migration_gap',
          reason: 'The observed people-selection and create-button controls do not establish Android base StartDM/openRoom or create-room routing. No genuine DM/create flow is bound.' });
        throw new Error('Complete create-room/direct-message action invariant is unproven: local selection is not a DM action or real navigation');
      }
    } else {
      await session.action('click', root.controls.entry);
      const form = await frame('setup:original-form', formSelectors, false);
      requireObserved(visibility(form.controls.input), 'Original address form unavailable');
      const namespace = await bind(form);
      if (spec.key === 'not_found_recovers') {
        let resolverNamespace = namespace;
        if (config.resolverModuleUrl) {
          requireObserved(config.resolverModuleUrl.startsWith('@bundle:' + config.bundleName + '/' + config.moduleName + '/ets/features/'),
            'Resolver URL is not in original app');
          resolverNamespace = await importModule(config.resolverModuleUrl);
        }
        record({ ...observer.bindExternalResolver(resolverNamespace),
          method: 'Task14.externalResolverBound', available: true });
      }
      requireObserved(typeof spec.given.address === 'string', 'Canonical address input unavailable');
      await session.action('input', form.controls.input, spec.given.address);
      await waitState(state => state.address === spec.given.address && (spec.key === 'invalid_after_continue' ?
        state.internalAddressState === 'invalid' : state.internalAddressState === 'resolving' && state.resolverRequests.length > 0));
      if (spec.key === 'not_found_recovers') {
        const pending = await frame('setup:pending-resolution', formSelectors);
        // Same as Android rendered fixture: Continue requests visible resolving
        // while the external response stays pending. It is setup, not the event.
        await session.action('click', pending.controls.continue);
        await waitState(state => state.validationRequested === true);
      }
      const before = await frame('before:event', formSelectors);
      requireObserved(before.controls.input.text === before.state.address, 'Canonical address is not rendered from the captured receiver');
      validateGiven(spec.given, { address: before.state.address, internalAddressState: before.state.internalAddressState,
        addressState: before.state.visibleAddressState ?? before.state.addressState,
        validationRequested: before.state.validationRequested });
      requireObserved(Number.isFinite(before.state.navigationCount),
        'Actual original navigator openRoomCount unavailable; route presence cannot substitute for a navigation counter');
      if (spec.key === 'invalid_after_continue') {
        requireObserved(spec.event.name === 'continue', 'Unexpected invalid-address event');
        const suppressed = !visibility(before.controls.invalid);
        await session.action('click', before.controls.continue);
        await waitState(state => state.calls.slice(before.state.calls.length).some(call => ['continue', 'requestContinue'].includes(call.method)));
        await session.delay(100);
        const after = await frame('after:event', formSelectors);
        sameReceiver(before, after);
        result.observed = { addressState: after.state.visibleAddressState ?? after.state.addressState,
          errorVisible: visibility(after.controls.invalid), navigationCount: after.state.navigationCount };
        invariant('invalid feedback is suppressed before validation is requested', suppressed && before.state.validationRequested === false,
          { before: summary(before), after: summary(after) });
      } else {
        requireObserved(spec.event.name === 'resolve_returns_empty_or_error', 'Unexpected resolver failure event');
        const requests = before.state.resolverRequests.filter(request => !request.settled && request.samePageResolver && request.alias === spec.given.address);
        requireObserved(requests.length === 1, 'One pending alias request from the original page resolver is required');
        observer.settle(requests[0].id);
        await waitState(state => state.internalAddressState !== 'resolving');
        await session.delay(100);
        const after = await frame('after:event', formSelectors);
        sameReceiver(before, after);
        requireObserved(typeof after.controls.input.enabled === 'boolean', 'Original editor enabled state unavailable');
        result.observed = { addressState: after.state.internalAddressState, errorVisible: visibility(after.controls.notFound),
          navigationCount: after.state.navigationCount, editingEnabled: after.controls.input.enabled };
        const staysOpen = before.routeName === after.routeName && before.windowId === after.windowId &&
          visibility(after.controls.input) && visibility(after.controls.continue) &&
          after.state.addressFlowVisible === true;
        invariant('resolution failures do not close the flow', staysOpen,
          { before: summary(before), after: summary(after) });
        if (result.observed.editingEnabled) {
          await session.action('input', after.controls.input, '#retry:example.org');
          await waitState(state => state.address === '#retry:example.org');
          await frame('diagnostic:real-retry-edit', formSelectors);
        }
      }
    }
  } catch (error) {
    result.unsupported = String(error.message || error);
    result.notes.push({ kind: 'fixture_or_observation_unavailable', reason: result.unsupported });
  } finally {
    if (observer) observer.dispose();
    if (!beforeRecorded) trace('before:event', { executed: false, reason: result.unsupported });
    if (!afterRecorded) trace('after:event', { executed: false, reason: result.unsupported });
    for (const description of spec.invariants || []) if (!result.invariantChecks.some(check => check.description === description))
      result.unsupportedInvariants.push({ description, reason: result.unsupported || 'Invariant not observed' });
  }
  return result;
}
