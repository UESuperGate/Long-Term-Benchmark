'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('V10 closes a focused password IME before locating submit', () => {
  const source = installer.e2eSource();
  const input = source.indexOf("await inputControl('login_password', loginPassword)");
  const focused = source.indexOf('await passwordNode.isFocused()', input);
  const back = source.indexOf('await driver.pressBack()', focused);
  const checkpoint = source.indexOf("checkpoint('login_keyboard_dismissed'", back);
  const submit = source.indexOf("control('login_submit')", checkpoint);
  assert.ok(input > 0 && focused > input && back > focused && checkpoint > back && submit > checkpoint);
  assert.match(source, /if \(passwordFocused\)/);
});

test('V10 keeps V9 page observer and V8 diagnostics', () => {
  assert.equal(installer.pageObserverAlias,
    "export { installTask14Observer } from './Task14JoinOwnerV3';\n");
  assert.match(installer.e2eSource(), /provider_tls_ready_before_login/);
  assert.match(installer.e2eSource(), /uniqueControlById\('session_error'\)/);
  assert.match(installer.bridgeSource(), /evaluateTask14FullNativeV10/);
});
