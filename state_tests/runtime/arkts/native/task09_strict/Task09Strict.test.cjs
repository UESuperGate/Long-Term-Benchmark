'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { install, modules } = require('./Task09Strict.install.cjs');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

function fixture(role) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task09-strict-install-'));
  const write = (relative, value) => { const file = path.join(work, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, value); };
  write('AppScope/app.json5', JSON.stringify({ app: { bundleName: 'com.qingyu.elementx.spaces.' + role } }));
  write('entry/src/main/module.json5', JSON.stringify({ module: { name: 'entry', mainElement: 'EntryAbility',
    pages: '$profile:main_pages', abilities: [{ name: 'EntryAbility' }] } }));
  write('entry/src/main/resources/base/profile/main_pages.json', JSON.stringify({ src: ['pages/Index'] }));
  write('entry/src/main/ets/pages/Index.ets', '@Entry\n@Component\nstruct Index { build() { Text(\'spaces\') } }\n');
  const feature = role === 'base' ? 'HomeRoomsFeature' : 'SpacesFeature';
  write('entry/src/main/ets/features/' + feature + '.ets', 'export class BoundFeature {}\n');
  write('entry/src/test/native-bundle.js', "import { createNativeContext } from './native-device-platform';\n" +
    "calls.push({ module: 'ArkUI', method: observation.method, nativeUI: true, observation: snapshot(observation) });\n" +
    'if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n' +
    'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge, context: {} }) };\n');
  write('entry/src/test/NativeBundle.test.ets', 'export default function nativeBundleTests(): void {}\n');
  return work;
}

