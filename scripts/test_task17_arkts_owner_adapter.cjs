'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { runCase } = require('../state_tests/runtime/arkts/native/Task17OwnerNativeUi.adapter.cjs');

const digest = 'a'.repeat(64);
const page = { path: 'entry/src/main/ets/pages/Index.ets', sha256: 'b'.repeat(64) };
const room = { path: 'entry/src/main/ets/features/MatrixRoomServices.ets', sha256: 'c'.repeat(64) };
const frames = [{ label: 'before_event' }, { label: 'after_event' }];
const spec = { key: 'empty_success', caseId: 'pm_state_003_empty_success', traceDigest: digest };

test('Task17 owner adapter accepts a complete page-owner transition', async () => {
  const traced = [];
  const result = await runCase({ taskId: '17_pinned_messages', caseSpec: spec,
    trace: (...args) => traced.push(args), native: { runTask17OwnerUI: async () => ({
      taskId: '17_pinned_messages', caseId: spec.caseId, key: spec.key, traceDigest: digest,
      entryExecuted: true, eventExecuted: true, frames, productionSources: [page, room],
      observed: { listState: 'empty' }, invariantChecks: [{ passed: true }],
      binding: { configuredBeforeScoredAbilityStart: true, importCompleted: true },
      fixture: { calls: [{ method: 'subscribeTimeline' }] }
    }) } });
  assert.equal(result.unsupported, undefined);
  assert.equal(result.integrationBoundary.appEntryExecuted, true);
  assert.equal(result.integrationBoundary.externalServicesExecuted, true);
  assert.equal(result.observed.listState, 'empty');
  assert.equal(traced.length, 2);
});

test('Task17 owner adapter requires the base feature-absence positive control', async () => {
  const result = await runCase({ taskId: '17_pinned_messages', caseSpec: spec, native: {
    runTask17OwnerUI: async () => ({ taskId: '17_pinned_messages', caseId: spec.caseId,
      key: spec.key, traceDigest: digest, entryExecuted: true, frames, productionSources: [page],
      semanticFeatureAbsent: true, evaluatorRole: 'base', observed: { listState: 'unavailable' },
      invariantChecks: [], basePositiveControl: { clickedBannerNext: true, finalEntryAbsent: true } })
  } });
  assert.equal(result.unsupported, undefined);
  assert.equal(result.nativeUI.semanticFeatureAbsent, true);
  assert.equal(result.integrationBoundary.externalServicesExecuted, false);
});

test('Task17 owner adapter fails closed on missing owner entry evidence', async () => {
  const result = await runCase({ taskId: '17_pinned_messages', caseSpec: spec, native: {
    runTask17OwnerUI: async () => ({ taskId: '17_pinned_messages', caseId: spec.caseId,
      key: spec.key, traceDigest: digest, entryExecuted: false, frames, productionSources: [page] })
  } });
  assert.match(result.unsupported, /identity\/entry incomplete/);
});
