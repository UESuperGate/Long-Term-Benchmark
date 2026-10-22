'use strict';
// Run the actual wrapper generator, but never launch a compiler or touch a device.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const wrapper = path.join(__dirname, 'task13_arkts_revision5_build.cjs');
const shared = path.join(__dirname, 'arkts_native_device.cjs');
const original = fs.readFileSync(shared, 'utf8');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const anchors = {
  copy: "      fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work",
  command: '        report.commands.push(command);',
  after: "        const log = redact((result.stdout || '') + (result.stderr || ''));"
};
const count = (text, token) => text.split(token).length - 1;
const stop = new Error('GENERATION_CAPTURED_NO_CHILD_STARTED');

function generate(template, role, wrapperCode = fs.readFileSync(wrapper, 'utf8')) {
  const writes = new Map();
  const output = path.join(root, '__task13_offline_virtual_output__');
  assert(!fs.existsSync(output));
  const source = role === 'base' ? path.join(root, '13_user_verification_base_25_03_1') :
    path.join(root, 'final_dev_nodes/13_user_verification_final_25_03_2');
  let childAttempts = 0;
  const fakeFs = Object.create(fs);
  fakeFs.statfsSync = () => ({ bavail: 8, bsize: 1024 ** 3 });
  fakeFs.readFileSync = (file, ...args) => path.resolve(file) === shared ? template : fs.readFileSync(file, ...args);
  fakeFs.mkdirSync = file => assert.equal(path.resolve(file), output);
  fakeFs.writeFileSync = (file, bytes) => {
    assert.equal(path.dirname(file), output);
    writes.set(file, String(bytes));
  };
  const exports = {};
  const context = {
    __dirname, __filename: wrapper, module: { exports }, exports, console,
    process: { argv: [process.execPath, wrapper, '--source', source, '--role', role,
      '--compile-only', '--output-dir', output], execPath: process.execPath },
    require(name) {
      if (name === 'node:fs') return fakeFs;
      if (name === 'node:child_process') return { spawnSync() { childAttempts++; throw stop; } };
      return require(name);
    }
  };
  vm.runInNewContext(wrapperCode, context, { filename: wrapper });
  let error;
  try { context.module.exports.main(); } catch (caught) { error = caught; }
  return { error, childAttempts, generated: writes.get(path.join(output, 'task13-revision5-builder.generated.cjs')) };
}

for (const token of Object.values(anchors)) assert.equal(count(original, token), 1);
const results = [];
for (const role of ['base', 'final']) {
  const result = generate(original, role);
  assert.equal(result.error, stop);
  assert.equal(result.childAttempts, 1, 'Only the intercepted launch boundary is reached');
  new vm.Script(result.generated, { filename: 'generated-task13-offline.cjs' });
  for (const token of Object.values(anchors)) assert.equal(count(result.generated, token), 1);
  for (const token of ['.beginCopy(source, work, output)', '.beforeCompile(work, output, target, ',
    '.afterCompile(work, output, target, task13CompileReceipt)', 'contractOverride: ',
    '.install(work, ']) assert.equal(count(result.generated, token), 1, token);
  assert(result.generated.indexOf('.beginCopy(') < result.generated.indexOf(anchors.copy));
  assert(result.generated.indexOf('.beforeCompile(') < result.generated.indexOf('const result = spawnSync('));
  assert(result.generated.indexOf('.afterCompile(') > result.generated.indexOf('const result = spawnSync('));
  results.push({ role, generatedSha256: sha(result.generated), syntaxValid: true });
}
let killed = 0;
for (const [name, token] of Object.entries(anchors)) {
  for (const template of [original.replace(token, '/* removed anchor */'), original.replace(token, token + '\n' + token)]) {
    const result = generate(template, 'final');
    assert.match(String(result.error), /instrumentation anchors? changed/i, name);
    assert.equal(result.childAttempts, 0, 'Malformed template must fail before any child');
    assert.equal(result.generated, undefined);
    killed++;
  }
}
const historicalWrapper = path.join(root,
  'experiment_results/runtime_transition_20261020/task13_page_owner_port_v1/entry_policy_v7/frozen/scripts/runtime_semantics/task13_arkts_revision5_build.cjs');
const historicalBytes = fs.readFileSync(historicalWrapper);
const historicalLiteral = /const copyAnchor = ("[^\n]+?");/.exec(historicalBytes.toString())[1];
const historicalAnchor = vm.runInNewContext(historicalLiteral);
assert.equal(count(original, historicalAnchor), 0);
const historical = generate(original, 'final', historicalBytes.toString());
assert.match(String(historical.error), /Raw copy instrumentation anchor changed/);
assert.equal(historical.childAttempts, 0);
assert.equal(historical.generated, undefined);
console.log(JSON.stringify({ passed: true, tier: 'pure generator regression; no HAP/compiler/device',
  wrapperSha256: sha(fs.readFileSync(wrapper)), sharedSha256: sha(original),
  anchorHits: Object.fromEntries(Object.entries(anchors).map(([name, token]) => [name, count(original, token)])),
  results, malformedTemplateMutationsKilled: killed,
  historicalV7: { wrapper: historicalWrapper, wrapperSha256: sha(historicalBytes),
    copyAnchor: historicalAnchor, anchorHits: count(original, historicalAnchor),
    reproducedFailure: String(historical.error), childStarted: false },
  dependenciesScope: 'before-compile dependency snapshot only; no dependency-after or SDK/tool/cache immutability claim' }, null, 2));
