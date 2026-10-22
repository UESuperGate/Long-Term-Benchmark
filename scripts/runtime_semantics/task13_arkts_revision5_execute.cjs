#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const shared = path.join(__dirname, 'arkts_device_execute.cjs');
const provider = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');

function deriveRunner(original) {
  const wait = `const lockDeadline = Date.now() + 3600 * 1000;
    while (!locked) {
      try { fs.mkdirSync(lock); locked = true; }
      catch (error) {
        if (error && error.code === 'EEXIST' && Date.now() < lockDeadline) {
          await new Promise(resolve => setTimeout(resolve, 2000));
          continue;
        }
        throw error;
      }
    }`;
  const singleResult = `if (files.length) {
      if (files.length !== 1 || !/^ltb-native-result_\\d+\\.json$/.test(files[0].name)) throw new Error('Invalid native result file marker');
      const artifact = files[0];
      const remote = \`/data/app/el2/\${users[0]}/base/\${build.bundleName}/cache/\${artifact.name}\`;
      const local = path.join(output, 'native-result.json');
      if (fs.existsSync(local)) throw new Error('Refusing old result file');
      run('pull-result', ['file', 'recv', remote, local]);
      const bytes = fs.readFileSync(local);
      const json = bytes.toString('utf8');
      if (bytes.length !== artifact.bytes || json.length !== artifact.characters) throw new Error('Native result length mismatch');
      const row = JSON.parse(json);
      if (['taskId', 'role', 'caseId'].some(key => row[key] !== artifact[key])) throw new Error('Native result file identity mismatch');
      if (report.executionNonce && (artifact.executionNonce !== report.executionNonce ||
          row.nativeBridge?.capabilities?.execution?.nonce !== report.executionNonce)) throw new Error('Native result execution nonce mismatch');
      report.rowArtifact = { remote, local, bytes: bytes.length, sha256: hash(local), processLogMarker: artifact };
      report.rows = [row];
    } else report.rows = decodeRows(log);`;
  const multipleResults = `if (!build.caseId) {
      report.rowArtifacts = [];
      const identities = new Set();
      const remoteCache = \`/data/app/el2/\${users[0]}/base/\${build.bundleName}/cache\`;
      const names = run('list-native-results', ['shell', 'ls', remoteCache]).split(/\\s+/)
        .map(name => path.basename(name)).filter(name => /^ltb-native-result_\\d+\\.json$/.test(name));
      if (names.length !== 10 || new Set(names).size !== 10) throw new Error('Expected ten fresh native result files in candidate cache');
      for (const [index, name] of names.sort().entries()) {
        const remote = remoteCache + '/' + name;
        const local = path.join(output, 'native-result-' + String(index + 1).padStart(2, '0') + '.json');
        run('pull-result-' + String(index + 1).padStart(2, '0'), ['file', 'recv', remote, local]);
        const bytes = fs.readFileSync(local), json = bytes.toString('utf8'), row = JSON.parse(json);
        if (row.taskId !== build.taskId || row.role !== build.role) throw new Error('Native result file identity mismatch');
        if (row.nativeBridge?.capabilities?.execution?.nonce !== report.executionNonce) throw new Error('Native result execution nonce mismatch');
        const identity = JSON.stringify([row.taskId, row.role, row.caseId]);
        if (identities.has(identity)) throw new Error('Duplicate native result identity');
        identities.add(identity);
        report.rows.push(row);
        report.rowArtifacts.push({ remote, local, bytes: bytes.length, sha256: hash(local), executionNonce: report.executionNonce });
      }
      if (identities.size !== 10) throw new Error('Native result inventory does not cover ten unique cases');
    } else if (files.length) {
      if (files.length !== 1 || !/^ltb-native-result_\\d+\\.json$/.test(files[0].name)) throw new Error('Invalid native result file marker');
      const artifact = files[0];
      const remote = \`/data/app/el2/\${users[0]}/base/\${build.bundleName}/cache/\${artifact.name}\`;
      const local = path.join(output, 'native-result.json');
      run('pull-result', ['file', 'recv', remote, local]);
      const bytes = fs.readFileSync(local), json = bytes.toString('utf8'), row = JSON.parse(json);
      if (bytes.length !== artifact.bytes || json.length !== artifact.characters) throw new Error('Native result length mismatch');
      if (['taskId', 'role', 'caseId'].some(key => row[key] !== artifact[key])) throw new Error('Native result file identity mismatch');
      if (report.executionNonce && row.nativeBridge?.capabilities?.execution?.nonce !== report.executionNonce) throw new Error('Native result execution nonce mismatch');
      report.rows = [row];
      report.rowArtifact = { remote, local, bytes: bytes.length, sha256: hash(local), processLogMarker: artifact };
    } else report.rows = decodeRows(log);`;
  const multiNonce = `function freshMultiNoncePid(before, after, expected, nonce) {
  const known = new Set(before.split('\\n'));
  const matching = after.split('\\n').filter(line => !known.has(line) && line.includes('ARKTS_NATIVE_ROW_FILE '))
    .map(line => ({ line, item: JSON.parse(line.slice(line.indexOf('ARKTS_NATIVE_ROW_FILE ') + 'ARKTS_NATIVE_ROW_FILE '.length)) }))
    .filter(entry => entry.item.taskId === expected.taskId && entry.item.role === expected.role &&
      entry.item.executionNonce === nonce && /^ltb-native-result_\\d+\\.json$/.test(entry.item.name));
  const cases = new Set(matching.map(entry => entry.item.caseId));
  const pids = new Set(matching.map(entry => {
    const match = entry.line.match(/^\\S+\\s+\\S+\\s+(\\d+)\\s+\\d+\\s/);
    return match && match[1];
  }));
  if (matching.length < 1 || cases.size !== matching.length || pids.size !== 1 || pids.has(null)) {
    throw new Error('Expected fresh unique nonce-bound canonical result markers from one process');
  }
  return [...pids][0];
}

`;
  const lockAnchor = /fs\.mkdirSync\(lock\);\s+locked = true;/g;
  if ([...original.matchAll(lockAnchor)].length !== 1) throw new Error('Shared lock acquisition is absent or ambiguous');
  const derived = original
    .replace("const providerHostFile = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');",
      'const providerHostFile = ' + JSON.stringify(provider) + ';')
    .replace(lockAnchor, wait)
    .replace(singleResult, multipleResults)
    .replace("const transcript = run('aa-test', command, 150000);", "const transcript = run('aa-test', command, 900000);")
    .replace('function screenLocked(layout) {', multiNonce + 'function screenLocked(layout) {')
    .replace('report.pid = freshNoncePid(resultBefore, resultAfter, build, report.executionNonce);',
      'report.pid = build.caseId ? freshNoncePid(resultBefore, resultAfter, build, report.executionNonce) : freshMultiNoncePid(resultBefore, resultAfter, build, report.executionNonce);');
  if (derived === original || !derived.includes('const lockDeadline = Date.now() + 3600 * 1000;') ||
    !derived.includes(JSON.stringify(provider)) || !derived.includes('report.rowArtifacts = [];') ||
    !derived.includes('freshMultiNoncePid(resultBefore')) {
    throw new Error('Shared execution runner shape changed');
  }
  return derived;
}

