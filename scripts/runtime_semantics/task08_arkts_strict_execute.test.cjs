'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { deriveTemplate } = require('./task08_arkts_strict_execute.cjs');

const template = fs.readFileSync(path.join(__dirname, 'task13_arkts_revision5_execute.cjs'), 'utf8');
const shared = fs.readFileSync(path.join(__dirname, 'arkts_device_execute.cjs'), 'utf8');
const withoutOs = shared.replace(/^const os\s*=\s*require\(['"](?:node:)?os['"]\);?\s*$/gm, '');
function derive(source = shared) {
  const wrapper = deriveTemplate(template, '/shared-executor.cjs', '/provider.cjs', 321);
  let generated;
  const module = { exports: {} };
  const context = {
    __dirname, module, console: { log() {}, error(message) { throw new Error(message); } },
    process: { argv: ['node', 'wrapper', '/build.json', 'unit-device', '/fresh'], execPath: process.execPath,
      stdout: { write() {} }, stderr: { write() {} } },
    require(name) {
      if (name === 'node:fs') return { existsSync: () => false, readFileSync: () => source,
        writeFileSync: (_, text) => { generated = text; } };
      if (name === 'node:child_process') return { spawnSync: () => ({ status: 0 }) };
      return require(name);
    }
  };
  context.require.main = module;
  vm.runInNewContext(wrapper, context);
  return generated;
}

test('current shared preacquired-lock branch derives with bounded wait and missing os import repaired', () => {
  const generated = derive(withoutOs);
  new vm.Script(generated);
  assert.match(generated, /const os = require\('node:os'\)/);
  assert.match(generated, /if \(!lockPreacquired\)/);
  assert.match(generated, /const lockDeadline = Date.now\(\) \+ 321 \* 1000/);
  assert.match(generated, /const task08ExecutionDeadline = Date.now\(\) \+ 321 \* 1000/);
  assert.match(generated, /Math\.min\(600000, Math\.max\(1, task08ExecutionDeadline - Date\.now\(\)\)\)/);
  assert.match(generated, /path.join\('\/tmp', 'ltb-arkts-device-'/);
  assert.match(generated, /names.length !== 9 \|\| new Set\(names\).size !== 9/);
  assert.match(generated, /identities.size !== 9/);
  assert.match(generated, /Native result execution nonce mismatch/);
  assert.match(generated, /candidateAbsentBeforeInstall = true/);
  assert.match(generated, /cleanup-uninstall/);
});

test('already imported os does not duplicate a binding', () => {
  const source = withoutOs.replace("const fs = require('node:fs');",
    "const fs = require('node:fs');\nconst os = require('node:os');");
  const generated = derive(source);
  assert.equal(generated.split("const os = require('node:os');").length, 2);
  new vm.Script(generated);
});

test('missing acquisition operation and changed preflight fail closed before device execution', () => {
  assert.throws(() => derive(shared.replace('fs.mkdirSync(lock);', 'otherOperation(lock);')), /shape changed|acquisition is absent/);
  assert.throws(() => derive(shared.replace("run('ui-preflight-dump'", "run('other-dump'")), /preflight patch failed/);
});
