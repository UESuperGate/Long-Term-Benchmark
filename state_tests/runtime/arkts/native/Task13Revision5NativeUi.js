import { connectTask13ExternalSdk } from './Task13PageOwnerSdk';
let binding;
let inventoryValidator;

export function configureTask13InventoryValidator(validator) { inventoryValidator = validator; }

export async function loadTask13Revision5Production() {
  if (!binding) throw new Error('Actual page production binding missing');
  return binding.importModule(binding.config.productionModuleUrl);
}

export function configureTask13Revision5Binding(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  if (!config.bundleName || config.moduleName !== 'entry' || !['base', 'final'].includes(config.role)) {
    throw new Error('Invalid Task13 revision5 binding');
  }
  binding = { config, importModule };
}


function observeBasePage(namespace) {
  const calls = [], presenters = [], restores = [];
  const blockCalls = [];
  const room = namespace.getRoomIdentityDataSource();
  let parent;
  const snapshot = presenter => ({ userId: presenter.userId, directMessageCalls: presenter.gateway.dmStarts });
  for (const [owner, isPresenter] of [[namespace.UserProfilePresenter, true], [namespace.UserProfileGateway, false]]) {
    const descriptor = owner && Object.getOwnPropertyDescriptor(owner.prototype, 'startDirectMessage');
    if (!descriptor || !descriptor.configurable || typeof descriptor.value !== 'function') {
      throw new Error('Original profile direct-message method cannot be observed');
    }
    Object.defineProperty(owner.prototype, 'startDirectMessage', { ...descriptor, value: function(...args) {
      if (isPresenter && !presenters.includes(this)) presenters.push(this);
      const presenter = isPresenter ? this : parent;
      if (!presenter) throw new Error('Unbound profile gateway observation');
      const call = { sequence: calls.length + 1, method: 'startDirectMessage', owner: isPresenter ? 'presenter' : 'gateway',
        presenterId: presenters.indexOf(presenter) + 1, sameGatewayReceiver: !isPresenter && presenter.gateway === this,
        completed: false, before: snapshot(presenter) };
      calls.push(call);
      const previous = parent;
      if (isPresenter) parent = this;
      try { const value = descriptor.value.apply(this, args); call.completed = true; return value; }
      finally { call.after = snapshot(presenter); parent = previous; }
    } });
    restores.push(() => Object.defineProperty(owner.prototype, 'startDirectMessage', descriptor));
  }
  let blockParent;
  for (const [owner, method, isPresenter] of [[namespace.UserProfilePresenter, 'toggleBlocked', true],
    [namespace.UserProfileGateway, 'setBlocked', false]]) {
    const descriptor = Object.getOwnPropertyDescriptor(owner.prototype, method);
    if (!descriptor?.configurable || typeof descriptor.value !== 'function') throw new Error('Original block binding unavailable');
    Object.defineProperty(owner.prototype, method, { ...descriptor, value: function(...args) {
      const presenter = isPresenter ? this : blockParent;
      if (!presenter) throw new Error('Unbound block gateway observation');
      const call = { method, userId: presenter.userId, completed: false,
        sameGatewayReceiver: !isPresenter && presenter.gateway === this,
        before: { blocked: presenter.blocked, gatewayBlocked: presenter.gateway.blocked } };
      blockCalls.push(call);
      const previous = blockParent;
      if (isPresenter) blockParent = this;
      try { const value = descriptor.value.apply(this, args); call.completed = true; return value; }
      finally { call.after = { blocked: presenter.blocked, gatewayBlocked: presenter.gateway.blocked }; blockParent = previous; }
    } });
    restores.push(() => Object.defineProperty(owner.prototype, method, descriptor));
  }
  return {
    read() { return { available: presenters.length === 1, instanceCount: presenters.length,
      calls: JSON.parse(JSON.stringify(calls)), state: presenters.length === 1 ? snapshot(presenters[0]) : null,
      blockCalls: JSON.parse(JSON.stringify(blockCalls)),
      sameRoomReceiver: presenters.length === 1 && presenters[0].room === room,
      sdkState: { currentUserId: room.currentUserId, verificationAvailable: room.verificationAvailable,
        encryptedRoom: room.isEncrypted,
        members: room.members.map(member => ({ userId: member.userId, displayName: member.displayName })),
        identities: room.identities.map(identity => ({ userId: identity.userId, identityState: identity.identityState })) } }; },
    dispose() { for (const restore of restores.reverse()) restore(); }
  };
}

