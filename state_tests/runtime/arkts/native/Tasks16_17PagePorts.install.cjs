'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function inventory(root, directory = path.join(root, 'entry/src/main')) {
  return fs.readdirSync(directory, { withFileTypes: true }).sort((a,b) => a.name.localeCompare(b.name)).flatMap(item => {
    const file = path.join(directory, item.name);
    if (item.isSymbolicLink()) throw new Error('Unbound input symlink');
    return item.isDirectory() ? inventory(root, file) : [{ path: path.relative(root, file), sha256: hash(fs.readFileSync(file)) }];
  });
}
function install(work) {
  const testRoot = path.join(work, 'entry/src/test'), before = inventory(work);
  const bundleFile = path.join(testRoot, 'native-bundle.js'), suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = fs.readFileSync(bundleFile, 'utf8'), originalSuite = fs.readFileSync(suiteFile, 'utf8');
  const taskMatch = originalBundle.match(/(?:const |let )taskId\s*=\s*["']([^"']+)["']/);
  // Task is supplied by the derived builder, never inferred from candidate name/ref.
  const taskId = process.env.LTB_PAGE_PORTS_TASK;
  if (!['16_identity_reset', '17_pinned_messages'].includes(taskId)) throw new Error('Explicit page port task required');
  const bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
  const config = { taskId, bundleName, productionSources: before,
    productionModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/' +
      (taskId === '16_identity_reset' ? 'IdentityResetFeature' : 'PinnedMessagesFeature'),
    serviceModuleUrl: '@bundle:' + bundleName + '/entry/ets/features/IdentityResetServices' };
  const tokens = ["if (candidateUI) await bridge.ui.navigate(candidateUI.route);",
    'module.exports.runCase({ ...context, native: bridge,'];
  for (const token of tokens) if (originalBundle.split(token).length !== 2) throw new Error('Unbound native bundle lifecycle');
  const modules = ['Tasks16_17SdkBoundary.js', 'Tasks16_17PhysicalPrefix.js', 'Task16Case003DomainInvariant.js', 'Tasks16_17PagePortsUi.js', 'Tasks16_17PagePortsUi.d.ts',
    'Tasks16_17PagePortsBridge.js', 'Tasks16_17PagePortsBridge.d.ts', 'Tasks16_17PagePortsSuite.ets',
    'Task17LoadingLaunch.js', 'Task17LoadingLaunchNative.js', 'Task17LoadingLaunchNative.d.ts'];
  const fixtures = modules.map(name => {
    const file = path.join(__dirname, name), bytes = fs.readFileSync(file);
    fs.copyFileSync(file, path.join(testRoot, name));
    return { file, installedPath: 'entry/src/test/' + name, sha256: hash(bytes) };
  });
  const adapterFile = path.join(__dirname, 'Tasks16_17PagePorts.adapter.cjs'), adapterSource = fs.readFileSync(adapterFile, 'utf8');
  const adapter = 'const ownedPageModule = { exports: {} };\n(function(module){\n' + adapterSource +
    '\n})(ownedPageModule); export const runPagePortsCase = ownedPageModule.exports.runCase;\n';
  fs.writeFileSync(path.join(testRoot, 'Tasks16_17PagePortsAdapter.js'), adapter);
  fixtures.push({ file: adapterFile, sourceSha256: hash(adapterSource), sha256: hash(adapter),
    installedPath: 'entry/src/test/Tasks16_17PagePortsAdapter.js' });
  fs.writeFileSync(bundleFile, "import { attachPagePortsProbe } from './Tasks16_17PagePortsBridge';\n" +
    "import { runPagePortsCase } from './Tasks16_17PagePortsAdapter';\n" + originalBundle
      .replace(tokens[0], 'attachPagePortsProbe(bridge);')
      .replace(tokens[1], 'runPagePortsCase({ ...context, native: bridge,'));
  const entry = 'export default function nativeBundleTests(): void {';
  if (originalSuite.split(entry).length !== 2) throw new Error('Unbound native suite lifecycle');
  fs.writeFileSync(suiteFile, "import { configurePagePortsBinding } from './Tasks16_17PagePortsUi';\n" +
    "import { configurePagePortsProbe } from './Tasks16_17PagePortsBridge';\n" +
    "import { runPagePortsProbe } from './Tasks16_17PagePortsSuite';\n" + originalSuite.replace(entry,
      entry + '\nconfigurePagePortsBinding(' + JSON.stringify(JSON.stringify(config)) + ');\n' +
      'configurePagePortsProbe(runPagePortsProbe, ' + JSON.stringify(bundleName) + ');\n'));
  if (JSON.stringify(before) !== JSON.stringify(inventory(work))) throw new Error('Production modified by evaluator');
  return { schemaVersion: 1, productionUnchanged: true, production: before, fixtures, binding: config,
    integrationTier: 'actual_page_controlled_external_sdk', liveMatrixSdkOrServerVerified: false,
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}
module.exports = { install };
