'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('base adapter executes a common route and never fabricates canonical post-state', () => {
  const adapter = installer.adapterSource();
  assert.match(adapter, /create_room_action/);
  assert.match(adapter, /create_room_cancel/);
  assert.match(adapter, /controls\.join\.present === false/);
  assert.match(adapter, /semantic_missing_feature_entry/);
  assert.match(adapter, /observed: \{\}/);
  assert.doesNotMatch(adapter, /expected:/);
});

test('base bridge uses real login E2E and candidate UI', () => {
  const bridge = installer.bridgeSource();
  assert.match(bridge, /createTask14NativeE2E/);
  assert.match(bridge, /evaluateTask14BaseV1/);
  assert.match(bridge, /await e2e\.prepare\(config\.bundleName\)/);
});
