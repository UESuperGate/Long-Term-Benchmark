// Pure validation shared by ArkVM evidence creation and independent host review.
function sameValue(left, right) {
  if (left === right) return true;
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object') return false;
  if (Array.isArray(left) !== Array.isArray(right)) return false;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every(key =>
    Object.prototype.hasOwnProperty.call(right, key) && sameValue(left[key], right[key]));
}

function mounted(frame, policy) {
  const node = frame && frame.anchor && frame.anchor.node;
  const viewport = frame && frame.viewport;
  const rect = node && String(node.bounds || '').match(/^\[\s*([-\d.]+),\s*([-\d.]+)\],\s*\[\s*([-\d.]+),\s*([-\d.]+)\]$/);
  if (!rect || !viewport || !Number.isFinite(viewport.width) || !Number.isFinite(viewport.height)) return false;
  const [left, top, right, bottom] = rect.slice(1).map(Number);
  return frame.available === true && frame.candidateRouteVerified === true &&
    String(frame.route.path || '') + String(frame.route.name || '') === policy.route &&
    frame.anchor.selector.kind === 'arkui_id' && frame.anchor.selector.value === policy.anchorId &&
    frame.anchor.present === true && node.type === policy.anchorType && node.visible === true &&
    right > left && bottom > top && Math.min(right, viewport.width) > Math.max(left, 0) &&
    Math.min(bottom, viewport.height) > Math.max(top, 0);
}

function deriveGivenChecks(spec, policy, probes) {
  const frame = probes[0] && probes[0].before;
  return Object.keys(spec.given || {}).map(field => {
    const binding = policy.givenBindings && policy.givenBindings[field];
    let established = !!binding && mounted(frame, policy) && sameValue(binding.value, spec.given[field]);
    if (established) {
      if (binding.kind === 'anchor_attributes') {
        established = !!binding.attributes && Object.keys(binding.attributes).length > 0 &&
          Object.entries(binding.attributes).every(([key, value]) => sameValue(frame.anchor.node[key], value));
      } else if (binding.kind !== 'rendered_surface') established = false;
    }
    return { field, expected: spec.given[field], established,
      observed: established ? binding.value : null,
      evidence: established ? [{ observationId: probes[0].observationId, pointer: '/before/anchor' }] : [],
      reason: established ? 'Source-bound UI observation matched the given binding' : 'Canonical given has no established same-instance runtime binding' };
  });
}

