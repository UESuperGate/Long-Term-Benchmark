'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function production(work) {
  const rows = [];
  const visit = directory => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(file);
      else if (entry.isFile()) rows.push({ path: path.relative(work, file), sha256: hash(fs.readFileSync(file)) });
    }
  };
  visit(path.join(work, 'entry/src/main'));
  return rows;
}

function install(work, evaluatorRole) {
  work = fs.realpathSync(work);
  if (!['base', 'final', 'agent'].includes(evaluatorRole)) throw new Error('Explicit Task16 evaluator role required');
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8');
  const originalSuite = fs.readFileSync(suiteFile, 'utf8');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const dispatch = 'module.exports.runCase({ ...context, native: bridge,';
  const dispose = 'try { await bridge.dispose(); }';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispatch],
    [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const before = production(work);
  const adapterFile = path.resolve(__dirname, '../Task16Revision5.adapter.cjs');
  const adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const revision5Module = { exports: {} };\n(function(module) {\n' + adapterSource +
    '\n})(revision5Module);\nexport const runTask16Revision5 = revision5Module.exports.runCase;\n';
  fs.writeFileSync(path.join(testRoot, 'Task16Revision5Adapter.js'), adapter);

  let bundlePrefix = "import { runTask16Revision5 } from './Task16Revision5Adapter';\n";
  let suitePrefix = '';
  let suiteConfiguration = '';
  const fixtures = [{ file: adapterFile, sourceSha256: hash(adapterSource),
    installedPath: 'entry/src/test/Task16Revision5Adapter.js', sha256: hash(adapter) }];
  let attach;
  const installFinal = evaluatorRole !== 'base';
  const installBase = evaluatorRole !== 'final';
  if (installFinal) {
    const modules = ['Task16PageObserver.js', 'Task16NativeUi.js', 'Task16NativeUi.d.ts', 'Task16NativeUiSuite.ets',
      'Task16NativeUiBridge.js', 'Task16NativeUiBridge.d.ts', 'Task16Launch.js', 'Task16LaunchNative.js', 'Task16LaunchNative.d.ts'];
    for (const name of modules) {
      const file = path.join(__dirname, name);
      fs.copyFileSync(file, path.join(testRoot, name));
      fixtures.push({ file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(fs.readFileSync(file)) });
    }
    const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
    const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
    const binding = { bundleName, moduleName: 'entry',
      productionModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/IdentityResetFeature' };
    const sources = before.filter(item => ['entry/src/main/ets/pages/Index.ets',
      'entry/src/main/ets/features/IdentityResetFeature.ets'].includes(item.path));
    bundlePrefix = "import { attachTask16UI } from './Task16NativeUiBridge';\n" + bundlePrefix;
    attach = "const task16Revision5UI = ['oidc_handle_routes_and_resets', 'cancel_cleans_up'].includes(caseSpec.key) && attachTask16UI(bridge, taskId, caseSpec.key);";
    suitePrefix = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
      "import { configureTask16UI } from './Task16NativeUiBridge';\n" +
      "import { configureTask16Binding } from './Task16NativeUi';\n" +
      "import { runTask16Probe } from './Task16NativeUiSuite';\n";
    suiteConfiguration = '\nconfigureTask16Binding(' + JSON.stringify(JSON.stringify(binding)) + ');\n' +
      'configureTask16UI(runTask16Probe, abilityDelegatorRegistry.getArguments().bundleName, ' +
      JSON.stringify(JSON.stringify(sources)) + ');\n';
  }
  if (installBase) {
    const modules = ['Task16BaseEntry.js', 'Task16BaseEntry.d.ts', 'Task16BaseEntrySuite.ets',
      'Task16BaseEntryBridge.js', 'Task16BaseEntryBridge.d.ts', 'Task16Launch.js',
      'Task16LaunchNative.js', 'Task16LaunchNative.d.ts'];
    for (const name of modules) {
      const file = path.join(__dirname, name);
      fs.copyFileSync(file, path.join(testRoot, name));
      fixtures.push({ file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(fs.readFileSync(file)) });
    }
    bundlePrefix = "import { attachTask16BaseEntry } from './Task16BaseEntryBridge';\n" + bundlePrefix;
    const baseAttach = 'const task16Revision5BaseUI = attachTask16BaseEntry(bridge, taskId);';
    attach = attach ? baseAttach + '\n    ' + attach : baseAttach;
    suitePrefix = (suitePrefix.includes("abilityDelegatorRegistry") ? '' :
      "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n") +
      "import { configureTask16BaseEntry } from './Task16BaseEntryBridge';\n" +
      "import { releaseTask16Launch } from './Task16LaunchNative';\n" +
      "import { probeTask16BaseEntry, probeTask16CandidateEntry } from './Task16BaseEntrySuite';\n" + suitePrefix;
    const probe = evaluatorRole === 'agent' ? 'probeTask16CandidateEntry' : 'probeTask16BaseEntry';
    const entrySources = before.filter(item => item.path === 'entry/src/main/ets/pages/Index.ets' ||
      ['IdentityResetFeature.ets', 'SecureBackupBase.ets'].some(name => item.path.endsWith('/' + name)));
    suiteConfiguration += '\nconfigureTask16BaseEntry(' + probe + ', abilityDelegatorRegistry.getArguments().bundleName, ' +
      JSON.stringify(JSON.stringify(entrySources)) + ', releaseTask16Launch);\n';
  }
  const bundle = bundlePrefix + originalBundle
    .replace(navigate, attach)
    .replace(dispatch, 'runTask16Revision5({ ...context, evaluatorRole: ' + JSON.stringify(evaluatorRole) + ', native: bridge,')
    .replace(dispose, 'try { try { await bridge.dispose(); } finally { ' +
      'if (bridge.disposeTask16UI) bridge.disposeTask16UI(); ' +
      'if (bridge.disposeTask16BaseUI) await bridge.disposeTask16BaseUI(); } }');
  const suite = suitePrefix + originalSuite.replace(suiteEntry, suiteEntry + suiteConfiguration);
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed during evaluator install');
  return {
    schemaVersion: 1,
    revision: 5,
    evaluatorRole,
    behaviorClassification: 'runtime_entry_only_for_agent',
    productionUnchanged: true,
    production: after,
    fixtures,
    beforeBundleSha256: hash(originalBundle),
    bundleSha256: hash(bundle),
    beforeSuiteSha256: hash(originalSuite),
    suiteSha256: hash(suite),
    scope: 'Task16 revision5 only; native ArkVM production transitions, actual candidate page, and original-page OIDC/cancel probes'
  };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2]), process.argv[3]), null, 2));
