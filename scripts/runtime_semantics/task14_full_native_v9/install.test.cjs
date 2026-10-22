'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('V9 restores the original page observer module contract', () => {
  assert.equal(installer.pageObserverAlias,
    "export { installTask14Observer } from './Task14JoinOwnerV3';\n");
  assert.match(installer.pageObserverAlias, /installTask14Observer/);
  assert.doesNotMatch(installer.pageObserverAlias, /evaluateTask14FullNative/);
  const expected = new Map(installer.expectedFixtures().map(item => [item.name, item]));
  assert.ok(expected.has('Task14PageObserver.js'));
  assert.ok(expected.has('Task14FullNativeV9.adapter.js'));
});

test('V9 retains V8 diagnostics and real configured SDK dispatch', () => {
  const e2e = installer.e2eSource();
  assert.match(e2e, /provider_tls_ready_before_login/);
  assert.match(e2e, /login_submit_clicked/);
  assert.match(e2e, /uniqueControlById\('session_error'\)/);
  assert.match(installer.adapterSource(), /runTask14ScalarCasesV6/);
  assert.match(installer.bridgeSource(), /evaluateTask14FullNativeV9/);
});
