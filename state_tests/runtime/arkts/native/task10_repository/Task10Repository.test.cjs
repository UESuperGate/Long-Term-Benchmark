'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { importBindings } = require('./Task10Repository.install.cjs');
function load(name) {
  const file = path.join(__dirname, name);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.CommonJS } }).outputText;
  const module = { exports: {} }; new Function('exports', 'module', code)(module.exports, module); return module.exports;
}
test('binding follows original imports, not private feature filenames', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task10-binding-test-'));
  try {
    fs.mkdirSync(path.join(work, 'entry/src/main/ets/pages'), { recursive: true });
    fs.mkdirSync(path.join(work, 'entry/src/main/ets/arbitrary'), { recursive: true });
    fs.writeFileSync(path.join(work, 'entry/src/main/ets/arbitrary/Renamed.ets'), 'export class Different {}');
    fs.writeFileSync(path.join(work, 'entry/src/main/ets/pages/Index.ets'), "import { Different } from '../arbitrary/Renamed';");
    const bindings = importBindings(work);
    assert.equal(bindings[0].modulePath, 'ets/arbitrary/Renamed');
    assert.equal(bindings[0].sha256.length, 64);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});
test('loaded runtime capability is independent of export name and fails closed on ambiguity', () => {
  const { findRuntimeClass } = load('Task10RepositoryInput.js');
  class Different { onChange() {} send() {} }
  assert.equal(findRuntimeClass([{ Random: Different }], ['onChange', 'send']), Different);
  assert.throws(() => findRuntimeClass([{}], ['onChange', 'send']), /Unbound/);
  class Other extends Different {}
  assert.throws(() => findRuntimeClass([{ Random: Different, Other }], ['onChange', 'send']), /ambiguous/);
});
test('observed overhead comes from executed estimator bytes and codec metadata, not expected constants', () => {
  const { effectiveHighOverhead } = load('Task10RepositorySuite.js');
  const state = { view: { metadata: { width: 1920, height: 1080, durationMs: 60000, bytes: 100000000, bytesKnown: true },
    plan: { options: [{ preset: 'high', estimatedBytes: 51315000 }] } },
    estimatorSpecs: [{ preset: 'high', maxLongEdge: 1920, videoBitrateBps: 6100000, audioBitrateBps: 120000 }] };
  assert.equal(effectiveHighOverhead(state), 1.1);
  state.view.plan.options[0].estimatedBytes = 46650000;
  assert.equal(effectiveHighOverhead(state), 1);
  assert.throws(() => effectiveHighOverhead({ ...state, estimatorSpecs: [] }), /unavailable/);
});
test('repository fixture preserves codec, fallback, selector, sender and UI implementation', () => {
  const input = fs.readFileSync(path.join(__dirname, 'Task10RepositoryInput.js'), 'utf8');
  assert.doesNotMatch(input, /patch\([^\n]*(buildPlan|refresh|chooseQuality|fallback|estimateVideoBytes|send')[,]/);
  assert.match(input, /original\.apply\(this, args\)/);
  assert.match(input, /original\.call\(this, request\)/);
  assert.doesNotMatch(input, /role\s*===|caseId\.includes|MediaQualityFeature/);
  const suite = fs.readFileSync(path.join(__dirname, 'Task10RepositorySuite.js'), 'utf8');
  assert.match(suite, /globalTap\(calculated.controls.send.bounds\)/);
  assert.match(suite, /before.controls.send|calculated.controls.send.enabled === true/);
  assert.match(suite, /prepared media is not established/);
});
