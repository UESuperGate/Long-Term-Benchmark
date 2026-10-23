#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { basename, dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectDirectory = resolve(scriptDirectory, '..');
const outputPath = resolve(projectDirectory, 'DELIVERY_MANIFEST.json');
const excludedNames = new Set(['debug.keystore']);

function isExcluded(path) {
  return path === outputPath || path.endsWith('.log') || excludedNames.has(basename(path));
}

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    const path = resolve(directory, entry.name);
    if (isExcluded(path)) {
      continue;
    }
    if (entry.isDirectory()) {
      files.push(...await collectFiles(path));
    } else if (entry.isFile()) {
      files.push(path);
    }
  }

  return files;
}

const files = await collectFiles(projectDirectory);
const manifestEntries = [];

for (const path of files) {
  const contents = await readFile(path);
  manifestEntries.push({
    path: relative(projectDirectory, path),
    bytes: contents.byteLength,
    sha256: createHash('sha256').update(contents).digest('hex')
  });
}

const manifest = {
  schemaVersion: 1,
  projectId: 'signal-android',
  scope: 'benchmark_projects/signal-android/**',
  excludes: ['DELIVERY_MANIFEST.json', '**/*.log', '**/debug.keystore'],
  fileCount: manifestEntries.length,
  files: manifestEntries
};

await writeFile(outputPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
console.log(JSON.stringify({ output: outputPath, fileCount: manifestEntries.length }));
