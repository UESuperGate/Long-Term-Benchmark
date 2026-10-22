function nodes(tree) {
  const result = [];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.$type) result.push(node);
    for (const child of node.$children || node.children || []) visit(child);
  }
  visit(tree);
  return result;
}

const fingerprint = tree => {
  if (!tree || typeof tree !== 'object') return null;
  const attrs = tree.$attrs || {};
  return { type: tree.$type, id: attrs.id, content: attrs.content, text: attrs.text,
    visibility: attrs.visibility, opacity: attrs.opacity, rect: tree.$rect,
    children: (tree.$children || tree.children || []).map(fingerprint) };
};

export function assessTask14RealFlowFrame(frame, expected) {
  const end = frame.bracketEnd;
  const reasons = [];
  const mixed = frame.windowId !== end?.windowId || frame.routeName !== end?.routeName ||
    JSON.stringify(fingerprint(frame.tree)) !== JSON.stringify(fingerprint(end?.tree));
  if (mixed) reasons.push('inspector/route/window changed during bracket');
  if (frame.routeName !== expected.routeName || end?.routeName !== expected.routeName)
    reasons.push('route mismatch: ' + frame.routeName + ' / ' + end?.routeName);
  const anchor = frame.controls?.[expected.anchor];
  if (anchor?.present !== true || anchor.visible !== true || anchor.enabled !== true || anchor.inspectorMatches !== 1)
    reasons.push('primary anchor is not uniquely visible/enabled in Driver and inspector');
  for (const name of expected.required || []) {
    const control = frame.controls?.[name];
    if (control?.present !== true || control.visible !== true || control.inspectorMatches !== 1)
      reasons.push(name + ' is not uniquely visible in Driver and inspector');
  }
  const treeIds = new Set(nodes(frame.tree).map(node => node.$attrs?.id).filter(Boolean));
  const forbidden = (expected.forbiddenIds || []).filter(id => treeIds.has(id));
  if (forbidden.length) reasons.push('foreign surface anchors present: ' + forbidden.join(', '));
  const coherentWrongRoute = !mixed && frame.routeName === end?.routeName && frame.routeName !== expected.routeName;
  const coherentWrongSurface = !mixed && forbidden.length > 0;
  return { consistent: reasons.length === 0, mixed, coherentWrongRoute, coherentWrongSurface, reasons };
}

export async function acquireTask14RealFlowFrame(session, label, selectors, expected, record,
  { timeoutMs = 5000, maxAttempts = 8 } = {}) {
  const started = Date.now();
  for (let attempt = 1; attempt <= maxAttempts && Date.now() - started < timeoutMs; attempt++) {
    const frame = await session.observeBracketed(label + ':' + attempt, selectors, () => ({}));
    const assessment = assessTask14RealFlowFrame(frame, expected);
    record({ method: 'Task14.realFlowFrameAttempt', label, attempt, elapsedMs: Date.now() - started,
      assessment, routeName: frame.routeName, routeParams: frame.routeParams, windowId: frame.windowId,
      controls: frame.controls });
    if (assessment.consistent) return frame;
    if (assessment.coherentWrongRoute || assessment.coherentWrongSurface)
      throw new Error('Coherent wrong Task14 surface: ' + assessment.reasons.join('; '));
    await session.delay(50);
  }
  throw new Error('Task14 frame remained mixed/unavailable: ' + label);
}
