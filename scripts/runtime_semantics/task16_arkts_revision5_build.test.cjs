'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { deriveBuilder } = require('./task16_arkts_revision5_build.cjs');

const shared = fs.readFileSync(path.join(__dirname, 'arkts_native_device.cjs'), 'utf8');

test('binds agent role to the exact Task16 revision-5 installer branch', () => {
  const derived = deriveBuilder(shared);
  const task16 = derived.indexOf("? 'Task16Revision5.install.cjs'");
  const task16Call = derived.indexOf('.install(work, role);', task16);
  const task12 = derived.indexOf("? 'Task12PartialUi.install.cjs'");
  const task12Call = derived.indexOf('.install(work);', task12);
  assert.ok(task16 >= 0 && task16Call > task16);
  assert.ok(task12 >= 0 && task12Call > task12 && task12Call < task16);
  assert.doesNotMatch(derived, /Task16NativeUi\.install\.cjs/);
});

test('fails closed when the shared Task16 installer block changes', () => {
  const mutated = shared.replace(".install(work);\n          if (taskId === '18_custom_notification_sounds'",
    ".install(work, 'mutated');\n          if (taskId === '18_custom_notification_sounds'");
  assert.throws(() => deriveBuilder(mutated), /builder shape changed/);
});
