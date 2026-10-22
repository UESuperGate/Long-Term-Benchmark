'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('V18 routes settle only through the real nonce-bound provider control', () => {
  const owner = installer.ownerSource();
  const routes = installer.routesSource();
  assert.match(owner, /async releaseProvider\(alias\)/);
  assert.match(owner, /providerControl\('release', \{ alias \}\)/);
  assert.match(routes, /row\.method === 'resolveWithTimeout'/);
  assert.match(routes, /await owner\.releaseProvider\(alias\)/);
  assert.doesNotMatch(routes, /owner\.resolveExternal/);
  assert.doesNotMatch(routes, /owner\.settle/);
  assert.match(routes, /after\.routeName === 'pages\/Room'/);
});

test('V18 normalizes only the complete legacy transition schema', () => {
  const adapter = installer.adapterSource();
  assert.match(adapter, /transition\.failure === undefined/);
  assert.match(adapter, /Array\.isArray\(transition\.unsupportedInvariants\)/);
  assert.match(adapter, /transition\.unsupportedInvariants\.length === 0/);
  assert.match(adapter, /transition\.failure = null/);
  assert.match(adapter, /runTask14ConfiguredRoutesV18/);
});
