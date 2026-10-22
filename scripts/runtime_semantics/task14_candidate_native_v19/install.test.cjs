'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');
const installer = require('./install.cjs');

const candidate = '/Users/z1an/research/.ltb-new-tasks-eval/task14_rebuilt_minimax_m3_probe_20261022_v2/arkts/14_join_room_by_address';

test('candidate V19 observes physical UI and provider without replacing production behavior', () => {
  const adapter = installer.adapterSource();
  const suite = installer.suiteSource();
  assert.match(adapter, /startTask14Page/);
  assert.match(adapter, /ports\.providerControl/);
  assert.doesNotMatch(adapter, /args\.load\(/);
  assert.doesNotMatch(adapter, /resolveExternal|\.settle\(/);
  assert.match(suite, /session\.action\('click'/);
  assert.match(suite, /session\.action\('input'/);
  assert.match(suite, /providerControl\('release'/);
  assert.match(suite, /value === 'not_found' \? 'room_not_found'/);
  assert.doesNotMatch(suite, /value === 'failed' \? 'room_not_found'/);
  assert.match(installer.bridgeSource(), /matrixNativeAddon/);
  assert.match(installer.e2eSource(), /matches\.length === 0/);
  assert.match(installer.e2eSource(), /await openUserCertificates\(\)/);
  assert.doesNotMatch(installer.e2eSource(), /uninstallUserTrustedCertificateSync/);
});

test('candidate V19 validates the real candidate chain and exports stable fixture hashes', () => {
  assert.ok(path.isAbsolute(candidate));
  const chain = installer.requireChain(candidate);
  assert.equal(chain.owner, 'entry/src/main/ets/features/JoinRoomByAddressOwner.ets');
  const fixtures = installer.expectedFixtures();
  assert.equal(fixtures.length, 15);
  assert.equal(new Set(fixtures.map(item => item.name)).size, fixtures.length);
  assert.ok(fixtures.every(item => /^[a-f0-9]{64}$/.test(item.sha256)));
});
