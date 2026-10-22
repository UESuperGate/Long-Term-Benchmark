const need = (value, reason) => { if (!value) throw Error(reason); };
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const selectors = {
  input: [{ id: 'room_address_input' }, { id: 'join_address_input' }],
  continue: [{ id: 'join_room_continue' }, { id: 'join_address_continue' }],
  cancel: [{ id: 'join_room_cancel' }, { id: 'join_address_cancel' }],
  invalid: [{ id: 'address_validation_message' }, { id: 'join_address_error' }],
  notFound: [{ id: 'address_notfound_label' }, { id: 'join_address_error' }],
  resolving: [{ id: 'address_loading' }, { id: 'join_address_loading' }]
};

export async function runTask14ScalarCasesV16(spec, config, session, observer, clock, emit, providerStatus) {
  const result = { protocol: 'task14.same-page-scalar.v16', caseId: spec.caseId,
    traceDigest: spec.traceDigest, frames: [], eventExecuted: false, failure: null,
    observed: {}, invariantChecks: [], providerAdmissions: [], clockSnapshots: [] };
  const capture = async label => {
    const frame = await session.observeBracketed(label, selectors, () => observer.read());
    const sample = { label, frame, state: observer.read(), clock: clock.read() };
    result.frames.push(clone(sample));
    return sample;
  };
  const tick = async ms => { await clock.advance(ms); result.clockSnapshots.push(clone(clock.read())); };
  const awaitHeld = async alias => {
    let state, external, own;
    for (let attempt = 0; attempt < 80; attempt++) {
      state = observer.read();
      own = state.resolverRequests?.find(row => row.alias === alias && row.samePageResolver && !row.settled);
      external = await providerStatus();
      const held = external.held?.filter(row => row.caseId === spec.caseId && row.alias === alias) || [];
      if (own && held.length === 1) {
        result.providerAdmissions.push({ alias, requestId: own.id, held: clone(held[0]), attempt });
        return { state, own, external };
      }
      await session.delay(50);
    }
    throw Error('Own SDK request and nonce-bound provider hold were not jointly observed; NS');
  };
  try {
    need(['update_trims_and_debounces', 'valid_address_resolves', 'timeout_recovers'].includes(spec.key),
      'Unknown scalar case');
    const root = await session.observeBracketed('scalar:common', {
      join: [{ id: 'join_room_by_address' }], search: [{ id: 'people_search_input' }]
    }, () => observer.read());
    need(root.controls.join.visible && root.controls.search.visible, 'Own original common UI missing');
    await session.action('click', root.controls.join.actionAncestor || root.controls.join);
    let form = await capture('setup:form');
    need(form.frame.controls.input.visible && form.state.available, 'Original form owner not acquired by real render');

    if (spec.key === 'update_trims_and_debounces') {
      need(form.state.address === '' && form.state.addressState === 'unknown', 'Empty canonical given unavailable');
      await capture('before:event');
      await session.action('input', form.frame.controls.input, spec.event.value);
      await tick(299);
      const boundary = await capture('boundary:299');
      await tick(1);
      const admitted = await awaitHeld('#team:example.org');
      const after = await capture('after:event');
      need(clock.read().calls.some(call => call.method === 'timerCallback' && call.at === 300),
        'Owned debounce callback at 300ms missing');
      result.observed = { address: admitted.state.address,
        addressStateBefore300ms: boundary.state.addressState, resolveAfterMs: 300 };
      form = await capture('invariant:before-second-edit');
      await session.action('input', form.frame.controls.input, '#other:example.org');
      await capture('invariant:second-edit');
      await observer.resolveExternal(admitted.own.id, { roomId: '!old:example.org', servers: ['example.org'] });
      await tick(0);
      await session.delay(100);
      const stale = await capture('invariant:stale-response');
      const invalidated = stale.state.address === '#other:example.org' &&
        stale.state.resolvedRoom?.roomId !== '!old:example.org' && stale.state.navigationCount === 0;
      result.invariantChecks.push({ description: 'each address change invalidates the previous resolution',
        passed: invalidated, observed: { firstRequestId: admitted.own.id,
          secondAddress: stale.state.address, resolvedRoom: stale.state.resolvedRoom || null,
          navigationCount: stale.state.navigationCount } });
      need(after.state.addressState === 'resolving', 'The admitted request was not reflected as resolving');
    } else if (spec.key === 'valid_address_resolves') {
      await session.action('input', form.frame.controls.input, spec.given.address);
      const before = await capture('before:event');
      need(before.state.addressState === 'unknown' && before.state.address === spec.given.address,
        'Canonical debounce given missing');
      await tick(spec.event.elapsedMs);
      const admitted = await awaitHeld(spec.given.address);
      const after = await capture('after:event');
      result.observed = { addressState: after.state.addressState,
        effect: 'resolve_room_alias', alias: admitted.own.alias };
      const countBeforeInvalid = after.state.resolverRequests.length;
      const invalid = await capture('invariant:before-invalid');
      await session.action('input', invalid.frame.controls.input, 'not-a-room');
      await tick(300);
      await session.delay(100);
      const invalidAfter = await capture('invariant:invalid');
      const onlyValid = invalidAfter.state.addressState === 'invalid' &&
        invalidAfter.state.resolverRequests.length === countBeforeInvalid &&
        invalidAfter.state.resolverRequests.every(row => /^#[^:]+:.+$/.test(row.alias));
      result.invariantChecks.push({ description: 'only syntactically valid room aliases are resolved',
        passed: onlyValid, observed: { requests: invalidAfter.state.resolverRequests,
          invalidAddress: invalidAfter.state.address, invalidState: invalidAfter.state.addressState } });
    } else {
      await session.action('input', form.frame.controls.input, spec.given.address);
      await tick(300);
      const admitted = await awaitHeld(spec.given.address);
      form = await capture('setup:pending');
      need(form.state.addressState === 'resolving' && admitted.own, 'Own pending resolver missing');
      await session.action('click', form.frame.controls.continue.actionAncestor || form.frame.controls.continue);
      await capture('before:event');
      await tick(spec.event.elapsedSeconds * 1000);
      await session.delay(100);
      const after = await capture('after:event');
      form = await capture('invariant:before-retry');
      await session.action('input', form.frame.controls.input, '#retry:example.org');
      const retry = await capture('invariant:retry-edit');
      result.observed = { addressState: after.state.addressState,
        navigationCount: after.state.navigationCount,
        retryByEditing: retry.state.address === '#retry:example.org' && retry.frame.controls.input.enabled === true };
      const recovered = after.state.addressState === 'room_not_found' &&
        after.frame.controls.input.enabled === true && retry.frame.controls.input.enabled === true;
      result.invariantChecks.push({ description: 'the resolver cannot leave the UI loading indefinitely',
        passed: recovered, observed: { timeoutState: after.state.addressState,
          inputEnabledAfterTimeout: after.frame.controls.input.enabled,
          retryAddress: retry.state.address } });
    }
    result.eventExecuted = true;
  } catch (error) {
    result.failure = String(error);
  }
  emit({ method: 'Task14.scalarEpisodeV16', ...clone(result) });
  return result;
}
