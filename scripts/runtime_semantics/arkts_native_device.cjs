#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { withTemporaryWorkspace } = require('./arkts_native_smoke.cjs');
const root = path.resolve(__dirname, '../..');
const studio = '/Applications/DevEco-Studio.app/Contents';
const sdk = path.join(os.homedir(), 'Library/OpenHarmony/Sdk');
const json5 = require(path.join(studio, 'tools/hvigor/hvigor-ohos-plugin/node_modules/json5'));
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const read = file => json5.parse(fs.readFileSync(file, 'utf8'));
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');

function files(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const name = path.join(directory, entry.name);
    return entry.isDirectory() ? files(name) : entry.isFile() ? [name] : [];
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('arkts_native_device.cjs --source CANDIDATE --task TASK --fixture 12_15|16_18|bundle|context_probe|copy_probe --output-dir DIR [--role ROLE --case CASE_ID] [--native-ui] [--signing-config JSON5] [--signing-name NAME] [--prepare-only]');
    return;
  }
  const value = flag => {
    const index = args.indexOf(flag);
    if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
    return args[index + 1];
  };
  const source = path.resolve(value('--source'));
  const taskId = value('--task');
  const fixture = value('--fixture');
  if (!['12_15', '16_18', 'bundle', 'context_probe', 'copy_probe'].includes(fixture)) throw new Error('Unsupported fixture');
  const role = fixture === 'bundle' ? value('--role') : null;
  const caseId = fixture === 'bundle' ? value('--case') : null;
  const nativeUI = args.includes('--native-ui');
  if (nativeUI && fixture !== 'bundle') throw new Error('--native-ui requires bundle fixture');
  const output = path.resolve(value('--output-dir'));
  let signing;
  const secrets = [];
  if (args.includes('--signing-config')) {
    const configFile = path.resolve(value('--signing-config'));
    const config = read(configFile);
    const configs = config.app?.signingConfigs || config.signingConfigs || [config];
    const name = args.includes('--signing-name') ? value('--signing-name') : null;
    if (!name && configs.length !== 1) throw new Error('Choose one --signing-name');
    signing = name ? configs.find(item => item.name === name) : configs[0];
    if (!signing?.name || !signing.material) throw new Error('Expected a named Hvigor signing configuration with material');
    for (const field of ['storeFile', 'certpath', 'profile']) {
      if (typeof signing.material[field] !== 'string') throw new Error('Signing material lacks ' + field);
      signing.material[field] = path.resolve(path.dirname(configFile), signing.material[field]);
      if (!fs.existsSync(signing.material[field])) throw new Error('Signing material file missing: ' + field);
    }
    for (const [key, secret] of Object.entries(signing.material)) {
      if (/password|pwd/i.test(key) && typeof secret === 'string' && secret) secrets.push(secret);
    }
  }
  const redact = text => secrets.reduce((text, secret) => text.split(secret).join('[REDACTED]'), text);
  fs.mkdirSync(output, { recursive: true });
  const provenance = files(path.join(source, 'entry/src/main')).map(file => ({ path: path.relative(source, file), sha256: hash(file) }));
  const report = { schemaVersion: 1, taskId, role, source, fixture, nativeRuntimeExecuted: false,
    status: 'prepared', compile: { passed: null, scope: 'canonical app compile not scored by fixture packaging' },
    runtimeCompile: { passed: null, scope: 'isolated candidate and device ohosTest HAP packaging' },
    production: provenance, commands: [], haps: [], signing: signing ?
      'configured local signature; device acceptance unverified' : 'unsigned; device acceptance unverified' };
  const reportPath = path.join(output, 'device-build-report.json');
  try {
    await withTemporaryWorkspace(async work => {
      report.work = work;
      fs.cpSync(source, work, { recursive: true, filter: name =>
        !['build', '.hvigor', 'oh_modules', 'node_modules', '.git'].includes(path.basename(name)) });
      fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work, 'oh_modules'), { recursive: true, verbatimSymlinks: true });
      fs.mkdirSync(path.join(work, 'node_modules/@ohos'), { recursive: true });
      for (const name of ['hvigor', 'hvigor-ohos-plugin']) fs.symlinkSync(path.join(studio, 'tools/hvigor', name), path.join(work, 'node_modules/@ohos', name));
      fs.writeFileSync(path.join(work, 'local.properties'), `sdk.dir=${sdk}\nhwsdk.dir=${studio}/sdk\n`);
      const profileFile = path.join(work, 'build-profile.json5');
      const profile = read(profileFile);
      profile.app.signingConfigs = signing ? [signing] : [];
      for (const product of profile.app.products) {
        if (signing) product.signingConfig = signing.name;
        else delete product.signingConfig;
      }
      write(profileFile, profile);
      const moduleFile = path.join(work, 'entry/build-profile.json5');
      const moduleProfile = read(moduleFile);
      if (!moduleProfile.targets.some(item => item.name === 'ohosTest')) moduleProfile.targets.push({ name: 'ohosTest' });
      write(moduleFile, moduleProfile);
      const tests = path.join(work, 'entry/src/ohosTest');
      fs.rmSync(tests, { recursive: true, force: true });
      fs.cpSync(path.join(root, 'elementx_harmony_full/entry/src/ohosTest'), tests, { recursive: true });
      const runnerFile = path.join(root, 'state_tests/runtime/arkts/native/DeviceTestRunner.ets');
      fs.copyFileSync(runnerFile, path.join(tests, 'ets/testrunner/OpenHarmonyTestRunner.ets'));
      report.harness = { path: runnerFile, sha256: hash(runnerFile),
        entry: 'TestRunner.onRun -> Hypium.hypiumTest',
        completionOwner: 'Hypium; transport completion is not a semantic verdict' };
      const fixtureNames = fixture === 'bundle' ? [] : fixture === 'copy_probe' ? ['DeviceCopyProbe.test.ets', 'Tasks16_18CopyTransport.test.ets'] : fixture === 'context_probe' ? ['DeviceContextProbe.test.ets'] : fixture === '12_15' ? ['Tasks12_15NativeUi.ets', 'Tasks12_15NativeUi.test.ets'] : ['Tasks16_18EntryUI.test.ets'];
      report.fixtures = fixtureNames.map(name => {
        const file = path.join(root, 'state_tests/runtime/arkts/native', name);
        fs.copyFileSync(file, path.join(tests, 'ets/test', name));
        return { path: file, sha256: hash(file) };
      });
      const suite = fixture === 'copy_probe' ? 'DeviceCopyProbe.test' : fixture === 'context_probe' ? 'DeviceContextProbe.test' : fixture === '12_15' ? 'Tasks12_15NativeUi.test' : 'Tasks16_18EntryUI.test';
      const invocation = ['12_15', 'context_probe', 'copy_probe'].includes(fixture) ? 'suite();' :
        "const args = abilityDelegatorRegistry.getArguments(); suite(args.parameters['taskId'], args.bundleName);";
      fs.writeFileSync(path.join(tests, 'ets/test/List.test.ets'),
        `import suite from './${suite}';\nimport abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';\nexport default function testsuite(): void { ${invocation} }\n`);
      if (fixture === 'bundle') {
        report.supportsExecutionNonce = true;
        fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true });
        const manifest = require('./arkts_native_bundle.cjs').generate(work, output, taskId, role, source, nativeUI, { device: true, caseId });
        if (nativeUI && taskId === '11_room_upgrade_navigation') {
          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native/Tasks08_11NativeUi.install.cjs')).install(work);
          report.nativeUITransport = require(path.join(root, 'state_tests/runtime/arkts/native/Tasks08_11DeviceUi.install.cjs')).install(work);
        }
        if (nativeUI && taskId === '12_report_room') {
          const installer = caseId === 'rr_state_008_leave_failure_is_partial'
            ? 'Task12PartialUi.install.cjs' : 'Tasks12_15NativeUi.install.cjs';
          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work);
        }
        if (nativeUI && taskId === '13_user_verification') {
          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native/Task13NativeUi.install.cjs')).install(work);
        }
        if (nativeUI && taskId === '14_join_room_by_address') {
          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native/Task14DeviceUi.install.cjs')).install(work);
        }
        if (nativeUI && taskId === '15_account_deactivation') {
          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native/Task15NativeUi.install.cjs')).install(work);
        }
        if (nativeUI && ['16_identity_reset', '17_pinned_messages', '18_custom_notification_sounds'].includes(taskId)) {
          const installer = taskId === '16_identity_reset' &&
            ['ir_state_005_oidc_handle_routes_and_resets', 'ir_state_010_cancel_cleans_up'].includes(caseId)
            ? 'Task16NativeUi.install.cjs' : taskId === '17_pinned_messages' && caseId === 'pm_state_001_open_loading'
              ? 'Task17LoadingUi.install.cjs' : 'Tasks16_18NativeUi.install.cjs';
          report.nativeUIObserver = require(path.join(root, 'state_tests/runtime/arkts/native', installer)).install(work);
          if (taskId === '18_custom_notification_sounds' && caseId === 'ns_state_003_message_picker_launch') {
            const providerHostFile = path.join(root, 'state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');
            report.supportsTasks16To18ProviderHost = true;
            report.providerHostSource = { path: providerHostFile, sha256: hash(providerHostFile) };
          }
        }
        report.bundleManifest = path.join(output, 'bundle-manifest.json');
        report.caseId = caseId;
        report.caseCount = manifest.caseCount;
        report.requiresFreshInstallPerCase = true;
        fs.writeFileSync(path.join(tests, 'ets/test/List.test.ets'),
          "import suite from '../../../test/List.test';\nexport default function testsuite(): void { suite(); }\n");
      }
      const bundleName = read(path.join(work, 'AppScope/app.json5')).app.bundleName;
      report.generatedEvaluator = [path.join(work, 'entry/src/test'), tests]
        .filter(directory => fs.existsSync(directory)).flatMap(directory => files(directory))
        .map(file => ({ path: path.relative(work, file), sha256: hash(file) }));
      report.bundleName = bundleName;
      report.deviceTestCommand = ['hdc', '-t', '<SERIAL>', 'shell', 'aa', 'test', '-b', bundleName,
        '-m', 'entry_test', '-s', 'unittest', 'OpenHarmonyTestRunner', '-s', 'taskId', taskId,
        '-s', 'timeout', nativeUI ? '60000' : '15000',
        ...(fixture === '12_15' ? ['-s', 'caseSpec', '<CANONICAL_CASE_JSON>'] : []), '-w', '120000'];
      if (args.includes('--prepare-only')) { report.status = 'prepared_only'; return; }
      for (const target of ['default', 'ohosTest']) {
        const command = [path.join(studio, 'tools/node/bin/node'), path.join(studio, 'tools/hvigor/hvigor/bin/hvigor.js'),
          'assembleHap', '--mode', 'module', '-p', `module=entry@${target}`, '-p', 'product=default', '-p', 'buildMode=debug', '--no-daemon', '--no-parallel'];
        report.commands.push(command);
        const result = spawnSync(command[0], command.slice(1), { cwd: work, encoding: 'utf8', timeout: 240000,
          maxBuffer: 8 * 1024 * 1024, env: { ...process.env, DEVECO_SDK_HOME: path.join(studio, 'sdk'), OHOS_SDK_HOME: sdk,
            NODE_PATH: path.join(work, 'node_modules'),
            JAVA_HOME: path.join(studio, 'jbr/Contents/Home'),
            PATH: `${studio}/jbr/Contents/Home/bin:${studio}/tools/node/bin:${studio}/tools/ohpm/bin:${process.env.PATH}` } });
        const log = redact((result.stdout || '') + (result.stderr || ''));
        fs.writeFileSync(path.join(output, `build-${target}.log`), log.split('\n').map(line => line.length > 4000 ? '[omitted SDK source dump]' : line).join('\n'));
        report.workKiB = Number(spawnSync('du', ['-sk', work], { encoding: 'utf8' }).stdout.split(/\s/)[0]);
        if (result.error || result.status !== 0) throw new Error(`${target} build failed: ${result.error || result.status}; see build-${target}.log`);
        if (report.workKiB > 900 * 1024) throw new Error('Temporary build exceeded 900 MiB budget');
      }
      for (const file of files(path.join(work, 'entry/build')).filter(file => file.endsWith('.hap'))) {
        const destination = path.join(output, path.basename(file));
        fs.copyFileSync(file, destination);
        report.haps.push({ path: destination, sha256: hash(destination), bytes: fs.statSync(destination).size,
          signed: path.basename(destination).endsWith('-signed.hap') });
      }
      report.runtimeCompile.passed = report.haps.length >= 2;
      report.status = report.runtimeCompile.passed ? 'built_not_executed' : 'missing_haps';
      report.copiedProductionUnchanged = provenance.every(item => hash(path.join(work, item.path)) === item.sha256);
    });
  } catch (error) {
    report.status = 'blocked'; report.error = redact(String(error)); report.runtimeCompile.passed = false;
    process.exitCode = 1;
  } finally {
    report.productionUnchanged = provenance.every(item => hash(path.join(source, item.path)) === item.sha256);
    report.temporaryProjectRemoved = !!report.work && !fs.existsSync(report.work);
    write(reportPath, report);
    console.log(JSON.stringify({ status: report.status, error: report.error, haps: report.haps, reportPath }, null, 2));
  }
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
