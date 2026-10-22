'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = source => crypto.createHash('sha256').update(source).digest('hex');

// Run AFTER Tasks08_11NativeUi.install, on the disposable generated device
// evaluator only. Never install this transport in a Previewer bundle.
function install(work, options = {}) {
  const json5 = options.json5 || require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const read = relative => json5.parse(fs.readFileSync(path.join(work, relative), 'utf8'));
  const app = read('AppScope/app.json5').app;
  const module = read('entry/src/main/module.json5').module;
  const profile = /^\$profile:([A-Za-z0-9_]+)$/.exec(module.pages);
  if (!profile) throw new Error('Candidate pages profile is not bound');
  const routes = read('entry/src/main/resources/base/profile/' + profile[1] + '.json').src;
  const config = { bundleName: app.bundleName, abilityName: module.mainElement, moduleName: module.name,
    entryRoute: options.entryRoute || 'pages/Index', allowedRoutes: routes, timeoutMs: 10000 };
  if (!config.bundleName || !module.abilities.some(ability => ability.name === config.abilityName) ||
      !Array.isArray(routes) || !routes.includes(config.entryRoute)) throw new Error('Candidate entry identity/routes are not bound');
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  let bundle = fs.readFileSync(bundleFile, 'utf8');
  let suite = fs.readFileSync(suiteFile, 'utf8');
  if (bundle.includes('Tasks08_11DeviceUi')) throw new Error('Device UI transport already installed');
  if (!bundle.includes("from './native-device-platform'")) throw new Error('Device evaluator required, not Previewer');
  const observerImport = "import { installConfiguredRoomObserver } from './Tasks08_11RoomObserver';";
  const installObserver = 'bridge.roomUpgrade = installConfiguredRoomObserver();';
  const configureObserver = 'configureRoomObserver(Tasks08_11Presenter);';
  const configureImport = "import { configureRoomObserver } from './Tasks08_11RoomObserver';";
  const candidates = [ ['RoomUpgradeFeature', 'RoomUpgradePresenter'], ['RoomFeature', 'RoomPresenter'] ];
  const selected = candidates.filter(([feature, presenter]) => suite.includes(
    `import { ${presenter} as Tasks08_11Presenter } from '../main/ets/features/${feature}';`));
  if (selected.length !== 1) throw new Error('Generated observer class import is ambiguous or unavailable');
  const [feature, presenter] = selected[0];
  const classImport = `import { ${presenter} as Tasks08_11Presenter } from '../main/ets/features/${feature}';`;
  config.productionModuleUrl = '@bundle:' + config.bundleName + '/' + config.moduleName + '/ets/features/' + feature;
  config.presenterExport = presenter;
  config.originalModuleImportMode = options.originalModuleImportMode || process.env.TASKS08_11_ORIGINAL_MODULE_IMPORT || 'disabled';
  if (!['disabled', 'after-page-ready-diagnostic', 'after-page-ready'].includes(config.originalModuleImportMode))
    throw new Error('Only disabled, after-page-ready-diagnostic or after-page-ready original module import is supported; pre-start import caused ArkVM fatal');
  for (const [source, token] of [[bundle, observerImport], [bundle, installObserver],
    [suite, configureObserver], [suite, configureImport], [suite, classImport]]) {
    if (source.split(token).length !== 2) throw new Error('Install original-module observer first; generated hook changed: ' + token);
  }
  bundle = bundle.replace(observerImport, "import { augment } from './Tasks08_11DeviceUi';")
    .replace(installObserver, 'await augment(bridge);');
  suite = "import { configureDeviceUi } from './Tasks08_11DeviceUi';\n" + suite
    .replace(classImport, '').replace(configureImport, '')
    .replace(configureObserver, 'configureDeviceUi(' + JSON.stringify(config) + ');');
  const modules = ['Tasks08_11DeviceUi.js', 'Tasks08_11DeviceUi.d.ts', 'Tasks08_11DeviceUi.core.js', 'Tasks08_11DeviceUi.binding.js'];
  const sources = modules.map(name => ({ name, source: fs.readFileSync(path.join(__dirname, name)) }));
  for (const { name, source } of sources) fs.writeFileSync(path.join(testRoot, name), source);
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  return { config, bundleFile, suiteFile, bundleSha256: hash(bundle), suiteSha256: hash(suite),
    modules: sources.map(({ name, source }) => ({ path: path.join(testRoot, name), sha256: hash(source) })),
    lifecycle: 'monitor -> cold start -> original candidate page -> opt-in import -> observer -> real UI receiver capture -> canonical adapter validation for allowlisted cases only',
    limitations: 'Original app import is disabled by default. Opt-in after-page-ready supports only task11 cases005/007; diagnostic mode stays unscored. Cache miss may still be fatal. One cold process per case; setup capture is not a semantic verdict.' };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
