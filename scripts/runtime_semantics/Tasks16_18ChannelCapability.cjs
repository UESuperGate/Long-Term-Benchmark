#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { withTemporaryWorkspace } = require('./arkts_native_smoke.cjs');
const root = path.resolve(__dirname, '../..');
const studio = '/Applications/DevEco-Studio.app/Contents';
const json5 = require(studio + '/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const record = file => ({ path: file, bytes: fs.statSync(file).size, sha256: sha(fs.readFileSync(file)) });
const write = (file, data) => fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
const files = directory => fs.readdirSync(directory, { withFileTypes: true }).flatMap(item =>
  item.isDirectory() ? files(path.join(directory, item.name)) : [path.join(directory, item.name)]);

function probeTone() {
  const samples = 800, data = Buffer.alloc(44 + samples * 2);
  data.write('RIFF'); data.writeUInt32LE(data.length - 8, 4); data.write('WAVEfmt ', 8);
  data.writeUInt32LE(16, 16); data.writeUInt16LE(1, 20); data.writeUInt16LE(1, 22);
  data.writeUInt32LE(8000, 24); data.writeUInt32LE(16000, 28); data.writeUInt16LE(2, 32);
  data.writeUInt16LE(16, 34); data.write('data', 36); data.writeUInt32LE(samples * 2, 40);
  for (let i = 0; i < samples; i++) data.writeInt16LE(Math.round(Math.sin(2 * Math.PI * 440 * i / 8000) * 4000), 44 + i * 2);
  return data;
}

function install(work) {
  const tests = path.join(work, 'entry/src/ohosTest');
  fs.rmSync(tests, { recursive: true, force: true });
  fs.cpSync(path.join(root, 'elementx_harmony_full/entry/src/ohosTest'), tests, { recursive: true });
  const fixture = path.join(root, 'state_tests/runtime/arkts/native/Tasks16_18ChannelCapability.test.ets');
  const runner = path.join(root, 'state_tests/runtime/arkts/native/DeviceTestRunner.ets');
  fs.copyFileSync(fixture, path.join(tests, 'ets/test/Tasks16_18ChannelCapability.test.ets'));
  fs.copyFileSync(runner, path.join(tests, 'ets/testrunner/OpenHarmonyTestRunner.ets'));
  fs.writeFileSync(path.join(tests, 'ets/test/List.test.ets'),
    "import suite from './Tasks16_18ChannelCapability.test';\nexport default function testsuite(): void { suite(); }\n");
  const tone = path.join(work, 'entry/src/main/resources/rawfile/Tasks16_18Capability.wav');
  fs.mkdirSync(path.dirname(tone), { recursive: true });
  fs.writeFileSync(tone, probeTone());
  return { fixtures: [record(fixture), record(runner)], evaluatorAsset: record(tone),
    assetScope: '0.1 second generated PCM tone, SDK diagnostic only; not a production preset or selected sound' };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('Tasks16_18ChannelCapability.cjs --output-dir NEW_DIR [--prepare-only] [--signing-config JSON5 --signing-name NAME]\nBuild only, never operates device. Native run needs fresh install and -s ltbExecutionNonce <32hex>.');
    return;
  }
  const value = flag => { const i = args.indexOf(flag); if (i < 0 || !args[i + 1] || args[i + 1].startsWith('--')) throw new Error('Missing ' + flag); return args[i + 1]; };
  const output = path.resolve(value('--output-dir'));
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite existing evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });
  const source = path.join(root, 'final_dev_nodes/18_custom_notification_sounds_final_26_06_1');
  const production = files(path.join(source, 'entry/src/main')).map(record);
  const report = { schemaVersion: 1, taskId: '18_custom_notification_sounds', kind: 'standalone_sdk_capability',
    canonicalPromotionAllowed: false, nativeRuntimeExecuted: false, source, production,
    buildScript: record(__filename), commands: [], haps: [], runtimeCompile: { passed: false }, status: 'preparing' };
  const secrets = [];
  let signing;
  if (args.includes('--signing-config')) {
    const file = path.resolve(value('--signing-config')), config = json5.parse(fs.readFileSync(file, 'utf8'));
    const options = config.app?.signingConfigs || config.signingConfigs || [config];
    signing = args.includes('--signing-name') ? options.find(item => item.name === value('--signing-name')) : options.length === 1 ? options[0] : null;
    if (!signing?.name || !signing.material) throw new Error('Choose a named signing config');
    for (const name of ['storeFile', 'certpath', 'profile']) {
      signing.material[name] = path.resolve(path.dirname(file), signing.material[name]);
      if (!fs.existsSync(signing.material[name])) throw new Error('Missing signing material ' + name);
    }
    for (const [key, value] of Object.entries(signing.material)) if (/password|pwd/i.test(key) && value) secrets.push(value);
  }
  try {
    await withTemporaryWorkspace(async work => {
      report.work = work;
      fs.cpSync(source, work, { recursive: true, filter: file => !['.git', '.hvigor', 'build', 'oh_modules', 'node_modules'].includes(path.basename(file)) });
      fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work, 'oh_modules'), { recursive: true, verbatimSymlinks: true });
      fs.mkdirSync(path.join(work, 'node_modules/@ohos'), { recursive: true });
      for (const name of ['hvigor', 'hvigor-ohos-plugin']) fs.symlinkSync(path.join(studio, 'tools/hvigor', name), path.join(work, 'node_modules/@ohos', name));
      const sdk = path.join(os.homedir(), 'Library/OpenHarmony/Sdk');
      fs.writeFileSync(path.join(work, 'local.properties'), `sdk.dir=${sdk}\nhwsdk.dir=${studio}/sdk\n`);
      for (const relative of ['build-profile.json5', 'entry/build-profile.json5']) {
        const file = path.join(work, relative), config = json5.parse(fs.readFileSync(file, 'utf8'));
        if (config.app) {
          config.app.signingConfigs = signing ? [signing] : [];
          for (const product of config.app.products) {
            if (signing) product.signingConfig = signing.name; else delete product.signingConfig;
          }
        } else if (!config.targets.some(item => item.name === 'ohosTest')) config.targets.push({ name: 'ohosTest' });
        write(file, config);
      }
      report.installation = install(work);
      report.bundleName = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app.bundleName;
      report.deviceTestCommand = ['hdc', '-t', '<RESERVED_SERIAL>', 'shell', 'aa', 'test', '-b', report.bundleName,
        '-m', 'entry_test', '-s', 'unittest', 'OpenHarmonyTestRunner', '-s', 'ltbExecutionNonce', '<32_HEX_NONCE>', '-s', 'timeout', '60000', '-w', '90000'];
      if (args.includes('--prepare-only')) { report.status = 'prepared_only'; return; }
      for (const target of ['default', 'ohosTest']) {
        const cmd = [studio + '/tools/node/bin/node', studio + '/tools/hvigor/hvigor/bin/hvigor.js', 'assembleHap', '--mode', 'module',
          '-p', `module=entry@${target}`, '-p', 'product=default', '-p', 'buildMode=debug', '--no-daemon', '--no-parallel'];
        const result = spawnSync(cmd[0], cmd.slice(1), { cwd: work, timeout: 240000, maxBuffer: 8 * 1024 * 1024, encoding: 'utf8',
          env: { ...process.env, OHOS_SDK_HOME: sdk, DEVECO_SDK_HOME: studio + '/sdk', NODE_PATH: work + '/node_modules',
            JAVA_HOME: studio + '/jbr/Contents/Home', PATH: `${studio}/jbr/Contents/Home/bin:${studio}/tools/node/bin:${studio}/tools/ohpm/bin:${process.env.PATH}` } });
        const log = secrets.reduce((text, secret) => text.split(secret).join('[REDACTED]'), (result.stdout || '') + (result.stderr || ''));
        fs.writeFileSync(path.join(output, `build-${target}.log`), log);
        report.commands.push({ argv: cmd, exitCode: result.status, error: result.error?.message });
        if (result.error || result.status !== 0) throw new Error('Build failed: ' + target);
        if (Number(spawnSync('du', ['-sk', work], { encoding: 'utf8' }).stdout.split(/\s/)[0]) > 900 * 1024) throw new Error('900 MiB build budget exceeded');
      }
      for (const file of files(path.join(work, 'entry/build')).filter(file => file.endsWith('.hap'))) {
        const destination = path.join(output, path.basename(file));
        fs.copyFileSync(file, destination); report.haps.push(record(destination));
      }
      report.runtimeCompile.passed = report.haps.length >= 2;
      report.status = 'built_not_executed';
      report.copiedCandidateFilesUnchanged = production.every(item => sha(fs.readFileSync(path.join(work, path.relative(source, item.path)))) === item.sha256);
    });
  } catch (error) { report.status = 'blocked'; report.error = String(error); process.exitCode = 1; }
  finally {
    report.productionUnchanged = production.every(item => sha(fs.readFileSync(item.path)) === item.sha256);
    report.temporaryProjectRemoved = !!report.work && !fs.existsSync(report.work);
    write(path.join(output, 'capability-build.json'), report);
    console.log(JSON.stringify({ status: report.status, error: report.error, output, haps: report.haps }, null, 2));
  }
}

module.exports = { install, probeTone };
if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
