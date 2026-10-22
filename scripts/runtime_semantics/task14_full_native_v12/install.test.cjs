'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('V12 admits modal controls only through unique focused Driver identity and geometry', () => {
  const source = installer.coreSource();
  assert.match(source, /strict && !state\.driverInventory/);
  assert.match(source, /bounds: await component\.getBounds\(\)/);
  assert.match(source, /exact\.length === 0/);
  assert.match(source, /typeof selector\.id === 'string'/);
  assert.match(source, /id === selector\.id/);
  assert.match(source, /driverIdentityMatches\.length === 1/);
  assert.match(source, /validRect\(bounds\) && intersects\(bounds, state\.viewport\)/);
  assert.match(source, /unique_focused_driver_identity_and_geometry/);
});

test('V12 re-acquires the action target with strict inventory evidence', () => {
  const source = installer.coreSource();
  assert.match(source, /inspect\(control\.selector, state, true\)/);
  assert.match(source, /if \(fresh\.visible !== true \|\| fresh\.enabled !== true\)/);
  assert.match(source, /Original UI action target changed/);
  assert.equal(installer.pageObserverAlias,
    "export { installTask14Observer } from './Task14JoinOwnerV3';\n");
});
