'use strict';
// Test doubles exist only at OS HTTP/Asset/file APIs. All client/store/transport logic is production.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../../..');
function fixture(role = 'final') {
  const project = path.join(root, role === 'base' ? '15_account_deactivation_base_0_6_1' : 'final_dev_nodes/15_account_deactivation_final_0_6_3');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task15-account-'));
  const filesDir = path.join(directory, 'files'), cacheDir = path.join(directory, 'cache');
  fs.mkdirSync(filesDir); fs.mkdirSync(cacheDir);
  const requests = [], assets = new Map(), events = [], handles = new Map(), modules = new Map();
  let responder;
  const errors = { assetRead: null, assetWrite: null, assetRemove: null, mkdir: null, rmdir: null };
  const tags = Object.fromEntries(['ALIAS', 'SECRET', 'RETURN_TYPE', 'RETURN_LIMIT', 'ACCESSIBILITY', 'AUTH_TYPE', 'SYNC_TYPE', 'CONFLICT_RESOLUTION'].map(n => [n, n]));
  const key = map => Buffer.from(map.get(tags.ALIAS)).toString();
  const sdkAsset = {
    Tag: tags, ReturnType: { ALL: 0 }, Accessibility: { DEVICE_FIRST_UNLOCKED: 1 }, AuthType: { NONE: 0 },
    SyncType: { NEVER: 0 }, ConflictResolution: { OVERWRITE: 0 },
    async query(map) {
      events.push('asset.query'); if (errors.assetRead) throw errors.assetRead;
      if (!assets.has(key(map))) throw Object.assign(new Error('not found'), { code: 24000002 });
      return [new Map([[tags.SECRET, assets.get(key(map))]])];
    },
    async add(map) { events.push('asset.add'); if (errors.assetWrite) throw errors.assetWrite; assets.set(key(map), map.get(tags.SECRET)); },
    async remove(map) { events.push('asset.remove'); if (errors.assetRemove) throw errors.assetRemove; assets.delete(key(map)); }
  };
  const sdkFs = {
    OpenMode: { CREATE: 1, READ_WRITE: 2, TRUNC: 4 },
    async mkdir(dir) {
      events.push('fs.mkdir:' + dir);
      if (errors.mkdir) throw errors.mkdir;
      if (fs.existsSync(dir)) throw Object.assign(new Error('File exists'), { code: 13900015 });
      fs.mkdirSync(dir, { recursive: true });
    },
    async open(file) { const fd = fs.openSync(file, 'w+'); handles.set(fd, file); return { fd }; },
    async write(fd, value) { return fs.writeSync(fd, value); },
    async close(file) { fs.closeSync(file.fd); handles.delete(file.fd); },
    async access(file) { return fs.existsSync(file); },
    async stat(file) { return fs.statSync(file); },
    async readText(file) { return fs.readFileSync(file, 'utf8'); },
    async rmdir(dir) { events.push('fs.rmdir:' + dir); if (errors.rmdir) throw errors.rmdir; fs.rmSync(dir, { recursive: true }); }
  };
  const sdkHttp = {
    RequestMethod: { POST: 'POST' }, HttpDataType: { STRING: 0 },
    createHttp() {
      let item;
      return {
        request(url, options) {
          return new Promise((resolve, reject) => {
            item = { url, options, body: JSON.parse(options.extraData), destroyed: false,
              respond(status, body) { resolve({ responseCode: status, result: typeof body === 'string' ? body : JSON.stringify(body) }); }, reject };
            requests.push(item); events.push('http:' + url);
            if (responder) responder(item);
          });
        },
        destroy() { if (item) item.destroyed = true; events.push('http.destroy'); }
      };
    }
  };
  const sdk = {
    '@ohos.net.http': sdkHttp, '@ohos.security.asset': sdkAsset, '@ohos.file.fs': sdkFs,
    '@ohos.util': { TextEncoder, TextDecoder: class { decodeWithStream(bytes) { return new TextDecoder('utf-8', { fatal: true }).decode(bytes); } } }
  };
  function load(file) {
    if (modules.has(file)) return modules.get(file).exports;
    const module = { exports: {} }; modules.set(file, module);
    const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true });
    assert.equal(result.diagnostics.length, 0);
    vm.runInNewContext(result.outputText, { exports: module.exports, module, Uint8Array, Map, Set, Error, JSON,
      require(name) {
        if (Object.hasOwn(sdk, name)) return { default: sdk[name] };
        if (!name.startsWith('.')) throw new Error('Unexpected SDK import ' + name);
        return load(path.resolve(path.dirname(file), name + '.ets'));
      } }, { filename: file });
    return module.exports;
  }
  const core = load(path.join(project, 'entry/src/main/ets/services/AccountClient.ets'));
  const platform = load(path.join(project, 'entry/src/main/ets/services/NativeAccountClient.ets'));
  const client = platform.createAccountClient({ filesDir, cacheDir });
  const session = { schemaVersion: 1, homeserver: 'https://matrix.example.org', userId: '@alice:example.org',
    deviceId: 'DEVICE', accessToken: 'test-token', authMode: 'matrix', phase: 'active' };
  const makeStore = () => new platform.NativeAccountSessionStore(filesDir, cacheDir);
  return { client, core, platform, load, project, filesDir, cacheDir, requests, assets, events, errors, session,
    store: makeStore(), newClient: () => platform.createAccountClient({ filesDir, cacheDir }),
    setResponder(value) { responder = value; },
    async signedIn(authMode = 'matrix') { await makeStore().save({ ...session, authMode }); await client.restore(); },
    async login() {
      await client.restore(); const pending = client.login(session.homeserver, 'alice', 'login-password');
      requests.at(-1).respond(200, { user_id: session.userId, device_id: session.deviceId, access_token: session.accessToken });
      await pending;
    },
    async waitRequests(count) {
      for (let i = 0; i < 60 && requests.length < count; i++) await new Promise(resolve => setImmediate(resolve));
      assert.equal(requests.length, count, 'Expected actual HTTP boundary request count');
    },
    dispose() { for (const fd of handles.keys()) fs.closeSync(fd); fs.rmSync(directory, { recursive: true, force: true }); }
  };
}
module.exports = { fixture };
