import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const arg = flag => process.argv[process.argv.indexOf(flag) + 1];
const optional = flag => process.argv.includes(flag) ? arg(flag) : null;
const platform = arg('--platform');
const taskId = arg('--task-id');
const project = path.resolve(arg('--project'));
const migration = path.resolve(arg('--migration'));
const probeProfile = optional('--probe-profile') ?? 'formal-agent';
if (!['android', 'arkts'].includes(platform)) throw new Error('platform must be android or arkts');
if (!['01_media_keyboard', '02_sticker_management'].includes(taskId)) throw new Error('unsupported task id');
if (!['formal-agent', 'calibration-base-control'].includes(probeProfile)) throw new Error('unsupported probe profile');
if (!fs.statSync(project).isDirectory()) throw new Error('agent project is not a directory');
if (['base', 'final'].includes(path.basename(project))) throw new Error('refusing to inject a hidden agent harness into a calibration base/final root');

const forbiddenNames = new Set(['transitions.json', 'transitions.draft.json', 'observer_rules.json', 'task.json', 'evidence.json']);
const inspect = directory => {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === '.benchmark-evaluator' || entry.name === 'build' || entry.name === '.hvigor') continue;
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) inspect(target);
    else if (forbiddenNames.has(entry.name)) throw new Error(`agent candidate contains evaluator oracle material: ${target}`);
  }
};
inspect(project);

const hidden = path.join(project, '.benchmark-evaluator');
fs.rmSync(hidden, { recursive: true, force: true });
fs.mkdirSync(hidden, { recursive: true });
const injectedRoots = [hidden];
const wiringFiles = [];
let probeMainClass = null;
let bindingContract = null;

if (platform === 'android') {
  const bindings = [
    {
      id: 'public-integration-contract',
      evaluator: 'final',
      probeMainClass: taskId === '01_media_keyboard'
        ? 'benchmark.evaluator.ImmutableMediaProbeKt'
        : 'benchmark.evaluator.ImmutableStickerProbeKt'
    },
    {
      id: 'reachable-legacy-production-prefix',
      evaluator: 'base',
      probeMainClass: taskId === '01_media_keyboard'
        ? 'benchmark.evaluator.ImmutableMediaProbeKt'
        : 'org.thoughtcrime.securesms.stickers.ImmutableStickerBaseProbeKt'
    },
    {
      id: 'mandatory-public-abi-runtime-gate',
      evaluator: taskId === '01_media_keyboard' ? 'base' : 'runtime-gate',
      probeMainClass: taskId === '01_media_keyboard'
        ? 'benchmark.evaluator.ImmutableMediaProbeKt'
        : 'benchmark.evaluator.MandatoryStickerContractProbeKt'
    }
  ];
  const candidates = probeProfile === 'calibration-base-control' ? bindings.slice(1, 2) : bindings;
  const bindingsRoot = path.join(hidden, 'bindings');
  for (const candidate of candidates) {
    const target = path.join(bindingsRoot, candidate.id);
    fs.cpSync(path.join(migration, 'android', 'evaluator', candidate.evaluator), target, { recursive: true });
  }
  const contractPath = path.resolve(migration, '..', '..', 'tasks', taskId, 'integration_contract.md');
  const contractBytes = fs.readFileSync(contractPath);
  bindingContract = {
    path: path.relative(path.resolve(migration, '..', '..'), contractPath),
    sha256: crypto.createHash('sha256').update(contractBytes).digest('hex'),
    policy: probeProfile === 'calibration-base-control'
      ? 'explicit_reachable_legacy_prefix_control'
      : 'compile_compatible_public_action_bridge_without_source_role_inference',
    candidates: candidates.map(candidate => ({
      id: candidate.id,
      sourceDirectory: path.relative(hidden, path.join(bindingsRoot, candidate.id)),
      probeMainClass: candidate.probeMainClass
    }))
  };
} else {
  const sourceRole = probeProfile === 'calibration-base-control' ? 'base' : 'final';
  const source = path.join(migration, 'arkts', 'evaluator', sourceRole, 'RuntimeObserver.ets');
  const targetDirectory = path.join(project, 'entry', 'src', 'main', 'ets', '.benchmark-evaluator');
  fs.rmSync(targetDirectory, { recursive: true, force: true });
  fs.mkdirSync(targetDirectory, { recursive: true });
  injectedRoots.push(targetDirectory);
  fs.copyFileSync(source, path.join(targetDirectory, 'RuntimeObserver.ets'));

  const indexPath = path.join(project, 'entry', 'src', 'main', 'ets', 'pages', 'Index.ets');
  let index = fs.readFileSync(indexPath, 'utf8');
  const functionName = taskId === '01_media_keyboard' ? 'runMediaSemanticObserver' : 'runStickerSemanticObserver';
  const importLine = `import { ${functionName} } from '../.benchmark-evaluator/RuntimeObserver';\n`;
  if (!index.includes(importLine.trim())) index = importLine + index;
  const ownerAppear = 'this.owner.appear();';
  if (!index.includes(ownerAppear)) {
    throw new Error('page_owner_binding_unavailable: candidate page has no executable owner.appear() binding');
  }
  index = index.replace(ownerAppear, `${ownerAppear}\n    ${functionName}(this.owner);`);
  fs.writeFileSync(indexPath, index);
  wiringFiles.push(indexPath);
}

const injectedFiles = [];
const collect = directory => {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) collect(target);
    else injectedFiles.push(path.relative(project, target));
  }
};
for (const root of injectedRoots) collect(root);
injectedFiles.sort();
const injectedText = injectedFiles.map(file => fs.readFileSync(path.join(project, file), 'utf8')).join('\n');
if (/traceDigest|\bexpected\b|\boracle\b/.test(injectedText)) {
  throw new Error('hidden probe unexpectedly contains expected/oracle material');
}
const fileRecord = file => {
  const bytes = fs.readFileSync(file);
  return {
    path: path.relative(project, file),
    bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex')
  };
};
fs.writeFileSync(path.join(hidden, 'PREPARED'), `${JSON.stringify({
  schemaVersion: 1,
  taskId,
  platform,
  probeProfile,
  classification: 'evaluator_owned_hidden_probe_and_build_wiring',
  containsExpectedOracle: false,
  productionLogicInjected: false,
  probeMainClass,
  bindingContract,
  injectedRoots: injectedRoots.map(root => path.relative(project, root)),
  files: injectedFiles,
  injectedFileRecords: injectedFiles.map(file => fileRecord(path.join(project, file))),
  wiringFileRecords: wiringFiles.map(fileRecord)
}, null, 2)}\n`);

