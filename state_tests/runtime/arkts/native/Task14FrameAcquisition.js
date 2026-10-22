import { inspectorBounds, sameBounds } from './Task14AncestorObserver';

function nodes(tree) {
  const result = [];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.$type) result.push(node);
    for (const child of node.$children || node.children || []) visit(child);
  }
  visit(tree); return result;
}

function fingerprint(tree) {
  if (!tree || typeof tree !== 'object') return null;
  const a = tree.$attrs || {};
  return { type: tree.$type, nodeId: tree.$ID, rect: tree.$rect,
    attrs: Object.fromEntries(['id', 'content', 'text', 'label', 'value', 'visibility', 'opacity', 'enabled']
      .map(k => [k, a[k]])), children: (tree.$children || tree.children || []).map(fingerprint) };
}

function surface(tree) {
  const all = nodes(tree);
  const search = all.filter(n => n.$attrs?.id === 'people_search_input');
  const input = all.filter(n => ['room_address_input', 'address_input'].includes(n.$attrs?.id));
  if (search.length === 1 && search[0].$type === 'TextInput' && input.length === 0) return 'root';
  if (input.length === 1 && input[0].$type === 'TextInput' && search.length === 0) return 'form';
  return undefined;
}

export function assessPageFrame(frame, expected) {
  const reasons = [];
  const end = frame.bracketEnd;
  for (const [label, view] of [['before', frame], ['after', end]]) {
    if (!view || view.routeName !== expected.routeName || (expected.windowId !== undefined && view.windowId !== expected.windowId))
      reasons.push(label + ': original page/window mismatch');
    if (!surface(view?.tree)) reasons.push(label + ': inspector surface is missing or ambiguous');
  }
  if (frame.windowId !== end?.windowId) reasons.push('window changed across Driver acquisition');
  if (JSON.stringify(fingerprint(frame.tree)) !== JSON.stringify(fingerprint(end?.tree))) reasons.push('inspector changed across Driver acquisition');
  const observedSurface = surface(frame.tree);
  const search = frame.controls?.search, input = frame.controls?.input;
  const present = observedSurface === 'root' ? search : input;
  const absent = observedSurface === 'root' ? input : search;
  if (present?.present !== true || present.visible !== true || present.inspectorMatches !== 1)
    reasons.push('Driver surface visibility not independently established');
  if (absent?.present !== false || absent.inspectorMatches !== 0) reasons.push('Driver opposite surface absence not established');
  // Every observed control must correspond to this same bracketed tree. Missing
  // people controls remain genuine absence, not a reason to retry for a PASS.
  const all = nodes(frame.tree);
  for (const [name, control] of Object.entries(frame.controls || {})) {
    if (control.present === false && control.inspectorMatches === 0) continue;
    const s = control.selector || {};
    const matching = all.filter(n => (!s.id || n.$attrs?.id === s.id) && (!s.type || n.$type === s.type) &&
      (s.text === undefined || ['content', 'text', 'label', 'value'].some(k => n.$attrs?.[k] === s.text)));
    if (control.present !== true || matching.length !== 1 || !sameBounds(inspectorBounds(matching[0]), control.bounds))
      reasons.push(name + ': Driver/inspector identity or bounds mismatch');
  }
  const a = frame.stateBefore, b = frame.stateAfter;
  if (expected.stateRequired !== false || a?.available || b?.available) {
    if (!a?.available || !b?.available || a.instanceCount !== 1 || b.instanceCount !== 1 ||
        a.instanceId !== b.instanceId || expected.instanceId !== undefined && a.instanceId !== expected.instanceId ||
        typeof a.addressFlowVisible !== 'boolean' || a.addressFlowVisible !== b.addressFlowVisible)
      reasons.push('original receiver unavailable or changed during acquisition');
  }
  // A stable model/UI disagreement is not a transport retry condition. Likewise
  // a coherent root after Join is returned as-is, never polled until it is form.
  const fatal = reasons.length === 0 && a?.available && b?.available &&
    a.addressFlowVisible !== (observedSurface === 'form') ? 'Stable original receiver/UI surface disagreement' : undefined;
  return { consistent: reasons.length === 0 && !fatal, reasons, surface: observedSurface, fatal };
}

export async function acquirePageFrame(session, selectors, readState, expected, record,
  { timeoutMs = 5000, maxAttempts = 8, now = () => Date.now(), phase = 'page', method = 'Task14.pageAcquisitionAttempt' } = {}) {
  if (typeof session.observeBracketed !== 'function') throw new Error('Bracketed native page acquisition unavailable');
  const started = now();
  for (let attempt = 1; attempt <= maxAttempts && now() - started < timeoutMs; attempt++) {
    // No UI events, presenter setters, business delay or visibility substitution.
    const frame = await session.observeBracketed('acquisition:' + phase + ':' + attempt, selectors, readState);
    const assessment = assessPageFrame(frame, expected);
    const elapsedMs = now() - started;
    record({ method, phase, attempt, elapsedMs, assessment, frame });
    if (assessment.fatal) throw new Error(assessment.fatal);
    if (elapsedMs >= timeoutMs) break;
    if (assessment.consistent) return frame;
  }
  throw new Error('Bounded ' + phase + ' acquisition did not establish consistent inspector/Driver/original receiver state');
}

export const assessReturnedFrame = assessPageFrame;
export const acquireReturnedFrame = (session, selectors, readState, expected, record, options = {}) =>
  acquirePageFrame(session, selectors, readState, expected, record,
    { ...options, phase: 'returned-start-chat', method: 'Task14.returnAcquisitionAttempt' });
