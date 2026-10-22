'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const binary = new Set(['.apk', '.hap', '.aab', '.apks', '.abc', '.dex', '.so', '.jar', '.class', '.har']);
const disposable = new Set(['.git', '.hvigor', 'build', 'oh_modules', 'node_modules']);

function record(file) {
  const bytes = fs.readFileSync(file);
  return { path: path.resolve(file), bytes: bytes.length, sha256: sha(bytes) };
}

function restoredBytes(item) {
  const archive = fs.readFileSync(item.gzip.path);
  if (archive.length !== item.gzip.bytes || sha(archive) !== item.gzip.sha256)
    throw new Error('Task11 compressed evidence binding changed');
  const bytes = zlib.gunzipSync(archive);
  if (bytes.length !== item.original.bytes || sha(bytes) !== item.original.sha256)
    throw new Error('Task11 restored original evidence differs');
  return bytes;
}

function retainTree(source, destination) {
  source = path.resolve(source); destination = path.resolve(destination);
  if (destination === source || destination.startsWith(source + path.sep))
    throw new Error('Task11 retention must be outside temporary artifact tree');
  fs.mkdirSync(path.join(destination, 'objects'), { recursive: true });
  const manifestFile = path.join(destination, 'manifest.json');
  const manifest = fs.existsSync(manifestFile) ? JSON.parse(fs.readFileSync(manifestFile)) : {
    schemaVersion: 1, taskId: '11_room_upgrade_navigation', originalRoot: source,
    retentionRoot: destination, compression: 'gzip_lossless_original_bytes', files: [], binaryHashes: [],
    scope: 'Native/build/execution/log/generated-fixture artifacts, excluding disposable build internals and binaries' };
  if (manifest.originalRoot !== source || manifest.retentionRoot !== destination)
    throw new Error('Task11 retention root changed');
  const visit = directory => {
    if (!fs.existsSync(directory)) return;
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error('Task11 evidence symlink unsupported');
      if (entry.isDirectory()) { if (!disposable.has(entry.name)) visit(file); continue; }
      if (!entry.isFile()) continue;
      const original = record(file);
      if (binary.has(path.extname(file).toLowerCase())) {
        if (!manifest.binaryHashes.some(row => row.path === original.path && row.sha256 === original.sha256))
          manifest.binaryHashes.push(original);
        continue;
      }
      const existing = manifest.files.find(row => row.original.path === original.path && row.original.sha256 === original.sha256);
      if (existing) { restoredBytes(existing); continue; }
      const bytes = fs.readFileSync(file);
      const target = path.join(destination, 'objects', original.sha256 + '.gz');
      if (!fs.existsSync(target)) fs.writeFileSync(target, zlib.gzipSync(bytes), { flag: 'wx' });
      const item = { original, relativePath: path.relative(source, file), gzip: record(target),
        originalBytesRestorable: true };
      if (!restoredBytes(item).equals(bytes)) throw new Error('Task11 evidence is not losslessly restorable');
      manifest.files.push(item);
    }
  };
  visit(source);
  const temporary = manifestFile + '.tmp';
  fs.writeFileSync(temporary, JSON.stringify(manifest, null, 2) + '\n');
  fs.renameSync(temporary, manifestFile);
  return record(manifestFile);
}

function restore(manifestFile, destination) {
  const manifest = JSON.parse(fs.readFileSync(manifestFile));
  destination = path.resolve(destination);
  if (fs.existsSync(destination)) throw new Error('Refuse to overwrite evidence restoration directory');
  const latest = new Map(manifest.files.map(item => [item.relativePath, item]));
  for (const item of latest.values()) {
    const target = path.resolve(destination, item.relativePath);
    if (!target.startsWith(destination + path.sep)) throw new Error('Unsafe restored evidence path');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, restoredBytes(item), { flag: 'wx' });
  }
  return { restoredFiles: latest.size, originalRoot: manifest.originalRoot, destination };
}

module.exports = { record, retainTree, restoredBytes, restore };
if (require.main === module) {
  const [, , manifestFile, destination] = process.argv;
  if (!manifestFile || !destination) throw new Error('Usage: task11_arkts_evidence_retention.cjs <manifest.json> <new-restore-directory>');
  console.log(JSON.stringify(restore(manifestFile, destination)));
}
