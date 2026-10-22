'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = {};
vm.createContext(context);
const source = fs.readFileSync(path.join(__dirname, 'Task08TimelineUI.js'), 'utf8');
vm.runInContext(source.replace(/^export /gm, ''), context);

test('native entry is launched before importing its original ABC and no expected oracle is read', () => {
  const body = source.slice(source.indexOf('export async function runTask08TimelineUI'));
  assert.ok(body.indexOf('await launch.start()') < body.indexOf('await importModule('));
  assert.ok(body.indexOf('await importModule(') < body.indexOf("await action('input', 'room_composer'"));
  assert.doesNotMatch(body, /spec\.expected/);
  assert.match(body, /result\.uiAssertions = uiChecks/);
  assert.match(body, /Object\.values\(uiChecks\)\.every\(Boolean\)/);
});

test('an optimistic local root cannot substitute for a missing SDK send relation', () => {
  const state = { thread: { visibleEvents: [{ rootId: '$root' }] }, calls: [{ kind: 'threadGateway',
    method: 'sendDraft', completed: true, result: true, args: [{ draftKind: 'text', text: 'hello' }] }] };
  assert.equal(context.task08SdkRoot(state), null);
  state.calls[0].args[0].threadRootId = '$root';
  assert.equal(context.task08SdkRoot(state), '$root');
  state.calls[0].result = false;
  assert.equal(context.task08SdkRoot(state), null);
});

function fixture(mutateFocus) {
  class RoomGateway { sendMessage() { return 'original-room-result'; } }
  class Room {
    constructor() { this.gateway = new RoomGateway(); this.events = []; this.composerText = ''; }
    setComposerText(value) { this.composerText = value; }
    sendMessage() { return 'original-send-result'; }
  }
  class ThreadGateway {
    constructor() { this.corpus = { '$root': {}, '$reply': {}, '$remote': {} }; this.corpusReplies = {}; this.sentDrafts = []; }
    sendDraft() { return false; }
  }
  class Thread {
    constructor() { this.gateway = new ThreadGateway(); this.focusedEventId = '$root'; }
    openThread() { return true; }
    focusEvent(value) { if (mutateFocus) return false; this.focusedEventId = value; return true; }
    snapshot() { return { focusedEventId: this.focusedEventId }; }
  }
  for (const method of ['closeThread', 'setReplyTarget', 'setComposerText', 'sendDraft', 'retrySend',
    'prepareAttachmentDraft', 'enterSurface', 'returnToThread']) Thread.prototype[method] = () => 'original-' + method;
  const original = Thread.prototype.focusEvent;
  const observer = context.observeTask08Timeline({ RoomTimelinePresenter: Room, RoomTimelineGateway: RoomGateway },
    { ThreadTimelinePresenter: Thread, ThreadTimelineGateway: ThreadGateway }, { key: 'focus_reply' });
  const room = new Room(), thread = new Thread();
  room.setComposerText(''); thread.openThread('$root');
  return { room, thread, observer, original, Thread };
}

for (const mutant of [false, true]) test('mutable given initialization does not implement focus transition: mutant=' + mutant, () => {
  const { room, thread, observer, original, Thread } = fixture(mutant);
  try {
    observer.seedRoom(); observer.seedFocusGiven(null);
    assert.equal(observer.read().thread.focusedEventId, null);
    assert.equal(room.sendMessage(), 'original-send-result');
    const result = observer.invoke('focusEvent', ['$reply']);
    assert.equal(result, !mutant);
    assert.equal(observer.read().thread.focusedEventId, mutant ? null : '$reply');
    assert.equal(observer.read().calls.filter(call => call.kind === 'fixture_input').length, 1);
    assert.equal(thread.gateway.sendDraft({ text: 'body' }), false);
  } finally { observer.dispose(); }
  assert.equal(Thread.prototype.focusEvent, original);
});

test('read-only focused state is not replaced to manufacture the given', () => {
  const { thread, observer } = fixture(false);
  try {
    Object.defineProperty(thread, 'focusedEventId', { writable: false });
    assert.throws(() => observer.seedFocusGiven(null), /mutable focus input unavailable/);
  } finally { observer.dispose(); }
});
