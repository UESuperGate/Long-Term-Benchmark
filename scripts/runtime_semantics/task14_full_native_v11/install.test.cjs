'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const installer = require('./install.cjs');

test('V11 adopts only the already prepared exact foreground candidate', () => {
  const source = installer.coreSource();
  assert.match(source, /preparedForegroundEntry === true/);
  assert.match(source, /getCurrentTopAbility/);
  assert.match(source, /Prepared foreground candidate identity unavailable/);
  assert.match(source, /Task14\.preparedForegroundAdopted/);
  assert.match(source, /const main = stage \? await stage\.getMainWindow\(\) : win/);
});

test('V11 retains strong window, route, and tree ownership checks', () => {
  const source = installer.coreSource();
  for (const marker of ['Last window is not original Stage main window', 'Foreign UIContext host',
    'Original Driver window ownership/focus unavailable', 'Driver/native Stage window geometry differs',
    'Route is not owned by the candidate', 'Original inspector tree is empty']) assert.match(source, new RegExp(marker));
  assert.equal(installer.pageObserverAlias,
    "export { installTask14Observer } from './Task14JoinOwnerV3';\n");
  assert.match(installer.e2eSource(), /login_keyboard_dismissed/);
});
