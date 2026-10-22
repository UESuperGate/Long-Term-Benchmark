'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, 'Task11Input.js'), 'utf8').replace('export function', 'function');
const { installTask11Input } = vm.runInNewContext(source + '\n({installTask11Input});', { Promise });

function fixture() {
  const stateOwners = [];
  class RoomGateway {
    lastOpenedRoomId = ''; lastOpenFailed = false;
    async requestRoomInfo(roomId) { return { roomId, successorRoom: { roomId: 'next' }, history: ['history'] }; }
    openRoom(roomId) { this.lastOpenedRoomId = roomId; return true; }
    roomSummaries() { return [{ roomId: 'room', history: ['history'] }, { roomId: 'next', history: ['next history'] }]; }
  }
  class RoomPresenter {
    constructor() { this.gateway = new RoomGateway(); this.room = { roomId: 'room', successorRoom: { roomId: 'next' } }; }
    async observeRoomInfo(roomId) {
      const info = await this.gateway.requestRoomInfo(roomId);
      stateOwners.push('original observeRoomInfo'); this.room = info; this.history = info.history;
    }
    openRoom(roomId) { const result = this.gateway.openRoom(roomId); this.room = { roomId }; return result; }
  }
  const presenter = new RoomPresenter(), events = [];
  const original = RoomPresenter.prototype.observeRoomInfo;
  const input = installTask11Input({ RoomPresenter, RoomGateway }, 'base',
    { roomId: 'room', successorRoom: { roomId: 'next' }, history: ['history'] }, event => events.push(event));
  return { input, presenter, events, original, RoomPresenter, stateOwners };
}

test('ordinary SDK setup and held successor delivery still execute original production state owner', async () => {
  const f = fixture();
  try {
    f.input.setAvailableResponse({ roomId: 'room', successorRoom: null, history: ['history'], composerEnabled: true });
    assert.equal(f.presenter.room.successorRoom.roomId, 'next', 'input configuration must not write presenter state');
    await f.presenter.observeRoomInfo('room');
    assert.equal(f.input.read().room.successorRoom, null);
    f.input.enableHold();
    const pending = f.presenter.observeRoomInfo('room');
    assert.equal(f.input.read().room.successorRoom, null, 'held SDK response must not already succeed');
    const request = f.input.read().requests.find(item => !item.settled);
    f.input.releaseResponse(request.id);
    await pending;
    assert.equal(f.input.read().room.successorRoom.roomId, 'next');
    assert.deepEqual(f.stateOwners, ['original observeRoomInfo', 'original observeRoomInfo']);
  } finally { f.input.dispose(); }
  assert.equal(f.RoomPresenter.prototype.observeRoomInfo, f.original);
});

test('navigation without template enums or counters is bound to original gateway return and current receiver', async () => {
  const f = fixture();
  try {
    await f.presenter.observeRoomInfo('room');
    assert.equal(f.input.read().navigationState, 'idle');
    f.presenter.openRoom('next');
    const state = f.input.read();
    assert.equal(state.currentRoomId, 'next');
    assert.equal(state.lastOpenedRoomId, 'next');
    assert.equal(state.navigationState, 'success');
    assert.equal(state.navigationCount, 1);
    assert.equal(state.navigationObservation.originalGatewayReturn.method, 'openRoom');
    assert.equal(state.navigationObservation.originalGatewayReturn.result, true);
  } finally { f.input.dispose(); }
});

test('external setup cannot silently change the canonical target room', () => {
  const f = fixture();
  try {
    assert.throws(() => f.input.setAvailableResponse({ roomId: 'unrelated' }), /identity changed/);
  } finally { f.input.dispose(); }
});
