'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function productionFiles(work) {
  const result = [];
  function visit(dir) {
    for (const item of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(dir, item.name);
      if (item.isSymbolicLink()) throw new Error('Candidate symlinks unsupported');
      if (item.isDirectory()) visit(file);
      else if (item.isFile()) result.push({ path: path.relative(work, file), sha256: hash(fs.readFileSync(file)) });
    }
  }
  visit(path.join(work, 'entry/src/main'));
  return result;
}

function install(work) {
  work = fs.realpathSync(work);
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js'), suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8'), originalSuite = fs.readFileSync(suiteFile, 'utf8');
  if (!originalBundle.includes("from './native-device-platform'")) throw new Error('Original device bundle required');
  if (originalBundle.includes('attachTask13UI')) throw new Error('Task13 UI already installed');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const dispose = 'try { await bridge.dispose(); }';
  const entry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispose], [originalSuite, entry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const names = ['Task13NativeUi.js', 'Task13NativeUi.d.ts', 'Task13UiTest.ets'];
  for (const name of names) if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file: ' + name);
  const before = productionFiles(work);
  const app = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app;
  const module = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module;
  if (!app.bundleName || !module.name || !module.abilities?.some(a => a.name === module.mainElement)) throw new Error('Original app identity unavailable');
  const feature = 'entry/src/main/ets/features/UserVerificationFeature.ets', page = 'entry/src/main/ets/pages/Index.ets';
  const config = { bundleName: app.bundleName, moduleName: module.name, abilityName: module.mainElement,
    moduleUrl: `@bundle:${app.bundleName}/${module.name}/ets/features/UserVerificationFeature`,
    sources: before.filter(item => [feature, page].includes(item.path)) };
  const bundle = "import { attachTask13UI } from './Task13NativeUi';\n" + originalBundle
    .replace(navigate, 'const task13UI = attachTask13UI(bridge, taskId, caseSpec.key);\n    if (!task13UI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
    .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTask13UI) bridge.disposeTask13UI(); } }');
  const imports = "import { configureTask13UI } from './Task13NativeUi';\n" +
    "import { runTask13UI, Task13Case, Task13Config } from './Task13UiTest';\n";
  const configuration = '\nconfigureTask13UI(async (caseJson: string, configJson: string): Promise<string> => {\n' +
    'return runTask13UI(JSON.parse(caseJson) as Task13Case, JSON.parse(configJson) as Task13Config);\n' +
    '}, ' + JSON.stringify(JSON.stringify(config)) + ');\n';
  const suite = imports + originalSuite.replace(entry, entry + configuration);
  const fixtures = names.map(name => {
    const file = path.join(__dirname, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, sha256: hash(bytes), installedPath: path.relative(work, path.join(testRoot, name)) };
  });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = productionFiles(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Production changed during evaluator installation');
  return { schemaVersion: 1, productionUnchanged: true, production: after, config, fixtures, bundleFile, suiteFile,
    installerSha256: hash(fs.readFileSync(__filename)), beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle),
    beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    integrationRequired: 'Parent must add tasks12_15 early branch returning args.native.evaluateTask13UI(args). No fourth CJS factory or independent scorer.',
    scope: 'Original profile UI call diagnostics; unresolved canonical navigation/non-self GIVEN remain NS.' };
}
module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
