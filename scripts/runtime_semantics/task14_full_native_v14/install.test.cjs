'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');
const installer = require('./install.cjs');

test('V14 configures the exact evaluator CA before login and preserves TLS checks', () => {
  const e2e = installer.e2eSource();
  const bridge = installer.bridgeSource();
  assert.match(e2e, /configureAdditionalRootCertificate\(certificateBytes\)/);
  assert.ok(e2e.indexOf('configureAdditionalRootCertificate(certificateBytes)') <
    e2e.indexOf("inputControl('login_homeserver'"));
  assert.match(e2e, /rootConfigurationCode !== 0/);
  assert.match(bridge, /import matrixNativeAddon from 'libmatrix_native\.so'/);
  assert.match(bridge, /http, matrixNativeAddon,/);
  assert.doesNotMatch(e2e + bridge, /disable_ssl_verification|danger_accept_invalid/);
});
