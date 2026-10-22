const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const need = (value, reason) => { if (!value) throw new Error(reason); };
const target = control => control?.actionAncestor || control;
const canonicalState = value => value === 'idle' ? 'unknown' : value === 'not_found' ? 'room_not_found' : value;
const rootSelectors = {
  search: [{ id: 'people_search_input' }], join: [{ id: 'join_room_by_address' }],
  create: [{ id: 'create_room_action' }]
};
const formSelectors = {
  panel: [{ id: 'join_room_by_address_panel' }], input: [{ id: 'room_address_input' }],
  state: [{ id: 'room_address_state' }], continue: [{ id: 'room_address_continue' }],
  cancel: [{ id: 'room_address_cancel' }], invalid: [{ id: 'room_address_invalid' }],
  resolving: [{ id: 'room_address_resolving' }], resolvingLabel: [{ id: 'room_address_resolving_label' }],
  roomId: [{ id: 'room_address_room_id' }], servers: [{ id: 'room_address_servers' }],
  notFound: [{ id: 'room_address_not_found' }], error: [{ id: 'room_address_error' }],
  retry: [{ id: 'room_address_retry' }]
};
const postSelectors = { ...rootSelectors, input: formSelectors.input, state: formSelectors.state,
  roomId: [{ id: 'room_id' }], roomBack: [{ id: 'room_back' }] };

async function waitFor(session, label, read, accept, attempts = 160, delayMs = 50) {
  let last;
  for (let attempt = 0; attempt < attempts; attempt++) {
    last = await read();
    if (accept(last)) return last;
    await session.delay(delayMs);
  }
  throw new Error(label + ' unavailable: ' + JSON.stringify(last));
}

async function held(session, providerControl, caseId, alias) {
  return waitFor(session, 'nonce-bound provider hold', () => providerControl('status', {}), status =>
    (status.held || []).filter(row => row.caseId === caseId && row.alias === alias).length === 1);
}

async function frame(session, label, selectors = formSelectors) {
  return session.observeBracketed(label, selectors, () => ({}));
}

async function waitState(session, expected) {
  return waitFor(session, 'rendered address state ' + expected, () => frame(session, 'wait:' + expected), value =>
    value.controls.state?.present === true && value.controls.state.text === expected, 220, 50);
}

