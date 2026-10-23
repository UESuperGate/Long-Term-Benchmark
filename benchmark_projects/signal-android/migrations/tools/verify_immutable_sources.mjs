import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const value = flag => process.argv[process.argv.indexOf(flag) + 1];
const project = path.resolve(value('--project'));
const repository = path.resolve(value('--repository'));
const manifest = JSON.parse(fs.readFileSync(path.join(project, 'IMMUTABLE_SOURCES.json'), 'utf8'));

const git = args => {
  const result = spawnSync('git', ['-C', repository, ...args], { encoding: null });
  if (result.status !== 0) throw new Error(result.stderr.toString('utf8'));
  return result.stdout;
};

const failures = [];
for (const entry of manifest.files) {
  const local = fs.readFileSync(path.join(project, 'immutable-src', entry.path));
  const object = git(['cat-file', 'blob', `${manifest.sourceCommit}:${entry.path}`]);
  const blob = git(['rev-parse', `${manifest.sourceCommit}:${entry.path}`]).toString('utf8').trim();
  const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
  if (blob !== entry.gitBlob || local.length !== entry.bytes || digest(local) !== entry.sha256 || !local.equals(object)) {
    failures.push(entry.path);
  }
}

if (failures.length > 0) {
  console.error(JSON.stringify({ status: 'failed', failures }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: 'passed', sourceCommit: manifest.sourceCommit, files: manifest.files.length }));
