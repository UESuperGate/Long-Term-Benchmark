'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const policies = {
  '11_room_upgrade_navigation': {
    directory: 'experiment_results/runtime_transition_20261020/task11_base_repair/before',
    manifestSha256: '2a71c85df2d5e939557b863aead8c000d863bd63d24930e9926538188de449c7',
    patchSha256: '6b25e0a17fbd5fc4cb1ba59ac4f9129d8b7228dcd4ea9e544273cd276d2dccb7'
  }
};

function requireThat(ok, message) { if (!ok) throw new Error(message); }

function regularFiles(directory) {
  requireThat(!fs.lstatSync(directory).isSymbolicLink(), 'Snapshot directory is a symlink');
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    requireThat(!entry.isSymbolicLink(), 'Snapshot contains a symlink');
    requireThat(entry.isDirectory() || entry.isFile(), 'Snapshot contains a special file');
    return entry.isDirectory() ? regularFiles(file) : [file];
  });
}

function verifySnapshot(repository, taskId, policy) {
  const before = path.resolve(repository, policy.directory);
  requireThat(before.startsWith(path.resolve(repository) + path.sep), 'Snapshot escapes repository');
  const source = path.join(before, 'project');
  const manifestFile = path.join(before, 'manifest.json');
  requireThat(!fs.lstatSync(manifestFile).isSymbolicLink(), 'Manifest is a symlink');
  requireThat(sha(fs.readFileSync(manifestFile)) === policy.manifestSha256, 'Archived base manifest changed');
  const manifest = JSON.parse(fs.readFileSync(manifestFile));
  requireThat(manifest.taskId === taskId && manifest.role === 'base' && manifest.stage === 'before', 'Wrong archived base identity');
  requireThat(Array.isArray(manifest.production) && manifest.production.length > 0, 'Empty archived source manifest');
  const seen = new Set();
  for (const item of manifest.production) {
    const file = path.resolve(repository, item.path);
    requireThat(file.startsWith(source + path.sep) && !seen.has(file), 'Invalid/duplicate archived source path');
    seen.add(file);
    requireThat(fs.lstatSync(file).isFile(), 'Snapshot file is not regular');
    const data = fs.readFileSync(file);
    requireThat(data.length === item.bytes && sha(data) === item.sha256, 'Archived base source changed: ' + item.path);
  }
  const actual = regularFiles(source);
  requireThat(actual.length === seen.size && actual.every(file => seen.has(file)), 'Unmanifested archived source files');
  const patch = path.join(repository, 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/provenance/patches', `arkts_${taskId}.patch`);
  requireThat(sha(fs.readFileSync(patch)) === policy.patchSha256, 'Archived agent patch changed');
  return { source, manifest: manifestFile, manifestSha256: policy.manifestSha256,
    patchSha256: policy.patchSha256, purpose: 'original_archived_candidate_replay_not_repaired_base_agent' };
}

function archivedBase(taskId) {
  const policy = policies[taskId];
  return policy ? verifySnapshot(root, taskId, policy) : null;
}

module.exports = { archivedBase, verifySnapshot };
if (require.main === module) {
  try {
    if (process.argv.length !== 3) throw new Error('Usage: archived_arkts_base.cjs TASK_ID');
    console.log(JSON.stringify(archivedBase(process.argv[2])));
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
