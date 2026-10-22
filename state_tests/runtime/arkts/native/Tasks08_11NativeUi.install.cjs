'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

// Apply only to a freshly GENERATED evaluator bundle in a disposable workspace.
// Candidate .ets files and the shared runner remain byte-for-byte unchanged.
function install(work) {
  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  let bundle = fs.readFileSync(bundleFile, 'utf8');
  if (bundle.includes('Tasks08_11RoomObserver')) throw new Error('Observer is already installed');
  const featureRoot = path.join(work, 'entry/src/main/ets/features');
  const moduleName = fs.existsSync(path.join(featureRoot, 'RoomUpgradeFeature.ets')) ? 'RoomUpgradeFeature' : 'RoomFeature';
  const sourceFile = path.join(featureRoot, moduleName + '.ets');
  const source = fs.readFileSync(sourceFile, 'utf8');
  const className = moduleName === 'RoomUpgradeFeature' ? 'RoomUpgradePresenter' : 'RoomPresenter';
  if (!new RegExp(`export class ${className}\\b`).test(source)) throw new Error('No supported room presenter export');
  const begin = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const end = 'try { await bridge.dispose(); }';
  for (const token of [begin, end]) if (bundle.split(token).length !== 2) throw new Error('Generated runner lifecycle changed: ' + token);
  bundle = "import { installConfiguredRoomObserver } from './Tasks08_11RoomObserver';\n" + bundle;
  bundle = bundle.replace(begin,
    'bridge.roomUpgrade = installConfiguredRoomObserver();\n    ' + begin);
  bundle = bundle.replace(end,
    'try { try { await bridge.dispose(); } finally { if (bridge.roomUpgrade) bridge.roomUpgrade.dispose(); } }');
  for (const extension of ['js', 'd.ts']) fs.copyFileSync(path.join(__dirname, 'Tasks08_11RoomObserver.' + extension),
    path.join(testRoot, 'Tasks08_11RoomObserver.' + extension));
  // ArkTS may import JS, but JS cannot import .ets. Pass the genuine class from
  // the generated ArkTS test entry, before any candidate page is constructed.
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const suite = fs.readFileSync(suiteFile, 'utf8');
  const entry = 'export default function nativeBundleTests(): void {';
  if (suite.split(entry).length !== 2) throw new Error('Generated ArkTS test entry changed');
  fs.writeFileSync(suiteFile,
    `import { ${className} as Tasks08_11Presenter } from '../main/ets/features/${moduleName}';\n` +
    "import { configureRoomObserver } from './Tasks08_11RoomObserver';\n" +
    suite.replace(entry, entry + '\nconfigureRoomObserver(Tasks08_11Presenter);'));
  fs.writeFileSync(bundleFile, bundle);
  return { sourceFile, sourceSha256: crypto.createHash('sha256').update(source).digest('hex'),
    fixture: 'Tasks08_11RoomObserver.js', bundleFile, suiteFile,
    bundleSha256: crypto.createHash('sha256').update(bundle).digest('hex'),
    limitations: 'Read-only same-module presenter instrumentation; real candidate page mounting and UI events still required.' };
}

module.exports = { install };
if (require.main === module) console.log(JSON.stringify(install(path.resolve(process.argv[2])), null, 2));
