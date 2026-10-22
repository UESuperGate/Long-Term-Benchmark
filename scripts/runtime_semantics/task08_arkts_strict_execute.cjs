#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function deriveTemplate(original, sharedExecutor, providerHost, timeoutSeconds) {
  const lockPatch = ".replace('fs.mkdirSync(lock);\\n    locked = true;', wait)";
  if (original.split(lockPatch).length === 2)
    original = original.replace(lockPatch, ".replace(/fs\\.mkdirSync\\(lock\\);\\s+locked = true;/, wait)");
  else if (!original.includes('.replace(lockAnchor, wait)') ||
      !original.includes("throw new Error('Shared lock acquisition is absent or ambiguous')"))
    throw new Error('Task08 lock template changed');
  const preflightOriginal = `uiPreflightFile = '/data/local/tmp/ltb-ui-preflight-' + Date.now() + '.json';
      run('ui-preflight-dump', ['shell', 'uitest', 'dumpLayout', '-p', uiPreflightFile], 120000);
      const layout = JSON.parse(run('ui-preflight-tree', ['shell', 'cat', uiPreflightFile]));`;
  const preflightReplacement = `uiPreflightFile = '/data/local/tmp/ltb-ui-preflight-' + Date.now() + '.json';
      let layout;
      const preflightErrors = [];
      for (let preflightAttempt = 1; preflightAttempt <= 5 && !layout; preflightAttempt++) {
        const dump = run('ui-preflight-dump-' + preflightAttempt,
          ['shell', 'uitest', 'dumpLayout', '-p', uiPreflightFile], 120000);
        try {
          if (/DumpLayout failed|Get window nodes failed/i.test(dump)) throw new Error(dump.trim());
          const text = run('ui-preflight-tree-' + preflightAttempt, ['shell', 'cat', uiPreflightFile]);
          const parsed = JSON.parse(text);
          if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.children)) {
            throw new Error('UI preflight JSON has no root children');
          }
          layout = parsed;
        } catch (error) {
          preflightErrors.push(String(error));
          if (preflightAttempt < 5) sleepSync(1000);
        }
      }
      if (!layout) throw new Error('Task08 UI preflight unavailable after bounded retries: ' + preflightErrors.join(' | '));`;
  const patchSharedRead = `const sharedOriginal = fs.readFileSync(shared, 'utf8');
  const withImports = sharedOriginal.includes("const os = require('node:os');") ? sharedOriginal :
    sharedOriginal.replace("const fs = require('node:fs');", "const fs = require('node:fs');\\nconst os = require('node:os');");
  const boundedTest = withImports.replace("const transcript = run('aa-test', command, 150000);",
    "const transcript = run('aa-test', command, Math.min(600000, Math.max(1, task08ExecutionDeadline - Date.now())));");
  if (boundedTest === withImports) throw new Error('Task08 aa-test timeout template changed');
  const original = boundedTest.replace("const fs = require('node:fs');",
    "const task08ExecutionDeadline = Date.now() + ${timeoutSeconds} * 1000;\\nconst fs = require('node:fs');")
    .replace(${JSON.stringify(preflightOriginal)}, ${JSON.stringify(preflightReplacement)});
  if (!original.includes('Task08 UI preflight unavailable after bounded retries')) throw new Error('Task08 UI preflight patch failed: shared executor changed');`;
  const derived = original
    .replace("const shared = path.join(__dirname, 'arkts_device_execute.cjs');",
      'const shared = ' + JSON.stringify(sharedExecutor) + ';')
    .replace("const provider = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');",
      'const provider = ' + JSON.stringify(providerHost) + ';')
    .replace("const original = fs.readFileSync(shared, 'utf8');", patchSharedRead)
    .replace("const derived = deriveRunner(fs.readFileSync(shared, 'utf8'));",
      patchSharedRead + '\n  const derived = deriveRunner(original);')
    .replaceAll('Task13', 'Task08')
    .replaceAll('task13', 'task08')
    .replace('const lockDeadline = Date.now() + 3600 * 1000;',
      'const lockDeadline = Date.now() + ' + timeoutSeconds + ' * 1000;')
    .replace("!derived.includes('const lockDeadline = Date.now() + 3600 * 1000;')",
      "!derived.includes('const lockDeadline = Date.now() + " + timeoutSeconds + " * 1000;')")
    .replace('names.length !== 10 || new Set(names).size !== 10', 'names.length !== 9 || new Set(names).size !== 9')
    .replace('identities.size !== 10', 'identities.size !== 9')
    .replace('Expected ten fresh native result files', 'Expected nine fresh native result files')
    .replace('cover ten unique cases', 'cover nine unique cases');
  if (derived === original || !derived.includes(JSON.stringify(sharedExecutor)) ||
    !derived.includes(JSON.stringify(providerHost)) ||
    !derived.includes('Task08 UI preflight unavailable after bounded retries') ||
    !derived.includes('const lockDeadline = Date.now() + ' + timeoutSeconds + ' * 1000;') ||
    !derived.includes('names.length !== 9') || !derived.includes('identities.size !== 9')) {
    throw new Error('Task13 execution template changed; refusing Task08 derivation');
  }
  return derived;
}

function main() {
  const args = process.argv.slice(2);
  const [buildFile, serial, outputDirectory] = args;
  if (!buildFile || !serial || !outputDirectory) {
    throw new Error('Usage: task08_arkts_strict_execute.cjs BUILD_REPORT SERIAL FRESH_OUTPUT_DIRECTORY [--timeout-seconds N]');
  }
  const timeoutIndex = args.indexOf('--timeout-seconds');
  const timeoutSeconds = timeoutIndex < 0 ? 3600 : Number(args[timeoutIndex + 1]);
  if (!Number.isInteger(timeoutSeconds) || timeoutSeconds < 1 || timeoutSeconds > 3600) {
    throw new Error('Task08 strict execute timeout must be an integer from 1 to 3600 seconds');
  }
  const output = path.resolve(outputDirectory);
  if (fs.existsSync(output)) throw new Error('Refusing existing Task08 execution evidence: ' + output);
  const template = path.join(__dirname, 'task13_arkts_revision5_execute.cjs');
  const sharedExecutor = path.join(__dirname, 'arkts_device_execute.cjs');
  const providerHost = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');
  const original = fs.readFileSync(template, 'utf8');
  const derived = deriveTemplate(original, sharedExecutor, providerHost, timeoutSeconds);
  const generated = path.join(path.dirname(path.resolve(buildFile)), 'task08-strict-execute-template.generated.cjs');
  fs.writeFileSync(generated, derived);
  const run = spawnSync(process.execPath, [generated, path.resolve(buildFile), serial, output], {
    cwd: path.resolve(__dirname, '../..'), encoding: 'utf8', timeout: (timeoutSeconds + 5) * 1000,
    maxBuffer: 16 * 1024 * 1024
  });
  process.stdout.write(run.stdout || '');
  process.stderr.write(run.stderr || '');
  if (run.error || run.status !== 0) process.exitCode = run.status || 1;
  else {
    const policy = path.join(__dirname, 'task08_arkts_entry_evidence.py');
    const normalized = spawnSync('python3', [policy, '--build', path.resolve(buildFile),
      '--execution', path.join(output, 'device-execution.json')], { encoding: 'utf8', timeout: 10000 });
    process.stdout.write(normalized.stdout || ''); process.stderr.write(normalized.stderr || '');
    if (normalized.error || normalized.status !== 0) process.exitCode = normalized.status || 1;
  }
}

module.exports = { deriveTemplate };

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
}
