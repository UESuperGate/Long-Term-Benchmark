'use strict';
// Small, evaluator-only bytecode check. No Hvigor, HAP, app build, Gradle or HDC.
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const crypto = require('node:crypto'), { spawnSync } = require('node:child_process');
const compiler = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/ets/build-tools/ets-loader/bin/ark/build-mac/bin/es2abc');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
function compileFixtures(work, report) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-offline-14-15-fixture-bytecode-'));
  const values = [];
  const fixtures = (report.fixtures || []).map(item => item.path || item.installedPath);
  fixtures.push(path.relative(work, report.bundleFile), path.relative(work, report.suiteFile));
  const result = { scope: 'API23 es2abc single-file evaluator bytecode only; NOT HAP/app/type-link validation',
    compiler: { path: compiler, sha256: hash(fs.readFileSync(compiler)) },
    heavyBuildStarted: false, deviceStarted: false, productionFilesModified: false,
    productionApplicationBuilt: false, generatedBundleContainsTranspiledProduction: true, files: values };
  const receipt = path.join(work, 'offline-evaluator-bytecode-receipt.json');
  try {
    for (const relative of [...new Set(fixtures)].filter(item => !item.endsWith('.d.ts'))) {
      if (!relative.startsWith('entry/src/test/') || relative.includes('..')) throw Error('Evaluator fixture scope violation');
      const file = path.join(work, relative), source = fs.readFileSync(file, 'utf8');
      const javascript = relative.endsWith('.ets') ? ts.transpileModule(source, {
        compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ES2020 }, reportDiagnostics: true
      }).outputText : source;
      const input = path.join(temporary, values.length + '.js'), output = path.join(temporary, values.length + '.abc');
      fs.writeFileSync(input, javascript);
      const command = [compiler, '--module', '--target-api-version=23', '--file-threads=1',
        '--function-threads=1', '--output=' + output, input];
      const process = spawnSync(command[0], command.slice(1), { encoding: 'utf8', timeout: 10000 });
      const record = { path: relative, sourceSha256: hash(source), compiledJsSha256: hash(javascript), command,
        exit: process.status, log: (process.stdout || '') + (process.stderr || ''),
        binary: fs.existsSync(output) ? { bytes: fs.statSync(output).size, sha256: hash(fs.readFileSync(output)) } : null };
      values.push(record);
      fs.writeFileSync(receipt, JSON.stringify(result, null, 2) + '\n');
      if (process.status !== 0 || process.error || !record.binary) throw Error('API23 fixture bytecode failed: ' + relative + ': ' + record.log);
      fs.unlinkSync(output); record.binary.removed = !fs.existsSync(output);
      fs.writeFileSync(receipt, JSON.stringify(result, null, 2) + '\n');
    }
    result.passed = true;
    return result;
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
    result.temporaryRemoved = !fs.existsSync(temporary); result.binariesRetained = false;
    fs.writeFileSync(receipt, JSON.stringify(result, null, 2) + '\n');
  }
}
module.exports = { compileFixtures };
