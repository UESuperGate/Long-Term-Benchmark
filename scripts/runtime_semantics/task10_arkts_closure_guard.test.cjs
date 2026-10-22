'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const guard = require('./task10_arkts_closure_guard.cjs');
const fixture = guard.loadFixture();
const clone = object => JSON.parse(JSON.stringify(object));
function attrs(node, match) {
  if (match(node.attributes)) return node.attributes;
  for (const child of node.children) { const found = attrs(child, match); if (found) return found; }
}
test('full reviewed source and complete initial UI only permit real-prefix eligibility', () => {
  const result = guard.assessBaseEntry({ ...fixture.fullInputInventory, root: '/arbitrary/agent-copy' }, fixture.initialUiProjection);
  assert.equal(result.eligible, true);
  assert.equal(result.status, 'eligible_for_real_common_prefix_only');
  assert.ok(!['pass', 'fail'].includes(result.status));
});
test('commonPreview/private IDs without reviewed whole source closure cannot fail semantics', () => {
  for (const inventory of [{ files: 19, sha256: '0'.repeat(64) }, { ...fixture.fullInputInventory, files: 20 }]) {
    const result = guard.assessBaseEntry(inventory, fixture.initialUiProjection);
    assert.equal(result.eligible, false); assert.equal(result.status, 'not_scored');
  }
});
test('unknown extra renamed hidden disabled and duplicate controls all produce NS eligibility', () => {
  const mutations = [
    tree => tree.children.push({ attributes: { id: 'new', type: 'Button', visible: 'true', enabled: 'true' }, children: [] }),
    tree => tree.children.push({ attributes: { id: '', type: 'CustomClickable', visible: 'false', enabled: 'false' }, children: [] }),
    tree => { attrs(tree, a => a.id === 'attachment_send').id = 'renamed'; },
    tree => { attrs(tree, a => a.id === 'attachment_caption').type = 'NewEditor'; },
    tree => { attrs(tree, a => a.id === 'attachment_send').enabled = 'false'; },
    tree => { attrs(tree, a => a.id === 'attachment_send').visible = 'false'; },
    tree => tree.children.push(clone(tree.children[0])),
    tree => tree.children.splice(0, 1),
  ];
  for (const mutate of mutations) {
    const tree = clone(fixture.initialUiProjection); mutate(tree);
    const result = guard.assessBaseEntry(fixture.fullInputInventory, tree);
    assert.equal(result.eligible, false); assert.equal(result.status, 'not_scored');
  }
});
test('only geometry window ids and focus are volatile, not extra UI semantics', () => {
  const tree = clone(fixture.initialUiProjection);
  const input = attrs(tree, a => a.id === 'attachment_caption');
  Object.assign(input, { bounds: '[1,1][2,2]', hostWindowId: '9999', focused: 'true' });
  assert.equal(guard.assessBaseEntry(fixture.fullInputInventory, tree).eligible, true);
  input.unreviewedAction = 'click';
  assert.equal(guard.assessBaseEntry(fixture.fullInputInventory, tree).eligible, false);
});
test('negative runner dispatch requires the independent guard, not commonPreview alone', () => {
  const source = fs.readFileSync(require.resolve('./task10_arkts_strict_runtime.cjs'), 'utf8');
  assert.match(source, /assessBaseEntry\(sourceBefore, tree\)/);
  assert.match(source, /closureEligibility\?\.eligible === true/);
  assert.match(source, /Unknown\/extra\/renamed entry/);
});
