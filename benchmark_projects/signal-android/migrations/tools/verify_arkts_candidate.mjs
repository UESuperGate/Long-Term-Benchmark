import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const project = path.resolve(process.argv[2] ?? '');
const manifestPath = process.argv[3] ? path.resolve(process.argv[3]) : path.join(project, 'SOURCE_MANIFEST.json');
const appPath = path.join(project, 'AppScope', 'app.json5');
if (!fs.existsSync(manifestPath)) throw new Error('candidate_source_manifest_missing');
if (!fs.existsSync(appPath)) throw new Error('candidate_identity_missing');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const app = JSON.parse(fs.readFileSync(appPath, 'utf8'));
if (!app.app?.bundleName || app.app.bundleName !== manifest.bundleName) throw new Error('candidate_identity_missing');
for (const item of manifest.files) {
  const target = path.join(project, item.path);
  if (!fs.existsSync(target)) throw new Error('candidate_source_provenance_mismatch');
  const bytes = fs.readFileSync(target);
  const hash = crypto.createHash('sha256').update(bytes).digest('hex');
  if (hash !== item.sha256 || bytes.length !== item.bytes) throw new Error('candidate_source_provenance_mismatch');
}
process.stdout.write(`${JSON.stringify({ status: 'verified', bundleName: manifest.bundleName, sourceCount: manifest.files.length })}\n`);
