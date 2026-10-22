'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');
const installer = require('./install.cjs');

test('V16 scalar source yields measured canonical values after joint admission', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-v16-scalar-'));
  const file = path.join(directory, 'scalar.mjs');
  fs.writeFileSync(file, installer.scalarSource());
  try {
    const loaded = await import(pathToFileURL(file).href + '?v=' + Date.now());
    const state = { available: true, address: '', addressState: 'unknown', visibleAddressState: 'unknown',
      addressFlowVisible: true, navigationCount: 0, resolverRequests: [], resolvedRoom: null };
    let now = 0, statusReads = 0;
    const observer = {
      read: () => JSON.parse(JSON.stringify(state)),
      resolveExternal: async () => {}
    };
    const controls = { join: { visible: true }, search: { visible: true },
      input: { visible: true, enabled: true }, continue: { visible: true } };
    const session = {
      observeBracketed: async () => ({ controls }), delay: async () => {},
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
      return { held: statusReads >= 2 ? [{ caseId: 'case2', alias: '#team:example.org', requestSequence: 4 }] : [] };
    };
    const result = await loaded.runTask14ScalarCasesV16({ caseId: 'case2', traceDigest: 'digest',
      key: 'update_trims_and_debounces', event: { value: '  #team:example.org  ' } }, {},
      session, observer, clock, () => {}, providerStatus);
    assert.equal(result.failure, null);
    assert.deepEqual(result.observed, { address: '#team:example.org',
      addressStateBefore300ms: 'unknown', resolveAfterMs: 300 });
    assert.equal(result.invariantChecks[0].description,
      'each address change invalidates the previous resolution');
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('V16 binds configured routes and refuses unadmitted raw episodes', () => {
  const adapter = installer.adapterSource();
  assert.match(adapter, /runTask14ConfiguredRoutesV16/);
  assert.match(adapter, /raw\.actions\.length > 0/);
  assert.match(adapter, /args\.caseSpec\.invariants/);
  assert.match(adapter, /Fresh configured SDK episode failed independent admission/);
  assert.doesNotMatch(adapter, /runTask14RealRoutesV6\(/);
});
