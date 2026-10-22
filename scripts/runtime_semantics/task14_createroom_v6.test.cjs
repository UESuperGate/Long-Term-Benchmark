'use strict';
// OFFLINE diagnostics only. These tests do not claim Cargo, HAP, device, or semantic runtime evidence.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');

const root = path.resolve(__dirname, '../..');
const out = path.join(root, 'experiment_results/runtime_transition_20261021/task14_createroom_boundaries_v6');
const v5 = path.join(root, 'experiment_results/runtime_transition_20261021/task14_startchat_preservation_v5');
const project = role => path.join(out, 'projects', role, 'entry/src/main/ets');
const source = (role, name) => fs.readFileSync(path.join(project(role), name), 'utf8');
const native = name => fs.readFileSync(path.join(out, 'native-prerequisite', name), 'utf8');

function loadOwner(role = 'base') {
  const file = path.join(project(role), 'features/ConfiguredStartChatOwner.ets');
  const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    fileName: file,
    reportDiagnostics: true,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  });
  assert.equal(result.diagnostics.some(row => row.category === ts.DiagnosticCategory.Error), false);
  const module = { exports: {} };
  vm.runInNewContext('(function(require,module,exports){' + result.outputText + '\n})',
    { Uint8Array, ArrayBuffer, Promise, Error, setTimeout, clearTimeout }, { filename: file })(
      specifier => {
        if (specifier.endsWith('ConfiguredStartChatService')) return {};
        throw new Error('Unbound owner dependency: ' + specifier);
      }, module, module.exports);
  return module.exports.ConfiguredCreateRoomOwner;
}

function contractCases(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8')).cases.filter(row => row.taskId === undefined || row.taskId === '14_join_room_by_address');
}

test('V6 non-UI ArkTS modules remain syntactically transpilable for both role copies', () => {
  const names = ['composition/StartChatRoutes.ets', 'features/ConfiguredStartChatOwner.ets',
    'matrix/production/ConfiguredSessionRooms.ets', 'matrix/production/ConfiguredStartChatService.ets',
    'nativebridge/AddonNativeMatrixBridge.ets', 'platform/feature/KnockFeatureFlag.ets',
    'platform/media/RoomAvatarMedia.ets', 'platform/share/SystemShareInvite.ets'];
  for (const role of ['base', 'final']) {
    for (const name of names) {
      const file = path.join(project(role), name);
      const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), { fileName: file, reportDiagnostics: true,
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } });
      const errors = result.diagnostics.filter(row => row.category === ts.DiagnosticCategory.Error);
      assert.equal(errors.length, 0, role + ': ' + name + ': ' + errors.map(row => row.messageText).join('; '));
    }
  }
});

test('V6 preserves the V5 same-screen DM, search, create, invite, recent and final address actions', () => {
  for (const role of ['base', 'final']) {
    const menu = source(role, 'components/ConfiguredStartChatMenu.ets');
    for (const id of ['people_search_input', 'people_search_close', 'create_room_action',
      'invite_friends_action', 'recent_dm_']) assert.ok(menu.includes(id), role + ': ' + id);
    assert.ok(menu.includes("id('join_room_by_address')"));
    const start = source(role, 'pages/StartChat.ets');
    assert.match(start, /ConfiguredStartChatMenu/);
    assert.equal(start.includes('confirmNewDM: true'), role === 'final');
    assert.equal(start.includes('showJoinAddress: true'), role === 'final');
  }
});

test('V6 retains V5 DM/search/create/address implementation instead of replacing it with a back-only page', () => {
  for (const role of ['base', 'final']) {
    const owner = source(role, 'features/ConfiguredStartChatOwner.ets');
    for (const token of ['loadRecent()', 'search(value:', 'service.findDM', 'service.createDM',
      'service.createRoom', 'service.addressAvailable', 'routes.openRoom']) assert.ok(owner.includes(token), role + ': ' + token);
    const menuV5 = fs.readFileSync(path.join(v5, 'projects', role, 'entry/src/main/ets/components/ConfiguredStartChatMenu.ets'));
    assert.deepEqual(fs.readFileSync(path.join(project(role), 'components/ConfiguredStartChatMenu.ets')), menuV5);
  }
});

