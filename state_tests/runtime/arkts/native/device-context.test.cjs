'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

test('device bridge passes native ApplicationContext by identity, not the delegator wrapper', async () => {
  const app = { cacheDir: '/actual/cache' };
  const base = { getApplicationContext() { return app; } };
  const calls = [];
  const bridge = { modules: {}, capabilities: { context: {} } };
  const env = {
    abilityDelegatorRegistry: { getAbilityDelegator: () => ({ getAppContext: () => base }),
      getArguments: () => ({ parameters: { '-s ltbExecutionNonce': 'a'.repeat(32) } }) },
    fileUri: {}, media: {}, notification: {},
    createPlatformContext: async (...args) => { calls.push(args); return bridge; }
  };
  const source = fs.readFileSync(path.join(__dirname, 'native-device-platform.js'), 'utf8')
    .replace(/^import .*;\r?\n/gm, '').replace('export async function', 'async function');
  vm.runInNewContext(source + '\nthis.create = createNativeContext;', env);
  assert.strictEqual(await env.create('case', '/host/never-used', 'pages/Index'), bridge);
  assert.strictEqual(calls[0][3], app);
  assert.equal(calls[0][1], '');
  assert.match(bridge.capabilities.context.origin, /getApplicationContext/);
  assert.equal(bridge.capabilities.execution.nonce, 'a'.repeat(32));
});