for (const role of ['base', 'final']) test('installer binds Task09 ' + role + ' without changing production', () => {
  const work = fixture(role);
  try {
    const before = hash(path.join(work, 'entry/src/main/ets/pages/Index.ets'));
    const result = install(work, role);
    assert.equal(result.role, role); assert.equal(result.productionUnchanged, true);
    assert.equal(hash(path.join(work, 'entry/src/main/ets/pages/Index.ets')), before);
    const bundle = fs.readFileSync(path.join(work, 'entry/src/test/native-bundle.js'), 'utf8');
    assert.match(bundle, /attachTask09Strict/); assert.match(bundle, /bridge\.evaluateTask09Strict \|\| module\.exports\.runCase/);
    for (const name of modules) assert.equal(fs.existsSync(path.join(work, 'entry/src/test', name)), true, name);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

test('suite binds all canonical identities and contains no source observer', () => {
  const suite = fs.readFileSync(path.join(__dirname, 'Task09Suite.js'), 'utf8');
  const contract = JSON.parse(fs.readFileSync(path.resolve(__dirname,
    '../../../../../benchmark_tasks/09_spaces_lifecycle/transitions.json')));
  for (const spec of contract.cases) assert.match(suite, new RegExp(spec.caseId));
  assert.doesNotMatch(suite, /readFileSync|source_observer|git apply/);
  assert.match(suite, /session\.action\('click'/);
});

test('missing entry never fabricates canonical post-state or failed invariants', () => {
  const suite = fs.readFileSync(path.join(__dirname, 'Task09Suite.js'), 'utf8');
  const start = suite.indexOf("if (config.productionVariant === 'base') {");
  const end = suite.indexOf("if (spec.key === 'accept_invite')", start);
  const branch = suite.slice(start, end);
  assert.match(branch, /common-chats-prefix/);
  assert.match(branch, /Task09\.missingFeatureEntry/);
  assert.match(branch, /before, after, stateBefore, stateAfter: state/);
  assert.doesNotMatch(branch, /absent\[|invariant\(false|result\.observed\s*=/);
});

test('case007 yields between real bulk and toggle UI actions', () => {
  const suite = fs.readFileSync(path.join(__dirname, 'Task09Suite.js'), 'utf8');
  const branch = suite.slice(suite.indexOf("spec.key === 'bulk_and_toggle_selection'"),
    suite.indexOf("spec.key === 'leave_failure_retry'"));
  assert.match(branch, /settledClick\('toggle-b-prefix'/);
  assert.match(branch, /settledClick\('deselect-all'/);
  assert.match(branch, /settledClick\('select-all'/);
  assert.match(branch, /settledClick\('toggle-b'/);
  assert.match(suite, /await session\.delay\(50\)/);
  assert.match(suite, /Task09\.harnessUiStepSettled/);
  assert.doesNotMatch(branch, /presenter\.|gateway\.|descriptor\.value/);
});

test('agent role uses the same external runtime boundaries as final', () => {
  const input = fs.readFileSync(path.join(__dirname, 'Task09Input.js'), 'utf8');
  assert.match(input, /if \(role === 'base' \|\| presenter\.gateway\.__task09StrictSources\) return/);
  assert.doesNotMatch(input, /role !== 'final'/);
});

test('strict matrix retries only empty transport failures and retains each attempt', () => {
  const runner = fs.readFileSync(path.resolve(__dirname,
    '../../../../../scripts/runtime_semantics/task09_arkts_strict_runner.cjs'), 'utf8');
  assert.match(runner, /execution-attempt-/);
  assert.match(runner, /execution\.rows\.length === 0/);
  assert.match(runner, /row\.status === 'not_scored'/);
  assert.match(runner, /cleanup\?\.ownedAppUninstalled === true/);
  assert.match(runner, /canonical device row missing\|App died\|THREAD_BLOCK/);
  assert.match(runner, /connect to AAMS\|RET_ERR_CONNECTION_EXIST/);
  assert.match(runner, /transportAttempts: attempts/);
  assert.match(runner, /rows\.push\(rowEntry\);\s+await sleep\(2000\)/);
  assert.doesNotMatch(runner, /row\.status === 'fail'.*retry/s);
});

test('final checkbox binding does not turn programmatic bulk selection into a toggle loop', () => {
  const page = fs.readFileSync(path.resolve(__dirname,
    '../../../../../final_dev_nodes/09_spaces_lifecycle_final_25_10_0/entry/src/main/ets/pages/Index.ets'), 'utf8');
  assert.match(page, /onChange\(\(selected: boolean\)/);
  assert.match(page, /selected !== presenterSelected/);
  assert.match(page, /presenter\.toggleRoomSelection\(room\.roomId\)/);
});

test('mutating expected state is rejected by the canonical comparison shape', () => {
  const contract = JSON.parse(fs.readFileSync(path.resolve(__dirname,
    '../../../../../benchmark_tasks/09_spaces_lifecycle/transitions.json')));
  const original = contract.cases.find(item => item.key === 'leave_selected_rooms').expected;
  const mutant = { ...original, payload: ['!a'] };
  assert.notDeepEqual(mutant, original);
  assert.deepEqual(original.payload, ['!a', '!c']);
});

test('agent may retain base bundle identity without being treated as base behavior', () => {
  const work = fixture('base');
  const write = (relative, text) => {
    const file = path.join(work, relative); fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, text);
  };
  try {
    write('entry/src/main/ets/pages/Index.ets',
      "import { SpacesPresenter } from '../features/custom/Controller';\n" +
      "import { SpaceServiceRegistry } from '../data/Registry';\n@Entry struct Index {}\n");
    write('entry/src/main/ets/features/custom/Controller.ets', 'export class SpacesPresenter {}');
    write('entry/src/main/ets/data/Registry.ets', 'export class SpaceServiceRegistry {}');
    write('entry/src/main/ets/pages/LeaveSpace.ets', "import { LeaveSpacePresenter } from '../features/custom/Leave';");
    write('entry/src/main/ets/features/custom/Leave.ets', 'export class LeaveSpacePresenter {}');
    write('entry/src/main/resources/base/profile/main_pages.json', JSON.stringify({ src: ['pages/Index', 'pages/LeaveSpace'] }));
    const before = hash(path.join(work, 'entry/src/main/ets/pages/Index.ets'));
    const result = install(work, 'agent');
    assert.equal(result.role, 'agent'); assert.equal(result.config.productionVariant, 'repository');
    assert.match(result.config.repositoryModules.spaces, /ets\/features\/custom\/Controller$/);
    assert.match(result.config.repositoryModules.registry, /ets\/data\/Registry$/);
    assert.equal(hash(path.join(work, 'entry/src/main/ets/pages/Index.ets')), before);
    assert.equal(result.productionUnchanged, true);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

test('unknown agent implementation fails closed instead of silently selecting the base probe', () => {
  const work = fixture('base');
  try {
    fs.writeFileSync(path.join(work, 'entry/src/main/ets/pages/Index.ets'),
      "import { OtherController } from '../features/OtherController';\n@Entry struct Index {}\n");
    assert.throws(() => install(work, 'agent'), /adapter_binding_incomplete/);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

test('preacquired device ownership is passed only by the owner, not inherited', () => {
  const { executionEnvironment } = require('../../../../../scripts/runtime_semantics/task09_arkts_strict_runner.cjs');
  assert.equal(executionEnvironment(true, {}).LTB_DEVICE_LOCK_PREACQUIRED, '1');
  assert.equal(executionEnvironment(false, { LTB_DEVICE_LOCK_PREACQUIRED: '1' }).LTB_DEVICE_LOCK_PREACQUIRED, undefined);
  assert.equal(executionEnvironment(false, { HOME: '/home/example' }).HOME, '/home/example');
});