export async function runTask14CandidateV19(spec, config, session, providerControl, emit = () => {}, trace = () => {}) {
  const result = { protocol: 'task14.candidate-native.v19', taskId: spec.taskId, caseId: spec.caseId,
    traceDigest: spec.traceDigest, observed: {}, invariantChecks: [], evidence: [], eventExecuted: false,
    failure: null, normalization: { idle: 'unknown', not_found: 'room_not_found' } };
  const record = value => { result.evidence.push(clone(value)); emit(value); };
  const invariant = (description, passed, observed) => {
    need(spec.invariants.includes(description), 'Unexpected invariant identity: ' + description);
    result.invariantChecks.push({ description, passed, observed: clone(observed) });
  };
  try {
    const root = await frame(session, 'setup:root', rootSelectors);
    need(root.routeName === config.entryRoute && root.controls.search.visible === true &&
      root.controls.join.visible === true && root.controls.create.visible === true,
      'Candidate StartChat root is not physically available');
    trace('before:setup', clone(root));
    const rootAvailability = { search: root.controls.search, create: root.controls.create };
    await session.action('click', target(root.controls.join));
    let form = await frame(session, 'setup:form');
    need(form.controls.input.visible === true && form.controls.continue.visible === true &&
      form.controls.cancel.visible === true, 'Candidate join-by-address form is not physically available');

    if (spec.key === 'entry_opens_address_flow') {
      trace('before:event', clone(root));
      trace('after:event', clone(form));
      result.observed = { addressFlowVisible: true, address: form.controls.input.text,
        addressState: canonicalState(form.controls.state.text) };
      await session.action('click', target(form.controls.cancel));
      const returned = await frame(session, 'invariant:returned-root', rootSelectors);
      invariant('existing create-room and direct-message actions remain available',
        rootAvailability.search.enabled === true && rootAvailability.create.enabled === true &&
        returned.controls.search.visible === true && returned.controls.search.enabled === true &&
        returned.controls.create.visible === true && returned.controls.create.enabled === true,
        { before: rootAvailability, after: { search: returned.controls.search, create: returned.controls.create } });
    } else if (spec.key === 'update_trims_and_debounces') {
      trace('before:event', clone(form));
      await session.action('input', form.controls.input, spec.event.value);
      const immediateStatus = await providerControl('status', {});
      form = await frame(session, 'boundary:before-debounce');
      await session.delay(300);
      const admitted = await held(session, providerControl, spec.caseId, '#team:example.org');
      const after = await frame(session, 'after:event'); trace('after:event', clone(after));
      result.observed = { address: after.controls.input.text,
        addressStateBefore300ms: canonicalState(form.controls.state.text), resolveAfterMs: 300 };
      await session.action('input', after.controls.input, '#other:example.org');
      await providerControl('release', { alias: '#team:example.org' });
      await session.delay(400);
      const stale = await frame(session, 'invariant:stale-response');
      invariant('each address change invalidates the previous resolution',
        stale.controls.input.text === '#other:example.org' && stale.controls.roomId.present !== true &&
        stale.routeName === config.entryRoute,
        { input: stale.controls.input.text, roomId: stale.controls.roomId.text || null,
          routeName: stale.routeName, immediateHeld: immediateStatus.held,
          admittedRequestCount: admitted.requestCount, admittedHeld: admitted.held });
      need(!(immediateStatus.held || []).some(row => row.alias === '#team:example.org'),
        'Alias request was already held at the immediate pre-debounce sample');
    } else if (spec.key === 'invalid_after_continue') {
      await session.action('input', form.controls.input, spec.given.address);
      await session.dismissKeyboard();
      form = await frame(session, 'before:event'); trace('before:event', clone(form));
      const suppressed = form.controls.invalid.present !== true;
      const before = await providerControl('status', {});
      await session.action('click', target(form.controls.continue));
      await session.delay(100);
      const after = await frame(session, 'after:event'); trace('after:event', clone(after));
      const afterStatus = await providerControl('status', {});
      result.observed = { addressState: canonicalState(after.controls.state.text),
        errorVisible: after.controls.invalid.visible === true, navigationCount: 0 };
      invariant('invalid feedback is suppressed before validation is requested', suppressed &&
        (before.held || []).length === 0 && (afterStatus.held || []).length === 0,
        { beforeInvalidVisible: !suppressed, afterInvalid: after.controls.invalid,
          providerHeldBefore: before.held, providerHeldAfter: afterStatus.held });
    } else if (spec.key === 'valid_address_resolves') {
      await session.action('input', form.controls.input, spec.given.address);
      const before = await frame(session, 'before:event'); trace('before:event', clone(before));
      await session.delay(spec.event.elapsedMs);
      const admitted = await held(session, providerControl, spec.caseId, spec.given.address);
      const after = await frame(session, 'after:event'); trace('after:event', clone(after));
      result.observed = { addressState: canonicalState(after.controls.state.text),
        effect: 'resolve_room_alias', alias: spec.given.address };
      await session.action('input', after.controls.input, 'not-a-room');
      await session.delay(400);
      const invalid = await frame(session, 'invariant:invalid');
      const finalStatus = await providerControl('status', {});
      invariant('only syntactically valid room aliases are resolved',
        invalid.controls.state.text === 'invalid' &&
        (finalStatus.held || []).filter(row => row.alias === spec.given.address).length === 1 &&
        !(finalStatus.held || []).some(row => row.alias === 'not-a-room'),
        { state: invalid.controls.state.text, heldBeforeInvalid: admitted.held,
          heldAfterInvalid: finalStatus.held });
    } else if (spec.key === 'found_then_continue_navigates') {
      await session.action('input', form.controls.input, '#team:example.org');
      await session.dismissKeyboard(); await held(session, providerControl, spec.caseId, '#team:example.org');
      await providerControl('release', { alias: '#team:example.org' });
      await session.delay(500);
      form = await frame(session, 'setup:after-resolution');
      trace('before:event', clone(form));
      await session.action('click', target(form.controls.continue));
      await session.delay(800);
      const after = await frame(session, 'after:event', postSelectors);
      trace('after:event', clone(after));
      result.observed = { dismissAddressFlow: after.controls.input.present !== true,
        openRoom: { roomIdOrAlias: after.routeParams?.roomId ?? null,
          serverNames: after.routeParams?.serverNames ?? null } };
      invariant('room navigation happens once', after.routeName === 'pages/Room' &&
        after.controls.roomId.text === spec.given.roomId && Number(after.stackLength) === 2,
        { routeName: after.routeName, routeParams: after.routeParams, stackLength: after.stackLength,
          renderedRoomId: after.controls.roomId.text });
    } else if (spec.key === 'continue_waits_for_resolution') {
      await session.action('input', form.controls.input, spec.given.address);
      await session.dismissKeyboard();
      const pending = await held(session, providerControl, spec.caseId, spec.given.address);
      form = await frame(session, 'setup:provider-held'); trace('before:event', clone(form));
      await session.action('click', target(form.controls.continue));
      const waiting = await frame(session, 'event:waiting');
      await providerControl('release', { alias: spec.given.address });
      await session.delay(800);
      const after = await frame(session, 'after:event', postSelectors);
      trace('after:event', clone(after));
      const finalStatus = await providerControl('status', {});
      result.observed = { validationRequested: waiting.controls.resolvingLabel.text === 'Opening the resolved room...',
        dismissAddressFlow: after.controls.input.present !== true, navigationCount: after.routeName === 'pages/Room' ? 1 : 0 };
      invariant('continue does not issue a second alias-resolution request',
        pending.held.filter(row => row.alias === spec.given.address).length === 1 &&
        (finalStatus.held || []).length === 0 && after.routeName === 'pages/Room' &&
        after.controls.roomId.text === spec.event.roomId,
        { heldBefore: pending.held, heldAfter: finalStatus.held, waitingLabel: waiting.controls.resolvingLabel.text,
          routeName: after.routeName, roomId: after.controls.roomId.text });
    } else if (spec.key === 'not_found_recovers') {
      await session.action('input', form.controls.input, spec.given.address);
      await session.dismissKeyboard(); await held(session, providerControl, spec.caseId, spec.given.address);
      form = await frame(session, 'setup:provider-held'); trace('before:event', clone(form));
      await providerControl('release', { alias: spec.given.address });
      await session.delay(500);
      const after = await frame(session, 'after:event'); trace('after:event', clone(after));
      result.observed = { addressState: canonicalState(after.controls.state.text),
        errorVisible: after.controls.notFound.visible === true, navigationCount: 0,
        editingEnabled: after.controls.input.enabled === true };
      invariant('resolution failures do not close the flow', after.routeName === config.entryRoute &&
        after.controls.input.visible === true && after.controls.continue.visible === true,
        { routeName: after.routeName, input: after.controls.input, state: after.controls.state.text });
    } else if (spec.key === 'timeout_recovers') {
      await session.action('input', form.controls.input, spec.given.address);
      await session.dismissKeyboard(); await held(session, providerControl, spec.caseId, spec.given.address);
      form = await frame(session, 'setup:provider-held'); trace('before:event', clone(form));
      await session.delay(spec.event.elapsedSeconds * 1000 + 300);
      const after = await frame(session, 'after:event');
      trace('after:event', clone(after));
      await session.action('input', after.controls.input, '#retry:example.org');
      const retry = await frame(session, 'invariant:retry-edit');
      result.observed = { addressState: canonicalState(after.controls.state.text), navigationCount: 0,
        retryByEditing: retry.controls.input.text === '#retry:example.org' };
      invariant('the resolver cannot leave the UI loading indefinitely',
        after.controls.state.text !== 'resolving' && after.controls.input.enabled === true &&
        retry.controls.input.text === '#retry:example.org',
        { timeoutState: after.controls.state.text, inputEnabled: after.controls.input.enabled,
          retryAddress: retry.controls.input.text });
    } else if (spec.key === 'dismiss_closes_flow') {
      await session.action('input', form.controls.input, '#team:example.org');
      await session.dismissKeyboard(); await held(session, providerControl, spec.caseId, '#team:example.org');
      form = await frame(session, 'setup:provider-held'); trace('before:event', clone(form));
      await session.action('click', target(form.controls.cancel));
      await providerControl('release', { alias: '#team:example.org' });
      await session.delay(500);
      const after = await frame(session, 'after:event', postSelectors); trace('after:event', clone(after));
      result.observed = { addressFlowVisible: after.controls.input.present === true, openRoomCount: 0 };
      invariant('dismissing never joins a room', after.routeName === config.entryRoute &&
        after.controls.input.present !== true && after.controls.search.visible === true,
        { routeName: after.routeName, inputPresent: after.controls.input.present,
          roomIdPresent: after.controls.roomId.present });
    } else {
      throw new Error('Unsupported Task14 candidate case: ' + spec.key);
    }
    result.eventExecuted = true;
  } catch (error) {
    result.failure = String(error);
  }
  record({ method: 'Task14.candidateEpisodeV19', caseId: spec.caseId,
    eventExecuted: result.eventExecuted, failure: result.failure });
  return result;
}
