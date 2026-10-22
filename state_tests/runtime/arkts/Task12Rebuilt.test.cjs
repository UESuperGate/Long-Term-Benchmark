'use strict';
// Host production execution. Only the external RoomTransport/HTTP SDK is controlled.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const http = require('node:http');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../..');
const projects = {
  base: '12_report_room_base_25_04_3_rebuilt',
  final: 'final_dev_nodes/12_report_room_final_25_05_4'
};
const roomId = '!alpha:rooms.invalid';
function loader(role, sdk) {
  const cache = new Map();
  return function load(name) {
    if (cache.has(name)) return cache.get(name);
    const file = path.join(root, projects[role], 'entry/src/main/ets/features', name + '.ets');
    const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true
    });
    assert.equal(compiled.diagnostics.length, 0);
    const module = { exports: {} };
    vm.runInNewContext(compiled.outputText, { exports: module.exports, module, require: request => {
      if (request === '@ohos.net.http' && sdk) return { default: sdk };
      assert.ok(request.startsWith('./'), 'Unexpected native/external import: ' + request);
      return load(request.slice(2));
    } }, { filename: file });
    cache.set(name, module.exports);
    return module.exports;
  };
}
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const response = (body, status = 200) => ({ status, body: JSON.stringify(body) });
function fixture(options = {}, role = 'final') {
  const calls = [], load = loader(role);
  const transport = { async request(method, url, body) {
    const call = { method, url, body }; calls.push(call);
    if (url.endsWith('/versions')) {
      if (options.capabilityError) throw new Error('External capability failure');
      return response(options.versions || { versions: ['v1.13'] });
    }
    if (url.endsWith('/joined_rooms')) return response({ joined_rooms: options.missing ? [] : [roomId] });
    if (url.endsWith('/state')) return response([
      { type: 'm.room.name', state_key: '', content: { name: 'Actual room name' } },
      { type: 'm.room.topic', state_key: '', content: { topic: 'Actual room topic' } },
      { type: 'm.room.member', state_key: '@alice:rooms.invalid', content: { membership: 'join' } }
    ]);
    if (url.endsWith('/report')) return options.report ? options.report(call) : response({});
    if (url.endsWith('/leave')) return options.leave ? options.leave(call) : response({});
    throw new Error('Unexpected external request ' + url);
  } };
  const types = role === 'final' ? load('ReportRoomFeature') : load('RoomDetailsFeature');
  const client = role === 'final' ? new (load('ReportRoomClient').MatrixReportingRoomClient)(transport) : new (load('RoomClient').MatrixRoomClient)(transport);
  const flow = role === 'final' ? new types.RoomFlow(roomId, client) : undefined;
  const details = flow?.details || new types.RoomDetailsPresenter(roomId, client);
  return { load, calls, types, client, flow, details, options };
}
const effects = f => f.calls.filter(c => c.method === 'POST').map(c => c.url.endsWith('/report') ? 'report' : 'leave');
async function form(f) { await f.details.load(); assert.equal(f.flow.openReport(), true); return f.flow.report; }

test('base loads real identity/details and confirms the preexisting leave without report API', async () => {
  const f = fixture({}, 'base');
  await f.details.load();
  assert.equal(f.details.room.roomId, roomId);
  assert.equal(f.details.room.name, 'Actual room name');
  assert.equal(f.details.room.memberCount, 1);
  assert.equal(typeof f.client.canReportRoom, 'undefined');
  assert.equal(typeof f.client.reportRoom, 'undefined');
  assert.deepEqual(effects(f), []);
  f.details.requestLeave(); assert.equal(f.details.leaveAction, 'confirming');
  f.details.cancelLeave(); assert.equal(f.details.leaveAction, 'uninitialized');
  await f.details.confirmLeave(); assert.deepEqual(effects(f), []);
  f.details.requestLeave(); await f.details.confirmLeave();
  assert.equal(f.details.leaveAction, 'success');
  assert.deepEqual(effects(f), ['leave']);
  assert.equal(f.calls.at(-1).url, '/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/leave');
});

