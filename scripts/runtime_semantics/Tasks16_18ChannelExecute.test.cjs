'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { inventory, validateResult, parseDeviceTime } = require('./Tasks16_18ChannelExecute.cjs');
const bundleName = 'com.example.task18';
const nonce = 'b'.repeat(32);

test('read-only inventory rejects preexisting candidate or ambiguous user', () => {
  assert.equal(inventory('ID: 107:\nother.app\n', bundleName), '107');
  for (const value of ['', 'error', 'ID: 0:\nID: 100:', 'ID: 100:\n  ' + bundleName]) {
    assert.throws(() => inventory(value, bundleName));
  }
});

test('device clock parser refuses unknown/non-millisecond shell output', () => {
  assert.equal(parseDeviceTime('1792490000000\n'), 1792490000000);
  for (const value of ['1792490000', '1792490000%3N', 'permission denied', '']) assert.throws(() => parseDeviceTime(value));
});

function result() {
  return { schemaVersion: 1, taskId: '18_custom_notification_sounds',
    observationLevel: 'native_sdk_capability_diagnostic_only', canonicalPromotionAllowed: false,
    nonce, bundleName, cacheDir: '/data/storage/el2/base/cache', startedAtMs: 10, finishedAtMs: 30,
    calls: [{ api: 'notificationManager.getSlots', inputJson: 'null', resultJson: '[]', startedAtMs: 11, finishedAtMs: 12 }],
    unsupported: [], cleanupErrors: [] };
}
const binding = { nonce, bundleName, startedAtMs: 9, finishedAtMs: 31 };

test('even valid diagnostic transport never grants production effect/readback proof', () => {
  const proof = validateResult(result(), binding);
  assert.equal(proof.canonicalPromotionAllowed, false);
  assert.equal(proof.effectiveCustomSoundProven, false);
  assert.equal(proof.productionConsumerObserved, false);
});

for (const variant of ['nonce', 'bundle', 'scope', 'promotion', 'time', 'path', 'empty', 'unknown_api', 'missing_result', 'unordered']) {
  test('reject unrelated/incomplete SDK diagnostic: ' + variant, () => {
    const row = result();
    if (variant === 'nonce') row.nonce = 'a'.repeat(32);
    if (variant === 'bundle') row.bundleName = 'other.app';
    if (variant === 'scope') row.observationLevel = 'production_domain';
    if (variant === 'promotion') row.canonicalPromotionAllowed = true;
    if (variant === 'time') row.startedAtMs = 8;
    if (variant === 'path') row.cacheDir = '/data/local/tmp';
    if (variant === 'empty') row.calls = [];
    if (variant === 'unknown_api') row.calls[0].api = 'gateway.ledger';
    if (variant === 'missing_result') delete row.calls[0].resultJson;
    if (variant === 'unordered') row.calls.push({ ...row.calls[0], startedAtMs: 10 });
    assert.throws(() => validateResult(row, binding));
  });
}
