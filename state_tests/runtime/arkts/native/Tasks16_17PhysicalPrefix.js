// Real original-page controls only. Input eligibility is checked independently.
export async function runPhysicalPrefix(spec, bundle, driver, ON, launch, options = {}) {
  const identity = spec.taskId === '16_identity_reset';
  const raw = { schemaVersion: 1, taskId: spec.taskId, caseId: spec.caseId, key: spec.key,
    traceDigest: spec.traceDigest, bundleName: bundle, frames: [], actions: [],
    integrationTier: 'actual_page_physical_prefix', liveMatrixSdkOrServerVerified: false,
    observed: null, invariantChecks: [], unevaluatedInvariants: spec.invariants,
    eventExecuted: false, classification: 'unverified' };
  let sequence = 0;
  const capture = async label => {
    const windowIdentity = await launch.check(driver), inventory = [];
    for (const node of await driver.findComponents(ON.inWindow(bundle)) || []) {
      inventory.push({ id: await node.getId(), text: await node.getText(), type: await node.getType(),
        enabled: await node.isEnabled(), clickable: await node.isClickable(), bounds: await node.getBounds() });
    }
    const frame = { label, sequence: ++sequence, windowIdentity, inventory };
    raw.frames.push(frame);
    return frame;
  };
  try {
    if (!options.alreadyStarted) await launch.start();
    let before;
    for (let index = 0; index < 80; index++) {
      try { before = await capture('before_event'); break; } catch (_) { await driver.delayMs(100); }
    }
    if (!before) throw new Error('Original physical page/window unavailable');
    const selector = identity ? ON.type('Button').text('Enable backup') : ON.id('pinned_banner_next');
    const nodes = await driver.findComponents(selector.inWindow(bundle)) || [];
    if (nodes.length !== 1 || !await nodes[0].isEnabled() || !await nodes[0].isClickable()) {
      throw new Error('Actual common-prefix control unavailable/ambiguous');
    }
    const action = { sequence: ++sequence, kind: 'click', id: await nodes[0].getId(),
      text: await nodes[0].getText(), type: await nodes[0].getType(), completed: false };
    raw.actions.push(action);
    await nodes[0].click(); action.completed = true;
    let after;
    const target = identity ? 'Backup state: enabled' : 'Welcome to the room';
    for (let index = 0; index < 80; index++) {
      const matches = await driver.findComponents(ON.text(target).inWindow(bundle)) || [];
      if (matches.length === 1) { after = await capture('after_event'); break; }
      await driver.delayMs(100);
    }
    if (!after) throw new Error('Actual positive-control state change unavailable');
    raw.eventExecuted = true;
    // This is a runtime proposal, not a score. A reviewed full-input closure is mandatory.
    raw.classification = 'physical_prefix_completed';
  } catch (error) {
    raw.failure = { message: String(error), stack: error?.stack };
  }
  return raw;
}
