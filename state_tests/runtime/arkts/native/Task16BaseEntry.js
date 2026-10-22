export async function runTask16BaseEntry(bundleName, driver, ON, launch, candidateMode = false) {
  const result = { bundleName, observationLevel: 'native_candidate_ui', actions: [], frames: [],
    entryExecuted: false, eventExecuted: false };
  const selectors = {
    root: ON.text('Chat backup'),
    finalTitle: ON.text('Reset cryptographic identity'),
    finalEntry: ON.id('identity_reset_continue'),
    enableBackup: ON.type('Button').text('Enable backup'),
    enabledState: ON.text('Backup state: enabled')
  };
  const find = async name => {
    const nodes = await driver.findComponents(selectors[name].inWindow(bundleName)) || [];
    if (nodes.length > 1) throw new Error('Ambiguous base selector: ' + name);
    return nodes[0];
  };
  const inspect = async name => {
    const node = await find(name);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds();
    return { name, present: true, visible: bounds.right > bounds.left && bounds.bottom > bounds.top,
      enabled: await node.isEnabled(), clickable: await node.isClickable(), id: await node.getId(),
      text: await node.getText(), type: await node.getType(), bounds };
  };
  const capture = async label => {
    const controls = [];
    for (const name of Object.keys(selectors)) controls.push(await inspect(name));
    const frame = { label, windowIdentity: launch.read().lastReady, controls };
    result.frames.push(frame);
    return frame;
  };
  const settle = async predicate => {
    for (let index = 0; index < 40; index++) {
      try { if (await predicate()) return true; } catch (_) {}
      await driver.delayMs(100);
    }
    return false;
  };
  try {
    await launch.start();
    result.entryExecuted = true;
    if (!await settle(async () => {
      await launch.check(driver);
      return (await inspect('root')).visible || (candidateMode && (await inspect('finalTitle')).visible);
    })) {
      throw new Error('Actual candidate page did not become ready');
    }
    const before = await capture('before_event');
    const finalEntry = before.controls.find(item => item.name === 'finalEntry');
    const finalTitle = before.controls.find(item => item.name === 'finalTitle');
    if (candidateMode && finalEntry?.visible && finalEntry.enabled && finalEntry.clickable && finalTitle?.visible) {
      result.eventExecuted = true;
      result.classification = 'feature_entry_present';
      result.positiveControl = 'Reset cryptographic identity';
      await launch.check(driver);
      await capture('after_event');
      return JSON.stringify(result);
    }
    const featureAbsent = before.controls.filter(item => ['finalTitle', 'finalEntry'].includes(item.name))
      .every(item => !item.present);
    const enable = before.controls.find(item => item.name === 'enableBackup');
    if (!featureAbsent || !enable.visible || !enable.enabled || !enable.clickable) {
      throw new Error('Base positive control or final-entry absence not established');
    }
    const node = await find('enableBackup');
    await node.click();
    result.actions.push({ target: 'enableBackup', executed: true, api: 'UiTest.Component.click' });
    result.eventExecuted = true;
    if (!await settle(async () => (await inspect('enabledState')).visible)) {
      throw new Error('Base production positive control did not update rendered state');
    }
    const after = await capture('after_event');
    if (!after.controls.filter(item => ['finalTitle', 'finalEntry'].includes(item.name)).every(item => !item.present)) {
      throw new Error('Final-only identity-reset entry appeared after the base action');
    }
    result.positiveControl = 'Backup state: enabled';
    result.classification = 'feature_entry_absent';
  } catch (error) {
    result.failure = { message: String(error), stack: error?.stack };
  } finally {
    try {
      if (result.classification === 'feature_entry_present') launch.retain();
      await launch.dispose({ deferTermination: true });
    }
    catch (error) { result.cleanupError = String(error); }
    result.launchEvidence = launch.read();
  }
  return JSON.stringify(result);
}
