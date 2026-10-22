'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');
const installer = require('./install.cjs');

test('V15 waits for both page-owned and provider-held requests after 300ms', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-v15-scalar-'));
  const file = path.join(directory, 'scalar.mjs');
  fs.writeFileSync(file, installer.scalarSource());
  try {
    const loaded = await import(pathToFileURL(file).href + '?v=' + Date.now());
    const state = { available: true, address: '', addressState: 'unknown', resolverRequests: [] };
    let now = 0, providerReads = 0, resolved = false;
    const observer = {
      read: () => JSON.parse(JSON.stringify(state)),
      resolveExternal: async id => { assert.equal(id, 1); resolved = true; }
    };
    const controls = { join: { visible: true }, search: { visible: true },
      input: { visible: true }, continue: { visible: true } };
    const session = {
      observeBracketed: async () => ({ controls }),
      action: async (kind, _control, value) => {
        if (kind === 'input') { state.address = String(value).trim(); state.addressState = 'unknown'; }
      }
    };
    const clock = {
      advance: async ms => { now += ms; },
      read: () => ({ now, calls: now >= 300 ? [{ method: 'timerCallback', at: 300 }] : [] })
    };
    const providerStatus = async () => {
      providerReads++;
      if (providerReads === 2) state.resolverRequests.push({ id: 1, samePageResolver: true, settled: false });
      return { held: providerReads >= 2 ? [{ caseId: 'case2', alias: '#team:example.org' }] : [] };
    };
    const result = await loaded.runTask14ScalarCasesV15({ caseId: 'case2', traceDigest: 'digest',
      key: 'update_trims_and_debounces', event: { value: '  #team:example.org  ' } }, {},
      session, observer, clock, () => {}, providerStatus);
    assert.equal(result.failure, null);
    assert.equal(result.eventExecuted, true);
    assert.equal(resolved, true);
    assert.ok(providerReads >= 2);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('V15 still requires timer, page owner, and provider request together', () => {
  const source = installer.scalarSource();
  assert.match(source, /samePageResolver && !r\.settled/);
  assert.match(source, /item\.caseId === spec\.caseId/);
  assert.match(source, /item\.alias === '#team:example\.org'/);
  assert.match(source, /c=>c\.method==='timerCallback' && c\.at===300/);
});
