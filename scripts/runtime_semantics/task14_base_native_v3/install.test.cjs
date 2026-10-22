'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('base V3 adopts the prepared foreground while retaining ownership checks', () => {
  const core = installer.coreSource();
  assert.match(core, /config\.preparedForegroundEntry === true/);
  assert.match(core, /Prepared foreground candidate identity unavailable/);
  assert.match(core, /Last window is not original Stage main window/);
  assert.match(core, /Foreign UIContext host/);
  assert.match(core, /Original Driver window ownership\/focus unavailable/);
  assert.match(core, /Driver\/native Stage window geometry differs/);
  assert.match(core, /Original inspector tree is empty/);
});
