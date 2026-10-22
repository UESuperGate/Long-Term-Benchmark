'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = source => crypto.createHash('sha256').update(source).digest('hex');
const modules = ['Task14DeviceUi.js', 'Task14DeviceUi.d.ts', 'Task14DeviceUi.core.js',
  'Task14DeviceUi.suite.js', 'Task14DeviceUi.adapter.js', 'Task14PageObserver.js', 'Task14AncestorObserver.js', 'Task14FrameAcquisition.js'];
modules.push('Task14RealFlowV2Observer.js', 'Task14RealFlowV2Frame.js',
  'Task14RealFlowV2.suite.js', 'Task14RealFlowV2.adapter.js');

function install(work, options = {}) {
  const json5 = options.json5 || require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const read = file => fs.readFileSync(path.join(work, file), 'utf8');
  const app = json5.parse(read('AppScope/app.json5')).app;
  const main = json5.parse(read('entry/src/main/module.json5')).module;
  const profile = /^\$profile:([\w]+)$/.exec(main.pages);
  if (!profile || !main.abilities.some(ability => ability.name === main.mainElement)) throw new Error('Original app entry metadata unavailable');
  const routes = json5.parse(read('entry/src/main/resources/base/profile/' + profile[1] + '.json')).src;
  const mode = options.mode || process.env.TASK14_ORIGINAL_MODULE_IMPORT || 'disabled';
  if (!['disabled', 'after-page-ready'].includes(mode)) throw new Error('Task14 supports only disabled or after-page-ready mode');
  const entryPage = 'entry/src/main/ets/pages/Index.ets';
  const page = read(entryPage);
  const apiBindings = require(path.join(__dirname, 'CandidateApiBindings.cjs'));
  const presenterClass = options.presenterClass || 'JoinRoomByAddressPresenter';
  if (typeof presenterClass !== 'string' || !/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(presenterClass)) {
    throw new Error('Invalid Task14 presenter class');
  }
  const api = apiBindings.exportedClass(work, presenterClass);
  if (!api.path.startsWith('entry/src/main/ets/features/')) throw new Error('Unbound presenter namespace');
  const feature = api.path.slice('entry/src/main/ets/features/'.length).replace(/\.(ets|ts)$/, '');
  const apiShape = api.parameters.length === 3 && api.methods.includes('isResolving') ? 'gatewayScheduler' : 'resolverNavigator';
  const prefix = '@bundle:' + app.bundleName + '/' + main.name + '/ets/features/';
  const realFlowFiles = ['ChatFeature', 'ChatRoutes', 'ChatRuntime'];
  const realFlowV2 = realFlowFiles.every(name => fs.existsSync(path.join(work,
    'entry/src/main/ets/features/' + name + '.ets'))) && page.includes("from '../components/StartChatView'") &&
    routes.includes('pages/CreateRoom') && routes.includes('pages/Room');
  const production = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(path.join(work, directory), { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const relative = directory + '/' + entry.name;
      if (entry.isSymbolicLink()) throw new Error('Candidate symlinks unsupported');
      if (entry.isDirectory()) visit(relative);
      else production.push({ path: relative, sha256: hash(fs.readFileSync(path.join(work, relative))) });
    }
  }
  visit('entry/src/main');
  const presenterSourcePath = feature && 'entry/src/main/ets/features/' + feature + '.ets';
  // Load-order discovery, not a semantic assertion. Indirect graph bindings
  // require a separately audited extension; never guess cache residency.
  const presenterLoadedByEntry = apiBindings.reaches(work, entryPage, api.path);
  const config = { mode, bundleName: app.bundleName, moduleName: main.name, abilityName: main.mainElement,
    entryRoute: 'pages/Index', allowedRoutes: routes, presenterSourcePath, presenterLoadedByEntry,
    addressRoute: routes.includes('pages/JoinRoomByAddress') ? 'pages/JoinRoomByAddress' : 'pages/Index',
    productionModuleUrl: feature && prefix + feature,
    peopleModuleUrl: page.includes("from '../features/CreateRoomBase'") &&
      fs.existsSync(path.join(work, 'entry/src/main/ets/features/CreateRoomBase.ets')) ? prefix + 'CreateRoomBase' : undefined,
    resolverModuleUrl: fs.existsSync(path.join(work, 'entry/src/main/ets/features/JoinRoomByAddress/HttpRoomAliasResolver.ets')) ?
      prefix + 'JoinRoomByAddress/HttpRoomAliasResolver' :
      page.includes("from '../features/JoinRoomRuntime'") &&
        fs.existsSync(path.join(work, 'entry/src/main/ets/features/JoinRoomRuntime.ets')) ?
        prefix + 'JoinRoomRuntime' : undefined,
    productionSources: production.filter(item => /\.(ets|ts)$/.test(item.path)), realFlowV2, apiShape,
    presenterClass,
    joinModuleUrl: feature && prefix + feature,
    chatFeatureModuleUrl: realFlowV2 ? prefix + 'ChatFeature' : undefined,
    chatRoutesModuleUrl: realFlowV2 ? prefix + 'ChatRoutes' : undefined,
    chatRuntimeModuleUrl: realFlowV2 ? prefix + 'ChatRuntime' : undefined,
    realFlowModuleUrls: realFlowV2 ? [feature && prefix + feature,
      prefix + 'ChatFeature', prefix + 'ChatRoutes', prefix + 'ChatRuntime'].filter(Boolean) : [] };
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8'), originalSuite = fs.readFileSync(suiteFile, 'utf8');
  if (!originalBundle.includes("from './native-device-platform'")) throw new Error('Task14 requires a device evaluator');
  if (originalBundle.includes('attachTask14DeviceUI')) throw new Error('Task14 already installed');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const run = 'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge,';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, run], [originalSuite, suiteEntry]])
    if (source.split(token).length !== 2) throw new Error('Generated device hook changed: ' + token);
  for (const name of modules) if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file ' + name);
  const bundle = "import { attachTask14DeviceUI } from './Task14DeviceUi';\n" + originalBundle
    .replace(navigate, 'const task14DeviceUI = attachTask14DeviceUI(bridge, taskId, caseSpec);\n    ' +
      'if (!task14DeviceUI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
    .replace(run, 'const adapter = { runCase: context => (bridge.evaluateTask14UI || module.exports.runCase)({ ...context, native: bridge,');
  const suite = "import { configureTask14DeviceUI } from './Task14DeviceUi';\n" + originalSuite.replace(suiteEntry,
    suiteEntry + '\nconfigureTask14DeviceUI(' + JSON.stringify(JSON.stringify(config)) + ');\n');
  const fixtures = modules.map(name => {
    const bytes = fs.readFileSync(path.join(__dirname, name));
    fs.writeFileSync(path.join(testRoot, name), bytes);
    return { path: 'entry/src/test/' + name, sha256: hash(bytes) };
  });
  fs.writeFileSync(bundleFile, bundle); fs.writeFileSync(suiteFile, suite);
  for (const source of production) if (hash(fs.readFileSync(path.join(work, source.path))) !== source.sha256) throw new Error('Candidate production changed');
  return { config, productionUnchanged: true, production, fixtures, bundleFile, suiteFile,
    bundleSha256: hash(bundle), suiteSha256: hash(suite),
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    scope: realFlowV2 ? 'Task14 real_flow_v2 case001 plus general device cases003/007. Original UI, presenter receiver, and rendered state.' :
      'Task14 cases001/003/007 only. Original cold page then explicit app import. No shared adapter or adapterFactory edit.' };
}
module.exports = { install };