test('base leave failure preserves identity and retries only at external leave', async () => {
  let attempts = 0;
  const f = fixture({ leave: () => response({}, ++attempts === 1 ? 500 : 200) }, 'base');
  await f.details.load(); f.details.requestLeave(); await f.details.confirmLeave();
  assert.equal(f.details.leaveAction, 'failure');
  await f.details.confirmLeave();
  assert.equal(f.details.leaveAction, 'success');
  assert.deepEqual(effects(f), ['leave', 'leave']);
});

test('final capability actually loads through client and opens one matching room flow', async () => {
  const f = fixture();
  assert.equal(f.details.canReportRoom, false); assert.equal(f.flow.openReport(), false);
  const p = await form(f);
  assert.equal(f.calls.filter(c => c.url.endsWith('/versions')).length, 1);
  assert.equal(p.roomId, roomId); assert.equal(p.service.client, f.details.client);
  assert.equal(f.flow.screen, 'report'); assert.equal(f.flow.openReport(), false);
  assert.equal(p.reason, ''); assert.equal(p.leaveRoom, false); assert.equal(p.canReport, false);
  assert.equal(p.reportAction, 'uninitialized'); assert.deepEqual(effects(f), []);
  f.flow.closeReport(); assert.equal(f.flow.screen, 'details');
});

test('unsupported/error/malformed capability stays hidden, without treating room absence as support', async () => {
  for (const options of [{ versions: { versions: ['v1.12'] } }, { capabilityError: true }, { versions: { versions: 'v1.13' } }, { missing: true }]) {
    const f = fixture(options); await f.details.load();
    assert.equal(f.details.canReportRoom, false); assert.equal(f.flow.openReport(), false);
    assert.deepEqual(effects(f), []);
  }
});

test('reason/toggle/blank/clear produce no network effect and keep independent form values', async () => {
  const f = fixture(), p = await form(f), count = f.calls.length;
  p.updateReason('Spam'); assert.equal(p.canReport, true); assert.equal(p.leaveRoom, false);
  p.toggleLeaveRoom(); assert.equal(p.reason, 'Spam'); assert.equal(p.leaveRoom, true);
  p.updateReason('   '); assert.equal(p.canReport, false); await p.submit();
  p.clearReportAction(); assert.equal(p.leaveRoom, true); assert.equal(p.reason, '   ');
  assert.equal(f.calls.length, count);
});

test('successful report uses exact room and untrimmed upstream reason; flow navigates back', async () => {
  const f = fixture(), p = await form(f);
  p.updateReason('  Spam  '); await f.flow.submitReport();
  assert.equal(p.reportAction, 'success'); assert.equal(f.flow.screen, 'details');
  assert.equal(f.details.leaveAction, 'uninitialized');
  assert.deepEqual(effects(f), ['report']);
  const call = f.calls.find(c => c.url.endsWith('/report'));
  assert.equal(call.url, '/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/report');
  assert.deepEqual(JSON.parse(call.body), { reason: '  Spam  ' });
});

test('external pending report keeps Loading and no leave; duplicate submit emits no duplicate effect', async () => {
  const started = deferred(), network = deferred();
  const f = fixture({ report: () => { started.resolve(); return network.promise; } }), p = await form(f);
  p.updateReason('Abuse'); p.toggleLeaveRoom();
  const pending = f.flow.submitReport(); await started.promise;
  assert.equal(p.reportAction, 'loading'); assert.deepEqual(effects(f), ['report']);
  f.flow.closeReport(); assert.equal(f.flow.screen, 'report');
  await p.submit(); assert.deepEqual(effects(f), ['report']);
  network.resolve(response({})); await pending;
  assert.deepEqual(effects(f), ['report', 'leave']); assert.equal(p.reportAction, 'success');
  assert.equal(f.details.leaveAction, 'success'); assert.equal(f.flow.screen, 'details');
});

