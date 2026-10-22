'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');
const installer = require('./install.cjs');

async function loadOwner() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-v13-owner-'));
  const file = path.join(directory, 'owner.mjs');
  fs.writeFileSync(file, installer.ownerSource());
  const module = await import(pathToFileURL(file).href + '?v=' + Date.now());
  return { module, dispose: () => fs.rmSync(directory, { recursive: true, force: true }) };
}

test('V13 correlates a real bridge continuation across an await', async () => {
  const loaded = await loadOwner();
  let resolveNative;
  try {
    class AddonNativeMatrixBridge {
      resolveRoomAlias(_handle, _alias) { return new Promise(resolve => { resolveNative = resolve; }); }
    }
    class ConfiguredSessionRooms {
      constructor(bridge) { this.bridge = bridge; }
      async resolveRoomAlias(alias) { await Promise.resolve(); return this.bridge.resolveRoomAlias(7, alias); }
    }
    class Resolver {
      constructor(rooms) { this.rooms = rooms; }
      resolveRoomAlias(alias) { return this.rooms.resolveRoomAlias(alias); }
    }
    class Presenter {
      constructor(resolver) { this.resolver = resolver; this.navigator = {}; }
      resolve(alias) { return this.resolver.resolveRoomAlias(alias); }
    }
    loaded.module.configureTask14ConfiguredNamespacesV7({ ConfiguredSessionRooms }, { AddonNativeMatrixBridge });
    const observer = loaded.module.installTask14JoinOwnerV3({ JoinRoomByAddressPresenter: Presenter }, async () => ({}));
    observer.bindExternalResolver();
    const pending = new Presenter(new Resolver(new ConfiguredSessionRooms(new AddonNativeMatrixBridge()))).resolve('#room:test');
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    const state = observer.read();
    assert.equal(state.configuredRoomCalls.length, 1);
    assert.equal(state.nativeBridgeCalls.length, 1);
    assert.equal(state.nativeBridgeCalls[0].roomCallId, state.configuredRoomCalls[0].id);
    assert.equal(state.nativeBridgeCalls[0].calledOriginal, true);
    resolveNative({ ok: true });
    await pending;
    observer.dispose();
  } finally { loaded.dispose(); }
});

test('V13 rejects ambiguous async rooms origins before executing native bridge', () => {
  const source = installer.ownerSource();
  assert.match(source, /candidates\.length === 1/);
  assert.match(source, /item\.receiver === active\?\.resolver\?\.rooms/);
  assert.match(source, /item\.bridgeReceiver === this/);
  assert.match(source, /item\.alias === alias/);
  assert.match(source, /item\.nativeCallId === undefined/);
  assert.match(source, /lacks one unambiguous async page-owned rooms origin/);
});
