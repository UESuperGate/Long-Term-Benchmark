'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');

const sha = value => crypto.createHash('sha256').update(value).digest('hex');

function production(work) {
  const result = [];
  const root = path.join(work, 'entry/src/main');
  const visit = directory => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(file);
      else if (entry.isFile()) result.push({ path: path.relative(work, file), sha256: sha(fs.readFileSync(file)) });
    }
  };
  visit(root);
  return result.sort((a, b) => a.path.localeCompare(b.path));
}

function install(work) {
  work = fs.realpathSync(work);
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8');
  const originalSuite = fs.readFileSync(suiteFile, 'utf8');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const factory = "adapterFactories[group](module.exports, hostShim, module);";
  const dispatch = 'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge,';
  const dispose = 'try { await bridge.dispose(); }';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, factory], [originalBundle, dispatch],
    [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const before = production(work);
  const app = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app;
  const module = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module;
  const pagePath = 'entry/src/main/ets/pages/Index.ets';
  const parsedPage = ts.createSourceFile(pagePath, fs.readFileSync(path.join(work, pagePath), 'utf8'), ts.ScriptTarget.Latest, true);
  const imports = {};
  for (const node of parsedPage.statements) if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
    const names = node.importClause?.namedBindings;
    if (names && ts.isNamedImports(names)) for (const item of names.elements)
      imports[item.propertyName?.text || item.name.text] = path.posix.normalize(path.posix.join(path.posix.dirname(pagePath), node.moduleSpecifier.text)) + '.ets';
  }
  const timeline = imports.ThreadTimelinePresenter && imports.RoomTimelinePresenter;
  const finalFeature = 'entry/src/main/ets/features/ThreadFeature.ets';
  const baseFeature = 'entry/src/main/ets/features/RoomTimelineFeature.ets';
  const productionVariant = timeline ? 'timeline' : fs.existsSync(path.join(work, finalFeature)) ? 'final' :
    fs.existsSync(path.join(work, baseFeature)) ? 'base' : null;
  if (!app.bundleName || module.name !== 'entry' || !productionVariant) {
    throw new Error('Original Task08 project identity unavailable');
  }
  const role = process.env.LTB_TASK08_ROLE || productionVariant;
  if (!['base', 'final', 'agent'].includes(role)) throw new Error('Invalid Task08 requested role');
  const feature = productionVariant === 'final' ? 'ThreadFeature' : 'RoomTimelineFeature';
  if (role === 'agent' && !timeline) {
    const page = path.join(work, 'entry/src/main/ets/pages/Index.ets');
    const parsed = ts.createSourceFile(page, fs.readFileSync(page, 'utf8'), ts.ScriptTarget.Latest, true);
    const unbound = parsed.statements.filter(node => ts.isImportDeclaration(node) &&
      ts.isStringLiteral(node.moduleSpecifier)).map(node => node.moduleSpecifier.text)
      .filter(name => name.startsWith('../features/') && name !== '../features/' + feature);
    if (unbound.length) {
      throw new Error('Task08 adapter_binding_incomplete: original page imports unbound production modules ' +
        JSON.stringify(unbound) + '; refusing to score them through the ' + productionVariant + ' probe');
    }
  }
  const moduleUrl = file => '@bundle:' + app.bundleName + '/entry/' + file.replace(/^entry\/src\/main\//, '').replace(/\.ets$/, '');
  const config = { bundleName: app.bundleName, moduleName: module.name, role, productionVariant,
    timelineModuleUrl: timeline ? moduleUrl(imports.ThreadTimelinePresenter) : null,
    roomModuleUrl: timeline ? moduleUrl(imports.RoomTimelinePresenter) : null,
    productionModuleUrl: `@bundle:${app.bundleName}/entry/ets/features/${feature}` };
  const sourcePaths = timeline ? [imports.ThreadTimelinePresenter, imports.RoomTimelinePresenter, pagePath] :
    [productionVariant === 'final' ? finalFeature : baseFeature, pagePath];
  const sources = before.filter(item => sourcePaths.includes(item.path));
  if (sources.length !== sourcePaths.length) throw new Error('Task08 scored production sources unavailable');

  let bundle = "import { attachTask08StrictUI } from './Task08StrictNativeUiBridge';\n" +
    "import { runTask08StrictCase } from './Task08StrictNativeUiAdapter';\n" + originalBundle
      .replace(factory, factory + '\n  const task08SharedRunCase = module.exports.runCase;')
      .replace(navigate, 'const task08StrictUI = attachTask08StrictUI(bridge, taskId);\n    if (!task08StrictUI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
      .replace(dispatch, 'const adapter = { runCase: context => (task08StrictUI ? runTask08StrictCase : module.exports.runCase)({ ...context, native: bridge, sharedRunCase: task08SharedRunCase,')
      .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask08StrictUI) bridge.disposeTask08StrictUI(); } }');
  {
    const receipt = "calls.push({ module: 'ArkUI', method: observation.method, nativeUI: true, observation: snapshot(observation) });";
    if (bundle.split(receipt).length !== 2) throw new Error('Task08 native provenance hook changed');
    bundle = bundle.replace(receipt, receipt + '\n      if (observation.available) for (const source of observation.productionSources || []) ' +
      'if (!evidence.some(item => item.path === source.path)) evidence.push(source);');
  }
  const suite = "import { configureTask08StrictUI } from './Task08StrictNativeUiBridge';\n" +
    "import { configureTask08StrictBinding } from './Task08StrictNativeUi';\n" +
    "import { runTask08StrictProbe } from './Task08StrictNativeUiSuite';\n" + originalSuite.replace(suiteEntry, suiteEntry +
      '\nconfigureTask08StrictBinding(' + JSON.stringify(JSON.stringify(config)) + ');\n' +
      'configureTask08StrictUI(runTask08StrictProbe, ' + JSON.stringify(JSON.stringify(config)) + ', ' +
      JSON.stringify(JSON.stringify(sources)) + ');\n');
  const sourceRoot = __dirname;
  const modules = ['Task08StrictNativeUi.js', 'Task08StrictNativeUi.d.ts',
    'Task08StrictNativeUiSuite.ets', 'Task08StrictNativeUiBridge.js',
    'Task08StrictNativeUiBridge.d.ts', 'Task08StrictNativeUiAdapter.js', 'Task08TimelineUI.js',
    'Task08LaunchNative.js', 'Task08LaunchNative.d.ts'];
  const fixtures = modules.map(name => {
    const file = path.join(sourceRoot, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: sha(bytes) };
  });
  for (const name of ['Task16Launch.js']) {
    const file = path.join(sourceRoot, '..', name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    fixtures.push({ file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: sha(bytes) });
  }
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed during Task08 evaluator installation');
  return { schemaVersion: 1, productionUnchanged: true, role, productionVariant, config,
    production: after, sources, fixtures, bundleFile, suiteFile,
    installer: { file: __filename, sha256: sha(fs.readFileSync(__filename)) },
    beforeBundleSha256: sha(originalBundle), bundleSha256: sha(bundle),
    beforeSuiteSha256: sha(originalSuite), suiteSha256: sha(suite),
    scope: 'Task08 only; original API23 application UI and original production classes; shared evaluator semantics' };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
