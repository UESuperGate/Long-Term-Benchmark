export async function launchOriginal(bundleName, delegator, wait, events, retained) {
  const event = { bundleName, monitorAdded: false, monitorRemoved: false, observations: [] };
  events.push(event);
  const identity = ability => {
    const info = ability?.context?.abilityInfo;
    return info ? { bundleName: info.bundleName, name: info.name, moduleName: info.moduleName } : null;
  };
  const matches = ability => {
    const info = identity(ability);
    return info?.bundleName === bundleName && info.name === 'EntryAbility' && info.moduleName === 'entry';
  };
  const monitor = { abilityName: 'EntryAbility',
    onAbilityCreate(ability) { if (matches(ability)) event.createdCallback = identity(ability); },
    onAbilityForeground(ability) { if (matches(ability)) event.foregroundCallback = identity(ability); },
    onAbilityDestroy(ability) { if (matches(ability)) event.destroyedAbility = identity(ability); }
  };
  let completed = false;
  await delegator.addAbilityMonitor(monitor);
  event.monitorAdded = true;
  try {
    await delegator.startAbility({ bundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
    const created = await delegator.waitAbilityMonitor(monitor, 10000);
    event.createdAbility = identity(created);
    if (!matches(created)) throw new Error('Capability monitor did not observe the original candidate EntryAbility');
    const foreground = await wait('original ability foreground', async () => {
      try {
        const top = await delegator.getCurrentTopAbility();
        event.observations.push({ identity: identity(top) });
        return top;
      } catch (error) {
        event.observations.push({ error: String(error) });
        return null;
      }
    }, matches);
    event.foregroundAbility = identity(foreground);
    if (retained) retained.push({ monitor, event });
    completed = true;
    return foreground;
  } finally {
    if (!retained || !completed) {
      await delegator.removeAbilityMonitor(monitor);
      event.monitorRemoved = true;
    }
  }
}

export async function inspectOriginal(driver, ON, bundleName, id) {
  const found = await driver.findComponents(ON.id(id).inWindow(bundleName));
  const nodes = found === null ? [] : found;
  if (!Array.isArray(nodes)) throw new Error('Capability UI query returned no valid component result');
  const query = { transportCompleted: true, windowBundle: bundleName, id, count: nodes.length,
    nullMeansNoMatch: found === null };
  if (!nodes.length) return { present: false, visible: false, text: '', query };
  if (nodes.length !== 1) throw new Error('Ambiguous original candidate capability UI selector: ' + id);
  const bounds = await nodes[0].getBounds();
  const visible = bounds.right > bounds.left && bounds.bottom > bounds.top;
  return { present: true, visible, text: await nodes[0].getText(), bounds, query };
}

export async function runCapabilityProbe(bundleName, delegator, driver, ON, filesystem, entryId = 'deactivate_account_entry') {
  if (!['deactivate_account_entry', 'settings_deactivate_account'].includes(entryId)) throw new Error('Unbound capability entry control');
  const result = { schemaVersion: 1, entryQueryId: entryId, status: 'not_scored', checkpoints: [], calls: [], cleanup: {}, startup: [] };
  const pause = () => driver.delayMs(100);
  const wait = async (name, read, accept) => {
    for (let attempt = 0; attempt < 80; attempt++) {
      const value = await read();
      if (accept(value)) return value;
      await pause();
    }
    throw new Error('Capability probe timed out: ' + name);
  };
  const inspect = id => inspectOriginal(driver, ON, bundleName, id);
  const retained = [];
  const disposeMonitor = async entry => {
    if (!entry.event.monitorRemoved) {
      await delegator.removeAbilityMonitor(entry.monitor);
      entry.event.monitorRemoved = true;
    }
  };
  const open = () => launchOriginal(bundleName, delegator, wait, result.startup, retained);
  let store, session, originalContext, resultPath;
  try {
    const initial = await open();
    await wait('initial signed-out form', () => inspect('account_homeserver'), value => value.present);
    originalContext = initial.context;
    resultPath = delegator.getAppContext().getApplicationContext().cacheDir + '/task15-capability-result.json';
    const native = await import('@bundle:' + bundleName + '/entry/ets/services/NativeAccountClient');
    store = new native.NativeAccountSessionStore(originalContext.filesDir, originalContext.cacheDir);
    session = { schemaVersion: 1, homeserver: 'https://task15-unsupported.invalid',
      userId: '@unsupported:task15.test', deviceId: 'UNSUPPORTED_CAPABILITY',
      accessToken: 'evaluator-owned-unused-oidc-token', authMode: 'oidc', phase: 'active' };
    await store.save(session);
    const stored = await store.read();
    const client = native.createAccountClient(originalContext);
    await client.restore();
    const capability = await client.canDeactivateAccount();
    result.calls.push({ method: 'NativeAccountSessionStore.save/read', production: true,
      authMode: stored?.authMode, phase: stored?.phase, userId: stored?.userId });
    result.calls.push({ method: 'AccountClient.restore/canDeactivateAccount', production: true,
      restoredUserId: client.userId(), capability });
    if (stored?.authMode !== 'oidc' || stored?.phase !== 'active' || client.userId() !== session.userId) {
      throw new Error('Authenticated unsupported given was not established');
    }
    result.checkpoints.push({ name: 'authenticated_unsupported_given', state: {
      authMode: stored.authMode, phase: stored.phase, userId: stored.userId, capability } });
    await initial.context.terminateSelf();
    await wait('original ability destruction before cold restart',
      () => Promise.resolve(retained[0].event.destroyedAbility),
      value => value?.bundleName === bundleName && value.name === 'EntryAbility' && value.moduleName === 'entry');
    await disposeMonitor(retained[0]);
    await open();
    const visibleSession = await wait('original page restored session', () => inspect('account_session_user'),
      value => value.present && value.visible && value.text === session.userId);
    const samples = [];
    for (let attempt = 0; attempt < 5; attempt++) {
      samples.push({ session: await inspect('account_session_user'),
        signOut: await inspect('account_sign_out'), entry: await inspect(entryId) });
      await pause();
    }
    const hidden = samples.every(item => item.session.present && item.session.visible && item.session.text === session.userId &&
      item.signOut.present && item.signOut.visible && item.entry.present === false);
    result.observed = { authenticatedUserId: visibleSession.text, capability,
      deactivateEntryVisible: !hidden, originalPageRestored: true };
    result.checkpoints.push({ name: 'original_settings_after_capability_load', state: { samples } });
    result.status = capability === false && hidden ? 'pass' : 'fail';
  } catch (error) {
    result.error = String(error);
    result.errorStack = String(error?.stack || '');
  } finally {
    for (const entry of retained) {
      try { await disposeMonitor(entry); }
      catch (error) { result.cleanup.monitorError = String(error); result.status = 'not_scored'; }
    }
    try {
      if (store && session) {
        await store.clear(session);
        result.cleanup.productionSessionRemoved = await store.read() === null;
      }
    } catch (error) { result.cleanup.error = String(error); }
    if (result.cleanup.productionSessionRemoved !== true) result.status = 'not_scored';
    const path = resultPath || delegator.getAppContext().getApplicationContext().cacheDir + '/task15-capability-result.json';
    filesystem.writeText(path, JSON.stringify(result));
  }
  return JSON.stringify(result);
}
