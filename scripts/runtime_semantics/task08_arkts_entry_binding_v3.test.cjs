'use strict';
// Source-binding eligibility negatives only; no SDK/device execution.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { validateTask08EntryBinding } = require('./task08_arkts_entry_binding_v3.cjs');
const root = path.resolve(__dirname, '../..');
const report = path.join(root, 'experiment_results/runtime_transition_20261021/task08_arkts_fresh_controls_after_focus_fix_v1/base/build/device-build-report.json');
const before = fs.readFileSync(report);
const fresh = () => JSON.parse(before);

test('actual v1 Task08 build has valid source-bound entry without any Task13 discovery schema', () => {
  const build = fresh();
  assert.equal(build.task13Revision5, undefined); assert.equal(build.task08Revision5, undefined);
  const result = validateTask08EntryBinding(build);
  assert.equal(result.productionVariant, 'base'); assert.equal(result.route, 'pages/Index');
  assert.equal(result.nativeEntryExecuted, false);
  assert.equal(result.subsequentNativeLaunchWindowStateAndSourceProofRequired, true);
  assert.deepEqual(fs.readFileSync(report), before);
});

for (const [name, mutate] of [
  ['wrong task', b => { b.taskId = '13_user_verification'; }],
  ['no original entry observer', b => { delete b.nativeUIObserver; }],
  ['compile-only', b => { b.compileOnly = true; }],
  ['fabricated discovery flag with compile-only', b => { b.task08Revision5 = { compileOnly: true, entryDiscovery: true }; }],
  ['mismatched module', b => { b.nativeUIObserver.config.productionModuleUrl += 'Wrong'; }],
  ['missing Index source', b => { b.nativeUIObserver.sources = b.nativeUIObserver.sources.filter(s => !s.path.endsWith('/Index.ets')); }],
  ['wrong installer', b => { b.nativeUIObserver.installer.sha256 = '0'.repeat(64); }],
  ['wrong application bundle', b => { b.nativeUIObserver.config.bundleName = 'com.wrong.app'; }]
]) test('reject ' + name + ' without projecting a semantic failure', () => {
  const build = fresh(); mutate(build);
  assert.throws(() => validateTask08EntryBinding(build), /Task08 native entry binding/);
});

test('no original import is rejected even when supplied source hashes match edited unit-copy bytes', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'task08-gate-unit-'));
  try {
    const build = fresh();
    fs.cpSync(build.source, temporary, { recursive: true });
    build.source = temporary;
    const relative = 'entry/src/main/ets/pages/Index.ets';
    fs.writeFileSync(path.join(temporary, relative), '@Entry\n@Component\nstruct Index { build() { Text("not-original") } }\n');
    const hash = crypto.createHash('sha256').update(fs.readFileSync(path.join(temporary, relative))).digest('hex');
    for (const items of [build.production, build.nativeUIObserver.production, build.nativeUIObserver.sources]) {
      items.find(item => item.path === relative).sha256 = hash;
    }
    assert.throws(() => validateTask08EntryBinding(build), /no original imported/);
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});
