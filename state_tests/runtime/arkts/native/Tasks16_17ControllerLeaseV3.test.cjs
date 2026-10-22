'use strict';

// Executes the original executor's control flow in a VM. Every HDC call is
// intercepted; no child process, device, build or canonical lock is touched.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const executor = path.resolve(__dirname, '../../../../scripts/runtime_semantics/arkts_device_execute.cjs');

async function fixture(preacquired) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-v3-lease-offline-'));
  const serial = 'UNIT-OFFLINE-NO-DEVICE';
  const lock = path.join('/tmp', 'ltb-arkts-device-' + crypto.createHash('sha256').update(serial).digest('hex').slice(0, 16));
  const marker = path.join(root, 'native-execution.started.json');
  const output = path.join(root, 'execution');
  const buildFile = path.join(root, 'build.json');
  const operations = [];
  const calls = [];
  const build = { taskId: '16_identity_reset', caseId: 'UNIT', role: 'unit',
    runtimeCompile: { passed: true }, productionUnchanged: true, copiedProductionUnchanged: true,
    bundleName: 'com.unit.notinstalled', supportsExecutionNonce: true };
  fs.writeFileSync(buildFile, JSON.stringify(build));
  fs.writeFileSync(marker, JSON.stringify({ unitOnly: true, phase: 'before-dispatch' }));
  const guardedFs = { ...fs };
  for (const name of ['mkdirSync', 'rmdirSync', 'writeFileSync', 'unlinkSync']) {
    guardedFs[name] = (file, ...args) => {
      if (String(file) === lock || String(file).startsWith(lock + '/')) {
        operations.push(name);
        throw new Error('UNIT refuses canonical lock access');
      }
      return fs[name](file, ...args);
    };
  }
  const customModule = { exports: {} };
  const customRequire = name => {
    if (name === 'node:fs') return guardedFs;
    if (name === 'node:child_process') return { spawnSync: (command, args) => {
      calls.push({ command, args, markerPresentBeforeDispatch: fs.existsSync(marker) });
      // Stop in installed-before's format check, before install/start/SDK setup.
      return { status: 0, stdout: 'UNIT stopped before device execution', stderr: '' };
    } };
    if (name.endsWith('/Tasks16_18ProviderHost.cjs')) return {};
    return require(name);
  };
  customRequire.main = customModule;
  const context = { require: customRequire, module: customModule, exports: customModule.exports,
    __dirname: path.dirname(executor), __filename: executor,
    process: { argv: ['node', executor, buildFile, serial, output],
      env: preacquired ? { LTB_DEVICE_LOCK_PREACQUIRED: '1' } : {} },
    console: { log() {}, error() {} }, Buffer, setTimeout, clearTimeout };
  try {
    vm.runInNewContext(fs.readFileSync(executor, 'utf8'), context, { filename: executor });
    await new Promise(resolve => setImmediate(resolve));
    return { operations, calls, expectedLock: lock, exportedLock: customModule.exports.deviceLockPath(serial),
      report: JSON.parse(fs.readFileSync(path.join(output, 'device-execution.json'))) };
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test('original executor skips canonical reacquisition/release with parent lease', async () => {
  const result = await fixture(true);
  assert.equal(result.exportedLock, result.expectedLock);
  assert.deepEqual(result.operations, []);
  assert.equal(result.calls.length, 1);
  assert.equal(result.calls[0].markerPresentBeforeDispatch, true);
  assert.deepEqual(Array.from(result.calls[0].args).slice(0, 2), ['-t', 'UNIT-OFFLINE-NO-DEVICE']);
  assert.match(result.report.error, /Unable to inventory installed apps/);
  assert.equal(result.report.cleanup.ownedAppUninstalled, false);
});

test('without inherited lease flag original executor would attempt canonical mkdir before HDC', async () => {
  const result = await fixture(false);
  assert.deepEqual(result.operations, ['mkdirSync']);
  assert.equal(result.calls.length, 0);
  assert.match(result.report.error, /UNIT refuses canonical lock access/);
});
