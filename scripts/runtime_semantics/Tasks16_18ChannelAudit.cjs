#!/usr/bin/env node
'use strict';
// Capture only immutable primary sources and local declarations, no device or scores.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const docs61 = 'b25734f4ed9e4e7ae5f003671fe8c6b42ecdbc16';
const docsMaster = 'f41b9345badd47c7ab0c263344cd7f4b5a549afb';
const service61 = '7e95a65e629c2e173005491fa261a587ced8afa5';
const remote = [
  ['docs', docs61, 'zh-cn/application-dev/reference/apis-notification-kit/js-apis-inner-notification-notificationRequest.md'],
  ['docs', docs61, 'zh-cn/application-dev/reference/apis-backgroundtasks-kit/js-apis-reminderAgentManager.md'],
  ['docs', docsMaster, 'zh-cn/application-dev/notification/notification-customized-ringtone.md'],
  ['notification_distributed_notification_service', service61, 'services/ans/src/advanced_notification_slot_service.cpp'],
  ['notification_distributed_notification_service', service61, 'services/ans/src/advanced_notification_service.cpp'],
  ['notification_distributed_notification_service', service61, 'frameworks/js/napi/src/slot.cpp'],
  ['notification_distributed_notification_service', service61, 'services/ans/src/advanced_notification_ringtone_service.cpp']
];

async function main() {
  const output = path.join(root, 'experiment_results/runtime_transition_20261020/task18_repair/capability-sources');
  fs.mkdirSync(output, { recursive: true });
  const inventory = [];
  const save = (relative, bytes, origin) => {
    const file = path.join(output, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    if (fs.existsSync(file) && sha(fs.readFileSync(file)) !== sha(bytes)) throw new Error('Pinned evidence differs: ' + relative);
    if (!fs.existsSync(file)) fs.writeFileSync(file, bytes);
    inventory.push({ path: relative, bytes: bytes.length, sha256: sha(bytes), ...origin });
  };
  for (const name of ['@ohos.notificationManager.d.ts', '@ohos.reminderAgentManager.d.ts', 'notification/notificationRequest.d.ts', 'notification/notificationSlot.d.ts', 'notification/notificationFlags.d.ts']) {
    const file = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/ets/api', name);
    save('sdk23/' + name, fs.readFileSync(file), { localPath: file });
  }
  const sdkVersion = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/ets/oh-uni-package.json');
  save('sdk23/oh-uni-package.json', fs.readFileSync(sdkVersion), { localPath: sdkVersion });
  for (const [repo, commit, file] of remote) {
    const url = `https://raw.githubusercontent.com/openharmony/${repo}/${commit}/${file}`;
    const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error(`${response.status}: ${url}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length > 1024 * 1024) throw new Error('Primary source exceeds 1 MiB budget');
    save(repo + '/' + commit + '/' + path.basename(file), bytes, { url, commit, repositoryPath: file });
  }
  const manifest = { schemaVersion: 1, generatedAt: new Date().toISOString(), nativeRuntimeExecuted: false,
    limitations: 'Open-source 6.1 service is architectural evidence, not proof of the installed vendor binary. No device result or canonical promotion.',
    inventory };
  const manifestFile = path.join(output, 'manifest.json');
  if (fs.existsSync(manifestFile)) {
    const previous = JSON.parse(fs.readFileSync(manifestFile));
    if (JSON.stringify(previous.inventory) !== JSON.stringify(inventory)) throw new Error('Pinned inventory differs');
  } else {
    fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, files: inventory.length, totalBytes: inventory.reduce((n, item) => n + item.bytes, 0) }));
}
if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
