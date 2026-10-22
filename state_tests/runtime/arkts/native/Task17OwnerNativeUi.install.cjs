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
  if (!['base', 'final', 'agent'].includes(evaluatorRole)) throw new Error('Explicit Task17 owner-bound role required');
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
  if (originalBundle.includes('attachTask17OwnerUI')) throw new Error('Task17 owner-bound UI already installed');
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispatch],
    [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }

  const modules = [
    'Task17OwnerNativeSdk.js', 'Task17OwnerNativeSdk.d.ts',
    'Task17OwnerNativeUi.js', 'Task17OwnerNativeUi.d.ts', 'Task17OwnerNativeUiSuite.ets',
    'Task17OwnerNativeUiBridge.js', 'Task17OwnerNativeUiBridge.d.ts',
    'Task17OwnerLaunch.js', 'Task17OwnerLaunchNative.js', 'Task17OwnerLaunchNative.d.ts'
  ];
  for (const name of [...modules, 'Task17OwnerNativeUiAdapter.js']) {
    if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file: ' + name);
  }
  const before = production(work);
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  const moduleName = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module.name;
  const matrixFeature = path.join(work, 'entry/src/main/ets/features/MatrixRoomServices.ets');
  const finalFeature = path.join(work, 'entry/src/main/ets/features/PinnedMessagesFeature.ets');
  const page = path.join(work, 'entry/src/main/ets/pages/Index.ets');
  if (!bundleName || moduleName !== 'entry' || !fs.existsSync(matrixFeature) || !fs.existsSync(page)) {
    throw new Error('Task17 owner-bound production entry/room port missing');
  }
  if (evaluatorRole === 'final' && !fs.existsSync(finalFeature)) throw new Error('Task17 final feature missing');
  const feature = evaluatorRole === 'final' ? 'PinnedMessagesFeature' : 'MatrixRoomServices';
  const binding = { bundleName, moduleName, evaluatorRole,
    roomModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/' + feature,
    sessionModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/' +
      (evaluatorRole === 'agent' ? 'PinnedMessagesSession' : feature),
    timelineModuleUrl: evaluatorRole === 'agent' ?
      '@bundle:' + bundleName + '/entry/ets/features/RoomTimeline' : null,
    bannerModuleUrl: evaluatorRole === 'agent' ?
      '@bundle:' + bundleName + '/entry/ets/features/PinnedMessagesBase' : null,
    sessionExport: evaluatorRole === 'final' ? 'PinnedMessagesSession' : 'RoomSession',
    resetSharedSession: evaluatorRole === 'agent',
    behaviorClassification: 'runtime_candidate_page_owner_and_room_port' };
  const sourcePaths = ['entry/src/main/ets/pages/Index.ets',
    'entry/src/main/ets/features/MatrixRoomServices.ets'];
  if (fs.existsSync(finalFeature)) sourcePaths.push('entry/src/main/ets/features/PinnedMessagesFeature.ets');
  const sources = before.filter(item => sourcePaths.includes(item.path));
  if (!sources.some(item => item.path === 'entry/src/main/ets/pages/Index.ets') ||
      !sources.some(item => item.path === 'entry/src/main/ets/features/MatrixRoomServices.ets')) {
    throw new Error('Task17 owner-bound source provenance incomplete');
  }

  const bundle = "import { attachTask17OwnerUI } from './Task17OwnerNativeUiBridge';\n" +
    "import { runTask17OwnerCase } from './Task17OwnerNativeUiAdapter';\n" + originalBundle
      .replace(navigate, 'const task17OwnerUI = attachTask17OwnerUI(bridge, taskId, caseSpec.key);\n    if (!task17OwnerUI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
      .replace(dispatch, '(task17OwnerUI ? runTask17OwnerCase : module.exports.runCase)({ ...context, native: bridge,')
      .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask17OwnerUI) bridge.disposeTask17OwnerUI(); } }');
  const suite = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import { configureTask17OwnerUI } from './Task17OwnerNativeUiBridge';\n" +
    "import { configureTask17OwnerBinding } from './Task17OwnerNativeUi';\n" +
    "import { runTask17OwnerProbe } from './Task17OwnerNativeUiSuite';\n" + originalSuite.replace(suiteEntry, suiteEntry +
      '\nconfigureTask17OwnerBinding(' + JSON.stringify(JSON.stringify(binding)) + ');\n' +
      'configureTask17OwnerUI(runTask17OwnerProbe, abilityDelegatorRegistry.getArguments().bundleName, ' +
      JSON.stringify(JSON.stringify(sources)) + ');\n');

  const adapterFile = path.join(__dirname, 'Task17OwnerNativeUi.adapter.cjs');
  const adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const task17OwnerModule = { exports: {} };\n(function(module) {\n' + adapterSource +
    '\n})(task17OwnerModule);\nexport const runTask17OwnerCase = task17OwnerModule.exports.runCase;\n';
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name);
    const bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(bytes) };
  });
  fs.writeFileSync(path.join(testRoot, 'Task17OwnerNativeUiAdapter.js'), adapter);
  fixtures.push({ file: adapterFile, sourceSha256: hash(adapterSource),
    installedPath: 'entry/src/test/Task17OwnerNativeUiAdapter.js', sha256: hash(adapter) });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed');
  return { schemaVersion: 1, productionUnchanged: true, production: after, binding, sources, fixtures,
    bundleFile, suiteFile, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle),
    beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    scope: 'All nine Task17 cases through the installed page owner and evaluator-owned Matrix room port.' };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2]), process.argv[3]), null, 2));
