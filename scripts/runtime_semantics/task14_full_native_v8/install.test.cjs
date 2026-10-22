'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('V8 observes real TLS, submit state, click, and rendered login failure', () => {
  const source = installer.e2eSource();
  assert.match(source, /provider_tls_ready_before_login/);
  assert.match(source, /login_submit_ready/);
  assert.match(source, /login_submit_clicked/);
  assert.match(source, /uniqueControlById\('session_error'\)/);
  assert.match(source, /providerRequestCount/);
  assert.doesNotMatch(source, /applicationMethodsReplaced:\s*true/);
});

test('V8 retains real candidate launch and configured SDK adapter', () => {
  const source = installer.e2eSource();
  assert.match(source, /candidate_started_for_login/);
  const adapter = installer.adapterSource();
  assert.match(adapter, /evaluateTask14FullNativeV8/);
  assert.match(adapter, /runTask14ScalarCasesV6/);
  assert.match(adapter, /task14\.full-nine-configured-sdk\.v8/);
  const names = installer.expectedFixtures().map(item => item.name);
  assert.ok(names.includes('Task14FullNativeV8.adapter.js'));
  assert.equal(names.length, new Set(names).size);
});
