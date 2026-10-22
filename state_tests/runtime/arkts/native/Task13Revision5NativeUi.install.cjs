'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function production(work) {
  const result = [];
  const visit = directory => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error('Candidate symlink unsupported');
      if (entry.isDirectory()) visit(file);
      else if (entry.isFile()) result.push({ path: path.relative(work, file), sha256: hash(fs.readFileSync(file)) });
    }
  };
  visit(path.join(work, 'entry/src/main'));
  return result;
}

function install(work, pageBinding) {
  work = fs.realpathSync(work);
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8');
  const originalSuite = fs.readFileSync(suiteFile, 'utf8');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const dispatch = 'module.exports.runCase({ ...context, native: bridge,';
  const dispose = 'try { await bridge.dispose(); }';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispatch], [originalBundle, dispose], [originalSuite, suiteEntry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const before = production(work);
  const app = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app;
  const module = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module;
  const role = pageBinding?.observedBinding;
  const actualBinding = require('./Task13PageBinding.cjs').bind(work, role);
  if (JSON.stringify(actualBinding) !== JSON.stringify(pageBinding)) throw Error('Actual page import binding differs');
  if (!app.bundleName || module.name !== 'entry' || !role) throw new Error('Original Task13 project identity unavailable');
  const config = { bundleName: app.bundleName, moduleName: module.name, role,
    productionFeaturePath: pageBinding.productionFeaturePath, pageBinding,
    productionModuleUrl: `@bundle:${app.bundleName}/entry/${pageBinding.productionModuleSuffix}` };
  const sources = before;
  const bundle = "import { attachTask13Revision5UI } from './Task13Revision5NativeUiBridge';\n" +
    "import { runTask13Revision5Case } from './Task13Revision5NativeUiAdapter';\n" + originalBundle
      .replace(navigate, 'const task13Revision5UI = attachTask13Revision5UI(bridge, taskId);\n    if (!task13Revision5UI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
      .replace(dispatch, '(task13Revision5UI ? runTask13Revision5Case : module.exports.runCase)({ ...context, native: bridge,')
      .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask13Revision5UI) bridge.disposeTask13Revision5UI(); } }');
  const suite = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import { configureTask13InventoryValidator } from './Task13Revision5NativeUi';\n" +
    "import { validateTask13UiInventory } from './Task13UiClosure';\n" +
    "import { configureTask13Revision5UI } from './Task13Revision5NativeUiBridge';\n" +
    "import { configureTask13Revision5Binding } from './Task13Revision5NativeUi';\n" +
    "import { runTask13Revision5Probe } from './Task13Revision5NativeUiSuite';\n" + originalSuite.replace(suiteEntry, suiteEntry +
      '\nconfigureTask13Revision5Binding(' + JSON.stringify(JSON.stringify(config)) + ');\n' +
      'configureTask13InventoryValidator(validateTask13UiInventory);\n' +
      'configureTask13Revision5UI(runTask13Revision5Probe, ' + JSON.stringify(JSON.stringify(config)) + ', ' +
      JSON.stringify(JSON.stringify(sources)) + ');\n');
  const modules = ['Task13Revision5NativeUi.js', 'Task13Revision5NativeUi.d.ts',
    'Task13Revision5NativeUiSuite.ets', 'Task13Revision5NativeUiBridge.js',
    'Task13Revision5NativeUiBridge.d.ts', 'Task16Launch.js', 'Task13LaunchNative.js',
    'Task13LaunchNative.d.ts', 'Task13PageOwnerSdk.js'];
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(bytes) };
  });
  const adapterFile = path.join(__dirname, 'Task13Revision5NativeUi.adapter.cjs');
  const adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const task13Revision5Module = { exports: {} };\n(function(module) {\n' + adapterSource +
    '\n})(task13Revision5Module);\nexport const runTask13Revision5Case = task13Revision5Module.exports.runCase;\n';
  fs.writeFileSync(path.join(testRoot, 'Task13Revision5NativeUiAdapter.js'), adapter);
  const closureFile = path.join(__dirname, 'Task13UiClosure.cjs');
  const closureSource = fs.readFileSync(closureFile, 'utf8');
  const closureModule = 'const closure = { exports: {} };\n(function(module) {\n' + closureSource +
    '\n})(closure);\nexport function validateTask13UiInventory(json) { return JSON.stringify(closure.exports.validate(JSON.parse(json))); }\n';
  fs.writeFileSync(path.join(testRoot, 'Task13UiClosure.js'), closureModule);
  fs.writeFileSync(path.join(testRoot, 'Task13UiClosure.d.ts'), 'export function validateTask13UiInventory(json: string): string;\n');
  fixtures.push({ file: closureFile, sourceSha256: hash(closureSource),
    installedPath: 'entry/src/test/Task13UiClosure.js', sha256: hash(closureModule) });
  fixtures.push({ file: adapterFile, sourceSha256: hash(adapterSource),
    installedPath: 'entry/src/test/Task13Revision5NativeUiAdapter.js', sha256: hash(adapter) });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = production(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production source changed during Task13 evaluator installation');
  return { schemaVersion: 1, productionUnchanged: true, role, config, production: after, sources, fixtures,
    bundleFile, suiteFile, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle),
    beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    scope: 'Task13 staged revision5 only; original API23 profile UI and original production classes; no production edits' };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
