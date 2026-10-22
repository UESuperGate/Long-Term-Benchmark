'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { sourceInventory } = require('./task11_arkts_strict_runtime.cjs');
const root = path.resolve(__dirname, '../..');
const shared = path.join(__dirname, 'arkts_native_device.cjs');
const installer = path.join(root, 'state_tests/runtime/arkts/native/task10_repository/Task10Repository.install.cjs');
function value(args, key) { const i = args.indexOf(key); if (i < 0 || !args[i + 1]) throw new Error(key + ' required'); return args[i + 1]; }
function derive(original, role) {
  const hook = "        if (nativeUI && taskId === '11_room_upgrade_navigation') {";
  if (original.split(hook).length !== 2) throw new Error('Shared builder lifecycle changed');
  return original.replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';')
    .replace("require('./arkts_native_smoke.cjs')", 'require(' + JSON.stringify(path.join(__dirname, 'arkts_native_smoke.cjs')) + ')')
    .replace("require('./arkts_native_bundle.cjs')", 'require(' + JSON.stringify(path.join(__dirname, 'arkts_native_bundle.cjs')) + ')')
    .replace(hook, "        if (nativeUI && taskId === '10_media_upload_quality') {\n" +
      '          report.nativeUIObserver = require(' + JSON.stringify(installer) + ').install(work, ' + JSON.stringify(role) + ');\n' +
      '        }\n' + hook);
}
function main() {
  const args = process.argv.slice(2), role = value(args, '--role');
  const source = path.resolve(value(args, '--source')), before = sourceInventory(source);
  const output = path.resolve(value(args, '--output-dir'));
  if (fs.existsSync(output) || !['base', 'final', 'agent'].includes(role)) throw new Error('Invalid/existing evidence');
  fs.mkdirSync(output, { recursive: true });
  const generated = path.join(output, 'task10-repository-builder.generated.cjs');
  fs.writeFileSync(generated, derive(fs.readFileSync(shared, 'utf8'), role));
  const result = spawnSync(process.execPath, [generated, '--source', path.resolve(value(args, '--source')),
    '--task', '10_media_upload_quality', '--fixture', 'bundle', '--native-ui', '--role', role,
    '--case', value(args, '--case'), '--output-dir', output], { cwd: root, timeout: 600000,
      encoding: 'utf8', maxBuffer: 12 * 1024 * 1024 });
  fs.writeFileSync(path.join(output, 'build-command.log'), (result.stdout || '') + (result.stderr || ''));
  if (result.error || result.status !== 0) throw new Error('Repository binding build failed: ' + (result.error || result.status));
  const after = sourceInventory(source);
  if (before.sha256 !== after.sha256) throw new Error('Candidate changed during source-bound package compilation');
  const reportFile = path.join(output, 'device-build-report.json');
  const report = JSON.parse(fs.readFileSync(reportFile));
  report.task10SourceInventory = before;
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
}
module.exports = { derive };
if (require.main === module) try { main(); } catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
