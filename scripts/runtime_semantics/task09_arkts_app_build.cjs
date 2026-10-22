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
const node = path.join(studio, 'tools/node/bin/node');
const hvigor = path.join(studio, 'tools/hvigor/hvigor/bin/hvigor.js');
const json5 = require(path.join(studio, 'tools/hvigor/hvigor-ohos-plugin/node_modules/json5'));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => ({ path: path.resolve(file), bytes: fs.statSync(file).size,
  sha256: sha(fs.readFileSync(file)) });
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');

function files(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? files(file) : entry.isFile() ? [file] : [];
  });
}

function value(args, flag) {
  const index = args.indexOf(flag);
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
  return args[index + 1];
}

async function main() {
  const args = process.argv.slice(2);
  const source = path.resolve(value(args, '--source'));
  const output = path.resolve(value(args, '--output-dir'));
  const role = value(args, '--role');
  const timeoutSeconds = Number(args.includes('--timeout') ? value(args, '--timeout') : '3600');
  if (!['base', 'final', 'agent'].includes(role) || !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0)
    throw new Error('Invalid role or timeout');
  if (!fs.statSync(source).isDirectory()) throw new Error('Candidate source is not a directory');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task09 app-build evidence: ' + output);
  fs.mkdirSync(output, { recursive: true });
  const started = process.hrtime.bigint();
  const elapsed = () => Number(process.hrtime.bigint() - started) / 1e9;
  const remainingMs = () => {
    const value = Math.floor((timeoutSeconds - elapsed()) * 1000);
    if (value <= 0) throw new Error('Task09 standalone ArkTS application build exhausted its total timeout');
    return value;
  };
  const contractFile = path.join(root, 'benchmark_tasks/09_spaces_lifecycle/transitions.json');
  const productionBefore = files(path.join(source, 'entry/src/main')).map(file => ({
    path: path.relative(source, file), sha256: sha(fs.readFileSync(file))
  }));
  const report = { schemaVersion: 1, taskId: '09_spaces_lifecycle', platform: 'arkts', role,
    source, timeoutSeconds, budgetClock: 'process.hrtime.bigint monotonic remaining',
    contract: fileRecord(contractFile), productionBefore, compile: {
      passed: false, status: 'not_run', scope: 'standalone_candidate_application_hap'
    }, runtimeCompile: { passed: null, status: 'not_run', scope: 'not_part_of_standalone_application_build' },
    commands: [], haps: [], startedAt: new Date().toISOString() };
  let work;
  try {
    await withTemporaryWorkspace(async temporary => {
      work = temporary;
      fs.cpSync(source, work, { recursive: true, filter: name =>
        !['build', '.hvigor', 'oh_modules', 'node_modules', '.git'].includes(path.basename(name)) });
      fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work, 'oh_modules'),
        { recursive: true, verbatimSymlinks: true });
      fs.mkdirSync(path.join(work, 'node_modules/@ohos'), { recursive: true });
      for (const name of ['hvigor', 'hvigor-ohos-plugin'])
        fs.symlinkSync(path.join(studio, 'tools/hvigor', name), path.join(work, 'node_modules/@ohos', name));
      fs.writeFileSync(path.join(work, 'local.properties'), `sdk.dir=${sdk}\nhwsdk.dir=${studio}/sdk\n`);
      const profileFile = path.join(work, 'build-profile.json5');
      const profile = json5.parse(fs.readFileSync(profileFile, 'utf8'));
      profile.app.signingConfigs = [];
      for (const product of profile.app.products) delete product.signingConfig;
      write(profileFile, profile);
      const command = [node, hvigor, 'assembleHap', '--mode', 'module', '-p', 'module=entry@default',
        '-p', 'product=default', '-p', 'buildMode=debug', '--no-daemon', '--no-parallel'];
      const budget = remainingMs();
      const result = spawnSync(command[0], command.slice(1), { cwd: work, encoding: 'utf8', timeout: budget,
        maxBuffer: 12 * 1024 * 1024, env: { ...process.env, DEVECO_SDK_HOME: path.join(studio, 'sdk'),
          OHOS_SDK_HOME: sdk, NODE_PATH: path.join(work, 'node_modules'),
          JAVA_HOME: path.join(studio, 'jbr/Contents/Home'),
          PATH: `${studio}/jbr/Contents/Home/bin:${studio}/tools/node/bin:${studio}/tools/ohpm/bin:${process.env.PATH}` } });
      const logFile = path.join(output, 'assemble-hap.log');
      fs.writeFileSync(logFile, (result.stdout || '') + (result.stderr || ''));
      report.commands.push({ command, budgetMs: budget, exitCode: result.status,
        error: result.error && String(result.error), log: fileRecord(logFile) });
      if (result.error || result.status !== 0) throw new Error('Standalone application HAP build failed');
      for (const file of files(path.join(work, 'entry/build')).filter(file => file.endsWith('.hap') && !file.includes('ohosTest'))) {
        const destination = path.join(output, path.basename(file));
        fs.copyFileSync(file, destination);
        report.haps.push(fileRecord(destination));
      }
      if (report.haps.length < 1) throw new Error('Standalone application build produced no HAP');
      report.compile = { passed: true, status: 'passed', scope: 'standalone_candidate_application_hap' };
    });
  } catch (error) {
    report.error = `${error.name || 'Error'}: ${error.message || error}`;
    report.compile.status = 'failed';
    process.exitCode = 1;
  } finally {
    report.productionAfter = files(path.join(source, 'entry/src/main')).map(file => ({
      path: path.relative(source, file), sha256: sha(fs.readFileSync(file))
    }));
    report.productionStableDuringBuild = JSON.stringify(report.productionBefore) === JSON.stringify(report.productionAfter);
    report.temporaryProjectRemoved = Boolean(work) && !fs.existsSync(work);
    report.elapsedSeconds = Number(elapsed().toFixed(3));
    report.finishedAt = new Date().toISOString();
    write(path.join(output, 'build-report.json'), report);
  }
  console.log(JSON.stringify({ compile: report.compile, haps: report.haps,
    elapsedSeconds: report.elapsedSeconds, temporaryProjectRemoved: report.temporaryProjectRemoved }));
}

if (require.main === module) main().catch(error => { console.error(error.stack || String(error)); process.exitCode = 1; });
