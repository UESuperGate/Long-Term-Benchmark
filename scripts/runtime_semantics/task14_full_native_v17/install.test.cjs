'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');
const installer = require('./install.cjs');

test('V17 forwards real scalar before/after frames to the canonical trace', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-v17-scalar-'));
  const file = path.join(directory, 'scalar.mjs');
  fs.writeFileSync(file, installer.scalarSource());
  try {
    const loaded = await import(pathToFileURL(file).href + '?v=' + Date.now());
    const state = { available: true, address: '', addressState: 'unknown', visibleAddressState: 'unknown',
      addressFlowVisible: true, navigationCount: 0, resolverRequests: [], resolvedRoom: null };
    let now = 0, statusReads = 0;
    const observer = { read: () => JSON.parse(JSON.stringify(state)), resolveExternal: async () => {} };
    const controls = { join: { visible: true }, search: { visible: true },
      input: { visible: true, enabled: true }, continue: { visible: true } };
    const session = {
      observeBracketed: async label => ({ label, controls }), delay: async () => {},
      action: async (kind, _control, value) => {
        if (kind === 'input') { state.address = String(value).trim(); state.addressState = 'unknown'; }
      }
    };
    const clock = { advance: async ms => { now += ms; },
      read: () => ({ now, calls: now >= 300 ? [{ method: 'timerCallback', at: 300 }] : [] }) };
    const providerStatus = async () => {
      statusReads++;
      if (statusReads === 2) {
        state.addressState = 'resolving';
        state.resolverRequests.push({ id: 1, alias: '#team:example.org', samePageResolver: true, settled: false });
      }
      return { held: statusReads >= 2 ? [{ caseId: 'case4', alias: '#team:example.org' }] : [] };
    };
    const traced = [];
    const result = await loaded.runTask14ScalarCasesV17({ caseId: 'case4', traceDigest: 'digest',
      key: 'valid_address_resolves', given: { address: '#team:example.org' }, event: { elapsedMs: 300 } }, {},
      session, observer, clock, () => {}, providerStatus, (label, value) => traced.push({ label, value }));
    assert.equal(result.failure, null);
    assert.deepEqual(traced.map(item => item.label), ['before:event', 'after:event']);
    assert.equal(traced[0].value.state.addressState, 'unknown');
    assert.equal(traced[1].value.state.addressState, 'resolving');
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('V17 requires physical room render for navigation cases', () => {
  const routes = installer.routesSource();
  const adapter = installer.adapterSource();
  assert.match(routes, /after\.routeName === 'pages\/Room'/);
  assert.match(routes, /after\.controls\.roomId\?\.text === spec\.given\.roomId/);
  assert.match(routes, /after\.controls\.roomId\?\.text === spec\.event\.roomId/);
  assert.match(adapter, /runTask14ScalarCasesV17/);
  assert.match(adapter, /owner\.providerStatus\(\), args\.trace/);
  assert.doesNotMatch(adapter, /runTask14ConfiguredRoutesV16\(/);
});