test('report failure stops leave; clear keeps form and performs no request', async () => {
  const f = fixture({ report: () => response({}, 500) }), p = await form(f);
  p.updateReason('Spam'); p.toggleLeaveRoom(); await f.flow.submitReport();
  assert.equal(p.reportAction, 'report_failed'); assert.equal(f.flow.screen, 'report');
  assert.deepEqual(effects(f), ['report']);
  const count = f.calls.length; p.clearReportAction();
  assert.equal(p.reportAction, 'uninitialized'); assert.equal(p.reason, 'Spam'); assert.equal(p.leaveRoom, true);
  assert.equal(f.calls.length, count);
});

test('actual leave failure remembers report and retry runs leave only on same client/room', async () => {
  let attempts = 0;
  const f = fixture({ leave: () => response({}, ++attempts === 1 ? 500 : 200) }), p = await form(f);
  p.updateReason('Spam'); p.toggleLeaveRoom(); await f.flow.submitReport();
  assert.equal(p.reportAction, 'leave_failed'); assert.equal(f.flow.screen, 'report');
  assert.deepEqual(effects(f), ['report', 'leave']);
  await f.flow.submitReport();
  assert.equal(p.reportAction, 'success'); assert.deepEqual(effects(f), ['report', 'leave', 'leave']);
  assert.equal(f.flow.screen, 'details'); assert.equal(f.details.leaveAction, 'success');
});

test('room removed after navigation produces room_not_found without report or leave', async () => {
  const f = fixture(), p = await form(f);
  f.options.missing = true; p.updateReason('Spam'); await f.flow.submitReport();
  assert.equal(p.reportAction, 'room_not_found'); assert.deepEqual(effects(f), []);
});

test('invalid room/session and cross-origin path fail before external dispatch', async () => {
  const f = fixture(), { RoomSession } = f.load('RoomClient');
  assert.throws(() => new f.types.RoomFlow('not-a-room-id', f.client), /room ID/);
  for (const value of ['https://user:pass@server', 'file:///tmp/server', 'https://server?q=x', 'http://remote.invalid']) {
    assert.throws(() => new RoomSession(value, 'token'), /homeserver/);
  }
  assert.throws(() => new RoomSession('https://server.invalid', ''), /token/);
  assert.equal(f.calls.length, 0);
});

test('production SDK transport sends real local HTTP and destroys handles on success/failure', { timeout: 5000 }, async t => {
  const receipts = [], resources = [];
  const server = http.createServer((request, response) => {
    let body = ''; request.on('data', chunk => body += chunk);
    request.on('end', () => {
      receipts.push({ method: request.method, url: request.url, auth: request.headers.authorization, body });
      response.writeHead(200, { 'content-type': 'application/json' });
      response.end(JSON.stringify(request.url.endsWith('/versions') ? { versions: ['v1.13'] } : {}));
    });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.closeAllConnections(); server.close(); });
  const sdk = { RequestMethod: { GET: 'GET', POST: 'POST' }, HttpDataType: { STRING: 0 }, createHttp() {
    const resource = { destroyed: false, async request(url, options) {
      const response = await fetch(url, { method: options.method, headers: options.header, body: options.extraData });
      return { responseCode: response.status, result: await response.text() };
    }, destroy() { this.destroyed = true; } };
    resources.push(resource); return resource;
  } };
  const load = loader('final', sdk), { RoomSession } = load('RoomClient');
  const transport = new (load('SdkRoomTransport').SdkRoomTransport)(new RoomSession('http://127.0.0.1:' + server.address().port, 'owned-test-token'));
  const client = new (load('ReportRoomClient').MatrixReportingRoomClient)(transport);
  assert.equal(await client.canReportRoom(), true);
  await client.reportRoom(roomId, 'Spam'); await client.leaveRoom(roomId);
  assert.equal(receipts.length, 3); assert.ok(receipts.every(r => r.auth === 'Bearer owned-test-token'));
  assert.deepEqual(JSON.parse(receipts[1].body), { reason: 'Spam' });
  assert.ok(resources.every(r => r.destroyed));
  await assert.rejects(transport.request('GET', 'https://foreign.invalid'), /Invalid Matrix request/);
  assert.equal(resources.length, 3);
  server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
  await assert.rejects(transport.request('GET', '/_matrix/client/versions'));
  assert.ok(resources.at(-1).destroyed);
});
