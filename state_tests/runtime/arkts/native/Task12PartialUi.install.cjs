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
  if (originalBundle.includes('attachTask12PartialUI')) throw new Error('Task12 partial native UI already installed');
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispatch], [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const modules = ['Task12PartialObserver.js', 'Task12PartialUi.js', 'Task12PartialUi.d.ts', 'Task12PartialUiSuite.ets',
    'Task12PartialUiBridge.js', 'Task12PartialUiBridge.d.ts', 'Task12PartialLaunch.js', 'Task12PartialLaunchNative.js', 'Task12PartialLaunchNative.d.ts'];
  for (const name of [...modules, 'Task12PartialUiAdapter.js']) {
    if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file: ' + name);
  }
  const before = production(work);
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  const moduleName = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module.name;
  if (!bundleName || moduleName !== 'entry') throw new Error('Original entry manifest required');
  const binding = { bundleName, moduleName, productionModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/ReportRoomFeature' };
  const sources = before.filter(item => ['entry/src/main/ets/pages/Index.ets', 'entry/src/main/ets/features/ReportRoomFeature.ets'].includes(item.path));
  const bundle = "import { attachTask12PartialUI } from './Task12PartialUiBridge';\n" +
    "import { runTask12PartialCase } from './Task12PartialUiAdapter';\n" + originalBundle
      .replace(navigate, 'const task12PartialUI = attachTask12PartialUI(bridge, taskId, caseSpec.key);\n    if (!task12PartialUI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
      .replace(dispatch, '(task12PartialUI ? runTask12PartialCase : module.exports.runCase)({ ...context, native: bridge,')
      .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask12PartialUI) bridge.disposeTask12PartialUI(); } }');
  const suite = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import { configureTask12PartialUI } from './Task12PartialUiBridge';\n" +
    "import { configureTask12Partial } from './Task12PartialUi';\n" +
    "import { runTask12PartialProbe } from './Task12PartialUiSuite';\n" + originalSuite.replace(suiteEntry, suiteEntry +
      '\nconfigureTask12Partial(' + JSON.stringify(JSON.stringify(binding)) + ');\n' +
      'configureTask12PartialUI(runTask12PartialProbe, abilityDelegatorRegistry.getArguments().bundleName, ' + JSON.stringify(JSON.stringify(sources)) + ');\n');
  // Embed the dependency-free CJS adapter in an evaluator-owned ES module.
  // No runtime require and no edits to the shared adapterFactories are needed.
  const adapterFile = path.join(__dirname, 'Task12PartialUi.adapter.cjs');
  const adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const task12PartialModule = { exports: {} };\n(function(module) {\n' + adapterSource +
    '\n})(task12PartialModule);\nexport const runTask12PartialCase = task12PartialModule.exports.runCase;\n';
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(bytes) };
  });
  fs.writeFileSync(path.join(testRoot, 'Task12PartialUiAdapter.js'), adapter);
  fixtures.push({ file: adapterFile, sourceSha256: hash(adapterSource), installedPath: 'entry/src/test/Task12PartialUiAdapter.js', sha256: hash(adapter) });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed');
  return { schemaVersion: 1, productionUnchanged: true, production: after, binding, sources, fixtures,
    bundleFile, suiteFile, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle), beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    scope: 'Task12 partial leave_failure_is_partial only; unchanged evaluateCase/persistRow; actual original presenter/service and UI' };
}
module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
