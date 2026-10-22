'use strict';

// Task08 private workspace helper only. No SDK or process starts on import.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const suffixes = new Set(['.hap', '.har', '.app', '.apk', '.abc', '.so', '.jar', '.aar', '.class', '.dex']);

function hash(file) {
  const h = crypto.createHash('sha256'), buffer = Buffer.alloc(1024 * 1024);
  const descriptor = fs.openSync(file, 'r');
  let bytes = 0;
  try {
    for (;;) {
      const count = fs.readSync(descriptor, buffer, 0, buffer.length, null);
      if (!count) break;
      bytes += count; h.update(buffer.subarray(0, count));
    }
  } finally { fs.closeSync(descriptor); }
  return { path: file, bytes, sha256: h.digest('hex') };
}

async function withTemporaryWorkspace(action, { keepTemp = false, prepareOnly = false } = {}) {
  const audit = process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR;
  if (!audit || !fs.statSync(audit).isDirectory()) throw new Error('Explicit owned intermediate audit directory required');
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task08-native-'));
  let result;
  try { result = await action(work); return result; }
  finally {
    if (!keepTemp && !(prepareOnly && result?.prepared)) {
      const removed = [], symlinks = [];
      const visit = directory => {
        for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
          const file = path.join(directory, entry.name);
          if (entry.isSymbolicLink()) symlinks.push({ path: file, target: fs.readlinkSync(file), followed: false });
          else if (entry.isDirectory()) visit(file);
          else if (entry.isFile() && suffixes.has(path.extname(file))) removed.push(hash(file));
        }
      };
      visit(work);
      const receipt = path.join(audit, 'temporary-cleanup-' + path.basename(work) + '.json');
      const report = { work, removed, symlinks, hashesRecordedBeforeRemoval: true, removedWorkspace: false };
      fs.writeFileSync(receipt, JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
      fs.rmSync(work, { recursive: true, force: true, maxRetries: 0 });
      report.removedWorkspace = !fs.existsSync(work);
      fs.writeFileSync(receipt, JSON.stringify(report, null, 2) + '\n');
      if (result?.report) result.report.temporaryProjectRemoved = true;
    }
  }
}

module.exports = { withTemporaryWorkspace };
