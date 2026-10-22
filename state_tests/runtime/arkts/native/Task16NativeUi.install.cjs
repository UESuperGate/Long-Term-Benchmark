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
  if (originalBundle.includes('attachTask16UI')) throw new Error('Task16 native UI already installed');
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispatch], [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const modules = ['Task16PageObserver.js', 'Task16NativeUi.js', 'Task16NativeUi.d.ts', 'Task16NativeUiSuite.ets',
    'Task16NativeUiBridge.js', 'Task16NativeUiBridge.d.ts', 'Task16Launch.js', 'Task16LaunchNative.js', 'Task16LaunchNative.d.ts'];
  for (const name of [...modules, 'Task16NativeUiAdapter.js']) {
    if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file: ' + name);
  }
  const before = production(work);
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  const moduleName = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module.name;
  if (!bundleName || moduleName !== 'entry') throw new Error('Original entry manifest required');
  const binding = { bundleName, moduleName, productionModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/IdentityResetFeature' };
  const sources = before.filter(item => ['entry/src/main/ets/pages/Index.ets',
    'entry/src/main/ets/features/IdentityResetFeature.ets',
    'entry/src/main/ets/features/SecureBackupBase.ets'].includes(item.path));
  const bundle = "import { attachTask16UI } from './Task16NativeUiBridge';\n" +
    "import { runTask16Case } from './Task16NativeUiAdapter';\n" + originalBundle
      .replace(navigate, 'const task16UI = attachTask16UI(bridge, taskId, caseSpec.key);\n    if (!task16UI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
      .replace(dispatch, '(task16UI ? runTask16Case : module.exports.runCase)({ ...context, native: bridge,')
      .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask16UI) bridge.disposeTask16UI(); } }');
  const suite = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import { configureTask16UI } from './Task16NativeUiBridge';\n" +
    "import { configureTask16Binding } from './Task16NativeUi';\n" +
    "import { runTask16Probe } from './Task16NativeUiSuite';\n" + originalSuite.replace(suiteEntry, suiteEntry +
      '\nconfigureTask16Binding(' + JSON.stringify(JSON.stringify(binding)) + ');\n' +
      'configureTask16UI(runTask16Probe, abilityDelegatorRegistry.getArguments().bundleName, ' + JSON.stringify(JSON.stringify(sources)) + ');\n');
  // Embed the dependency-free CJS adapter in an evaluator-owned ES module.
  // No runtime require and no edits to the shared adapterFactories are needed.
  const adapterFile = path.join(__dirname, 'Task16NativeUi.adapter.cjs');
  const adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const task16Module = { exports: {} };\n(function(module) {\n' + adapterSource +
    '\n})(task16Module);\nexport const runTask16Case = task16Module.exports.runCase;\n';
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(bytes) };
  });
  fs.writeFileSync(path.join(testRoot, 'Task16NativeUiAdapter.js'), adapter);
  fixtures.push({ file: adapterFile, sourceSha256: hash(adapterSource), installedPath: 'entry/src/test/Task16NativeUiAdapter.js', sha256: hash(adapter) });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed');
  return { schemaVersion: 1, productionUnchanged: true, production: after, binding, sources, fixtures,
    bundleFile, suiteFile, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle), beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    scope: 'All staged Task16 revision-5 cases; unchanged evaluateCase/persistRow; actual original presenter/service and API23 ArkUI' };
}
module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