export async function runTask13Revision5NativeUi(caseJson, bundleName, driver, ON, launch) {
  const spec = JSON.parse(caseJson);
  if (!binding || binding.config.bundleName !== bundleName || spec.taskId !== '13_user_verification') {
    throw new Error('Task13 revision5 native identity mismatch');
  }
  const result = { taskId: spec.taskId, caseId: spec.caseId, key: spec.key,
    traceDigest: spec.traceDigest, bundleName, role: binding.config.role,
    sessionId: spec.caseId + ':' + Date.now(), frames: [], actions: [], entryExecuted: false,
    eventExecuted: false, observationMode: 'runtime_state_transition' };
  let observer, sequence = 0, stage = 'start';
  const selectors = {
    profile: [ON.id('profile_user_id'), ON.text('@alice:example.org')],
    dm: [ON.id('start_direct_message')],
    dmOpened: [ON.text('Opening direct message')],
    verify: [ON.id('verify_user_action')],
    remoteAccepted: [ON.id('verification_remote_accepted')],
    request: [ON.id('request_user_verification')],
    start: [ON.id('start_sas_verification')],
    accept: [ON.id('accept_sas_challenge')], decline: [ON.id('decline_sas_challenge')],
    reset: [ON.id('reset_verification')], step: [ON.id('verification_step')],
    target: [ON.id('verification_target_user')], loading: [ON.id('verification_reply_loading')],
    cancel: [ON.id('cancel_verification')],
    profileViolation: [ON.id('profile_verification_violation')],
    timelineWarning: [ON.id('timeline_identity_warning')],
    roomMemberWarning: [ON.id('room_member_identity_warning')],
    withdraw: [ON.id('withdraw_verification_action')],
    verifiedBadge: [ON.id('profile_verified_badge')], legacyVerify: [ON.id('legacy_verify_identity')],
    profileName: [ON.id('profile_display_name')],
    memberAlice: [ON.text('Alice').type('Button')], memberBob: [ON.text('Bob').type('Button')],
    block: [ON.id('toggle_block_user')],
    openTimeline: [ON.id('open_timeline')], openMembers: [ON.id('open_members')],
    openProfile: [ON.id('open_profile')], timelineWithdraw: [ON.id('timeline_acknowledge_identity')]
  };
  async function find(name) {
    for (const selector of selectors[name]) {
      const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
      if (nodes.length > 1) throw new Error('Ambiguous Task13 control: ' + name);
      if (nodes.length === 1) return nodes[0];
    }
    return undefined;
  }
  async function inspect(name) {
    const window = await launch.check(driver), node = await find(name);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds(), viewport = window.bounds;
    return { name, present: true, id: await node.getId(), text: await node.getText(),
      enabled: await node.isEnabled(), clickable: await node.isClickable(), bounds,
      visible: Math.min(viewport.right, bounds.right) > Math.max(viewport.left, bounds.left) &&
        Math.min(viewport.bottom, bounds.bottom) > Math.max(viewport.top, bounds.top) };
  }
  async function capture(label) {
    const controls = [];
    for (const name of Object.keys(selectors)) controls.push(await inspect(name));
    const frame = { label, sequence: ++sequence, sessionId: result.sessionId, bundleName,
      windowIdentity: launch.read().lastReady, controls, pageObserver: observer?.read() || { available: false } };
    result.frames.push(frame);
    {
      if (!inventoryValidator) throw new Error('Complete native UI inventory validator unavailable');
      const window = await launch.check(driver);
      const components = await driver.findComponents(ON.inWindow(bundleName));
      const nodes = [];
      for (const component of components) {
        const bounds = await component.getBounds();
        nodes.push({ id: await component.getId(), text: await component.getText(), type: await component.getType(),
          enabled: await component.isEnabled(), clickable: await component.isClickable(),
          longClickable: await component.isLongClickable(), scrollable: await component.isScrollable(),
          checkable: await component.isCheckable(), bounds,
          visible: bounds.left >= window.bounds.left && bounds.top >= window.bounds.top &&
            bounds.right <= window.bounds.right && bounds.bottom <= window.bounds.bottom &&
            bounds.right > bounds.left && bounds.bottom > bounds.top });
      }
      frame.uiInventory = { complete: true, selector: 'all_components_in_original_window',
        windowBounds: window.bounds, nodeCount: nodes.length, nodes };
      if (binding.config.role === 'base') frame.uiClosure = JSON.parse(inventoryValidator(JSON.stringify(frame.uiInventory)));
    }
    return frame;
  }
  const visible = (frame, name) => frame.controls.some(control => control.name === name && control.visible);
  async function click(name) {
    const control = await inspect(name), node = await find(name);
    if (!node || !control.visible || !control.enabled || !control.clickable) {
      throw new Error('Task13 control unavailable: ' + name);
    }
    const action = { kind: 'click', target: name, sequence: ++sequence,
      sessionId: result.sessionId, executed: false };
    result.actions.push(action);
    await node.click();
    action.executed = true;
    await driver.delayMs(100);
  }
  try {
    stage = 'launch';
    await launch.start();
    result.entryExecuted = true;
    let ready = false;
    let readinessError = '';
    for (let attempt = 0; attempt < 40; attempt++) {
      try {
        const profile = await inspect('profile');
        if (profile.visible) { ready = true; break; }
      } catch (error) { readinessError = String(error); }
      await driver.delayMs(120);
    }
    if (!ready) throw new Error('Original Task13 profile did not become ready: ' + readinessError);
    if (binding.config.role === 'final') {
      // The original HAP must load through its Ability before importing its module.
      // Otherwise API23 resolves an uninitialized entry module as a missing HSP.
      const namespace = await binding.importModule(binding.config.productionModuleUrl);
      observer = connectTask13ExternalSdk(namespace);
      await driver.delayMs(100);
      result.sdkSetupOrder = 'original_ability_profile_ready_then_original_module_then_external_ports';
    }
    if (binding.config.role === 'base') {
      const namespace = await binding.importModule(binding.config.productionModuleUrl);
      observer = observeBasePage(namespace);
      const room = namespace.getRoomIdentityDataSource();
      const sdkEffects = [];
      room.connectEncryptionService({
        async withdrawVerification(userId) { sdkEffects.push({ method: 'withdrawVerification', userId }); },
        async pinUserIdentity(userId) { sdkEffects.push({ method: 'pinUserIdentity', userId }); }
      });
      room.receiveSession('@current:example.org', true);
      room.receiveRoomSync(true, [new namespace.RoomMember('@alice:example.org', 'Alice'),
        new namespace.RoomMember('@bob:example.org', 'Bob')]);
      room.receiveIdentityChanges([new namespace.IdentityChange('@alice:example.org', namespace.IdentityState.Pinned),
        new namespace.IdentityChange('@bob:example.org', namespace.IdentityState.Pinned)]);
      await driver.delayMs(100);
      result.sdkInputReceipts = [{ kind: 'initial_sdk_inputs', state: observer.read().sdkState }];
      const before = await capture('before_event');
      if (!visible(before, 'profile')) throw new Error('Original profile positive anchor missing');
      if (!visible(before, 'dm') || visible(before, 'verify')) throw new Error('Base profile boundary differs');
      if (spec.key === 'identity_violation_surfaces') {
        room.receiveIdentityChanges([new namespace.IdentityChange('@alice:example.org', namespace.IdentityState.VerificationViolation),
          new namespace.IdentityChange('@bob:example.org', namespace.IdentityState.Pinned)]);
        result.actions.push({ kind: 'sdk_input', target: 'identity_violation_surfaces', sequence: ++sequence,
          sessionId: result.sessionId, executed: true });
        result.sdkInputReceipts.push({ kind: 'identity_state_change', state: observer.read().sdkState });
        await driver.delayMs(100);
        await capture('after_identity_change_profile');
        await click('openTimeline');
        await capture('after_identity_change_timeline');
        await click('openMembers');
        await capture('after_identity_change_members');
        await click('openProfile');
        await capture('after_identity_change_profile_restored');
      } else {
        const attempt = { sessionId: result.sessionId, sequence: ++sequence, event: 'select_verify_user',
          selectorId: 'verify_user_action', attempted: true, componentFound: null, failure: null };
        try { await click('verify'); throw new Error('Unexpected reachable verification entry'); }
        catch (error) {
          if (error.message !== 'Task13 control unavailable: verify') throw error;
          if (await find('verify')) throw new Error('Verification entry exists but its interactability is unverified');
          attempt.componentFound = false;
          attempt.failure = error.message;
        }
        result.entryAttempt = attempt;
        await capture('after_missing_entry_attempt');
      }
      await click('dm');
      const after = await capture('after_event');
      if (!visible(after, 'dmOpened')) throw new Error('Base direct-message positive control did not execute');
      result.basePositiveControl = { profileRendered: true, directMessageExecuted: true };
      if (spec.key === 'identity_violation_surfaces') {
        // Exercise the old Android timeline action only after the canonical
        // profile/member assertions. The SDK reply is a separate input event.
        await click('openTimeline');
        await click('timelineWithdraw');
        if (sdkEffects.length !== 1 || sdkEffects[0].method !== 'withdrawVerification' ||
            sdkEffects[0].userId !== '@alice:example.org') {
          throw new Error('Old timeline action did not invoke the original connected encryption service');
        }
        const pending = await capture('post_assertion_timeline_withdraw_requested');
        if (!visible(pending, 'timelineWarning')) throw new Error('Timeline optimistically changed before the SDK identity stream');
        room.receiveIdentityChanges([new namespace.IdentityChange('@alice:example.org', namespace.IdentityState.Pinned),
          new namespace.IdentityChange('@bob:example.org', namespace.IdentityState.Pinned)]);
        await driver.delayMs(100);
        const restored = await capture('post_assertion_timeline_sdk_updated');
        if (visible(restored, 'timelineWarning')) throw new Error('Original timeline did not consume the SDK identity update');
        result.oldTimelinePositiveControl = { sdkEffects: sdkEffects.map(effect => ({ ...effect })),
          warningHeldUntilSdkUpdate: true, warningCleared: true };
        await click('openProfile');
        room.receiveIdentityChanges([new namespace.IdentityChange('@alice:example.org', namespace.IdentityState.Verified),
          new namespace.IdentityChange('@bob:example.org', namespace.IdentityState.Pinned)]);
        room.receiveRoomSync(true, [new namespace.RoomMember('@alice:example.org', 'Alice updated'),
          new namespace.RoomMember('@bob:example.org', 'Bob')]);
        await driver.delayMs(100);
        const verified = await capture('post_assertion_verified_profile_sdk_updated');
        if (!visible(verified, 'verifiedBadge') || visible(verified, 'legacyVerify') ||
            verified.controls.find(control => control.name === 'profileName')?.text !== 'Alice updated') {
          throw new Error('Old profile did not react to verification/profile SDK streams');
        }
        room.receiveIdentityChanges([new namespace.IdentityChange('@alice:example.org', namespace.IdentityState.Pinned),
          new namespace.IdentityChange('@bob:example.org', namespace.IdentityState.Pinned)]);
        room.receiveRoomSync(true, [new namespace.RoomMember('@alice:example.org', 'Alice'),
          new namespace.RoomMember('@bob:example.org', 'Bob')]);
        await driver.delayMs(100);
        const unverified = await capture('post_assertion_unverified_profile_sdk_updated');
        if (visible(unverified, 'verifiedBadge') || !visible(unverified, 'legacyVerify')) {
          throw new Error('Old unverified profile did not restore the disabled legacy row');
        }
        await click('openMembers');
        const memberList = await capture('post_assertion_member_navigation_source');
        if (!visible(memberList, 'memberAlice') || !visible(memberList, 'memberBob')) {
          throw new Error('Original member list did not render both SDK members');
        }
        const search = await driver.findComponent(ON.type('TextInput').inWindow(bundleName));
        if (!search) throw new Error('Original member search input unavailable');
        await search.inputText('Bob');
        await driver.delayMs(100);
        const filtered = await capture('post_assertion_member_search_filtered');
        if (visible(filtered, 'memberAlice') || !visible(filtered, 'memberBob')) {
          throw new Error('Original member search did not filter the production SDK member list');
        }
        await search.clearText();
        await driver.delayMs(100);
        const cleared = await capture('post_assertion_member_search_cleared');
        if (!visible(cleared, 'memberAlice') || !visible(cleared, 'memberBob')) throw new Error('Original member search did not restore the list');
        await click('memberBob');
        const bob = await capture('post_assertion_member_navigation_destination');
        if (bob.controls.find(control => control.name === 'profile')?.text !== '@bob:example.org' ||
            bob.controls.find(control => control.name === 'profileName')?.text !== 'Bob') {
          throw new Error('Original member selection did not open the actual Bob profile');
        }
        await click('block');
        const blocked = await capture('post_assertion_original_block_control');
        const blockedCalls = blocked.pageObserver.blockCalls;
        if (blocked.controls.find(control => control.name === 'block')?.text !== 'Unblock user' ||
            blockedCalls.length !== 2 || !blockedCalls.every(call => call.completed && call.userId === '@bob:example.org' && call.after.gatewayBlocked === true) ||
            !blockedCalls[1].sameGatewayReceiver) throw new Error('Original block control is not bound to the page gateway');
        await click('block');
        const unblocked = await capture('post_assertion_original_unblock_control');
        if (unblocked.controls.find(control => control.name === 'block')?.text !== 'Block user' ||
            unblocked.pageObserver.blockCalls.length !== 4 || unblocked.pageObserver.blockCalls[3].after.gatewayBlocked !== false) {
          throw new Error('Original unblock control did not restore the source-bound profile');
        }
        result.baseStreamPositiveControl = { verifiedBadgeUpdated: true, legacyRowUpdated: true,
          displayNameUpdated: true, bothMembersRendered: true, memberProfileNavigated: true,
          searchFilteredAndRestored: true, blockAndUnblockBound: true };
      }
      result.eventExecuted = true;
    } else {
      stage = 'actual_route_owner_and_external_sdk_replay';
      const namespace = await binding.importModule(binding.config.productionModuleUrl);
      const pause = async () => { await driver.delayMs(100); };
      const receipt = async action => {
        const record = { kind: 'canonical_prefix', name: action.name, sequence: ++sequence, sessionId: result.sessionId, executed: false };
        result.actions.push(record);
        switch (action.name) {
          case 'open_room_member_profile': await click('openProfile'); break;
          case 'select_verify_user': await click('verify'); break;
          case 'request_verification': await click('request'); break;
          case 'receive_verification_request_acceptance': observer.emit('accepted'); break;
          case 'start_sas_verification': await click('start'); break;
          case 'receive_sas_started': observer.emit('started'); break;
          case 'receive_challenge': observer.emit('challenge', action.sas || spec.given.sas); break;
          case 'accept_challenge': await click('accept'); break;
          case 'receive_sdk_failure': observer.emit('failed'); break;
          default: throw Error('Unsupported canonical production prefix: ' + action.name);
        }
        await pause(); record.executed = true;
        record.frameLabel = 'prefix_' + record.sequence;
        await capture(record.frameLabel);
      };
      const initial = await capture('initial_profile');
      if (!visible(initial, 'profile') || !visible(initial, 'dm') || !visible(initial, 'verify')) {
        throw Error('Controlled SDK did not reach the real unverified production profile');
      }
      if (spec.key === 'identity_violation_surfaces') {
        await capture('before_event');
        observer.identities(namespace.IdentityState.VerificationViolation);
        result.actions.push({ kind: 'sdk_input', name: 'observe_identity_change', sequence: ++sequence,
          sessionId: result.sessionId, executed: true });
        await pause();
        await capture('after_identity_change_profile');
        await click('openTimeline'); await capture('after_identity_change_timeline');
        await click('openMembers'); await capture('after_identity_change_members');
        await click('openProfile'); await capture('after_event');
        await click('withdraw');
        const pending = await capture('post_assertion_withdraw_pending_sdk');
        if (!visible(pending, 'profileViolation')) throw Error('Withdrawal optimistically cleared the identity stream');
        observer.identities(namespace.IdentityState.Unverified); await pause();
        const completed = await capture('post_assertion_withdraw_sdk_update');
        if (visible(completed, 'profileViolation') || !visible(completed, 'verify')) throw Error('Withdrawal SDK update did not refresh profile');
        result.withdrawPositiveControl = { effectDelegated: true, warningHeldUntilSdkUpdate: true };
      } else {
        for (const action of spec.setup?.actions || []) await receipt(action);
        if (spec.given.identityState === 'verification_violation') {
          observer.identities(namespace.IdentityState.VerificationViolation); await pause();
          await capture('given_identity_stream');
        }
        if (spec.key === 'challenge_is_stable') result.pendingSdkPayload = observer.queueChallenge(spec.given.sas);
        await capture('before_event');
        switch (spec.event.name) {
          case 'verify_user_from_profile': await click('verify'); break;
          case 'request_verification': await click('request'); break;
          case 'start_sas_verification': await click('start'); break;
          case 'receive_challenge': observer.deliverChallenge(); break;
          case 'accept_challenge': await click('accept'); break;
          case 'decline_challenge': await click('decline'); break;
          case 'verification_finished':
            observer.emit('finished'); await pause();
            await capture('finish_rejected_without_sdk_verified_status');
            observer.setVerified('@alice:example.org', true);
            observer.identities(namespace.IdentityState.Verified);
            break;
          case 'cancel': await click('cancel'); break;
          case 'reset': await click('reset'); break;
          default: throw Error('Unsupported canonical event: ' + spec.event.name);
        }
        await pause(); await capture('after_event');
        result.actions.push({ kind: 'canonical_event', name: spec.event.name, sequence: ++sequence,
          sessionId: result.sessionId, executed: true });
      }
      result.eventExecuted = true;
      result.semanticTier = 'android_equivalent_controlled_external_sdk';
    }
  } catch (error) {
    result.failure = { stage, message: String(error), stack: error?.stack };
    try { await capture('failure_diagnostic_only'); } catch (captureError) { result.failure.captureError = String(captureError); }
  } finally {
    result.launchEvidence = launch.read();
    try { await launch.dispose(); result.launchCleanup = launch.read(); }
    catch (error) { result.failure = { ...result.failure, cleanupError: String(error) }; }
    result.ownerCleanup = observer?.read();
    observer?.dispose();
  }
  return JSON.stringify(result);
}

export { observeBasePage };
