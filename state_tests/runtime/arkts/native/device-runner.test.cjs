'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const source = fs.readFileSync(path.join(__dirname, 'DeviceTestRunner.ets'), 'utf8');

function harness(initializationError) {
  const calls = [];
  const loads = [];
  const completion = [];
  const suite = () => {};
  const args = { bundleName: 'test.only', parameters: {} };
  const delegator = {
    startAbility() { throw new Error('Runner must not launch TestAbility'); },
    finishTest(...values) { completion.push(values); }
  };
  const context = { exports: {}, console: { info() {}, error() {} }, require(name) {
    if (name === '@kit.TestKit') return { abilityDelegatorRegistry: {
      getAbilityDelegator: () => delegator, getArguments: () => args
    } };
    if (name === '@ohos/hypium') return { Hypium: { hypiumTest(...values) {
      calls.push(values);
      if (initializationError) throw initializationError;
    } } };
    if (name === '../test/List.test') { loads.push(name); return { default: suite }; }
    throw new Error('Unexpected dependency ' + name);
  } };
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText, context);
  return { runner: new context.exports.default(), calls, loads, completion, suite, args, delegator };
}

test('runner defers native suite import until onRun and schedules once without claiming completion', async () => {
  const state = harness();
  state.runner.onPrepare();
  assert.equal(state.calls.length, 0);
  assert.equal(state.loads.length, 0);
  state.runner.onRun();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(state.loads.length, 1);
  state.runner.onRun();
  assert.equal(state.calls.length, 1);
  assert.equal(state.calls[0][0], state.delegator);
  assert.equal(state.calls[0][1], state.args);
  assert.equal(state.calls[0][2], state.suite);
  assert.equal(state.completion.length, 0);
  assert.equal(state.runner.onDestroy, undefined);
});

test('initialization errors finish negatively, never as successful transport', async () => {
  const state = harness(new Error('registration failed'));
  state.runner.onRun();
  await new Promise(resolve => setImmediate(resolve));
  state.runner.onRun();
  assert.equal(state.completion.length, 1);
  assert.match(state.completion[0][0], /registration failed/);
  assert.equal(state.completion[0][1], -1);
});

test('packager overlays only its isolated test runner', () => {
  const packager = fs.readFileSync(path.resolve(__dirname, '../../../../scripts/runtime_semantics/arkts_native_device.cjs'), 'utf8');
  assert.match(packager, /fs\.copyFileSync\(runnerFile, path\.join\(tests, 'ets\/testrunner\/OpenHarmonyTestRunner\.ets'\)\)/);
});
