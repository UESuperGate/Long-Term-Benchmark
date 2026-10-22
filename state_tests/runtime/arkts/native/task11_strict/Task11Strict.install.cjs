'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const modules = ['Task11Input.js', 'Task11Session.js', 'Task11Tree.js', 'Task11Frame.js',
  'Task11Suite.js', 'Task11Adapter.js', 'Task11Device.js', 'Task11Device.d.ts'];

function productionFiles(work) {
  const files = [];
  const visit = directory => {
    for (const entry of fs.readdirSync(path.join(work, directory), { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const relative = directory + '/' + entry.name;
      if (entry.isSymbolicLink()) throw new Error('Task11 candidate symlinks unsupported');
      if (entry.isDirectory()) visit(relative);
      else if (entry.isFile()) files.push({ path: relative, sha256: hash(fs.readFileSync(path.join(work, relative))) });
    }
  };
  visit('entry/src/main');
  return files;
}

function install(work, options = {}) {
  work = fs.realpathSync(work);
  const read = file => fs.readFileSync(path.join(work, file), 'utf8');
  const app = json5.parse(read('AppScope/app.json5')).app;
  const main = json5.parse(read('entry/src/main/module.json5')).module;
  const role = options.role;
  const apiVariant = options.apiVariant;
  if (!['base', 'final', 'agent'].includes(role) || !['base', 'final', 'auto'].includes(apiVariant) ||
      main.name !== 'entry' || !main.abilities.some(ability => ability.name === main.mainElement))
    throw new Error('Task11 explicit role, API variant and application identity are required');
  const profile = /^\$profile:(\w+)$/.exec(main.pages);
  if (!profile) throw new Error('Task11 original pages profile unavailable');
  const routes = json5.parse(read('entry/src/main/resources/base/profile/' + profile[1] + '.json')).src;
  const pagePath = 'entry/src/main/ets/pages/Index.ets';
  const pageImports = [...read(pagePath).matchAll(/from\s+['"]\.\.\/features\/([^'"]+)['"]/g)];
  if (apiVariant === 'auto' && pageImports.length !== 1) throw new Error('Original page feature import is ambiguous');
  const feature = apiVariant === 'auto' ? pageImports[0][1] : apiVariant === 'base' ? 'RoomFeature' : 'RoomUpgradeFeature';
  const featurePath = 'entry/src/main/ets/features/' + feature + '.ets';
  const before = productionFiles(work);
  const sources = before.filter(item => [featurePath, pagePath].includes(item.path));
  if (sources.length !== 2 || !routes.includes('pages/Index')) throw new Error('Task11 production feature/page binding unavailable');
  const config = { mode: 'after-page-ready-prefix', role, apiVariant, bundleName: app.bundleName,
    moduleName: main.name, abilityName: main.mainElement, entryRoute: 'pages/Index', allowedRoutes: routes,
    productionModuleUrl: '@bundle:' + app.bundleName + '/' + main.name + '/ets/features/' + feature,
    productionSources: sources };
  const testRoot = path.join(work, 'entry/src/test');
  const bundlePath = path.join(testRoot, 'native-bundle.js');
  const suitePath = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundlePath, 'utf8');
  const originalSuite = fs.readFileSync(suitePath, 'utf8');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const run = 'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge,';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  if (!originalBundle.includes("from './native-device-platform'")) throw new Error('Task11 strict requires device evaluator');
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, run], [originalSuite, suiteEntry]])
    if (source.split(token).length !== 2) throw new Error('Generated Task11 lifecycle changed: ' + token);
  for (const name of modules) if (fs.existsSync(path.join(testRoot, name)))
    throw new Error('Refusing existing Task11 evaluator file: ' + name);
  const bundle = "import { attachTask11Strict } from './Task11Device';\n" + originalBundle
    .replace(navigate, 'const task11Strict = attachTask11Strict(bridge, taskId, caseSpec);\n    ' +
      'if (!task11Strict && candidateUI) await bridge.ui.navigate(candidateUI.route);')
    .replace(run, 'const adapter = { runCase: context => (bridge.evaluateTask11Strict || module.exports.runCase)({ ...context, native: bridge,');
  const suite = "import { configureTask11Strict } from './Task11Device';\n" + originalSuite
    .replace(suiteEntry, suiteEntry + '\nconfigureTask11Strict(' + JSON.stringify(JSON.stringify(config)) + ');\n');
  const fixtures = modules.map(name => {
    const bytes = fs.readFileSync(path.join(__dirname, name));
    fs.writeFileSync(path.join(testRoot, name), bytes, { flag: 'wx' });
    return { path: 'entry/src/test/' + name, sha256: hash(bytes) };
  });
  fs.writeFileSync(bundlePath, bundle);
  fs.writeFileSync(suitePath, suite);
  const after = productionFiles(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Task11 production changed during evaluator installation');
  return { schemaVersion: 1, role, apiVariant, config, productionUnchanged: true, production: after, fixtures,
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle),
    beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    scope: 'Task11 six canonical cases; original ArkUI page, original presenter/gateway, external room-info input only' };
}

module.exports = { install, modules };
