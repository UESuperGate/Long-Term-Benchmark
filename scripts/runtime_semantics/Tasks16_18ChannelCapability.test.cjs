'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { install, probeTone } = require('./Tasks16_18ChannelCapability.cjs');

test('SDK diagnostic WAV is small, real PCM and non-silent', () => {
  const bytes = probeTone();
  assert.equal(bytes.subarray(0, 4).toString(), 'RIFF');
  assert.equal(bytes.subarray(8, 12).toString(), 'WAVE');
  assert.equal(bytes.readUInt32LE(4) + 8, bytes.length);
  assert.equal(bytes.readUInt32LE(40) + 44, bytes.length);
  assert.equal(bytes.readUInt32LE(24), 8000);
  assert.ok(bytes.subarray(44).some(value => value !== 0));
  assert.ok(bytes.length < 2048);
});

test('probe installer does not replace candidate code or grant permissions', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks16_18-capability-test-'));
  try {
    const page = path.join(work, 'entry/src/main/ets/pages/Index.ets');
    const module = path.join(work, 'entry/src/main/module.json5');
    fs.mkdirSync(path.dirname(page), { recursive: true });
    fs.writeFileSync(page, 'untouched production');
    fs.writeFileSync(module, '{"module": {"name":"entry"}}');
    const receipt = install(work);
    assert.equal(fs.readFileSync(page, 'utf8'), 'untouched production');
    assert.equal(fs.readFileSync(module, 'utf8'), '{"module": {"name":"entry"}}');
    assert.equal(receipt.fixtures.length, 2);
    assert.ok(receipt.fixtures.every(item => /^[a-f0-9]{64}$/.test(item.sha256)));
    assert.equal(receipt.evaluatorAsset.bytes, probeTone().length);
    const source = fs.readFileSync(path.join(work, 'entry/src/ohosTest/ets/test/Tasks16_18ChannelCapability.test.ets'), 'utf8');
    assert.match(source, /canonicalPromotionAllowed: false/);
    assert.match(source, /notificationManager\.getSlot\(slot\)/);
    assert.match(source, /notificationManager\.getActiveNotifications\(\)/);
    assert.match(source, /SDK call exceeded 4000ms/);
    assert.match(source, /clearTimeout\(timer\)/);
    assert.doesNotMatch(source, /requestEnableNotification|setAdditionalConfig|setSlotFlagsAsBundle/);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});
