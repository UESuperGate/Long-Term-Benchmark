'use strict';
// Runs the REAL bundle generator and installers; does NOT run Hvigor/HDC.
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const crypto = require('node:crypto'), test = require('node:test'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const generate = require('../arkts_native_bundle.cjs').generate;
const installer = require('./install.cjs');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const sources = {
  final: path.join(root, 'final_dev_nodes/14_join_room_by_address_final_25_03_0'),
  candidate: path.join(root, 'experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1/sources/14_join_room_by_address/candidate')
};

for (const [label, source] of Object.entries(sources)) test('real source ' + label + ': native route fixtures and suite bindings package offline', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task14-v4-package-unit-'));
  try {
    const work = path.join(temporary, 'work'), evidence = path.join(temporary, 'evidence');
    fs.cpSync(source, work, { recursive: true, filter: file => !['.git', 'build', '.hvigor', 'oh_modules', 'node_modules'].includes(path.basename(file)) });
    fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true }); fs.mkdirSync(evidence);
    generate(work, evidence, '14_join_room_by_address', 'agent', source, true,
      { device: true, caseId: installer.CASES[0] });
    const manifest = installer.install(work, { deadlineEpochMs: Date.now() + 3600000 });
    assert.equal(manifest.productionUnchanged, true);
    assert.equal(manifest.config.mode, 'after-page-ready');
    assert.equal(manifest.semanticVerdictAssigned, false);
    for (const item of manifest.production) assert.equal(hash(fs.readFileSync(path.join(source, item.path))), item.sha256);
    for (const item of manifest.fixtures) assert.equal(hash(fs.readFileSync(path.join(work, item.path))), item.sha256);
    const expected = JSON.parse(require('node:child_process').execFileSync('python3', ['-B', '-c',
      'import json; from scripts.runtime_semantics.task14_actual_routes_packaging_v4 import expected_fixtures; print(json.dumps(expected_fixtures()))'],
      {cwd:root,env:{...process.env,PYTHONPATH:'scripts:.'},encoding:'utf8',timeout:10000}));
    assert.deepEqual(manifest.fixtures.map(item=>({name:path.basename(item.path),sha256:item.sha256}))
      .sort((a,b)=>a.name.localeCompare(b.name)), expected.sort((a,b)=>a.name.localeCompare(b.name)));
    const bridge = fs.readFileSync(path.join(work, 'entry/src/test/Task14DeviceUi.js'), 'utf8');
    assert.ok(bridge.includes('evaluateTask14RealRoutesV4(args, config, ports, record)'));
    for (const id of installer.CASES) assert.ok(bridge.includes(id));
    assert.equal(manifest.config.addressRoute, label === 'final' ? 'pages/Index' : 'pages/JoinRoomByAddress');
    assert.ok(fs.readFileSync(manifest.suiteFile, 'utf8').includes('actualRoutesV4'));
    const compiled = require('../offline_task14_15_fixture_compile_v1.cjs').compileFixtures(work, manifest);
    assert.equal(compiled.passed, true); assert.equal(compiled.binariesRetained, false);
    assert.ok(compiled.files.every(item => item.binary.bytes > 0 && item.binary.removed));
    if (process.env.LTB_OFFLINE_RECEIPT_DIR) {
      fs.writeFileSync(path.join(process.env.LTB_OFFLINE_RECEIPT_DIR, 'task14-' + label + '.json'),
        JSON.stringify({label,...compiled}, null, 2) + '\n', {flag:'wx'});
    } else {
      console.info('TASK14_OFFLINE_BYTECODE_RECEIPT ' + JSON.stringify({label,...compiled,files:undefined,fileCount:compiled.files.length}));
    }
    assert.throws(() => installer.install(work, { deadlineEpochMs: Date.now() - 1 }), /deadline/);
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});

test('source scanner does not parse commented-out buttons as real UI bindings', () => {
  const binder = require('../task15_page_owner_packaging_v6.cjs');
  assert.equal(binder.controls("// Button('Fake').id('fake')\nButton('Real').id('real')", 'unit.ets').length, 1);
  assert.throws(() => binder.controls("Button('Real').id(dynamicId)", 'unit.ets'), /Dynamic/);
});

for (const [label, source] of Object.entries({
  final: path.join(root, 'final_dev_nodes/15_account_deactivation_final_0_6_3'),
  candidate: path.join(root, 'experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1/sources/15_account_deactivation/candidate')
})) test('Task15 ' + label + ': own source controls/property discovered, never native approval', () => {
  const bindings = require('../task15_page_owner_packaging_v6.cjs').discover(source);
  assert.equal(bindings.approvedNativeProfile, false); assert.equal(bindings.semanticResultFromSource, false);
  assert.equal(bindings.ownerBinding.property, 'presenter');
  assert.equal(bindings.controlBindings.close.label, label === 'final' ? 'Close' : 'Dismiss');
  assert.deepEqual(bindings.controlSelectors.erase, label === 'final' ? { type: 'Toggle' } : { id: 'deactivation_erase_data' });
  assert.equal(bindings.ownerBinding.pageSourcePath, label === 'final' ? 'entry/src/main/ets/pages/Index.ets' :
    'entry/src/main/ets/components/AccountDeactivationControls.ets');
});
