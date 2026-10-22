'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { exportedClass, reaches } = require('./CandidateApiBindings.cjs');
const root = path.resolve(__dirname, '../../../..');
const audit = path.join(root, 'experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

test('binds actual immutable candidate APIs through the entry import graph without changing sources', () => {
  for (const [task, symbol, file, count] of [
    ['14_join_room_by_address', 'JoinRoomByAddressPresenter', 'ChatFeature.ets', 3],
    ['15_account_deactivation', 'AccountDeactivationPresenter', 'AccountDeactivation.ets', 2]
  ]) {
    const source = path.join(audit, 'sources', task, 'candidate');
    const before = hash(path.join(source, 'entry/src/main/ets/features', file));
    const api = exportedClass(source, symbol);
    assert.equal(api.path, 'entry/src/main/ets/features/' + file);
    assert.equal(api.parameters.length, count);
    assert.equal(reaches(source, 'entry/src/main/ets/pages/Index.ets', api.path), true);
    assert.equal(hash(path.join(source, api.path)), before);
  }
});

test('exported API discovery supports renamed files and rejects duplicate or absent exports', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-candidate-api-'));
  try {
    const features = path.join(temporary, 'entry/src/main/ets/features');
    const pages = path.join(temporary, 'entry/src/main/ets/pages');
    fs.mkdirSync(features, { recursive: true });
    fs.mkdirSync(pages, { recursive: true });
    fs.writeFileSync(path.join(features, 'Renamed.ets'), 'export class Presenter { constructor(port: Object) {} run(): void {} }');
    fs.writeFileSync(path.join(pages, 'Index.ets'), "import {Presenter} from '../features/Renamed';");
    assert.equal(exportedClass(temporary, 'Presenter').path, 'entry/src/main/ets/features/Renamed.ets');
    assert.equal(reaches(temporary, 'entry/src/main/ets/pages/Index.ets', 'entry/src/main/ets/features/Renamed.ets'), true);
    assert.throws(() => exportedClass(temporary, 'Unknown'), /no unique exported/);
    fs.copyFileSync(path.join(features, 'Renamed.ets'), path.join(features, 'Duplicate.ets'));
    assert.throws(() => exportedClass(temporary, 'Presenter'), /no unique exported/);
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});

test('a source symlink cannot bind another project API', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-candidate-api-'));
  try {
    const features = path.join(temporary, 'entry/src/main/ets/features');
    fs.mkdirSync(features, { recursive: true });
    fs.symlinkSync(__filename, path.join(features, 'Escaped.ets'));
    assert.throws(() => exportedClass(temporary, 'Presenter'), /symlink unsupported/);
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});
