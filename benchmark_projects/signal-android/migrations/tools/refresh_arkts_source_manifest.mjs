import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const project = path.resolve(process.argv[2] ?? '');
if (!project || !fs.existsSync(project)) throw new Error('usage: refresh_arkts_source_manifest.mjs <candidate-project>');
const sourceRoot = path.join(project, 'entry', 'src', 'main', 'ets');
const appPath = path.join(project, 'AppScope', 'app.json5');
const app = JSON.parse(fs.readFileSync(appPath, 'utf8'));
const files = [];
const visit = directory => {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === '.benchmark-evaluator') continue;
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) visit(target);
    else if (/\.(?:ets|ts)$/.test(entry.name)) {
      const bytes = fs.readFileSync(target);
      files.push({
        path: path.relative(project, target),
        sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
        bytes: bytes.length
      });
    }
  }
};
visit(sourceRoot);
files.sort((left, right) => left.path.localeCompare(right.path));
const manifest = {
  schemaVersion: 1,
  platform: 'arkts',
  bundleName: app.app.bundleName,
  apiVersion: 23,
  sourceObserver: false,
  files
};
fs.writeFileSync(path.join(project, 'SOURCE_MANIFEST.json'), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ project, bundleName: manifest.bundleName, files: files.length })}\n`);