test('CreateRoom exposes gallery, camera, remove, invite, address and Knock controls on both roles', () => {
  for (const role of ['base', 'final']) {
    const page = source(role, 'pages/CreateRoom.ets');
    for (const id of ['create_room_avatar_gallery', 'create_room_avatar_camera', 'create_room_avatar_remove',
      'create_room_people', 'create_room_invited', 'create_room_visibility', 'create_room_access',
      'create_room_alias', 'create_room_submit']) assert.ok(page.includes(id), role + ': ' + id);
    assert.match(page, /owner\.setAvatar\(selected\.uri, selected\.jpeg\)/);
    assert.match(page, /owner\.roomAccess = index === 1 \? 'knock' : 'anyone'/);
    assert.match(page, /KnockFeatureFlag\.create/);
    assert.match(page, /if \(this\.knockEnabled\)/);
  }
  const flag = native('entry/src/main/ets/platform/feature/KnockFeatureFlag.ets');
  assert.ok(flag.includes("KEY: string = 'feature.knock'"));
  assert.ok(flag.includes("get(KnockFeatureFlag.KEY, 'false') === 'true'"));
});

test('Harmony media boundary uses real gallery/camera pickers, JPEG preprocessing and releases native objects', () => {
  const media = native('entry/src/main/ets/platform/media/RoomAvatarMedia.ets');
  for (const token of ['new picker.PhotoViewPicker(context)', 'PhotoViewMIMETypes.IMAGE_TYPE',
    'cameraPicker.pick(context', 'PickerMediaType.PHOTO', 'CAMERA_POSITION_BACK',
    'image.createImageSource(uri)', 'image.createImagePacker()', "format: 'image/jpeg'",
    'packer.release()', 'source.release()']) assert.ok(media.includes(token), token);
  assert.match(media, /result\.resultCode !== 0/);
  assert.doesNotMatch(media, /demo|fixture|base64|hardcoded/i);
});

test('configured native ABI owns avatar upload and forwards the returned MXC into create-room state', () => {
  const rust = native('native/matrix-sdk-bridge/src/startchat.rs');
  const cpp = native('entry/src/main/cpp/matrix_native_addon.cpp');
  const service = native('entry/src/main/ets/matrix/production/ConfiguredStartChatService.ets');
  for (const token of ['client_for_handle(handle)?', 'client.media().upload(', 'elementx_matrix_bridge_upload_avatar',
    'm.room.avatar', 'avatar_url']) assert.ok(rust.includes(token), token);
  for (const token of ['napi_get_typedarray_info', 'context->bytes.assign', 'DataOperation::UploadAvatar',
    'elementx_matrix_bridge_upload_avatar']) assert.ok(cpp.includes(token), token);
  assert.ok(service.includes("!/^mxc:\\/\\/[^/]+\\/.+$/.test"));
  assert.doesNotMatch(rust, /Client::builder|reqwest::Client|demo\.local/);
});

test('HOST ONLY: avatar upload completes before create and public Knock/address/invites reach one request', async () => {
  const Owner = loadOwner();
  const calls = [];
  const service = {
    async uploadAvatar(bytes) { calls.push(['upload', Array.from(bytes)]); return 'mxc://media.unit/avatar'; },
    async createRoom(parameters) { calls.push(['create', JSON.parse(JSON.stringify(parameters))]); return '!created:unit'; },
    async addressAvailable(address) { calls.push(['alias', address]); return true; }
  };
  const routes = { async openRoom(roomId) { calls.push(['open', roomId]); } };
  const owner = new Owner(service, routes, '@me:unit');
  owner.name = 'Room'; owner.visibility = 'public'; owner.roomAccess = 'knock';
  owner.toggleInvite('@other:unit', true);
  owner.setAvatar('file://avatar.jpg', new Uint8Array([0xff, 0xd8, 0xff, 0xd9]));
  await owner.updateAlias('public-room');
  await owner.submit();
  assert.deepEqual(calls.map(row => row[0]), ['alias', 'upload', 'create', 'open']);
  assert.deepEqual(calls[2][1], { name: 'Room', topic: null, invite: ['@other:unit'], visibility: 'public',
    roomAliasName: 'public-room', joinRule: 'knock', avatarUrl: 'mxc://media.unit/avatar' });
});

