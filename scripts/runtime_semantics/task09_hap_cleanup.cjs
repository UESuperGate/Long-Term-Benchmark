#!/usr/bin/env node
'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

function removeCopiedHaps(buildReportFile) {
  const reportFile = path.resolve(buildReportFile);
  const evidenceRoot = path.dirname(reportFile);
  const report = JSON.parse(fs.readFileSync(reportFile, 'utf8'));
  if (!Array.isArray(report.haps) || report.haps.length === 0)
    throw new Error('Task09 device build report has no copied HAP metadata');
  const files = [];
  for (const item of report.haps) {
    const file = path.resolve(item.path);
    const relative = path.relative(evidenceRoot, file);
    if (relative.startsWith('..' + path.sep) || path.isAbsolute(relative))
      throw new Error('Refusing to clean HAP outside Task09 evidence directory: ' + file);
    if (!fs.existsSync(file)) throw new Error('Copied Task09 HAP is missing before cleanup: ' + file);
    const bytes = fs.statSync(file).size;
    const digest = sha256(file);
    if (bytes !== item.bytes || digest !== item.sha256)
      throw new Error('Copied Task09 HAP differs from retained build metadata: ' + file);
    fs.unlinkSync(file);
    files.push({ path: file, bytes, sha256: digest, signed: Boolean(item.signed), deleted: !fs.existsSync(file) });
  }
  return { policy: 'delete_copied_haps_after_device_execution', copiedHapsDeleted: files.every(item => item.deleted),
    metadataRetainedInBuildReport: true, buildReport: reportFile, files, cleanedAt: new Date().toISOString() };
}

if (require.main === module) {
  const reportFile = process.argv[2];
  const manifestFile = process.argv[3];
  if (!reportFile) throw new Error('Usage: task09_hap_cleanup.cjs BUILD_REPORT [MANIFEST]');
  const result = removeCopiedHaps(reportFile);
  if (manifestFile) {
    fs.mkdirSync(path.dirname(path.resolve(manifestFile)), { recursive: true });
    fs.writeFileSync(path.resolve(manifestFile), JSON.stringify(result, null, 2) + '\n');
  }
  console.log(JSON.stringify(result));
}

module.exports = { removeCopiedHaps };
