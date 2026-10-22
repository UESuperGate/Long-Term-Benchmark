'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const excludes = new Set(['.git', '.hvigor', 'build', 'node_modules', 'oh_modules']);

function record(file) {
  const data = fs.readFileSync(file);
  return { path: path.resolve(file), bytes: data.length, sha256: sha(data) };
}

function snapshot(directory, dependencies = false) {
  const entries = [], payloads = {};
  const visit = relative => {
    const file = path.join(directory, relative), stat = fs.lstatSync(file);
    const item = { path: relative || '.', mode: stat.mode & 0o7777 };
    if (stat.isSymbolicLink()) {
      item.kind = 'symlink'; item.target = fs.readlinkSync(file);
    } else if (stat.isDirectory()) {
      item.kind = 'directory'; entries.push(item);
      for (const name of fs.readdirSync(file).sort()) {
        if (!dependencies && excludes.has(name)) continue;
        visit(relative ? relative + '/' + name : name);
      }
      return;
    } else if (stat.isFile()) {
      const data = fs.readFileSync(file);
      item.kind = 'file'; item.bytes = data.length; item.sha256 = sha(data);
      payloads[item.path] = data.toString('base64');
    } else throw new Error('Unsupported compiler input type: ' + relative);
    entries.push(item);
  };
  visit('');
  return { root: path.resolve(directory), entries, payloads };
}

function save(output, label, input) {
  const file = path.join(output, label + '.json.gz');
  const plain = Buffer.from(JSON.stringify(input));
  const compressed = zlib.gzipSync(plain);
  fs.writeFileSync(file, compressed, { flag: 'wx' });
  if (!zlib.gunzipSync(fs.readFileSync(file)).equals(plain)) throw new Error('Lossless input archive validation failed');
  return { ...record(file), encoding: 'gzip-json-with-base64-original-bytes', uncompressedBytes: plain.length,
    uncompressedSha256: sha(plain), entries: input.entries.length };
}

function beginCopy(source, work, output) {
  const original = snapshot(source), copied = snapshot(work);
  const left = original.entries.filter(item => item.path !== '.');
  const right = copied.entries.filter(item => item.path !== '.');
  if (JSON.stringify(left) !== JSON.stringify(right)) throw new Error('Raw source -> copied inputs differ in path/type/mode/link/bytes');
  return { source: save(output, 'candidate-before-copy', original),
    copied: save(output, 'candidate-after-copy', copied),
    exactNonRootEntries: true, rootModes: { source: original.entries[0].mode, copied: copied.entries[0].mode },
    rootDirectoryModeIsNotClaimedEqual: true };
}

function beforeCompile(work, output, target, producers) {
  const inputs = snapshot(work);
  const dependencies = snapshot(path.join(work, 'oh_modules'), true);
  const receipt = { target, capturedBeforeCompilerInvocation: true,
    projectInputs: save(output, 'compiler-' + target + '-before', inputs),
    dependencies: save(output, 'compiler-' + target + '-dependencies', dependencies),
    producerSources: producers.map(record), helper: record(__filename) };
  return receipt;
}

function afterCompile(work, output, target, receipt) {
  receipt.projectInputsAfter = save(output, 'compiler-' + target + '-after', snapshot(work));
  receipt.producerSourcesAfter = receipt.producerSources.map(item => record(item.path));
  if (JSON.stringify(receipt.producerSourcesAfter) !== JSON.stringify(receipt.producerSources)) throw new Error('Compiler producer sources changed during execution');
}

module.exports = { snapshot, record, beginCopy, beforeCompile, afterCompile };
