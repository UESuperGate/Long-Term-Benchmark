'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { install, modules } = require('./Task11Strict.install.cjs');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

function fixture(role) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task11-strict-install-'));
  const write = (relative, value) => {
    const file = path.join(work, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, value);
  };
  write('AppScope/app.json5', JSON.stringify({ app: { bundleName: 'com.qingyu.elementx.roomupgrade.' + role } }));
  write('entry/src/main/module.json5', JSON.stringify({ module: { name: 'entry', mainElement: 'EntryAbility',
    pages: '$profile:main_pages', abilities: [{ name: 'EntryAbility' }] } }));
  write('entry/src/main/resources/base/profile/main_pages.json', JSON.stringify({ src: ['pages/Index'] }));
  write('entry/src/main/ets/pages/Index.ets', '@Entry\n@Component\nstruct Index { build() { Text(\'room\') } }\n');
  const feature = role === 'base' ? 'RoomFeature' : 'RoomUpgradeFeature';
  write('entry/src/main/ets/features/' + feature + '.ets', 'export class BoundFeature {}\n');
  write('entry/src/test/native-bundle.js', "import { createNativeContext } from './native-device-platform';\n" +
    'if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n' +
    'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge, context: {} }) };\n');
  write('entry/src/test/NativeBundle.test.ets', 'export default function nativeBundleTests(): void {}\n');
  return work;
}

for (const [role, apiVariant] of [['base', 'base'], ['final', 'final'], ['agent', 'final']])
test('installer binds Task11 ' + role + '/' + apiVariant + ' without changing production', () => {
  const work = fixture(apiVariant);
  try {
    const before = hash(path.join(work, 'entry/src/main/ets/pages/Index.ets'));
    const result = install(work, { role, apiVariant });
    assert.equal(result.role, role);
    assert.equal(result.apiVariant, apiVariant);
    assert.equal(result.productionUnchanged, true);
    assert.equal(hash(path.join(work, 'entry/src/main/ets/pages/Index.ets')), before);
    const bundle = fs.readFileSync(path.join(work, 'entry/src/test/native-bundle.js'), 'utf8');
    const suite = fs.readFileSync(path.join(work, 'entry/src/test/NativeBundle.test.ets'), 'utf8');
    assert.match(bundle, /attachTask11Strict/);
    assert.match(bundle, /bridge\.evaluateTask11Strict \|\| module\.exports\.runCase/);
    assert.match(suite, /configureTask11Strict/);
    for (const name of modules) assert.equal(fs.existsSync(path.join(work, 'entry/src/test', name)), true, name);
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
  }
});

test('strict suite carries all six canonical identities and no source observer', () => {
  const suite = fs.readFileSync(path.join(__dirname, 'Task11Suite.js'), 'utf8');
  const contract = JSON.parse(fs.readFileSync(path.resolve(__dirname,
    '../../../../../benchmark_tasks/11_room_upgrade_navigation/transitions.json')));
  for (const spec of contract.cases) assert.match(suite, new RegExp(spec.caseId));
  assert.doesNotMatch(suite, /readFileSync|source observer|source_observer/);
  assert.match(suite, /predecessorRoom\?\.lastEventId === g\.predecessor\.lastEventId/);
});

test('installer never infers a role from the bundle name', () => {
  const source = fs.readFileSync(path.join(__dirname, 'Task11Strict.install.cjs'), 'utf8');
  assert.doesNotMatch(source, /endsWith\(['"]\.(?:base|final)['"]\)/);
  assert.match(source, /options\.role/);
  assert.match(source, /options\.apiVariant/);
});

for (const variant of ['base', 'final']) test('agent auto binds the actual production import: ' + variant, () => {
  const work = fixture(variant);
  const feature = variant === 'base' ? 'RoomFeature' : 'RoomUpgradeFeature';
  try {
    const page = path.join(work, 'entry/src/main/ets/pages/Index.ets');
    fs.writeFileSync(page, "import { BoundFeature } from '../features/" + feature + "';\n" + fs.readFileSync(page));
    const before = hash(page);
    const result = install(work, { role: 'agent', apiVariant: 'auto' });
    assert.equal(result.role, 'agent');
    assert.equal(result.apiVariant, 'auto');
    assert.equal(hash(page), before);
    const adapter = fs.readFileSync(path.join(__dirname, 'Task11Adapter.js'), 'utf8');
    assert.match(adapter, /ports\.importModule\(config\.productionModuleUrl\)/);
    assert.match(adapter, /typeof namespace\.RoomPresenter\?\.prototype\?\.observeRoomInfo/);
    assert.doesNotMatch(adapter, /config\.role\s*===\s*['"]base/);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});
