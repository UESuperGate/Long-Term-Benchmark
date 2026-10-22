'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { deriveBuilder } = require('./task17_arkts_strict_build.cjs');

const shared = fs.readFileSync(path.join(__dirname, 'arkts_native_device.cjs'), 'utf8');

test('binds evaluator role only to the Task17 strict installer branch', () => {
  const derived = deriveBuilder(shared);
  const task17 = derived.indexOf("? 'Task17StrictNativeUi.install.cjs'");
  const task17Call = derived.indexOf('.install(work, role);', task17);
  const task12 = derived.indexOf("? 'Task12PartialUi.install.cjs'");
  const task12Call = derived.indexOf('.install(work);', task12);
  assert.ok(task17 >= 0 && task17Call > task17);
  assert.ok(task12 >= 0 && task12Call > task12 && task12Call < task17);
});

test('fails closed when the shared Task17 installer block changes', () => {
  const mutated = shared.replace(".install(work);\n          if (taskId === '18_custom_notification_sounds'",
    ".install(work, 'mutated');\n          if (taskId === '18_custom_notification_sounds'");
  assert.throws(() => deriveBuilder(mutated), /builder shape changed/);
});
