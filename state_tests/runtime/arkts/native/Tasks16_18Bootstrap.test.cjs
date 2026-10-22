'use strict';

// Production domain regression with Preferences/filesystem external boundaries.
// Neither this suite nor the gateway ledger establishes an OS channel effect.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const sourcePath = path.resolve(__dirname, '../../../../final_dev_nodes/18_custom_notification_sounds_final_26_06_1/entry/src/main/ets/features/NotificationSoundFeature.ets');

function fixture(options = {}) {
  const stores = new Map();
  let failure = false;
  const sdk = {
    '@ohos.data.preferences': { async getPreferences(_context, name) {
      if (!stores.has(name)) stores.set(name, new Map());
      const values = stores.get(name);
      return { async get(key, fallback) { return values.has(key) ? values.get(key) : fallback; },
        async put(key, value) { if (failure) throw new Error('disk unavailable'); values.set(key, value); },
        async flush() {} };
    } },
    '@ohos.file.fs': options.fileApi || { unlinkSync() {} },
    '@ohos.multimedia.media': {}
  };
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
  }).outputText;
  new vm.Script(`(function(exports, require, module) { ${code}\n})`).runInNewContext()(module.exports,
    name => { if (!sdk[name]) throw new Error('Unbound SDK: ' + name); return { default: sdk[name] }; }, module);
  const api = module.exports;
  const store = new api.NotificationSoundStore();
  const presenter = new api.NotificationSettingsPresenter(store, new api.NotificationSoundCopier(), new api.NotificationChannelGateway());
  return { api, presenter, store, stores, context: { filesDir: '/test-owned/files' }, failWrites() { failure = true; } };
}

test('actual startup migrates message v0 once, preserves call, and survives fresh presenter', async () => {
  const f = fixture();
  await f.presenter.load(f.context);
  assert.equal(f.presenter.snapshot.messageSound.kind, 'element_default');
  assert.equal(f.presenter.snapshot.messageChannelVersion, 1);
  assert.equal(f.presenter.snapshot.callRingtone.kind, 'system_default');
  assert.equal(f.presenter.snapshot.callChannelVersion, 0);
  await f.presenter.load(f.context);
  const fresh = new f.api.NotificationSettingsPresenter(f.store, new f.api.NotificationSoundCopier(), new f.api.NotificationChannelGateway());
  await fresh.load(f.context);
  assert.equal(fresh.snapshot.messageChannelVersion, 1);
  assert.equal((await f.store.load(f.context)).messageSound.kind, 'element_default');
  assert.equal(f.stores.has('element_x_notification_channels'), false, 'bootstrap does not manufacture OS evidence');
});

test('production preference sequence is bootstrap1 -> explicit SystemDefault2 -> next change3', async () => {
  const f = fixture();
  await f.presenter.load(f.context);
  assert.equal(await f.presenter.selectPreset(f.context, f.api.SoundSlot.Message, f.api.NotificationSoundKind.SystemDefault), true);
  assert.equal(f.presenter.snapshot.messageChannelVersion, 2);
  await f.presenter.load(f.context);
  assert.equal(f.presenter.snapshot.messageSound.kind, 'system_default');
  assert.equal(f.presenter.snapshot.messageChannelVersion, 2);
  assert.equal(await f.presenter.selectPreset(f.context, f.api.SoundSlot.Message, f.api.NotificationSoundKind.ElementDefault), true);
  assert.equal(f.presenter.snapshot.messageChannelVersion, 3);
  assert.equal(f.presenter.snapshot.callChannelVersion, 0);
});

for (const [kind, version] of [['element_default', 0], ['silent', 0], ['custom', 0], ['system_default', 2]]) {
  test(`bootstrap preserves explicit ${kind}/v${version} and unrelated call selection`, async () => {
    const f = fixture();
    const state = new f.api.NotificationSoundSnapshot(new f.api.NotificationSoundSelection(kind, kind === 'custom' ? 'file:///owned' : '', 'Saved'),
      f.api.NotificationSoundSelection.custom('file:///call', 'Call'), version, 3);
    await f.store.save(f.context, state);
    await f.presenter.load(f.context);
    assert.equal(JSON.stringify(f.presenter.snapshot), JSON.stringify(state));
  });
}

test('bootstrap storage error rejects instead of publishing a migrated snapshot', async () => {
  const f = fixture();
  f.failWrites();
  await assert.rejects(f.presenter.load(f.context), /disk unavailable/);
  assert.equal(f.presenter.snapshot.messageChannelVersion, 0);
  assert.equal(f.stores.has('element_x_notification_channels'), false);
});

test('actual serialized custom updates after explicit SystemDefault commit v3 then v4', async () => {
  let releaseFirst, enteredFirst;
  const entered = new Promise(resolve => { enteredFirst = resolve; });
  const blocked = new Promise(resolve => { releaseFirst = resolve; });
  const copies = [];
  const f = fixture({ fileApi: { OpenMode: { READ_ONLY: 0 },
    async open(uri) { return { fd: uri }; }, async close() {},
    async copyFile(fd, destination) {
      copies.push({ fd, destination });
      if (fd === 'content://A') { enteredFirst(); await blocked; }
    }, unlinkSync() {} } });
  await f.presenter.load(f.context);
  await f.presenter.selectPreset(f.context, f.api.SoundSlot.Message, f.api.NotificationSoundKind.SystemDefault);
  const versions = [];
  const first = f.presenter.setCustomSound(f.context, f.api.SoundSlot.Message, 'content://A').then(value => {
    versions.push(f.presenter.snapshot.messageChannelVersion); return value;
  });
  await entered;
  const second = f.presenter.setCustomSound(f.context, f.api.SoundSlot.Message, 'content://B').then(value => {
    versions.push(f.presenter.snapshot.messageChannelVersion); return value;
  });
  assert.equal(copies.length, 1, 'second external copy has not started while first is pending');
  releaseFirst();
  assert.deepEqual(await Promise.all([first, second]), [true, true]);
  assert.deepEqual(copies.map(call => call.fd), ['content://A', 'content://B']);
  assert.deepEqual(versions, [3, 4]);
  assert.equal((await f.store.load(f.context)).messageChannelVersion, 4);
  assert.equal(f.presenter.snapshot.callChannelVersion, 0);
});
