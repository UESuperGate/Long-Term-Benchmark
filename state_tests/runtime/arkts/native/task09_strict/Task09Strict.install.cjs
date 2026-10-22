'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const ownModules = ['Task09Input.js', 'Task09Suite.js', 'Task09Repository.js', 'Task09Adapter.js', 'Task09Device.js', 'Task09Device.d.ts'];
const borrowedModules = ['Task11Session.js', 'Task11Tree.js'];
const modules = [...ownModules, ...borrowedModules];

function productionFiles(work) {
  const files = [];
  const visit = directory => {
    for (const entry of fs.readdirSync(path.join(work, directory), { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const relative = directory + '/' + entry.name;
      if (entry.isSymbolicLink()) throw new Error('Task09 candidate symlinks unsupported');
      if (entry.isDirectory()) visit(relative);
      else if (entry.isFile()) files.push({ path: relative, sha256: hash(fs.readFileSync(path.join(work, relative))) });
    }
  };
  visit('entry/src/main');
  return files;
}

function install(work, requestedRole) {
  work = fs.realpathSync(work);
  const read = file => fs.readFileSync(path.join(work, file), 'utf8');
  const app = json5.parse(read('AppScope/app.json5')).app;
  const main = json5.parse(read('entry/src/main/module.json5')).module;
  const inferred = app.bundleName.endsWith('.base') ? 'base' : app.bundleName.endsWith('.final') ? 'final' : null;
  const role = requestedRole || inferred;
  if (!['base', 'final', 'agent'].includes(role) || main.name !== 'entry' ||
      !main.abilities.some(ability => ability.name === main.mainElement)) throw new Error('Task09 application identity required');
  if (requestedRole !== 'agent' && inferred !== role) throw new Error('Task09 requested role differs from immutable app identity');
  const profile = /^\$profile:(\w+)$/.exec(main.pages);
  if (!profile) throw new Error('Task09 original pages profile unavailable');
  const routes = json5.parse(read('entry/src/main/resources/base/profile/' + profile[1] + '.json')).src;
  const pagePath = 'entry/src/main/ets/pages/Index.ets';
  const before = productionFiles(work);
  const imports = file => {
    const parsed = ts.createSourceFile(file, read(file), ts.ScriptTarget.Latest, true);
    const result = {};
    for (const node of parsed.statements) if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const names = node.importClause?.namedBindings;
      if (names && ts.isNamedImports(names)) for (const item of names.elements)
        result[item.propertyName?.text || item.name.text] = path.posix.normalize(path.posix.join(path.posix.dirname(file), node.moduleSpecifier.text)) + '.ets';
    }
    return result;
  };
  const pageImports = imports(pagePath);
  const split = pageImports.SpacesPresenter;
  const featurePath = split || pageImports.SpacesGateway || pageImports.SpacesPresenter ||
    (before.some(item => item.path === 'entry/src/main/ets/features/SpacesFeature.ets') ?
      'entry/src/main/ets/features/SpacesFeature.ets' : 'entry/src/main/ets/features/HomeRoomsFeature.ets');
  // A role is a score label, not a description inferred from the bundle suffix.
  const productionVariant = split && split !== 'entry/src/main/ets/features/SpacesFeature.ets' ? 'repository' :
    featurePath.endsWith('/SpacesFeature.ets') ? 'spaces' : 'base';
  if (role === 'agent' && productionVariant === 'base' && Object.values(pageImports).some(file =>
    file.includes('/features/') && !file.endsWith('/HomeRoomsFeature.ets')))
    throw new Error('Task09 adapter_binding_incomplete: refusing a partial base projection of unbound page imports');
  const moduleUrl = file => '@bundle:' + app.bundleName + '/' + main.name + '/' + file.replace(/^entry\/src\/main\//, '').replace(/\.ets$/, '');
  const repositoryModules = {};
  if (productionVariant === 'repository') {
    const leavePath = 'entry/src/main/ets/pages/LeaveSpace.ets';
    if (!routes.includes('pages/LeaveSpace') || !before.some(item => item.path === leavePath))
      throw new Error('Task09 adapter_binding_incomplete: original leave route unavailable');
    const leaveImports = imports(leavePath);
    const modulePaths = { spaces: split, leave: leaveImports.LeaveSpacePresenter, registry: pageImports.SpaceServiceRegistry };
    for (const [key, file] of Object.entries(modulePaths)) {
      if (!file || !before.some(item => item.path === file))
        throw new Error('Task09 adapter_binding_incomplete: original ' + key + ' module unavailable');
      repositoryModules[key] = moduleUrl(file);
    }
  }
  const sources = productionVariant === 'repository' ? before : before.filter(item => [featurePath, pagePath].includes(item.path));
  if (sources.length < 2 || !routes.includes('pages/Index')) throw new Error('Task09 production feature/page binding unavailable');
  const config = { mode: 'after-page-ready-prefix', role, productionVariant, repositoryModules, bundleName: app.bundleName,
    moduleName: main.name, abilityName: main.mainElement, entryRoute: 'pages/Index', allowedRoutes: routes,
    productionModuleUrl: moduleUrl(featurePath),
    productionSourcePath: featurePath, productionSources: sources };
  const testRoot = path.join(work, 'entry/src/test');
  const bundlePath = path.join(testRoot, 'native-bundle.js');
  const suitePath = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundlePath, 'utf8');
  const originalSuite = fs.readFileSync(suitePath, 'utf8');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const run = 'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge,';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  const observation = "calls.push({ module: 'ArkUI', method: observation.method, nativeUI: true, observation: snapshot(observation) });";
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, run], [originalSuite, suiteEntry]])
    if (source.split(token).length !== 2) throw new Error('Generated Task09 lifecycle changed: ' + token);
  for (const name of modules) if (fs.existsSync(path.join(testRoot, name)))
    throw new Error('Refusing existing Task09 evaluator file: ' + name);
  const bundle = "import { attachTask09Strict } from './Task09Device';\n" + originalBundle
    .replace(navigate, 'const task09Strict = attachTask09Strict(bridge, taskId, caseSpec);\n    ' +
      'if (!task09Strict && candidateUI) await bridge.ui.navigate(candidateUI.route);')
    .replace(run, 'const adapter = { runCase: context => (bridge.evaluateTask09Strict || module.exports.runCase)({ ...context, native: bridge,');
  if (productionVariant === 'repository' && originalBundle.split(observation).length !== 2)
    throw new Error('Task09 native production provenance hook changed');
  const boundBundle = productionVariant === 'repository' ? bundle.replace(observation, observation +
    '\n      if (observation.available) for (const source of observation.productionSources || []) ' +
    'if (!evidence.some(item => item.path === source.path)) evidence.push(source);') : bundle;
  const suite = "import { configureTask09Strict } from './Task09Device';\n" + originalSuite
    .replace(suiteEntry, suiteEntry + '\nconfigureTask09Strict(' + JSON.stringify(JSON.stringify(config)) + ');\n');
  const fixtures = [];
  for (const name of ownModules) {
    const bytes = fs.readFileSync(path.join(__dirname, name));
    fs.writeFileSync(path.join(testRoot, name), bytes, { flag: 'wx' });
    fixtures.push({ path: 'entry/src/test/' + name, source: path.join(__dirname, name), sha256: hash(bytes) });
  }
  const task11 = path.resolve(__dirname, '../task11_strict');
  for (const name of borrowedModules) {
    const bytes = fs.readFileSync(path.join(task11, name));
    fs.writeFileSync(path.join(testRoot, name), bytes, { flag: 'wx' });
    fixtures.push({ path: 'entry/src/test/' + name, source: path.join(task11, name), sha256: hash(bytes) });
  }
  fs.writeFileSync(bundlePath, boundBundle);
  fs.writeFileSync(suitePath, suite);
  const after = productionFiles(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Task09 production changed during evaluator installation');
  return { schemaVersion: 1, role, config, productionUnchanged: true, production: after, fixtures,
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(boundBundle), beforeSuiteSha256: hash(originalSuite),
    suiteSha256: hash(suite), installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    scope: 'Task09 nine canonical cases; original ArkUI page/presenter/gateway with external hierarchy and join responses only' };
}

module.exports = { install, modules };
