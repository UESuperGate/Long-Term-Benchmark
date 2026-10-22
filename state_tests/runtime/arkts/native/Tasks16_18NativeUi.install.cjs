'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function productionFiles(work) {
  const files = [];
  function visit(directory) {
    for (const item of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(directory, item.name);
      if (item.isSymbolicLink()) throw new Error('Candidate symlinks are unsupported by this isolated installer');
      if (item.isDirectory()) visit(file);
      else if (item.isFile()) files.push({ path: path.relative(work, file), sha256: digest(fs.readFileSync(file)) });
    }
  }
  visit(path.join(work, 'entry/src/main'));
  return files;
}

// Only generated evaluator files in a disposable project are edited. Call
// after bundle generation and before building; retain this return as evidence.
function install(work) {
  work = fs.realpathSync(work);
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8');
  const originalSuite = fs.readFileSync(suiteFile, 'utf8');
  if (!originalBundle.includes("from './native-device-platform'")) throw new Error('Tasks16_18 UI install requires a generated device bundle');
  if (originalBundle.includes('attachTasks16To18UI')) throw new Error('Tasks16_18 UI already installed');
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const dispose = 'try { await bridge.dispose(); }';
  const entry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, dispose], [originalSuite, entry]]) {
    if (source.split(token).length !== 2) throw new Error('Generated evaluator lifecycle changed: ' + token);
  }
  const fixtures = ['Tasks16_18TransitionsUI.test.ets', 'Tasks16_18NativeUi.js', 'Tasks16_18NativeUi.d.ts',
    'Tasks16_18ProviderEvidence.js', 'Tasks16_18ProviderEvidence.d.ts'];
  for (const name of fixtures) {
    if (fs.existsSync(path.join(testRoot, name))) throw new Error('Refusing existing fixture: ' + name);
  }
  const before = productionFiles(work);
  const candidates = ['NotificationSoundFeature', 'NotificationSettingsBase'];
  const moduleName = candidates.find(name => {
    const file = path.join(work, 'entry/src/main/ets/features', name + '.ets');
    return fs.existsSync(file) && /export class NotificationSettingsPresenter\b/.test(fs.readFileSync(file, 'utf8'));
  });
  const sourcePath = moduleName ? `entry/src/main/ets/features/${moduleName}.ets` : undefined;
  const presenterSource = sourcePath ? before.find(file => file.path === sourcePath) : null;
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const app = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app;
  const module = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module;
  if (!app.bundleName || !module.name || !module.abilities?.some(ability => ability.name === module.mainElement)) {
    throw new Error('Original app bundle/module/ability identity is unavailable');
  }
  const originalModule = { bundleName: app.bundleName, moduleName: module.name, abilityName: module.mainElement,
    feature: moduleName || null, presenterExport: 'NotificationSettingsPresenter',
    moduleUrl: moduleName ? `@bundle:${app.bundleName}/${module.name}/ets/features/${moduleName}` : null,
    importTiming: 'after-mounted-page-positive-controls-before-message-dialog' };
  const bundle = "import { attachTasks16To18UI } from './Tasks16_18NativeUi';\n" + originalBundle
    .replace(navigate, 'const tasks16To18UI = attachTasks16To18UI(bridge, taskId, caseSpec.key);\n    ' +
      'if (!tasks16To18UI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
    .replace(dispose, 'try { try { await bridge.dispose(); } finally { if (bridge.disposeTasks16To18UI) bridge.disposeTasks16To18UI(); } }');
  const imports = "import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\n" +
    "import Tasks16_18Picker from '@ohos.file.picker';\n" +
    "import { configureTasks16To18UI } from './Tasks16_18NativeUi';\n" +
    "import { probeTasks16To18Transition, Tasks16_18UIRequest } from './Tasks16_18TransitionsUI.test';\n";
  const configuration = '\nconfigureTasks16To18UI(async (requestJson: string): Promise<string> => {\n' +
    'const request = JSON.parse(requestJson) as Tasks16_18UIRequest;\n' +
    'request.emitChunks = false;\n' +
    'return JSON.stringify(await probeTasks16To18Transition(request));\n' +
    '}, abilityDelegatorRegistry.getArguments().bundleName, ' + JSON.stringify(JSON.stringify(originalModule)) +
    ', ' + JSON.stringify(JSON.stringify(presenterSource)) + ', Tasks16_18Picker.AudioViewPicker);\n';
  const suite = imports + originalSuite.replace(entry, entry + configuration);
  const fixtureEvidence = fixtures.map(name => {
    const file = path.join(__dirname, name);
    const bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: path.relative(work, path.join(testRoot, name)), sha256: digest(bytes) };
  });
  fs.writeFileSync(bundleFile, bundle);
  fs.writeFileSync(suiteFile, suite);
  const after = productionFiles(work);
  if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Candidate production files changed during evaluator installation');
  return { schemaVersion: 1, installer: { file: __filename, sha256: digest(fs.readFileSync(__filename)) },
    productionUnchanged: true, production: after, presenterSource, originalModule, fixtures: fixtureEvidence,
    bundleFile, suiteFile, beforeBundleSha256: digest(originalBundle), bundleSha256: digest(bundle),
    beforeSuiteSha256: digest(originalSuite), suiteSha256: digest(suite),
    pickerObserver: { api: '@ohos.file.picker.AudioViewPicker.prototype.select',
      mechanism: 'Native ArkTS export passed into JS observer; original call/Promise/context preserved; never awaited by probe.',
      sdkReference: 'https://github.com/openharmony/docs/blob/master/en/application-dev/reference/apis-core-file-kit/js-apis-file-picker.md',
      systemIdentityReference: 'https://github.com/openharmony/applications_filepicker/blob/5438caec93de79e5c7395887771d2e7a304bd861/AppScope/app.json5' },
    limitations: 'Device-only original-page UI; picker remains unscored without all GIVEN, actual launch effects and same-instance persistence evidence. No candidate source rewritten.' };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
