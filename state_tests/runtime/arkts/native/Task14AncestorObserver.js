// Relate a live inspector ancestor to a live Driver component, never source code.
export function inspectorBounds(node) {
  if (typeof node?.$rect !== 'string') return undefined;
  try {
    const points = JSON.parse('[' + node.$rect + ']');
    if (points.length !== 2 || points.some(p => !Array.isArray(p) || p.length !== 2 || p.some(n => !Number.isFinite(n)))) return undefined;
    const [a, b] = points;
    return { left: a[0], top: a[1], right: b[0], bottom: b[1] };
  } catch (_) { return undefined; }
}

export const sameBounds = (a, b) => Boolean(a && b &&
  ['left', 'top', 'right', 'bottom'].every(k => Number.isFinite(a[k]) && Number.isFinite(b[k]) && Math.abs(a[k] - b[k]) <= 1));

export async function findActionAncestor(tree, anchor, anchorBounds, inspect) {
  if (!sameBounds(inspectorBounds(anchor), anchorBounds)) return undefined;
  const paths = [];
  function visit(node, parents) {
    if (!node || typeof node !== 'object') return;
    if (node === anchor) paths.push(parents);
    for (const child of node.$children || node.children || []) visit(child, [...parents, node]);
  }
  visit(tree, []);
  if (paths.length !== 1) return undefined;
  for (const node of [...paths[0]].reverse()) {
    const bounds = inspectorBounds(node);
    if (!bounds || node.$ID === undefined || !node.$type) continue;
    const control = await inspect({ type: node.$type, inspectorId: node.$ID, bounds });
    if (control.present === true && control.visible === true && control.enabled === true && control.clickable === true) {
      return { ...control, anchorInspectorId: anchor.$ID,
        inspectorPath: paths[0].map(n => ({ type: n.$type, inspectorId: n.$ID, bounds: inspectorBounds(n) })),
        observationScope: 'Live inspector ancestry + unique same-type/same-bounds Driver component with observed enabled/clickable' };
    }
  }
  return undefined;
}

export function observePeopleSelection(namespace, record) {
  const proto = namespace?.CreateRoomBasePresenter?.prototype;
  const descriptor = proto && Object.getOwnPropertyDescriptor(proto, 'selectPerson');
  if (typeof descriptor?.value !== 'function') throw new Error('Original people selection method unavailable');
  const receivers = new Map();
  const calls = [];
  Object.defineProperty(proto, 'selectPerson', { ...descriptor, value: function(...args) {
    if (!receivers.has(this)) receivers.set(this, receivers.size + 1);
    const before = this.selectedPerson;
    const result = descriptor.value.apply(this, args);
    const event = { method: 'Task14.originalSelectPerson', receiverId: receivers.get(this),
      receiverCount: receivers.size, args: [...args], before, after: this.selectedPerson,
      scope: 'Original selection only; not DM creation or room navigation' };
    calls.push(event); record(event);
    return result;
  } });
  return { read: () => calls.slice(), dispose: () => Object.defineProperty(proto, 'selectPerson', descriptor) };
}
