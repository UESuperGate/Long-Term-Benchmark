'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const digest = text => crypto.createHash('sha256').update(text).digest('hex');

function notificationConstants() {
  const file = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/ets/api/@ohos.notification.d.ts');
  const source = fs.readFileSync(file, 'utf8');
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  let declaration;
  function visit(node) {
    if (ts.isEnumDeclaration(node) && node.name.text === 'SlotType') declaration = node;
    ts.forEachChild(node, visit);
  }
  visit(ast);
  if (!declaration) throw new Error('SDK notification SlotType enum missing');
  const values = {};
  for (const member of declaration.members) {
    if (!member.initializer || !ts.isNumericLiteral(member.initializer)) {
      throw new Error('Unsupported SDK SlotType initializer: ' + member.getText(ast));
    }
    values[member.name.text] = Number(member.initializer.text);
  }
  return { file, sha256: digest(source), module: '@ohos.notification', export: 'SlotType', values };
}

function selectedTasks(taskSelection) {
  const catalog = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/extraction_catalog.json'), 'utf8'));
  if (taskSelection === 'all') return catalog.acceptedTaskIds;
  // Explicit single-task replay remains available for historical diagnostics.
  if (!/^\d\d_[a-z0-9_]+$/.test(taskSelection) ||
      !fs.existsSync(path.join(root, 'benchmark_tasks', taskSelection, 'task.json')))
    throw new Error(`No selected tasks: ${taskSelection}`);
  return [taskSelection];
}

