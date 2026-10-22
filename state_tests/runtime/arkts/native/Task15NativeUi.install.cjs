'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
function production(work) {
  const result = [];
  const visit = dir => {
    for (const item of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(dir, item.name);
      if (item.isSymbolicLink()) throw new Error('Candidate symlink unsupported');
      if (item.isDirectory()) visit(file);
      else result.push({ path: path.relative(work, file), sha256: hash(fs.readFileSync(file)) });
    }
  };
  visit(path.join(work, 'entry/src/main'));
  return result;
}

function install(work) {
  work = fs.realpathSync(work);
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js'), suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8'), originalSuite = fs.readFileSync(suiteFile, 'utf8');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const dispatch = 'module.exports.runCase({ ...context, native: bridge,';
  const dispose = 'try { await bridge.dispose(); }';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  if (!originalBundle.includes("from './native-device-platform'")) throw new Error('Native device bundle required');
  if (originalBundle.includes('attachTask15UI')) throw new Error('Task15 native UI already installed');
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispatch], [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const modules = ['Task15PageObserver.js', 'Task15NativeUi.js', 'Task15NativeUi.d.ts', 'Task15NativeUiSuite.ets',
    'Task15NativeE2E.js', 'Task15NativeE2E.d.ts',
    'Task15NativeUiBridge.js', 'Task15NativeUiBridge.d.ts', 'Task15Launch.js', 'Task15LaunchNative.js', 'Task15LaunchNative.d.ts'];
  for (const name of [...modules, 'Task15NativeUiAdapter.js']) {
    if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file: ' + name);
  }
  const before = production(work);
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  const moduleName = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module.name;
  if (!bundleName || moduleName !== 'entry') throw new Error('Original entry manifest required');
  const apiBindings = require(path.join(__dirname, 'CandidateApiBindings.cjs'));
  const api = apiBindings.exportedClass(work, 'AccountDeactivationPresenter');
  const clientCallback = api.methods.includes('refreshAvailability') && api.methods.includes('openForm');
  const service = apiBindings.exportedClass(work, 'AccountClient');
  for (const target of [api.path, service.path]) if (!apiBindings.reaches(work, 'entry/src/main/ets/pages/Index.ets', target))
    throw new Error('Original entry does not load the bound account API: ' + target);
  const url = file => '@bundle:' + bundleName + '/' + moduleName + '/' + file.slice('entry/src/main/'.length).replace(/\.(ets|ts)$/, '');
  const binding = { bundleName, moduleName, productionModuleUrl: url(api.path), presenterSourcePath: api.path,
    serviceModuleUrl: url(service.path), apiShape: clientCallback ? 'clientCallback' : 'capabilityService',
    entryId: clientCallback ? 'settings_deactivate_account' : 'deactivate_account_entry',
    submitId: clientCallback ? 'deactivation_submit' : 'deactivate_submit',
    confirmationText: clientCallback ? 'Deactivate this account?' : 'Are you sure you want to deactivate this account?',
    confirmText: clientCallback ? 'Deactivate now' : 'Confirm deactivation',
    loadingId: clientCallback ? 'deactivation_loading' : 'deactivation_loading_dialog',
    failureId: clientCallback ? 'deactivation_failure' : '' };
  const observedSources = new Set(['entry/src/main/ets/pages/Index.ets', api.path,
    'entry/src/main/ets/services/AccountClient.ets', 'entry/src/main/ets/services/NativeAccountClient.ets',
    'entry/src/main/ets/components/AccountSessionControls.ets']);
  if (clientCallback) observedSources.add('entry/src/main/ets/components/AccountDeactivationControls.ets');
  const sources = before.filter(item => observedSources.has(item.path));
  const bundle = "import { attachTask15UI } from './Task15NativeUiBridge';\n" +
    "import { runTask15Case } from './Task15NativeUiAdapter';\n" + originalBundle
      .replace(navigate, 'const task15UI = attachTask15UI(bridge, taskId, caseSpec.key);\n    if (!task15UI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
      .replace(dispatch, '(task15UI ? runTask15Case : module.exports.runCase)({ ...context, native: bridge,')
      .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask15UI) bridge.disposeTask15UI(); } }');
  const suite = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import { configureTask15UI } from './Task15NativeUiBridge';\n" +
    "import { configureTask15Binding } from './Task15NativeUi';\n" +
    "import { runTask15Probe } from './Task15NativeUiSuite';\n" + originalSuite.replace(suiteEntry, suiteEntry +
      '\nconfigureTask15Binding(' + JSON.stringify(JSON.stringify(binding)) + ');\n' +
      'configureTask15UI(runTask15Probe, abilityDelegatorRegistry.getArguments().bundleName, ' + JSON.stringify(JSON.stringify(sources)) + ');\n');
  // Embed the dependency-free CJS adapter in an evaluator-owned ES module.
  // No runtime require and no edits to the shared adapterFactories are needed.
  const adapterFile = path.join(__dirname, 'Task15NativeUi.adapter.cjs');
  const adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const task15Module = { exports: {} };\n(function(module) {\n' + adapterSource +
    '\n})(task15Module);\nexport const runTask15Case = task15Module.exports.runCase;\n';
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(bytes) };
  });
  fs.writeFileSync(path.join(testRoot, 'Task15NativeUiAdapter.js'), adapter);
  fixtures.push({ file: adapterFile, sourceSha256: hash(adapterSource), installedPath: 'entry/src/test/Task15NativeUiAdapter.js', sha256: hash(adapter) });
  const caFile = process.env.TASK15_NATIVE_E2E_CA_DER;
  let e2e;
  if (caFile) {
    const resolvedCA = fs.realpathSync(caFile);
    const rawRoot = path.join(work, 'entry/src/ohosTest/resources/rawfile');
    fs.mkdirSync(rawRoot, { recursive: true });
    const installedCA = path.join(rawRoot, 'task15-ca.der');
    fs.copyFileSync(resolvedCA, installedCA);
    const moduleFile = path.join(work, 'entry/src/ohosTest/module.json5');
    const moduleConfig = json5.parse(fs.readFileSync(moduleFile, 'utf8'));
    const permissions = moduleConfig.module.requestPermissions || [];
    if (!permissions.some(item => item.name === 'ohos.permission.ACCESS_CERT_MANAGER')) {
      permissions.push({ name: 'ohos.permission.ACCESS_CERT_MANAGER' });
    }
    moduleConfig.module.requestPermissions = permissions;
    fs.writeFileSync(moduleFile, JSON.stringify(moduleConfig, null, 2) + '\n');
    e2e = { enabled: true, caSource: resolvedCA, caSha256: hash(fs.readFileSync(resolvedCA)),
      installedPath: path.relative(work, installedCA), testPermission: 'ohos.permission.ACCESS_CERT_MANAGER',
      securityScope: 'ohosTest only; production HAP manifest and transport are unchanged' };
  }
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed');
  return { schemaVersion: 1, productionUnchanged: true, production: after, binding, sources, fixtures, e2e,
    bundleFile, suiteFile, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle), beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    scope: 'Task15 first_submit_confirms plus optional evaluator-owned HTTPS E2E continuation; unchanged evaluateCase/persistRow; original page/client/store and pass-through observation only' };
}
module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
