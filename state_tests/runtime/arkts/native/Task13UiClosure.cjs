'use strict';

function requireFact(value, reason) {
  if (!value) throw new Error('Unbound Task13 UI closure: ' + reason);
}

function validate(inventory) {
  requireFact(inventory?.complete === true && inventory.selector === 'all_components_in_original_window', 'incomplete inventory');
  const nodes = inventory.nodes;
  requireFact(Array.isArray(nodes) && nodes.length > 0 && nodes.length === inventory.nodeCount, 'empty/truncated inventory');
  const view = nodes.some(node => node.id === 'profile_user_id') ? 'profile' :
    nodes.some(node => node.type === 'Text' && node.text === 'Messages') ? 'timeline' :
    nodes.some(node => node.type === 'Text' && node.text === 'Room members') ? 'members' : null;
  requireFact(view, 'unknown original page surface');
  const ids = new Set();
  const named = {
    open_profile: ['Button', /^Profile$/], open_timeline: ['Button', /^Timeline$/], open_members: ['Button', /^Members$/],
    profile_display_name: ['Text', /^(Alice(?: updated)?|Bob|@(?:alice|bob):example\.org)$/],
    profile_user_id: ['Text', /^@(?:alice|bob):example\.org$/], profile_verified_badge: ['Text', /^Verified$/],
    legacy_verify_identity: ['Button', /^Verify identity$/], start_direct_message: ['Button', /^Message (Alice(?: updated)?|Bob|@(?:alice|bob):example\.org)$/],
    toggle_block_user: ['Button', /^(?:Block|Unblock) user$/],
    timeline_identity_warning: ['Text', /^(?:Alice(?: updated)?|Bob|@(?:alice|bob):example\.org) identity changed$/],
    timeline_acknowledge_identity: ['Button', /^(?:Withdraw verification|OK)$/]
  };
  const counts = {};
  for (const node of nodes) {
    requireFact(typeof node.id === 'string' && typeof node.text === 'string' && typeof node.type === 'string', 'node identity/type missing');
    for (const key of ['enabled', 'clickable', 'longClickable', 'scrollable', 'checkable', 'visible']) {
      requireFact(typeof node[key] === 'boolean', 'missing native boolean: ' + key);
    }
    const boundSearch = view === 'members' && node.type === 'TextInput' && node.id === '';
    requireFact(node.visible && !node.checkable && (boundSearch || (!node.longClickable && !node.scrollable)), 'hidden/overflow/scroll/extra gesture');
    const bounds = node.bounds, window = inventory.windowBounds;
    requireFact(bounds && window && ['left', 'top', 'right', 'bottom'].every(key => Number.isFinite(bounds[key]) && Number.isFinite(window[key])) &&
      bounds.left >= window.left && bounds.top >= window.top && bounds.right <= window.right && bounds.bottom <= window.bottom &&
      bounds.right > bounds.left && bounds.bottom > bounds.top, 'incomplete viewport');
    counts[node.type] = (counts[node.type] || 0) + 1;
    if (node.id) {
      requireFact(!ids.has(node.id), 'duplicate ID');
      ids.add(node.id);
      const descriptor = named[node.id];
      requireFact(descriptor && node.type === descriptor[0] && descriptor[1].test(node.text), 'additional/renamed control: ' + node.id);
      if (node.id === 'legacy_verify_identity') requireFact(!node.enabled && !node.clickable, 'legacy verification became actionable');
      else requireFact(node.enabled && node.clickable === (node.type === 'Button'), 'binding/interactability differs: ' + node.id);
    } else if (['root', 'Column', 'Row'].includes(node.type)) {
      requireFact(node.text === '' && !node.clickable, 'unbound container action/text');
    } else if (node.type === 'Text') {
      const texts = ['User profile', 'Opening direct message', 'User blocked', 'User unblocked', 'Messages', 'Room members'];
      requireFact(texts.includes(node.text) && !node.clickable, 'additional unbound text/surface');
    } else if (view === 'members' && node.type === 'Button') {
      requireFact(['Alice', 'Bob'].includes(node.text) && node.enabled && node.clickable, 'unbound member action');
    } else if (view === 'members' && node.type === 'TextInput') {
      requireFact(['', 'Bob'].includes(node.text) && node.enabled && node.clickable && node.longClickable && node.scrollable,
        'unbound search/input or native search capabilities differ');
    } else requireFact(false, 'additional unbound component: ' + node.type);
  }
  for (const id of ['open_profile', 'open_timeline', 'open_members']) requireFact(ids.has(id), 'navigation closure missing');
  requireFact(counts.root === 1 && counts.Row === 1, 'root/navigation inventory not complete');
  if (view === 'profile') {
    for (const id of ['profile_display_name', 'profile_user_id', 'start_direct_message', 'toggle_block_user']) requireFact(ids.has(id), 'profile closure missing');
    requireFact(ids.has('legacy_verify_identity') !== ids.has('profile_verified_badge'), 'unknown profile verification boundary');
    requireFact(counts.Column === 3 && counts.Text === (ids.has('profile_verified_badge') ? 4 : 3) &&
      counts.Button === (ids.has('legacy_verify_identity') ? 6 : 5) && nodes.length === 14, 'additional/missing profile nodes');
  } else if (view === 'timeline') {
    const warning = ids.has('timeline_identity_warning');
    requireFact(warning === ids.has('timeline_acknowledge_identity') && counts.Column === 1 &&
      counts.Button === (warning ? 4 : 3) && counts.Text === (warning ? 3 : 2) && nodes.length === (warning ? 10 : 8), 'timeline closure differs');
  } else {
    const members = nodes.filter(node => !node.id && node.type === 'Button');
    requireFact(members.length >= 1 && members.length <= 2 && counts.Column === 1 && counts.Text === 1 &&
      counts.TextInput === 1 && counts.Button === members.length + 3 && nodes.length === members.length + 8, 'member closure differs');
  }
  return { validated: true, view, nodeCount: nodes.length, unboundNodes: 0 };
}

function fromLayout(nodes, windowBounds) {
  const boolean = value => {
    requireFact(value === 'true' || value === 'false', 'incomplete layout boolean');
    return value === 'true';
  };
  return { complete: true, selector: 'all_components_in_original_window', windowBounds,
    nodeCount: nodes.length, nodes: nodes.map(node => {
      const match = /^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$/.exec(node.bounds || '');
      requireFact(match, 'layout bounds missing');
      return { id: node.id, text: node.text, type: node.type,
        enabled: boolean(node.enabled), clickable: boolean(node.clickable), longClickable: boolean(node.longClickable),
        scrollable: boolean(node.scrollable), checkable: boolean(node.checkable), visible: boolean(node.visible),
        bounds: { left: +match[1], top: +match[2], right: +match[3], bottom: +match[4] } };
    }) };
}

module.exports = { validate, fromLayout };
