'use strict';

// Host regression only: transpile the unchanged production source and replace
// external SDK services, never production methods. Not native scoring evidence.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.LTB_TYPESCRIPT ||
  '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const sourceFile = path.resolve(__dirname,
  '../../../../final_dev_nodes/18_custom_notification_sounds_final_26_06_1/entry/src/main/ets/features/NotificationSoundFeature.ets');
const compiled = ts.transpileModule(fs.readFileSync(sourceFile, 'utf8'), {
  fileName: sourceFile.replace(/\.ets$/, '.ts'), reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
});
assert.equal(compiled.diagnostics.filter(d => d.category === ts.DiagnosticCategory.Error).length, 0);

function fixture(options = {}) {
  const calls = [];
  const record = (name, args) => {
    calls.push({ name, args });
    if ((options.fail || []).includes(name)) throw new Error(name + ' unavailable');
  };
  const sources = [];
  let openCount = 0;
  const extractor = {
    set fdSrc(value) { record('fdSrc', value); },
    async fetchMetadata() { record('metadata'); return { title: options.title }; },
    async release() { record('release'); }
  };
  const fileApi = {
    OpenMode: { READ_ONLY: 0 },
    async open(...args) {
      record('open', args);
      if (++openCount === 1 && options.failMetadataOpen) throw new Error('metadata open unavailable');
      const source = { fd: 51 + sources.length };
      sources.push(source);
      return source;
    },
    async stat(fd) { record('stat', fd); return { size: 1700 }; },
    async close(file) {
      assert.ok(sources.includes(file));
      record('close', file.fd);
      if (file === sources[0] && options.failMetadataClose) throw new Error('metadata close unavailable');
    },
    async copyFile(...args) {
      assert.equal(typeof args[0], 'number', 'copyFile must receive the descriptor returned by open');
      assert.equal(args[0], sources.at(-1).fd);
      record('copy', args);
    }
  };
  const mediaApi = { async createAVMetadataExtractor() { record('create'); return extractor; } };
  const module = { exports: {} };
  const sdk = { '@ohos.file.fs': fileApi, '@ohos.multimedia.media': mediaApi,
    '@ohos.data.preferences': new Proxy({}, { get() { throw new Error('Copier must not access preferences'); } }) };
  new vm.Script(`(function(exports, require, module) {\n${compiled.outputText}\n})`, { filename: sourceFile })
    .runInNewContext()(module.exports, name => {
      assert.ok(Object.hasOwn(sdk, name), 'Unexpected runtime SDK import: ' + name);
      return { default: sdk[name] };
    }, module);
  return { calls,
    run: (uri = 'file:///selected/42', slot = module.exports.SoundSlot.Message) =>
      new module.exports.NotificationSoundCopier().copyToAppFiles({ filesDir: '/app/files' }, uri, slot) };
}

test('actual source metadata wins over a numeric URI basename and is closed before copy', async () => {
  const f = fixture({ title: 'An actual selected title' });
  const result = await f.run();
  assert.equal(result.succeeded, true);
  assert.equal(result.displayName, 'An actual selected title');
  assert.equal(result.appOwnedUri, 'file:///app/files/notification_sound_message.audio');
  assert.deepEqual(f.calls.map(c => c.name), ['open', 'stat', 'create', 'fdSrc', 'metadata', 'release', 'close', 'open', 'copy', 'close']);
  assert.deepEqual(JSON.parse(JSON.stringify(f.calls.find(c => c.name === 'fdSrc').args)), { fd: 51, offset: 0, length: 1700 });
  assert.deepEqual(f.calls.find(c => c.name === 'copy').args, [52, '/app/files/notification_sound_message.audio']);
  assert.equal(f.calls.at(-1).args, 52);
});

test('foreign titles retain the production control-character stripping and 256-character bound', async () => {
  const clean = await fixture({ title: ' \u0007Title\u007f with\n controls ' }).run();
  assert.equal(clean.displayName, 'Title with controls');
  const capped = await fixture({ title: 'x'.repeat(600) }).run();
  assert.equal(capped.displayName, 'x'.repeat(256));
});

for (const title of [undefined, '', ' \t\n ']) {
  test('missing or blank title falls back to decoded filename: ' + JSON.stringify(title), async () => {
    const result = await fixture({ title }).run('file:///selected/My%20tone.wav?token=secret#fragment', 'call');
    assert.equal(result.displayName, 'My tone.wav');
    assert.equal(result.appOwnedUri, 'file:///app/files/notification_sound_call.audio');
  });
}

for (const failure of ['stat', 'create', 'fdSrc', 'metadata']) {
  test('metadata boundary failure falls back and releases acquired resources: ' + failure, async () => {
    const f = fixture({ title: 'Unused title', fail: [failure] });
    const result = await f.run();
    assert.equal(result.succeeded, true);
    assert.equal(result.displayName, '42');
    const names = f.calls.map(c => c.name);
    assert.equal(names.filter(name => name === 'close').length, 2);
    assert.equal(names.filter(name => name === 'release').length, ['fdSrc', 'metadata'].includes(failure) ? 1 : 0);
    assert.equal(names.at(-1), 'close');
  });
}

for (const fail of [['release'], ['metadata'], ['metadata', 'release']]) {
  test('cleanup failures do not skip remaining cleanup or change copy outcome: ' + fail.join(','), async () => {
    const f = fixture({ title: 'Selected title', fail, failMetadataClose: true });
    const result = await f.run();
    assert.equal(result.succeeded, true);
    assert.equal(result.displayName, fail.includes('metadata') ? '42' : 'Selected title');
    assert.deepEqual(f.calls.slice(-5).map(c => c.name), ['release', 'close', 'open', 'copy', 'close']);
  });
}

test('copy errors remain failures after metadata resources are released', async () => {
  const f = fixture({ title: 'Selected title', fail: ['copy'] });
  const result = await f.run();
  assert.equal(result.succeeded, false);
  assert.equal(result.appOwnedUri, '');
  assert.match(result.errorMessage, /copy unavailable/);
  assert.deepEqual(f.calls.slice(-5).map(c => c.name), ['release', 'close', 'open', 'copy', 'close']);
});

test('unopenable source fails without copy and never invents a descriptor', async () => {
  const f = fixture({ fail: ['open'] });
  const result = await f.run('datashare://provider/audio/42');
  assert.equal(result.succeeded, false);
  assert.deepEqual(f.calls.map(c => c.name), ['open', 'open']);
});

test('optional metadata open failure can fall back when the copy open succeeds', async () => {
  const f = fixture({ failMetadataOpen: true });
  const result = await f.run('file:///selected/42');
  assert.equal(result.succeeded, true);
  assert.equal(result.displayName, '42');
  assert.deepEqual(f.calls.map(c => c.name), ['open', 'open', 'copy', 'close']);
});

test('copy descriptor close failure is not reported as a clean successful copy', async () => {
  const f = fixture({ fail: ['close'] });
  const result = await f.run();
  assert.equal(result.succeeded, false);
  assert.match(result.errorMessage, /close unavailable/);
  assert.deepEqual(f.calls.slice(-3).map(c => c.name), ['open', 'copy', 'close']);
});

test('unsupported source scheme never reaches native I/O', async () => {
  const f = fixture();
  const result = await f.run('https://example.invalid/audio.wav');
  assert.equal(result.succeeded, false);
  assert.deepEqual(f.calls, []);
});
