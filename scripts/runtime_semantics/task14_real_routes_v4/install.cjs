'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../..');
const native = path.join(root, 'state_tests/runtime/arkts/native');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Versioned Task14 packaging anchor changed: ' + old);
  return text.replace(old, next);
};
const CASES = ['jr_state_005_found_then_continue_navigates', 'jr_state_006_continue_waits_for_resolution',
  'jr_state_009_dismiss_closes_flow'];
function install(work, options = {}) {
  const deadline = Number(options.deadlineEpochMs || process.env.LTB_TASK14_ROUTE_DEADLINE_EPOCH_MS);
  if (!Number.isFinite(deadline) || deadline <= Date.now()) throw Error('One original scorer deadline required');
  const report = require(path.join(native, 'Task14DeviceUi.install.cjs')).install(work,
    { ...options, mode: 'after-page-ready' });
  const config = { ...report.config, deadlineEpochMs: deadline, actualRoutesV4: true };
  for (const name of ['productionModuleUrl', 'chatFeatureModuleUrl', 'chatRoutesModuleUrl', 'chatRuntimeModuleUrl'])
    if (!config[name]) throw Error('Unbound production runtime namespace: ' + name + '; NS, not missing-entry FAIL');
  const testRoot = path.join(work, 'entry/src/test');
  const newFiles = [
    [path.join(__dirname, '../task14_real_routes_v3/Task14JoinOwnerV3.js'), 'Task14JoinOwnerV3.js'],
    [path.join(__dirname, '../task14_real_routes_v3/Task14RealRoutesV3.suite.js'), 'Task14RealRoutesV3.suite.js'],
    [path.join(__dirname, 'Task14RealRoutesV4.adapter.js'), 'Task14RealRoutesV4.adapter.js']
  ];
  for (const [source, name] of newFiles) {
    const target = path.join(testRoot, name);
    if (fs.existsSync(target)) throw Error('Refusing candidate-owned evaluator filename: ' + name);
    fs.copyFileSync(source, target);
    report.fixtures.push({ path: 'entry/src/test/' + name, source,
      sha256: hash(fs.readFileSync(source)) });
  }
  const bridgeFile = path.join(testRoot, 'Task14DeviceUi.js');
  let bridge = fs.readFileSync(bridgeFile, 'utf8');
  bridge = "import { evaluateTask14RealRoutesV4 } from './Task14RealRoutesV4.adapter';\n" + bridge;
  bridge = replace(bridge, 'TASK14_CASES[caseSpec.caseId] !== caseSpec.key',
    '(TASK14_CASES[caseSpec.caseId] !== caseSpec.key && !' + JSON.stringify(CASES) + '.includes(caseSpec.caseId))');
  bridge = replace(bridge, "return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?",
    'if (' + JSON.stringify(CASES) + '.includes(caseSpec.caseId)) return evaluateTask14RealRoutesV4(args, config, ports, record);\n' +
    "    return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?");
  fs.writeFileSync(bridgeFile, bridge);
  const suite = fs.readFileSync(report.suiteFile, 'utf8');
  fs.writeFileSync(report.suiteFile, replace(suite, JSON.stringify(JSON.stringify(report.config)), JSON.stringify(JSON.stringify(config))));
  report.fixtures = report.fixtures.map(item => item.path === 'entry/src/test/Task14DeviceUi.js' ?
    { ...item, source: path.join(native, 'Task14DeviceUi.js'), derivedBy: __filename, sha256: hash(bridge) } : item);
  for (const item of report.production)
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production bytes changed');
  return { ...report, config, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    upstreamInstaller: report.installer, suiteSha256: hash(fs.readFileSync(report.suiteFile)),
    protocol: 'task14.arkts.actual-route-envelope.v4', semanticVerdictAssigned: false,
    scope: 'Own physical cases005/006/009; raw only. Original app/controller/router/RoomPresenter.' };
}
module.exports = { install, CASES };