function main() {
  const [buildFile, serial, outputDirectory] = process.argv.slice(2);
  if (!buildFile || !serial || !outputDirectory) {
    throw new Error('Usage: task13_arkts_revision5_execute.cjs BUILD_REPORT SERIAL FRESH_OUTPUT_DIRECTORY');
  }
  const build = JSON.parse(fs.readFileSync(buildFile));
  if (build.task13Revision5?.compileOnly === true || !build.task13Revision5?.entryDiscovery) {
    throw new Error('Compile-only scaffolding is not actual entry discovery; device execution refused');
  }
  const output = path.resolve(outputDirectory);
  if (fs.existsSync(output)) throw new Error('Refusing existing Task13 execution evidence: ' + output);
  let derived = deriveRunner(fs.readFileSync(shared, 'utf8'));
  const anchor = "  const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');";
  if (derived.split(anchor).length !== 2) throw new Error('Execution source-binding anchor changed');
  const bindings = `  const task13Sources = [${JSON.stringify(__filename)}, ${JSON.stringify(shared)}, __filename];
  const task13SourceDirectory = path.join(output, 'execution-sources');
  fs.mkdirSync(task13SourceDirectory);
  report.task13ExecutionSources = task13Sources.map((file, index) => {
    const data = fs.readFileSync(file);
    const original = {path: file, bytes: data.length, sha256: hash(file)};
    const retained = path.join(task13SourceDirectory, index + '-' + path.basename(file));
    fs.writeFileSync(retained, data, {flag: 'wx'});
    return {original, retained: {path: retained, bytes: data.length, sha256: hash(retained)}};
  });
  fs.writeFileSync(path.join(output, 'execution-source-binding.json'), JSON.stringify({
    capturedBeforeDeviceCommands: true, executionNonce: report.executionNonce,
    buildReport: report.buildReport, sources: report.task13ExecutionSources
  }, null, 2));
`;
  derived = derived.replace(anchor, bindings + anchor);
  const generated = path.join(path.dirname(path.resolve(buildFile)), 'task13-revision5-execute.generated.cjs');
  fs.writeFileSync(generated, derived);
  const run = spawnSync(process.execPath, [generated, path.resolve(buildFile), serial, output], {
    cwd: path.resolve(__dirname, '../..'), encoding: 'utf8', timeout: 3700 * 1000,
    maxBuffer: 16 * 1024 * 1024
  });
  process.stdout.write(run.stdout || '');
  process.stderr.write(run.stderr || '');
  if (run.error || run.status !== 0) process.exitCode = run.status || 1;
}

module.exports = { deriveRunner };

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
}