test('HOST ONLY: upload failure cannot create or navigate, and no-avatar private create does not synthesize media', async () => {
  const Owner = loadOwner();
  const badCalls = [];
  const bad = new Owner({
    async uploadAvatar() { badCalls.push('upload'); throw new Error('upload failed'); },
    async createRoom() { badCalls.push('create'); return '!forbidden:unit'; }
  }, { async openRoom() { badCalls.push('open'); } }, '@me:unit');
  bad.name = 'Room'; bad.setAvatar('file://avatar.jpg', new Uint8Array([0xff, 0xd8, 0xff, 0xd9]));
  await bad.submit();
  assert.deepEqual(badCalls, ['upload']);
  assert.equal(bad.createdRoomId, '');
  assert.match(bad.error, /upload failed/);

  const calls = [];
  const plain = new Owner({ async createRoom(value) { calls.push(value); return '!plain:unit'; } },
    { async openRoom() {} }, '@me:unit');
  plain.name = 'Plain'; await plain.submit();
  assert.equal(calls[0].avatarUrl, null);
  assert.equal(calls[0].joinRule, null);
});

test('HOST ONLY: routing retry reuses the created room without re-uploading avatar or creating again', async () => {
  const Owner = loadOwner();
  const calls = [];
  let routeAttempts = 0;
  const owner = new Owner({
    async uploadAvatar() { calls.push('upload'); return 'mxc://media.unit/avatar'; },
    async createRoom() { calls.push('create'); return '!created:unit'; }
  }, { async openRoom() { calls.push('open'); routeAttempts += 1; if (routeAttempts === 1) throw new Error('route failed'); } }, '@me:unit');
  owner.name = 'Room'; owner.setAvatar('file://avatar.jpg', new Uint8Array([0xff, 0xd8, 0xff, 0xd9]));
  await owner.submit();
  assert.equal(owner.createdRoomId, '!created:unit');
  await owner.submit();
  assert.deepEqual(calls, ['upload', 'create', 'open', 'open']);
});

test('Knock is an explicit SDK join-rule event with invite power level; private encryption remains', () => {
  const rust = native('native/matrix-sdk-bridge/src/startchat.rs');
  for (const token of ['Some("knock")', '"m.room.join_rules"', '"join_rule": "knock"',
    'levels["invite"]', 'with_recommended_defaults()', 'RoomPreset::PrivateChat', 'RoomPreset::PublicChat']) {
    assert.ok(rust.includes(token), token);
  }
});

test('invite action keeps configured permalink and uses the actual ShareKit controller boundary', () => {
  for (const role of ['base', 'final']) {
    const routes = source(role, 'composition/StartChatRoutes.ets');
    const share = source(role, 'platform/share/SystemShareInvite.ets');
    assert.match(routes, /foundation\.startChat\.permalink\(\)/);
    assert.match(routes, /this\.share\.show\(context, url\)/);
    for (const token of ['new systemShare.SharedData', "utd: 'general.hyperlink'",
      'new systemShare.ShareController', 'controller.show(context', 'SelectionMode.SINGLE',
      'SharePreviewMode.DETAIL']) assert.ok(share.includes(token), role + ': ' + token);
  }
});

test('Task14 canonical contracts remain identical across benchmark, migration and central contract', () => {
  const benchmark = contractCases(path.join(root, 'benchmark_tasks/14_join_room_by_address/transitions.json'));
  const migration = contractCases(path.join(root, 'migrations/14_join_room_by_address/canonical/transitions.json'));
  const central = contractCases(path.join(root, 'state_tests/canonical/new_tasks_cross_platform_contract.json'));
  assert.deepEqual(migration, benchmark);
  assert.deepEqual(central, benchmark);
  assert.equal(benchmark.length, 9);
});
