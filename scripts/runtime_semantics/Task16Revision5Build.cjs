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
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const hash = file => sha(fs.readFileSync(file));
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
const read = file => json5.parse(fs.readFileSync(file, 'utf8'));

function files(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? files(file) : entry.isFile() ? [file] : [];
  });
}

async function main() {
  const args = process.argv.slice(2);
  const value = flag => {
    const index = args.indexOf(flag);
    if (index < 0 || !args[index + 1]) throw new Error(flag + ' is required');
    return args[index + 1];
  };
  const source = path.resolve(value('--source'));
  const role = value('--role');
  const output = path.resolve(value('--output-dir'));
  const contract = path.resolve(value('--contract'));
  const binding = path.resolve(value('--binding'));
  if (!['base', 'final'].includes(role)) throw new Error('--role must be base or final');
  if (fs.existsSync(output)) throw new Error('Refusing existing output directory');
  for (const file of [contract, binding]) if (!fs.existsSync(file)) throw new Error('Missing staged input: ' + file);
  const parsedContract = JSON.parse(fs.readFileSync(contract));
  const parsedBinding = JSON.parse(fs.readFileSync(binding));
  if (parsedContract.taskId !== '16_identity_reset' || parsedContract.revision !== 5 ||
      parsedBinding.taskId !== '16_identity_reset' || parsedContract.cases.length !== 10) {
    throw new Error('Task16 staged revision5 contract/binding required');
  }
  const digests = parsedContract.cases.map(item => item.traceDigest);
  if (JSON.stringify(digests) !== JSON.stringify(parsedBinding.cases.map(item => item.traceDigest))) {
    throw new Error('Staged contract and binding digests differ');
  }
  fs.mkdirSync(output, { recursive: true });
  const production = files(path.join(source, 'entry/src/main')).map(file => ({
    path: path.relative(source, file), sha256: hash(file)
  }));
  const report = {
    schemaVersion: 1,
    taskId: '16_identity_reset',
    role,
    revision: 5,
    source,
    output,
    startedAt: new Date().toISOString(),
    contract: { path: contract, sha256: hash(contract), caseDigests: digests },
    binding: { path: binding, sha256: hash(binding) },
    activeCanonical: { path: path.join(root, 'benchmark_tasks/16_identity_reset/transitions.json'),
      sha256: hash(path.join(root, 'benchmark_tasks/16_identity_reset/transitions.json')) },
    production,
    compile: { passed: null, scope: 'actual default application HAP and evaluator ohosTest HAP' },
    runtimeCompile: { passed: null },
    commands: [],
    haps: [],
    temporaryProjectRemoved: false
  };
  const reportFile = path.join(output, 'build-report.json');
  try {
    await withTemporaryWorkspace(async work => {
      report.temporaryProject = work;
      fs.cpSync(source, work, { recursive: true, filter: name =>
        !['build', '.hvigor', 'oh_modules', 'node_modules', '.git'].includes(path.basename(name)) });
      fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work, 'oh_modules'),
        { recursive: true, verbatimSymlinks: true });
      fs.mkdirSync(path.join(work, 'node_modules/@ohos'), { recursive: true });
      for (const name of ['hvigor', 'hvigor-ohos-plugin']) {
        fs.symlinkSync(path.join(studio, 'tools/hvigor', name), path.join(work, 'node_modules/@ohos', name));
      }
      fs.writeFileSync(path.join(work, 'local.properties'), `sdk.dir=${sdk}\nhwsdk.dir=${studio}/sdk\n`);
      const profileFile = path.join(work, 'build-profile.json5');
      const profile = read(profileFile);
      profile.app.signingConfigs = [];
      for (const product of profile.app.products) delete product.signingConfig;
      write(profileFile, profile);
      const moduleFile = path.join(work, 'entry/build-profile.json5');
      const moduleProfile = read(moduleFile);
      if (!moduleProfile.targets.some(item => item.name === 'ohosTest')) moduleProfile.targets.push({ name: 'ohosTest' });
      write(moduleFile, moduleProfile);
      const tests = path.join(work, 'entry/src/ohosTest');
      fs.rmSync(tests, { recursive: true, force: true });
      fs.cpSync(path.join(root, 'elementx_harmony_full/entry/src/ohosTest'), tests, { recursive: true });
      const runner = path.join(root, 'state_tests/runtime/arkts/native/DeviceTestRunner.ets');
      fs.copyFileSync(runner, path.join(tests, 'ets/testrunner/OpenHarmonyTestRunner.ets'));
      fs.mkdirSync(path.join(work, 'entry/src/test'), { recursive: true });
      const manifest = require('./arkts_native_bundle.cjs').generate(work, output, '16_identity_reset', role,
        source, true, { device: true, contractOverride: contract });
      report.bundleManifest = { path: path.join(output, 'bundle-manifest.json'), sha256: hash(path.join(output, 'bundle-manifest.json')) };
      report.bundleCaseCount = manifest.caseCount;
      report.evaluatorInstall = require(path.join(root,
        'state_tests/runtime/arkts/native/Task16NativeUi.install.cjs')).install(work);
      fs.writeFileSync(path.join(tests, 'ets/test/List.test.ets'),
        "import suite from '../../../test/List.test';\nexport default function testsuite(): void { suite(); }\n");
      const bundleName = read(path.join(work, 'AppScope/app.json5')).app.bundleName;
      report.bundleName = bundleName;
      report.deviceTestCommand = ['shell', 'aa', 'test', '-b', bundleName, '-m', 'entry_test',
        '-s', 'unittest', 'OpenHarmonyTestRunner', '-s', 'timeout', '180000', '-w', '240000'];
      for (const target of ['default', 'ohosTest']) {
        const command = [path.join(studio, 'tools/node/bin/node'),
          path.join(studio, 'tools/hvigor/hvigor/bin/hvigor.js'), 'assembleHap', '--mode', 'module',
          '-p', `module=entry@${target}`, '-p', 'product=default', '-p', 'buildMode=debug',
          '--no-daemon', '--no-parallel'];
        const startedAt = new Date().toISOString();
        const result = spawnSync(command[0], command.slice(1), { cwd: work, encoding: 'utf8', timeout: 360000,
          maxBuffer: 16 * 1024 * 1024, env: { ...process.env,
            DEVECO_SDK_HOME: path.join(studio, 'sdk'), OHOS_SDK_HOME: sdk,
            NODE_PATH: path.join(work, 'node_modules'), JAVA_HOME: path.join(studio, 'jbr/Contents/Home'),
            PATH: `${studio}/jbr/Contents/Home/bin:${studio}/tools/node/bin:${studio}/tools/ohpm/bin:${process.env.PATH}` } });
        const logFile = path.join(output, `build-${target}.log`);
        fs.writeFileSync(logFile, (result.stdout || '') + (result.stderr || ''));
        report.commands.push({ argv: command, startedAt, finishedAt: new Date().toISOString(),
          exitCode: result.status, error: result.error && String(result.error), log: path.basename(logFile), sha256: hash(logFile) });
        if (result.error || result.status !== 0) throw new Error(target + ' build failed; see ' + logFile);
      }
      for (const file of files(path.join(work, 'entry/build')).filter(file => file.endsWith('.hap'))) {
        const destination = path.join(output, path.basename(file));
        fs.copyFileSync(file, destination);
        report.haps.push({ path: destination, sha256: hash(destination), bytes: fs.statSync(destination).size });
      }
      report.compile.passed = report.haps.some(item => path.basename(item.path).includes('default'));
      report.runtimeCompile.passed = report.haps.some(item => path.basename(item.path).includes('ohosTest'));
      report.productionCopiedUnchanged = production.every(item => hash(path.join(work, item.path)) === item.sha256);
    });
    report.status = report.compile.passed && report.runtimeCompile.passed && report.productionCopiedUnchanged ? 'built' : 'blocked';
  } catch (error) {
    report.status = 'blocked';
    report.error = String(error.stack || error);
    process.exitCode = 1;
  } finally {
    report.productionSourceUnchanged = production.every(item => hash(path.join(source, item.path)) === item.sha256);
    report.temporaryProjectRemoved = !!report.temporaryProject && !fs.existsSync(report.temporaryProject);
    report.finishedAt = new Date().toISOString();
    write(reportFile, report);
    console.log(JSON.stringify({ status: report.status, role, reportFile, error: report.error,
      haps: report.haps.map(item => path.basename(item.path)) }, null, 2));
  }
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
