'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const adapter = require('./Task17StrictNativeUi.adapter.cjs');

const digest = 'a'.repeat(64);
const spec = {
  taskId: '17_pinned_messages', caseId: 'pm_state_004_filled_list', key: 'filled_list',
  traceDigest: digest, given: { pinnedTimelineItems: [{ eventId: '$a' }, { eventId: '$b' }] },
  event: { name: 'timeline_items_updated' }, expected: {}, invariants: ['event identity and server order are preserved']
};
const source = path => ({ path, sha256: 'b'.repeat(64) });
const frame = label => ({ label, sessionId: 'session', bundleName: 'candidate.final' });

function finalRaw() {
  return {
    taskId: spec.taskId, caseId: spec.caseId, key: spec.key, traceDigest: digest,
    entryExecuted: true, eventExecuted: true,
    evaluatorRole: 'final', runtimeClassification: 'feature_entry_present',
    runtimeMode: 'original_installed_module_presenter_repository_and_native_preferences',
    frames: [frame('before_event'), frame('after_event')], actions: [{ executed: true }],
    binding: { importCompleted: true,
      productionModuleUrl: '@bundle:candidate.final/entry/ets/features/PinnedMessagesFeature' },
    nativePreferences: { sameAbilityContext: true, storeName: 'element_x_pinned_messages' },
    productionSources: [source('entry/src/main/ets/pages/Index.ets'),
      source('entry/src/main/ets/features/PinnedMessagesFeature.ets')],
    observed: { listState: 'filled', visibleEventIds: ['$a', '$b'], loadedPinnedMessagesCount: 2 },
    invariantChecks: [{ description: spec.invariants[0], passed: true }]
  };
}

function baseRaw() {
  return {
    taskId: spec.taskId, caseId: spec.caseId, key: spec.key, traceDigest: digest,
    entryExecuted: true, eventExecuted: true,
    evaluatorRole: 'base', runtimeClassification: 'feature_entry_absent',
    runtimeMode: 'actual_base_page_feature_absence_with_positive_control',
    frames: [frame('before_event'), frame('after_event')], actions: [{ executed: true }],
    baseFeatureAbsent: true,
    basePositiveControl: { clickedBannerNext: true, bodyChanged: true },
    productionSources: [source('entry/src/main/ets/pages/Index.ets'),
      source('entry/src/main/ets/features/PinnedMessagesBase.ets')],
    observed: {}, invariantChecks: []
  };
}

async function execute(raw) {
  const loaded = [];
  const result = await adapter.runCase({ taskId: spec.taskId, caseSpec: spec,
    native: { bundleName: raw.baseFeatureAbsent ? 'candidate.base' : 'candidate.final',
      runTask17StrictUI: async () => raw },
    load: async file => { loaded.push(file); return {}; }, trace() {} });
  return { result, loaded };
}

test('accepts complete original-module ArkVM and native Preferences evidence', async () => {
  const { result, loaded } = await execute(finalRaw());
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(result.observed.visibleEventIds, ['$a', '$b']);
  assert.equal(result.integrationBoundary.nativePreferencesExecuted, true);
  assert.deepEqual(loaded, ['entry/src/main/ets/features/PinnedMessagesFeature.ets']);
});

test('accepts base only with a physical positive control and final entry absence', async () => {
  const { result, loaded } = await execute(baseRaw());
  assert.equal(result.unsupported, undefined);
  assert.equal(result.nativeUI.baseFeatureAbsent, true);
  assert.deepEqual(result.observed, {});
  assert.deepEqual(result.invariantChecks, []);
  assert.deepEqual(loaded, ['entry/src/main/ets/features/PinnedMessagesBase.ets']);
});

test('agent base classification does not require a base feature filename', async () => {
  const raw = baseRaw();
  raw.evaluatorRole = 'agent';
  raw.productionSources = [source('entry/src/main/ets/pages/Index.ets')];
  const { result, loaded } = await execute(raw);
  assert.equal(result.unsupported, undefined);
  assert.equal(result.nativeUI.runtimeClassification, 'feature_entry_absent');
  assert.deepEqual(loaded, []);
});

for (const [name, mutate, pattern] of [
  ['wrong digest', raw => { raw.traceDigest = 'c'.repeat(64); }, /transition incomplete/],
  ['missing after frame', raw => { raw.frames.pop(); }, /before\/after/],
  ['missing page provenance', raw => { raw.productionSources.shift(); }, /page provenance/],
  ['wrong installed module', raw => { raw.binding.productionModuleUrl = '@bundle:other/entry/ets/features/PinnedMessagesFeature'; }, /feature binding/i],
  ['different Preferences context', raw => { raw.nativePreferences.sameAbilityContext = false; }, /Preferences evidence/],
  ['missing final feature provenance', raw => { raw.productionSources.pop(); }, /feature binding/i]
]) {
  test('rejects mutation: ' + name, async () => {
    const raw = finalRaw();
    mutate(raw);
    const { result } = await execute(raw);
    assert.match(result.unsupported, pattern);
  });
}

for (const [name, mutate] of [
  ['unclicked control', raw => { raw.basePositiveControl.clickedBannerNext = false; }],
  ['unchanged banner body', raw => { raw.basePositiveControl.bodyChanged = false; }],
  ['missing base feature provenance', raw => { raw.productionSources.pop(); }]
]) {
  test('rejects base mutation: ' + name, async () => {
    const raw = baseRaw();
    mutate(raw);
    const { result } = await execute(raw);
    assert.match(result.unsupported, /Base positive control/);
  });
}
