const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function fingerprint(tree) {
  if (!tree || typeof tree !== 'object') return null;
  const attrs = tree.$attrs || {};
  return { type: tree.$type, id: tree.$ID, rect: tree.$rect,
    attrs: Object.fromEntries(['id', 'content', 'text', 'label', 'value', 'enabled', 'visibility', 'opacity'].map(key => [key, attrs[key]])),
    children: (tree.$children || tree.children || []).map(fingerprint) };
}
export function assessTask11Frame(frame) {
  const reasons = [];
  const end = frame.bracketEnd, a = frame.stateBefore, b = frame.stateAfter;
  if (!frame.available || !end || frame.routeName !== end.routeName || frame.windowId !== end.windowId)
    reasons.push('Original route/window changed during acquisition');
  if (!equal(frame.viewport, end?.viewport)) reasons.push('Original window geometry changed during acquisition');
  if (!equal(fingerprint(frame.tree), fingerprint(end?.tree))) reasons.push('Original inspector changed during Driver acquisition');
  if (!a?.available || !b?.available || a.instanceCount !== 1 || b.instanceCount !== 1 ||
      a.instanceId !== b.instanceId || a.gatewayId !== b.gatewayId || !equal(a.room, b.room) || !equal(a.history, b.history))
    reasons.push('Original receiver/input state changed during acquisition');
  for (const [name, control] of Object.entries(frame.controls || {})) {
    if (control.present === false && control.inspectorMatches === 0) continue;
    if (control.present !== true || control.inspectorMatches !== 1 || typeof control.visible !== 'boolean')
      reasons.push(name + ': Driver/inspector observation incomplete');
  }
  return { consistent: reasons.length === 0, reasons };
}
export async function acquireTask11Frame(session, label, selectors, read, record) {
  if (typeof session.observeBracketed !== 'function') throw new Error('Original page bracketed acquisition unavailable');
  for (let attempt = 1; attempt <= 4; attempt++) {
    const frame = await session.observeBracketed(label, selectors, read);
    const assessment = assessTask11Frame(frame);
    record({ method: 'Task11.frameAcquisition', label, attempt, assessment, frame });
    if (assessment.consistent) return { ...frame, state: frame.stateAfter };
  }
  throw new Error('Original page frame remains incoherent or visibility unobserved; no semantic verdict');
}