export function assessEntryAssertion(assertion, spec, policy, binding, usedObservationIds = []) {
  const errors = [];
  const require = (condition, reason) => { if (!condition) errors.push(reason); };
  try {
    require(['base', 'final', 'agent'].includes(binding.role) &&
      [binding.sourceSha256, binding.policySha256, spec.traceDigest].every(value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)),
      'Execution identity must contain a role and full SHA-256 digests');
    require(assertion.schemaVersion === 1 && assertion.kind === 'runtime_entry_assertion' && assertion.failPhase === 'entry', 'Invalid early-assertion discriminator');
    require(assertion.taskId === policy.taskId && assertion.caseId === spec.caseId && assertion.traceDigest === spec.traceDigest,
      'Canonical task/case/digest binding differs');
    require(policy.caseId === spec.caseId && policy.traceDigest === spec.traceDigest && policy.eventName === spec.event.name,
      'Entry policy is not bound to this canonical event');
    require(assertion.role === binding.role && assertion.taskId === binding.taskId && spec.taskId === binding.taskId,
      'Execution role/task binding differs');
    require(assertion.sourceSha256 === binding.sourceSha256 && policy.sourceSha256 === binding.sourceSha256,
      'Candidate page differs from the reviewed source');
    require(assertion.policySha256 === binding.policySha256 && assertion.policyId === policy.id, 'Policy provenance differs');
    require(policy.approval === 'approved' && policy.selectorCoverage === 'reviewed_complete', 'Entry policy requires independent review');
    require(assertion.postState === null && assertion.transitionExecuted === false && assertion.invariants.evaluated === false &&
      sameValue(assertion.invariants.unobserved, spec.invariants || []), 'Early failure must not invent post-state or evaluated invariants');
    require(Array.isArray(policy.entryIds) && policy.entryIds.length > 0 && new Set(policy.entryIds).size === policy.entryIds.length,
      'Entry policy requires distinct reviewed selectors');
    require(assertion.probes.length === policy.entryIds.length, 'Not every required entry alternative was attempted');
    require(sameValue(assertion.prerequisiteChecks, assertion.probes.flatMap(probe => probe.prerequisiteChecks)),
      'Prerequisite check references differ from the underlying probes');
    const probeIds = new Set();
    const instance = assertion.probes[0] && assertion.probes[0].instanceId;
    for (let index = 0; index < assertion.probes.length; index++) {
      const probe = assertion.probes[index];
      const selector = policy.entryIds[index];
      require(probe.schemaVersion === 1 && probe.kind === 'native_ui_entry_probe' && probe.backend === 'native_previewer_arkui', 'Unsupported UI proof backend');
      require(probe.caseId === `${binding.taskId}:${binding.role}:${spec.caseId}` && probe.instanceId === instance &&
        typeof instance === 'string' && instance.length > 0, 'UI proof is not from this case instance');
      require(typeof probe.observationId === 'string' && probe.observationId.startsWith(instance + '_entry_') &&
        !probeIds.has(probe.observationId) && !usedObservationIds.includes(probe.observationId), 'UI proof identity was reused');
      probeIds.add(probe.observationId);
      require(probe.candidateRoute === policy.route && mounted(probe.before, policy) && mounted(probe.after, policy),
        'Actual candidate route and onscreen positive anchor must remain mounted');
      for (const frame of [probe.before, probe.after]) {
        require(frame.target.selector.kind === 'arkui_id' && frame.target.selector.value === selector &&
          frame.target.present === false && frame.target.node === null, 'Required entry selector was not observed absent');
      }
      const action = probe.action;
      require(action.api === 'sendEventByKey' && action.selector.kind === 'arkui_id' && action.selector.value === selector &&
        action.action === 10 && sameValue(action.params, {}) && action.attempted === true && action.delivered === false && !action.error,
        'Native entry action was not actually rejected');
      require([probe.before.capturedAt, action.attemptedAt, probe.after.capturedAt].every(value => Number.isFinite(value) && value > 0) &&
        probe.before.capturedAt <= action.attemptedAt && action.attemptedAt <= probe.after.capturedAt,
        'Before/action/after timestamps are invalid');
    }
    const givens = deriveGivenChecks(spec, policy, assertion.probes);
    require(sameValue(assertion.givenChecks, givens), 'Given evidence does not match runtime observations');
    require(givens.every(check => check.established), 'Canonical givens remain unestablished');
  } catch (error) { errors.push('Malformed entry evidence: ' + String(error)); }
  return { status: errors.length ? 'not_scored' : 'fail', failPhase: errors.length ? null : 'entry', errors,
    reason: errors.length ? errors.join('; ') : 'Reviewed required entry is unavailable after an actual native action; post-state was not reached' };
}

export function createEntryAssertion(spec, policy, binding, probes) {
  const assertion = { schemaVersion: 1, kind: 'runtime_entry_assertion', failPhase: 'entry',
    taskId: binding.taskId, role: binding.role, caseId: spec.caseId, traceDigest: spec.traceDigest,
    policyId: policy.id, policySha256: binding.policySha256, sourceSha256: binding.sourceSha256,
    givenChecks: deriveGivenChecks(spec, policy, probes), probes,
    prerequisiteChecks: probes.flatMap(probe => probe.prerequisiteChecks),
    postState: null, transitionExecuted: false,
    invariants: { evaluated: false, unobserved: spec.invariants || [] } };
  return { assertion, assessment: assessEntryAssertion(assertion, spec, policy, binding) };
}
