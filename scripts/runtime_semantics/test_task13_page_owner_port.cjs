'use strict';
// Offline regression only; these tests are not benchmark semantic evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('/Users/z1an/Library/OpenHarmony/Sdk/23/ets/build-tools/ets-loader/node_modules/typescript');
const root = path.resolve(__dirname, '../..');
const settled = () => new Promise(resolve => setImmediate(resolve));
const feature = path.join(root, 'final_dev_nodes/13_user_verification_final_25_03_2/entry/src/main/ets/features');
const mutation = process.argv[2];
const mutations = {
  stale_session: ['SessionVerificationService', 'if (generation !== this.generation || flow !== this.flow) return;', ''],
  completion_gate: ['UserVerificationFeature', 'this.gateway.service.isVerified(this.request.userId) &&', 'true &&'],
  repeated_approval: ['UserVerificationFeature', 'this.replyState !== ReplyState.Uninitialized) return;', 'false) return;'],
  disposed_owner: ['UserVerificationFeature', 'this.active = false; this.lifecycle += 1; this.detachService?.();', 'this.active = true; this.lifecycle += 1;']
};
function load(name, cache = new Map()) {
  const file = path.join(feature, name + '.ets');
  if (cache.has(file)) return cache.get(file);
  const mod = { exports: {} }; cache.set(file, mod.exports);
  let code = fs.readFileSync(file, 'utf8');
  if (mutations[mutation]?.[0] === name) code = code.replaceAll(mutations[mutation][1], mutations[mutation][2]);
  const source = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText;
  vm.runInThisContext('(function(exports,require,module){' + source + '\n})', { filename: file })(
    mod.exports, relative => load(path.basename(relative), cache), mod);
  return mod.exports;
}
function sdk() {
  const subscriptions = [], calls = [];
  let pending;
  const port = { subscriptions, calls, verified: false,
    subscribeVerifiedStatus(listener) { listener('not_verified'); return () => {}; },
    setListener(listener) { port.incomingListener = listener; },
    acknowledgeVerificationRequest(id) { calls.push(['acknowledge', id]); return Promise.resolve(); },
    acceptVerificationRequest() { calls.push(['acceptIncoming']); return Promise.resolve(); },
    subscribe(listener) { const record = { listener, active: true }; subscriptions.push(record); return () => { record.active = false; }; },
    emit(kind, sas = []) { subscriptions.filter(item => item.active).forEach(item => item.listener({ kind, sas })); },
    isVerified() { return port.verified; },
    requestUserVerification(userId) { calls.push(['request', userId]); return pending || Promise.resolve(); },
    requestCurrentSessionVerification() { calls.push(['self']); return Promise.resolve(); },
    startVerification() { calls.push(['start']); return Promise.resolve(); },
    approveVerification() { calls.push(['approve']); return Promise.resolve(); },
    declineVerification() { calls.push(['decline']); return Promise.resolve(); },
    cancelVerification() { calls.push(['cancel']); return Promise.resolve(); },
    resetVerification(value) { calls.push(['reset', value]); return Promise.resolve(); },
    holdRequest() { pending = new Promise((resolve, reject) => { port.resolve = resolve; port.reject = reject; }); }
  }; return port;
}
async function main() {
  const m = load('UserVerificationFeature');
  const room = m.getRoomIdentityDataSource(), service = m.getSessionVerificationService();
  const port = sdk(); service.connect(port);
  room.receiveRoomSync(true, [new m.RoomMember('@alice:example.org', 'Alice'), new m.RoomMember('@bob:example.org', 'Bob')]);
  room.receiveIdentityChanges([new m.IdentityChange('@alice:example.org', m.IdentityState.Unverified),
    new m.IdentityChange('@bob:example.org', m.IdentityState.Pinned)]);
  const presenter = () => new m.UserVerificationPresenter(new m.VerificationRequest(m.VerificationRequestType.User,
    '@alice:example.org'), new m.VerificationGateway(), new m.IdentityStateStore('@alice:example.org'));
  const p = presenter(); let renders = 0; p.attach(() => renders++); await settled();
  await p.requestVerification(); assert.equal(p.step, 'awaiting_other_device_response');
  assert.deepEqual(port.calls.filter(item => item[0] === 'request'), [['request', '@alice:example.org']]);
  port.emit('challenge', ['premature']); assert.equal(p.step, 'awaiting_other_device_response');
  port.emit('accepted'); assert.equal(p.step, 'ready'); await p.startSasVerification();
  port.emit('started'); port.emit('challenge', ['Dog', 'Tree', 'Rocket']);
  await p.acceptChallenge(); await p.acceptChallenge();
  assert.equal(port.calls.filter(item => item[0] === 'approve').length, 1);
  assert.equal(p.replyState, 'loading'); assert.equal(p.step, 'verifying');
  room.receiveIdentityChanges([new m.IdentityChange('@alice:example.org', m.IdentityState.VerificationViolation)]);
  port.emit('finished'); assert.equal(p.step, 'verifying'); assert.equal(p.identityStore.warningVisible, true);
  room.receiveIdentityChanges([new m.IdentityChange('@alice:example.org', m.IdentityState.Verified)]);
  assert.equal(p.step, 'verifying');
  port.verified = true; room.receiveIdentityChanges([new m.IdentityChange('@alice:example.org', m.IdentityState.Verified)]);
  assert.equal(p.step, 'completed'); assert.equal(p.identityStore.warningVisible, false);
  p.dispose(); const count = renders; port.emit('failed'); assert.equal(p.step, 'completed'); assert.equal(renders, count);
  const q = presenter(); q.attach(() => {}); await settled();
  port.holdRequest(); const oldRequest = q.requestVerification();
  const oldListener = port.subscriptions.findLast(item => item.active).listener;
  q.dispose(); port.reject(new Error('late request')); await oldRequest;
  assert.equal(q.error, '');
  const next = sdk(); service.connect(next); const r = presenter(); r.attach(() => {}); await settled();
  await r.requestVerification(); oldListener({ kind: 'accepted', sas: [] }); assert.equal(r.step, 'awaiting_other_device_response');
  next.emit('failed'); const resetListener = next.subscriptions.findLast(item => item.active).listener;
  await r.reset(); assert.equal(r.step, 'initial');
  await r.requestVerification(); resetListener({ kind: 'started', sas: [] }); resetListener({ kind: 'challenge', sas: ['stale'] });
  assert.deepEqual(r.sas, []); assert.equal(r.step, 'awaiting_other_device_response');
  next.emit('accepted'); await r.startSasVerification(); next.emit('started'); next.emit('challenge', ['fresh']);
  assert.deepEqual(r.sas, ['fresh']); r.dispose(); service.disconnect();
  await assert.rejects(() => service.requestUserVerification('@alice:example.org'), /not connected/);
  const incoming = sdk(); service.connect(incoming);
  let incomingCount = 0; service.setListener(() => incomingCount++);
  const lateIncoming = incoming.incomingListener;
  await service.acknowledgeVerificationRequest('sdk-request-1'); await service.acceptVerificationRequest();
  assert.deepEqual(incoming.calls, [['acknowledge', 'sdk-request-1'], ['acceptIncoming']]);
  service.connect(sdk()); lateIncoming('old-sdk-request'); assert.equal(incomingCount, 0); service.disconnect();
  const nativeFile = path.join(root, 'state_tests/runtime/arkts/native/Task13PageOwnerSdk.js');
  const nativeModule = { exports: {} };
  const nativeCode = ts.transpileModule(fs.readFileSync(nativeFile, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText;
  vm.runInThisContext('(function(exports,module){' + nativeCode + '\n})', { filename: nativeFile })(nativeModule.exports, nativeModule);
  const observation = nativeModule.exports.connectTask13ExternalSdk(m);
  const actual = presenter(); actual.attach(() => {}); await settled();
  await actual.requestVerification(); observation.emit('accepted');
  let observed = observation.read();
  assert.equal(observed.instanceCount, 1); assert.equal(observed.state.step, 'ready');
  assert(observed.state.sameRoom && observed.state.sameService);
  assert(observed.calls.some(call => call.owner === 'gateway' && call.method === 'requestUserVerification' &&
    call.sameGatewayReceiver && call.presenterId === observed.state.presenterId &&
    call.gatewayId === observed.state.gatewayId && call.serviceId === observed.state.serviceId));
  assert(observed.ledger.some(item => item.kind === 'production_callback' && item.presenterId === observed.state.presenterId &&
    item.serviceId === observed.state.serviceId && item.after.step === 'ready'));
  actual.dispose(); observation.emit('failed');
  observed = observation.read(); assert.equal(observed.state.step, 'ready');
  assert(observed.ledger.some(item => item.kind === 'production_unsubscribe'));
  observation.dispose();
  assert.equal(fs.readFileSync(path.join(feature, 'SessionVerificationService.ets'), 'utf8'),
    fs.readFileSync(path.join(root, '13_user_verification_base_25_03_1/entry/src/main/ets/features/SessionVerificationService.ets'), 'utf8'));
  if (!mutation) {
    const { spawnSync } = require('node:child_process');
    for (const name of Object.keys(mutations)) {
      const result = spawnSync(process.execPath, [__filename, name], { encoding: 'utf8', timeout: 20000 });
      assert.notEqual(result.status, 0, 'Mutation was not killed: ' + name);
      assert(result.stderr.includes('AssertionError'), 'Mutation failed for an unrelated reason: ' + result.stderr);
    }
  }
  const { validateOwnerInventory } = require('../../state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs');
  const inventory = { complete: true, nodeCount: 1, nodes: [{ id: 'verify_user_action', type: 'Button', clickable: true }] };
  assert.equal(validateOwnerInventory(inventory), true);
  assert.throws(() => validateOwnerInventory({ ...inventory, complete: false }), /Incomplete/);
  assert.throws(() => validateOwnerInventory({ ...inventory, nodes: [{ ...inventory.nodes[0], id: 'renamed_verify' }] }), /Unknown/);
  assert.throws(() => validateOwnerInventory({ ...inventory, nodes: [{ type: 'Button', text: 'New verification', clickable: true }] }), /Unreviewed/);
  const page = fs.readFileSync(path.join(feature, '../pages/Index.ets'), 'utf8');
  assert(!page.includes('verification_remote_accepted')); assert(!page.includes('finish_verification'));
  assert(!page.includes('Dog')); assert(page.includes('this.presenter.attach('));
  const adapter = fs.readFileSync(path.join(root, 'state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs'), 'utf8');
  assert(!adapter.includes('new module.')); assert(!adapter.includes('actionPrefix'));
  const nativeBuilder = require('./task13_arkts_revision5_build.cjs');
  const originalStatfs = fs.statfsSync;
  try {
    fs.statfsSync = () => ({ bavail: 7, bsize: 1024 ** 3 });
    assert.throws(() => nativeBuilder.main(), /requires 8 GiB/);
    fs.statfsSync = () => ({ bavail: 8, bsize: 1024 ** 3 });
    assert.throws(() => nativeBuilder.main(), /--output-dir is required/);
  } finally { fs.statfsSync = originalStatfs; }
  console.log(JSON.stringify({ passed: true, tier: 'offline unit regression, not semantic score',
    mutationTests: { killed: 4, total: 4 },
    checks: ['SDK delegation', 'callback-only transitions', 'single approval', 'verified-status gate',
      'dispose late completion', 'session generation', 'reset stale callback', 'no default success', 'unknown UI fail closed'] }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
