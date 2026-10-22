'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function production(work) {
  const result = [];
  const visit = directory => {
    for (const item of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(directory, item.name);
      if (item.isSymbolicLink()) throw new Error('Candidate symlink unsupported');
      if (item.isDirectory()) visit(file);
      else result.push({ path: path.relative(work, file), sha256: hash(fs.readFileSync(file)) });
    }
  };
  visit(path.join(work, 'entry/src/main'));
  return result;
}

function install(work, evaluatorRole) {
  work = fs.realpathSync(work);
  if (!['base', 'final', 'agent'].includes(evaluatorRole)) throw new Error('Explicit Task17 evaluator role required');
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8');
  const originalSuite = fs.readFileSync(suiteFile, 'utf8');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const dispatch = 'module.exports.runCase({ ...context, native: bridge,';
  const dispose = 'try { await bridge.dispose(); }';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  if (!originalBundle.includes("from './native-device-platform'")) throw new Error('Native device bundle required');
  if (originalBundle.includes('attachTask17StrictUI')) throw new Error('Task17 strict native UI already installed');
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispatch],
    [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }

  const modules = [
    'Task17StrictNativeSdk.js', 'Task17StrictNativeSdk.d.ts',
    'Task17StrictNativeUi.js', 'Task17StrictNativeUi.d.ts', 'Task17StrictNativeUiSuite.ets',
    'Task17StrictNativeUiBridge.js', 'Task17StrictNativeUiBridge.d.ts',
    'Task17LoadingUi.js', 'Task17LoadingUi.d.ts',
    'Task17LoadingObserver.js', 'Task17LoadingFrames.js', 'Task17LoadingReadback.js',
    'Task17LoadingLaunch.js', 'Task17LoadingLaunchNative.js', 'Task17LoadingLaunchNative.d.ts'
  ];
  for (const name of [...modules, 'Task17StrictNativeUiAdapter.js']) {
    if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file: ' + name);
  }
  const before = production(work);
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  const moduleName = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module.name;
  const finalFeature = path.join(work, 'entry/src/main/ets/features/PinnedMessagesFeature.ets');
  const baseFeature = path.join(work, 'entry/src/main/ets/features/PinnedMessagesBase.ets');
  if (!bundleName || moduleName !== 'entry') throw new Error('Invalid Task17 application identity');
  if (evaluatorRole === 'base' && !fs.existsSync(baseFeature)) throw new Error('Calibrated Task17 base feature missing');
  if (evaluatorRole === 'final' && !fs.existsSync(finalFeature)) throw new Error('Calibrated Task17 final feature missing');
  const binding = { bundleName, moduleName,
    productionModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/PinnedMessagesFeature',
    evaluatorRole, behaviorClassification: 'runtime_ui_entry' };
  const sourcePaths = ['entry/src/main/ets/pages/Index.ets'];
  if (fs.existsSync(finalFeature)) sourcePaths.push('entry/src/main/ets/features/PinnedMessagesFeature.ets');
  if (fs.existsSync(baseFeature)) sourcePaths.push('entry/src/main/ets/features/PinnedMessagesBase.ets');
  const sources = before.filter(item => sourcePaths.includes(item.path));
  if (!sources.some(item => item.path === 'entry/src/main/ets/pages/Index.ets')) {
    throw new Error('Task17 production page provenance incomplete');
  }

  const bundle = "import { attachTask17StrictUI } from './Task17StrictNativeUiBridge';\n" +
    "import { runTask17StrictCase } from './Task17StrictNativeUiAdapter';\n" + originalBundle
      .replace(navigate, 'const task17StrictUI = attachTask17StrictUI(bridge, taskId, caseSpec.key);\n    if (!task17StrictUI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
      .replace(dispatch, '(task17StrictUI ? runTask17StrictCase : module.exports.runCase)({ ...context, native: bridge,')
      .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask17StrictUI) bridge.disposeTask17StrictUI(); } }');
  const suite = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import { configureTask17StrictUI } from './Task17StrictNativeUiBridge';\n" +
    "import { configureTask17StrictBinding } from './Task17StrictNativeUi';\n" +
    "import { runTask17StrictProbe } from './Task17StrictNativeUiSuite';\n" + originalSuite.replace(suiteEntry, suiteEntry +
      '\nconfigureTask17StrictBinding(' + JSON.stringify(JSON.stringify(binding)) + ');\n' +
      'configureTask17StrictUI(runTask17StrictProbe, abilityDelegatorRegistry.getArguments().bundleName, ' +
      JSON.stringify(JSON.stringify(sources)) + ');\n');

  const adapterFile = path.join(__dirname, 'Task17StrictNativeUi.adapter.cjs');
  const adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const task17StrictModule = { exports: {} };\n(function(module) {\n' + adapterSource +
    '\n})(task17StrictModule);\nexport const runTask17StrictCase = task17StrictModule.exports.runCase;\n';
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name);
    const bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(bytes) };
  });
  fs.writeFileSync(path.join(testRoot, 'Task17StrictNativeUiAdapter.js'), adapter);
  fixtures.push({ file: adapterFile, sourceSha256: hash(adapterSource),
    installedPath: 'entry/src/test/Task17StrictNativeUiAdapter.js', sha256: hash(adapter) });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed');
  return { schemaVersion: 1, productionUnchanged: true, production: after, binding, sources, fixtures,
    bundleFile, suiteFile, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle),
    beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    scope: 'All nine Task17 canonical cases; actual base/final entry, original installed feature module, ArkVM, UiTest and native Preferences.' };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2]), process.argv[3]), null, 2));
