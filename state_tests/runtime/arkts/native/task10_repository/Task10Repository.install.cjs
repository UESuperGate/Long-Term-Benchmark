'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const plugin = '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/';
const ts = require(plugin + 'typescript');
const json5 = require(plugin + 'json5');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');

function importBindings(work) {
  const page = 'entry/src/main/ets/pages/Index.ets';
  const text = fs.readFileSync(path.join(work, page), 'utf8');
  const ast = ts.createSourceFile(page, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const imports = ast.statements.filter(node => ts.isImportDeclaration(node) &&
    ts.isStringLiteral(node.moduleSpecifier) && node.moduleSpecifier.text.startsWith('.'));
  return imports.map(node => {
    const relative = path.posix.normalize(path.posix.join(path.posix.dirname(page), node.moduleSpecifier.text));
    if (!relative.startsWith('entry/src/main/ets/')) throw new Error('Original page import escapes production root');
    const file = ['.ets', '.ts'].map(ext => relative + ext).find(file => fs.existsSync(path.join(work, file)));
    if (!file) throw new Error('Original page import unavailable: ' + relative);
    return { path: file, sha256: sha(fs.readFileSync(path.join(work, file))),
      modulePath: file.replace('entry/src/main/', '').replace(/\.(ets|ts)$/, '') };
  });
}

function install(work, role) {
  const app = json5.parse(fs.readFileSync(path.join(work, 'AppScope/app.json5'), 'utf8')).app;
  const main = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/module.json5'), 'utf8')).module;
  const profile = /^\$profile:(\w+)$/.exec(main.pages);
  if (!profile || !['base', 'final', 'agent'].includes(role)) throw new Error('Explicit source identity/role required');
  const routes = json5.parse(fs.readFileSync(path.join(work, 'entry/src/main/resources/base/profile/' + profile[1] + '.json'), 'utf8')).src;
  const sources = importBindings(work);
  const config = { role, bundleName: app.bundleName, moduleName: main.name, abilityName: main.mainElement,
    entryRoute: 'pages/Index', allowedRoutes: routes, productionSources: sources,
    moduleUrls: sources.map(item => '@bundle:' + app.bundleName + '/' + main.name + '/' + item.modulePath) };
  const target = path.join(work, 'entry/src/test');
  const bundleFile = path.join(target, 'native-bundle.js');
  const suiteFile = path.join(target, 'NativeBundle.test.ets');
  const bundle = fs.readFileSync(bundleFile, 'utf8');
  const suite = fs.readFileSync(suiteFile, 'utf8');
  const nav = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const run = 'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge,';
  const entry = 'export default function nativeBundleTests(): void {';
  for (const [text, token] of [[bundle, nav], [bundle, run], [suite, entry]])
    if (text.split(token).length !== 2) throw new Error('Device evaluator lifecycle changed');
  const fixtures = [];
  for (const [name, source] of [
    ['Task10RepositoryDevice.js', path.join(__dirname, 'Task10RepositoryDevice.js')],
    ['Task10RepositoryDevice.d.ts', path.join(__dirname, 'Task10RepositoryDevice.d.ts')],
    ['Task10RepositoryInput.js', path.join(__dirname, 'Task10RepositoryInput.js')],
    ['Task10RepositorySuite.js', path.join(__dirname, 'Task10RepositorySuite.js')],
    ['Task11Session.js', path.join(__dirname, '../task11_strict/Task11Session.js')],
    ['Task11Tree.js', path.join(__dirname, '../task11_strict/Task11Tree.js')]
  ]) {
    const bytes = fs.readFileSync(source);
    fs.writeFileSync(path.join(target, name), bytes, { flag: 'wx' });
    fixtures.push({ path: 'entry/src/test/' + name, source, sha256: sha(bytes) });
  }
  fs.writeFileSync(bundleFile, "import { attachTask10Repository } from './Task10RepositoryDevice';\n" + bundle
    .replace(nav, 'attachTask10Repository(bridge, taskId, caseSpec);')
    .replace(run, 'const adapter = { runCase: context => bridge.evaluateTask10Repository({ ...context, native: bridge,'));
  fs.writeFileSync(suiteFile, "import { configureTask10Repository } from './Task10RepositoryDevice';\n" + suite
    .replace(entry, entry + '\nconfigureTask10Repository(' + JSON.stringify(JSON.stringify(config)) + ');'));
  for (const item of sources) if (sha(fs.readFileSync(path.join(work, item.path))) !== item.sha256)
    throw new Error('Evaluator changed production');
  return { config, fixtures, productionUnchanged: true, binding: 'original_page_import_graph_and_loaded_callable_runtime' };
}
module.exports = { install, importBindings };
