'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { classifyEntry } = require('./task10_arkts_entry_binding.cjs');
const common = [
  { id: 'attachment_caption', type: 'TextInput', visible: 'true' },
  { id: 'attachment_send', type: 'Button', text: 'Send original', visible: 'true' }
];
test('actual common controls are not a missing-entry proof when alternative controls exist', () => {
  for (const id of ['video_quality_button', 'random-selector', '']) {
    const result = classifyEntry([...common, { id, type: 'Button', text: 'Change', visible: 'true', enabled: 'false' }]);
    assert.equal(result.binding, 'production_repository_probe_required');
    assert.equal(result.commonPreview, false);
  }
});
test('unknown common action semantics stay unbound to the old negative fixture', () => {
  const nodes = common.map(node => ({ ...node })); nodes[1].text = 'Send';
  assert.equal(classifyEntry(nodes).binding, 'production_repository_probe_required');
});
test('exact calibrated base and final visual entries remain distinct', () => {
  assert.equal(classifyEntry(common).binding, 'canonical_original_media_ui');
  assert.equal(classifyEntry(['media_caption', 'media_send', 'video_quality_selector'].map(id =>
    ({ id, visible: 'true' }))).binding, 'canonical_quality_ui');
  assert.equal(classifyEntry([]).binding, 'unbound');
});