function generate(work, evidence, taskSelection = '12_report_room', roleSelection = 'final', sourceOverride = null, nativeUI = false, options = {}) {
  const roles = roleSelection === 'all' ? ['base', 'final', 'agent'] : [roleSelection];
  if (roles.some(role => !['base', 'final', 'agent'].includes(role))) throw new Error('Unknown role');
  const tasks = selectedTasks(taskSelection);
  if (options.contractOverride && tasks.length !== 1) throw new Error('Contract override requires one selected task');
  if (!tasks.length) throw new Error(`No selected tasks: ${taskSelection}`);
  if (sourceOverride && (tasks.length !== 1 || roles.length !== 1)) throw new Error('--source requires one --bundle task and one --role');
  if (nativeUI && (tasks.length !== 1 || roles.length !== 1)) throw new Error('--native-ui requires one --bundle task and one --role');
  const factories = [], contracts = {}, metadata = {}, adapters = {};
  const manifest = { taskSelection, roles, generatedAt: new Date().toISOString(), production: [], adapters: [], evaluator: [], candidates: [], contracts: [] };
  const notification = notificationConstants();
  manifest.platformConstants = [notification];
  const platformConstants = { [notification.module]: { SlotType: notification.values } };
  for (const group of ['tasks08_11', 'tasks12_15', 'tasks16_18']) {
    const file = path.join(root, 'state_tests/runtime/arkts', group + '.cjs');
    const source = fs.readFileSync(file, 'utf8');
    const transformed = ts.transpileModule(source, {
      fileName: group + '.js',
      compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, allowJs: true },
      transformers: { before: [context => sourceFile => {
        const visit = node => {
          if (ts.isMethodDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === 'delete') {
            return ts.factory.updateMethodDeclaration(node, node.modifiers, node.asteriskToken,
              ts.factory.createStringLiteral('delete'), node.questionToken, node.typeParameters,
              node.parameters, node.type, ts.visitEachChild(node.body, visit, context));
          }
          return ts.visitEachChild(node, visit, context);
        };
        return ts.visitNode(sourceFile, visit);
      }] }
    }).outputText;
    adapters[group] = transformed;
    manifest.adapters.push({ file, sha256: digest(source), bundledSha256: digest(transformed),
      transform: 'TypeScript ES2020 print; quote delete method name for es2abc parser compatibility' });
  }
  for (const task of tasks) {
    const migration = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks', task, 'task.json'), 'utf8'));
    const contractPath = options.contractOverride ? path.resolve(options.contractOverride) :
      path.join(root, 'benchmark_tasks', task, 'transitions.json');
    const contractSource = fs.readFileSync(contractPath, 'utf8');
    contracts[task] = JSON.parse(contractSource);
    if (contracts[task].taskId !== task) throw new Error('Contract override belongs to a different task');
    manifest.contracts.push({ taskId: task, file: contractPath, sha256: digest(contractSource),
      override: Boolean(options.contractOverride) });
    for (const role of roles) {
    const archivedBase = role === 'agent' && !sourceOverride ? require('./archived_arkts_base.cjs').archivedBase(task) : null;
    const original = sourceOverride ? path.resolve(sourceOverride) : archivedBase?.source || path.join(root, migration.arkts[role === 'final' ? 'finalPath' : 'basePath']);
    const project = path.join(work, '.native-candidates', role, task);
    fs.cpSync(original, project, { recursive: true, filter: file => !['.git', '.hvigor', 'build', 'oh_modules', 'node_modules'].includes(path.basename(file)) });
    const provenance = { taskId: task, role, original, project, sourceOverride: Boolean(sourceOverride) };
    if (archivedBase) provenance.archivedBase = archivedBase;
    if (role === 'agent' && !sourceOverride) {
      const patch = path.join(root, 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/provenance/patches', `arkts_${task}.patch`);
      provenance.patch = patch;
      provenance.patchSha256 = digest(fs.readFileSync(patch));
      execFileSync('git', ['init', '-q', project]);
      execFileSync('git', ['apply', '--binary', patch], { cwd: project });
    }
    manifest.candidates.push(provenance);
    const virtualRoot = '/projects/' + role + '/' + task;
    function visit(directory) {
      if (!fs.existsSync(directory)) return;
      for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        const file = path.join(directory, entry.name);
        if (entry.isDirectory()) { visit(file); continue; }
        if (!/\.(ets|ts)$/.test(file)) continue;
        const source = fs.readFileSync(file, 'utf8');
        const relative = path.relative(project, file);
        const compiled = ts.transpileModule(source, { fileName: file.replace(/\.ets$/, '.ts'), reportDiagnostics: true,
          compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, experimentalDecorators: true } });
        const errors = (compiled.diagnostics || []).filter(item => item.category === ts.DiagnosticCategory.Error);
        if (errors.length) throw new Error(errors.map(item => ts.flattenDiagnosticMessageText(item.messageText, '\n')).join('\n'));
        const id = virtualRoot + '/' + relative;
        metadata[id] = { path: relative, sha256: digest(source) };
        manifest.production.push({ taskId: task, role, file, originalFile: role === 'agent' && !sourceOverride ? null : path.join(original, relative), ...metadata[id], transpiledSha256: digest(compiled.outputText) });
        factories.push(`${JSON.stringify(id)}: function(exports, require, module, getContext) {\n${compiled.outputText}\n}`);
      }
    }
    visit(path.join(project, 'entry/src/main/ets/features'));
    }
  }
  const evaluatorFile = path.join(root, 'scripts/runtime_semantics/arkts_runtime.cjs');
  const evaluator = fs.readFileSync(evaluatorFile, 'utf8');
  const ast = ts.createSourceFile(evaluatorFile, evaluator, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const shared = ['snapshot', 'compareExpected', 'evaluateCase'].map(name => {
    const declaration = ast.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === name);
    if (!declaration) throw new Error(`Evaluator no longer exports ${name}`);
    const source = declaration.getText(ast);
    manifest.evaluator.push({ name, file: evaluatorFile, sha256: digest(source) });
    return source;
  }).join('\n');
  const runtime = fs.readFileSync(path.join(root, 'state_tests/runtime/arkts/native/bundle-runtime.js'), 'utf8');
  const platformFile = path.join(root, 'state_tests/runtime/arkts/native/native-platform.js');
  const platformSandboxRoot = path.join(work, 'native-case-sandboxes');
  fs.mkdirSync(platformSandboxRoot);
  let candidateUI = null;
  if (nativeUI) {
    const candidate = manifest.candidates[0];
    const candidateMain = path.join(candidate.project, 'entry/src/main');
    fs.rmSync(path.join(work, 'entry/src/main'), { recursive: true, force: true });
    fs.cpSync(candidateMain, path.join(work, 'entry/src/main'), { recursive: true });
    const page = 'entry/src/main/ets/pages/Index.ets';
    candidateUI = { route: 'pages/Index', taskId: candidate.taskId, role: candidate.role,
      productionSource: { path: page, sha256: digest(fs.readFileSync(path.join(candidate.project, page))) } };
    manifest.candidateUI = candidateUI;
  }
  manifest.nativeBridge = { file: platformFile, sha256: digest(fs.readFileSync(platformFile)),
    api: 'adapter context.native: context, sandbox, capabilities, fs, preferences, ui, openPreferences, reopenPreferences',
    nativeImports: ['@ohos.file.fs', '@ohos.data.preferences', '@ohos.router', '@ohos.arkui.UIContext'] };
  if (options.device) {
    const devicePlatform = path.join(root, 'state_tests/runtime/arkts/native/native-device-platform.js');
    fs.copyFileSync(devicePlatform, path.join(work, 'entry/src/test/native-device-platform.js'));
    manifest.nativeBridge.deviceModule = { file: devicePlatform, sha256: digest(fs.readFileSync(devicePlatform)) };
    manifest.nativeBridge.nativeImports.push('@ohos.file.fileuri', '@ohos.multimedia.media', '@ohos.notification', '@ohos.app.ability.abilityDelegatorRegistry');
    manifest.requiresFreshInstallPerCase = true;
  }
  const bundle = `import { createNativeContext } from './${options.device ? 'native-device-platform' : 'native-platform'}';\n` +
    `const platformSandboxRoot = ${JSON.stringify(platformSandboxRoot)};\n` +
    `const candidateUI = ${JSON.stringify(candidateUI)};\n` +
    `const factories = {${factories.join(',\n')}};\nconst metadata = ${JSON.stringify(metadata)};\n` +
    `const platformConstants = ${JSON.stringify(platformConstants)};\n` +
    'for (const module of Object.values(platformConstants)) { for (const value of Object.values(module)) Object.freeze(value); Object.freeze(module); }\nObject.freeze(platformConstants);\n' +
    `const contracts = ${JSON.stringify(contracts)};\nconst adapterFactories = {` + Object.entries(adapters)
      .map(([name, code]) => `${JSON.stringify(name)}: function(exports, require, module) {\n${code}\n}`).join(',\n') +
    `};\n${shared}\n${runtime}`;
  const testRoot = path.join(work, 'entry/src/test');
  fs.copyFileSync(platformFile, path.join(testRoot, 'native-platform.js'));
  fs.copyFileSync(path.join(root, 'state_tests/runtime/arkts/native/entry-assertion.js'), path.join(testRoot, 'entry-assertion.js'));
  fs.writeFileSync(path.join(testRoot, 'native-bundle.js'), bundle);
  fs.writeFileSync(path.join(evidence, 'native-bundle.generated.js'), bundle);
  fs.writeFileSync(path.join(testRoot, 'native-bundle.d.ts'), 'export function runNativeCase(taskId: string, role: string, caseId: string): Promise<string>;\n');
  const cases = tasks.flatMap(task => roles.flatMap(role => contracts[task].cases.map(caseSpec => ({ task, role, caseSpec }))))
    .filter(item => !options.caseId || item.caseSpec.caseId === options.caseId);
  if (!cases.length) throw new Error('No selected canonical cases');
  const suite = "import { describe, it, expect } from '@ohos/hypium';\nimport { runNativeCase } from './native-bundle';\n" +
    "export default function nativeBundleTests(): void { describe('NativeAdapterBundle', () => {\n" +
    cases.map(({ task, role, caseSpec }) => `it(${JSON.stringify(role + '__' + caseSpec.caseId)}, 0, async () => {\n` +
      `const result: string = await runNativeCase(${JSON.stringify(task)}, ${JSON.stringify(role)}, ${JSON.stringify(caseSpec.caseId)});\n` +
      `expect(result).assertEqual('executed');\n});`).join('\n') + '\n}); }\n';
  fs.writeFileSync(path.join(testRoot, 'NativeBundle.test.ets'), suite);
  fs.writeFileSync(path.join(testRoot, 'List.test.ets'), "import suite from './NativeBundle.test';\nexport default function testsuite(): void { suite(); }\n");
  manifest.caseCount = cases.length;
  manifest.bundleSha256 = digest(bundle);
  fs.writeFileSync(path.join(evidence, 'bundle-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  fs.writeFileSync(path.join(evidence, 'NativeBundle.generated.test.ets'), suite);
  return manifest;
}

module.exports = { generate, selectedTasks };
