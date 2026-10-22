#!/usr/bin/env node
'use strict';

// Keep V1's audited lifecycle, certificate cleanup and transcript redaction;
// only bind it to the V2 provider implementation and version labels.
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');

const sourceFile = path.join(__dirname, 'task14_matrix_provider_host_v1.cjs');
let source = fs.readFileSync(sourceFile, 'utf8');
const replacements = [
  ["require('./task14_matrix_provider_v1.cjs')", "require('./task14_matrix_provider_v2.cjs')"],
  [/task14_matrix_provider_host_v1/g, 'task14_matrix_provider_host_v2']
];
for (const [before, after] of replacements) {
  if (typeof before === 'string' && source.split(before).length !== 2) {
    throw new Error('Task14 provider host V2 derivation changed: ' + before);
  }
  source = source.replace(before, after);
}

const derived = new Module(__filename + ':derived', module);
derived.filename = sourceFile;
derived.paths = module.paths;
derived._compile(source, sourceFile);

if (require.main === module) {
  derived.exports.runHost(derived.exports.parseArguments(process.argv.slice(2))).catch(error => {
    process.stderr.write(`Task14 provider host V2 failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}

module.exports = derived.exports;
