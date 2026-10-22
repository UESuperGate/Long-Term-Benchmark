'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function productionFiles(work) {
  const files = [];
  function visit(directory) {
    for (const item of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(directory, item.name);
      if (item.isSymbolicLink()) throw new Error('Candidate symlinks are unsupported');
      if (item.isDirectory()) visit(file);
      else if (item.isFile()) files.push({ path: path.relative(work, file), sha256: hash(fs.readFileSync(file)) });
    }
  }
  visit(path.join(work, 'entry/src/main'));
  return files;
}

function install(work) {
  work = fs.realpathSync(work);
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8');
  const originalSuite = fs.readFileSync(suiteFile, 'utf8');
  if (!originalBundle.includes("from './native-device-platform'")) throw new Error('Device evaluator required');
  if (originalBundle.includes('attachTasks12To15UI')) throw new Error('Tasks12_15 UI already installed');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const dispose = 'try { await bridge.dispose(); }';
  const entry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispose], [originalSuite, entry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const modules = ['Tasks12_15NativeUi.ets', 'Tasks12_15NativeUi.test.ets',
    'Tasks12_15ReportPageObserver.js', 'Tasks12_15ReportPageObserver.d.ts',
    'Tasks12_15NativeUiBridge.js', 'Tasks12_15NativeUiBridge.d.ts',
    'Tasks12_15NativeUi.binding.js', 'Tasks12_15NativeUi.binding.d.ts'];
  for (const name of modules) if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing evaluator file: ' + name);
  const before = productionFiles(work);
  const featurePath = 'entry/src/main/ets/features/ReportRoomFeature.ets';
  const pagePath = 'entry/src/main/ets/pages/Index.ets';
  const feature = before.find(item => item.path === featurePath);
  const page = before.find(item => item.path === pagePath);
  // Packaging/export discovery only, never semantic scoring or source rewriting.
  const hasPresenter = feature && /export class ReportRoomPresenter\b/.test(fs.readFileSync(path.join(work, featurePath), 'utf8'));
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  const moduleName = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module.name;
  if (!bundleName || moduleName !== 'entry') throw new Error('Task12 original module binding requires the candidate entry manifest');
  const binding = { bundleName, moduleName, productionModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/ReportRoomFeature',
    presenterExport: 'ReportRoomPresenter' };
  const sources = [page, hasPresenter ? feature : null].filter(Boolean);
  const bundle = "import { attachTasks12To15UI } from './Tasks12_15NativeUiBridge';\n" + originalBundle
    .replace(navigate, 'const tasks12To15UI = attachTasks12To15UI(bridge, taskId, caseSpec.key);\n    ' +
      'if (!tasks12To15UI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
    .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTasks12To15UI) bridge.disposeTasks12To15UI(); } }');
  const imports = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import { configureTasks12To15UI } from './Tasks12_15NativeUiBridge';\n" +
    "import { configureTasks12ReportPageBinding } from './Tasks12_15NativeUi.binding';\n" +
    "import { runTasks12To15NativeUi, NativeUiCase } from './Tasks12_15NativeUi.test';\n";
  const configuration = '\nconfigureTasks12ReportPageBinding(' + JSON.stringify(JSON.stringify(binding)) + ');\n' +
    'configureTasks12To15UI(async (caseJson: string, bundleName: string): Promise<string> => {\n' +
    'return JSON.stringify(await runTasks12To15NativeUi(JSON.parse(caseJson) as NativeUiCase, bundleName));\n' +
    '}, abilityDelegatorRegistry.getArguments().bundleName, ' + JSON.stringify(JSON.stringify(sources)) + ');\n';
  const suite = imports + originalSuite.replace(entry, entry + configuration);
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: hash(bytes) };
  });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = productionFiles(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Candidate production changed');
  return { schemaVersion: 1, installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    productionUnchanged: true, production: after, presenterSource: hasPresenter ? feature : null,
    pageSource: page || null, binding, fixtures, bundleFile, suiteFile,
    beforeBundleSha256: hash(originalBundle), bundleSha256: hash(bundle),
    beforeSuiteSha256: hash(originalSuite), suiteSha256: hash(suite),
    scope: 'Only task12 blank_reason_disabled; original same-module ArkTS presenter; existing evaluateCase and persistRow transport.' };
}
module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
