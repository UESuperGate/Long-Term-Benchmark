'use strict';
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { decodeRows, freshPid, freshResultPid, freshNoncePid, screenLocked, inputSetupBlocked,
  deviceLockPath } = require('./arkts_device_execute.cjs');
const row = { taskId: 'task', role: 'final', caseId: 'case', status: 'not_scored' };
const json = JSON.stringify(row);
test('all device executors use the canonical cross-runtime lock root', () => {
  assert.match(deviceLockPath('127.0.0.1:5555'), /^\/tmp\/ltb-arkts-device-[0-9a-f]{16}$/);
});
test('locked device preflight is distinct from candidate failure and empty trees fail closed', () => {
  assert.equal(screenLocked({ children: [{ attributes: { id: 'ScreenLockRootComponent' } }] }), true);
  assert.equal(screenLocked({ children: [{ attributes: { id: 'launcher' } }] }), false);
  assert.throws(() => screenLocked({ children: [] }), /no window tree/);
});
test('keyboard onboarding requires actual keyboard window ownership and both native controls', () => {
  const controls = ['Paf.Permission.button_cancel', 'Paf.Permission.button_confirm']
    .map(id => ({ attributes: { id, visible: 'true' } }));
  const tree = bundleName => ({ children: [{ attributes: { bundleName }, children: controls }] });
  assert.equal(inputSetupBlocked(tree('com.huawei.hmos.inputmethod')), true);
  assert.equal(inputSetupBlocked(tree('com.example.candidate')), false);
  assert.equal(inputSetupBlocked({ children: [] }), false);
  controls[1].attributes.visible = 'false';
  assert.equal(inputSetupBlocked(tree('com.huawei.hmos.inputmethod')), false);
});
const chunk = (index, text) => 'ARKTS_NATIVE_ROW ' + JSON.stringify({ ...row, chunks: 2, index, text });
test('device rows reconstruct without converting unscored into passes', () => {
  assert.deepEqual(decodeRows(chunk(1, json.slice(20)) + '\n' + chunk(0, json.slice(0, 20))), [row]);
});
test('missing, duplicate and identity-conflicting fragments cannot become evidence', () => {
  assert.throws(() => decodeRows(chunk(0, json)), /Incomplete/);
  assert.throws(() => decodeRows(chunk(0, json) + '\n' + chunk(0, json)), /Duplicate/);
  assert.throws(() => decodeRows(chunk(0, JSON.stringify({ ...row, caseId: 'other' })) + '\n' + chunk(1, '')), /identity/);
});
test('new process selection excludes stale logs and rejects ambiguous concurrent runs', () => {
  const old = '10-19 20:00:00.000 111 111 I TAG: ARKTS_DEVICE_HARNESS_START';
  const fresh = '10-19 20:01:00.000 222 222 I TAG: ARKTS_DEVICE_HARNESS_START';
  assert.equal(freshPid(old, old + '\n' + fresh), '222');
  assert.throws(() => freshPid(old, old), /exactly one/);
  assert.throws(() => freshPid('', old + '\n' + fresh), /exactly one/);
});
test('rotated start marker requires a fresh exact-case result and the live candidate PID', () => {
  const marker = (pid, item = row) => `10-19 22:00:00.000 ${pid} ${pid} I TAG: ARKTS_NATIVE_ROW_FILE ` +
    JSON.stringify({ ...item, name: 'ltb-native-result_1234.json' });
  const fresh = marker(42);
  assert.equal(freshResultPid('', fresh, '42\n', row), '42');
  assert.throws(() => freshResultPid(fresh, fresh, '42', row), /exactly one fresh/);
  assert.throws(() => freshResultPid('', fresh, '43', row), /current candidate/);
  assert.throws(() => freshResultPid('', fresh, '42 43', row), /ambiguous/);
  assert.throws(() => freshResultPid('', fresh, '', row), /absent/);
  assert.throws(() => freshResultPid('', marker(42, { ...row, caseId: 'different' }), '42', row), /exactly one fresh/);
  assert.throws(() => freshResultPid('', fresh + '\n' + marker(43), '42', row), /exactly one fresh/);
  assert.throws(() => freshResultPid('', fresh.replace('result_1234', 'result_old'), '42', row), /exactly one fresh/);
});
test('terminated test processes require exact fresh nonce identity when their start logs rotate', () => {
  const nonce = 'b'.repeat(32);
  const marker = item => '10-19 22:00:00.000 42 42 I TAG: ARKTS_NATIVE_ROW_FILE ' +
    JSON.stringify({ ...row, name: 'ltb-native-result_123.json', executionNonce: nonce, ...item });
  const fresh = marker({});
  assert.equal(freshNoncePid('', fresh, row, nonce), '42');
  assert.throws(() => freshNoncePid(fresh, fresh, row, nonce), /exactly one/);
  assert.throws(() => freshNoncePid('', marker({ executionNonce: 'a'.repeat(32) }), row, nonce), /exactly one/);
  assert.throws(() => freshNoncePid('', marker({ role: 'agent' }), row, nonce), /exactly one/);
  assert.throws(() => freshNoncePid('', fresh + '\n' + fresh, row, nonce), /exactly one/);
  assert.throws(() => freshNoncePid('', fresh, row, 'bad'), /Invalid/);
});
