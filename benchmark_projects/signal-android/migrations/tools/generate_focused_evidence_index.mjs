import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const value = flag => process.argv[process.argv.indexOf(flag) + 1];
const migration = path.resolve(value('--migration'));
const taskId = path.basename(migration);
const output = path.join(migration, 'provenance', 'evidence-index.json');
const roots = ['canonical', 'results', 'provenance'];
const fixed = ['manifest.json', 'execution.json', 'materialize.sh', 'reproduce.sh', 'android/task.json', 'android/UPSTREAM_PROVENANCE.json', 'android/TEST_DESIGN.md'];

const paths = [...fixed];
for (const root of roots) {
  const visit = current => {
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const absolute = path.join(current, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else paths.push(path.relative(migration, absolute));
    }
  };
  visit(path.join(migration, root));
}
for (const role of ['base', 'final']) {
  for (const name of ['IMMUTABLE_SOURCES.json', 'VERIFIED_PRODUCTION_PATHS.json', 'VERIFIED_TEST_PATHS.json']) {
    paths.push(`android/${role}/${name}`);
  }
}

const records = [...new Set(paths)]
  .filter(relative => relative !== 'provenance/evidence-index.json')
  .filter(relative => fs.existsSync(path.join(migration, relative)))
  .sort()
  .map(relative => {
    const bytes = fs.readFileSync(path.join(migration, relative));
    return { path: relative, bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
  });

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify({
  schemaVersion: 1,
  taskId,
  generatedAt: new Date().toISOString(),
  records,
  retainedBinaryArtifacts: [],
  binaryHashesRetainedIn: 'provenance/build-evidence.json'
}, null, 2)}\n`);
