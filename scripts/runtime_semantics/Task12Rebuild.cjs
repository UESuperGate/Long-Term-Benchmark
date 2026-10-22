'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { withTemporaryWorkspace } = require('./arkts_native_smoke.cjs');
const root = path.resolve(__dirname, '../..');
const audit = path.join(root, 'experiment_results/runtime_transition_20261020/task12_rebuild');
const projects = [
  ['base', '12_report_room_base_25_04_3', '12_report_room_base_25_04_3_rebuilt'],
  ['final', 'final_dev_nodes/12_report_room_final_25_05_0', 'final_dev_nodes/12_report_room_final_25_05_4']
];
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
function manifest(dir) {
  return fs.readdirSync(dir, { recursive: true }).sort().filter(p => fs.statSync(path.join(dir, p)).isFile())
    .map(p => ({ path: p, bytes: fs.statSync(path.join(dir, p)).size, sha256: sha(fs.readFileSync(path.join(dir, p))) }));
}
function snapshot() {
  const target = path.join(audit, 'before');
  if (fs.existsSync(target)) throw new Error('Snapshot already exists; refusing overwrite');
  for (const [, , project] of projects) if (fs.existsSync(path.join(root, project))) throw new Error('Rebuilt project already exists');
  fs.mkdirSync(target, { recursive: true });
  const records = [];
  for (const [role, oldProject, newProject] of projects) {
    const original = path.join(root, oldProject);
    const files = manifest(original);
    fs.cpSync(original, path.join(target, role), { recursive: true, errorOnExist: true, force: false });
    fs.cpSync(original, path.join(root, newProject), { recursive: true, errorOnExist: true, force: false });
    records.push({ role, oldProject, newProject, files });
  }
  fs.writeFileSync(path.join(target, 'manifest.json'), JSON.stringify({ schemaVersion: 1, records }, null, 2) + '\n');
}
async function build(role) {
  const record = projects.find(p => p[0] === role);
  if (!record) throw new Error('Use base or final');
  const source = path.join(root, record[2]);
  const out = path.join(audit, 'build-' + role);
  fs.mkdirSync(out, { recursive: true });
  const studio = '/Applications/DevEco-Studio.app/Contents';
  const report = { role, source, files: manifest(source), nativeRuntimeExecuted: false, status: 'building' };
  try {
    await withTemporaryWorkspace(async work => {
      report.work = work;
      fs.cpSync(source, work, { recursive: true });
      fs.cpSync(path.join(root, 'elementx_harmony_full/oh_modules'), path.join(work, 'oh_modules'), { recursive: true, verbatimSymlinks: true });
      fs.mkdirSync(path.join(work, 'node_modules/@ohos'), { recursive: true });
      for (const name of ['hvigor', 'hvigor-ohos-plugin']) fs.symlinkSync(path.join(studio, 'tools/hvigor', name), path.join(work, 'node_modules/@ohos', name));
      fs.writeFileSync(path.join(work, 'local.properties'), `sdk.dir=${process.env.HOME}/Library/OpenHarmony/Sdk\nhwsdk.dir=${studio}/sdk\n`);
      const command = [path.join(studio, 'tools/node/bin/node'), path.join(studio, 'tools/hvigor/hvigor/bin/hvigor.js'),
        'assembleHap', '--mode', 'module', '-p', 'module=entry@default', '-p', 'product=default', '-p', 'buildMode=debug', '--no-daemon', '--no-parallel'];
      report.command = command;
      const result = spawnSync(command[0], command.slice(1), { cwd: work, encoding: 'utf8', timeout: 240000, maxBuffer: 8 * 1024 * 1024,
        env: { ...process.env, DEVECO_SDK_HOME: path.join(studio, 'sdk'), NODE_PATH: path.join(work, 'node_modules'),
          JAVA_HOME: path.join(studio, 'jbr/Contents/Home'), PATH: `${studio}/jbr/Contents/Home/bin:${studio}/tools/node/bin:${studio}/tools/ohpm/bin:${process.env.PATH}` } });
      const log = (result.stdout || '') + (result.stderr || '');
      fs.writeFileSync(path.join(out, 'build.log'), log);
      report.exitCode = result.status;
      report.logSha256 = sha(log);
      if (result.error || result.status !== 0) throw new Error(String(result.error || 'Build failed; see build.log'));
      const hap = path.join(work, 'entry/build/default/outputs/default/entry-default-unsigned.hap');
      const bytes = fs.readFileSync(hap);
      const saved = path.join(out, 'entry-default-unsigned.hap'); fs.writeFileSync(saved, bytes);
      report.hap = { path: saved, bytes: bytes.length, sha256: sha(bytes) };
      report.productionUnchanged = report.files.every(f => sha(fs.readFileSync(path.join(work, f.path))) === f.sha256);
      report.status = 'built_not_executed';
    });
  } catch (error) { report.status = 'build_failed'; report.error = String(error); process.exitCode = 1; }
  report.temporaryProjectRemoved = !!report.work && !fs.existsSync(report.work);
  report.sourceUnchanged = JSON.stringify(manifest(source)) === JSON.stringify(report.files);
  fs.writeFileSync(path.join(out, 'build-report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ role, status: report.status, error: report.error, hap: report.hap, temporaryProjectRemoved: report.temporaryProjectRemoved }, null, 2));
}
if (require.main === module) {
  if (process.argv[2] === 'snapshot') snapshot();
  else build(process.argv[2]).catch(error => { console.error(error); process.exitCode = 1; });
}
module.exports = { manifest, projects };
