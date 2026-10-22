'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const installer = require('./install.cjs');

test('V7 launches the real candidate before the first login control query', () => {
  const source = installer.e2eSource();
  const launch = source.indexOf("await abilityDelegator.startAbility({ bundleName: candidateBundleName");
  const firstQuery = source.indexOf("await control('login_homeserver')", launch);
  assert.ok(launch > 0 && firstQuery > launch);
  assert.equal(source.split('candidate_started_for_login').length, 2);
  assert.doesNotMatch(source, /NativeDataOperationResult|applicationMethodsReplaced:\s*true/);
});

test('V7 renames only evaluator protocol/adapter and retains the configured SDK suites', () => {
  const adapter = installer.adapterSource();
  const bridge = installer.bridgeSource();
  assert.match(adapter, /evaluateTask14FullNativeV7/);
  assert.match(adapter, /runTask14ScalarCasesV6/);
  assert.match(adapter, /task14\.full-nine-configured-sdk\.v7/);
  assert.match(bridge, /Task14FullNativeV7\.adapter/);
  assert.match(bridge, /ports\.providerControl = e2e\.control/);
  const names = installer.expectedFixtures().map(item => item.name);
  assert.ok(names.includes('Task14FullNativeV7.adapter.js'));
  assert.ok(!names.includes('Task14FullNativeV6.adapter.js'));
  assert.equal(names.length, new Set(names).size);
});
