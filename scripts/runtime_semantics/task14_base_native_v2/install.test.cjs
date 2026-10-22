'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('base V2 provides the native trust dependency required by the shared E2E factory', () => {
  const bridge = installer.bridgeSource();
  assert.match(bridge, /import matrixNativeAddon from 'libmatrix_native\.so'/);
  assert.match(bridge, /http, matrixNativeAddon,/);
  assert.match(installer.e2eSource(), /configureAdditionalRootCertificate/);
  assert.match(bridge, /evaluateTask14BaseV1/);
});
