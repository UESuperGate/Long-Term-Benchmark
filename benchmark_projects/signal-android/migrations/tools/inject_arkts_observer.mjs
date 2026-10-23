import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const [projectArg, observerArg] = process.argv.slice(2);
if (!projectArg || !observerArg) throw new Error('usage: inject_arkts_observer.mjs <project> <observer>');

const project = path.resolve(projectArg);
const observer = path.resolve(observerArg);
const source = fs.readFileSync(observer, 'utf8');
const functionName = source.includes('runMediaSemanticObserver')
  ? 'runMediaSemanticObserver'
  : source.includes('runStickerSemanticObserver')
    ? 'runStickerSemanticObserver'
    : null;
if (!functionName) throw new Error(`observer entrypoint unavailable: ${observer}`);

const targetDirectory = path.join(project, 'entry', 'src', 'main', 'ets', '.benchmark-evaluator');
fs.rmSync(targetDirectory, { recursive: true, force: true });
fs.mkdirSync(targetDirectory, { recursive: true });
fs.copyFileSync(observer, path.join(targetDirectory, 'RuntimeObserver.ets'));

const indexPath = path.join(project, 'entry', 'src', 'main', 'ets', 'pages', 'Index.ets');
let index = fs.readFileSync(indexPath, 'utf8');
const importLine = `import { ${functionName} } from '../.benchmark-evaluator/RuntimeObserver';\n`;
if (index.includes('.benchmark-evaluator/RuntimeObserver')) throw new Error('observer already injected');
index = importLine + index;
const ownerAppear = 'this.owner.appear();';
if (!index.includes(ownerAppear)) {
  throw new Error('page_owner_binding_unavailable: Index must expose owner.appear() from aboutToAppear');
}
index = index.replace(ownerAppear, `${ownerAppear}\n    ${functionName}(this.owner);`);
fs.writeFileSync(indexPath, index);
