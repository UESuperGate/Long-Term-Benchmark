'use strict';
// Eligibility for native discovery only. Actual launch/window/state checks remain mandatory.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const root = path.resolve(__dirname, '../..');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const requireBinding = (value, message) => { if (!value) throw new Error('Task08 native entry binding: ' + message); };

function validateTask08EntryBinding(build, benchmarkRoot = root) {
  requireBinding(build.taskId === '08_threads' && ['base', 'final', 'agent'].includes(build.role), 'wrong task/role');
  requireBinding(build.compileOnly !== true && build.task13Revision5?.compileOnly !== true &&
    build.task08Revision5?.compileOnly !== true, 'compile-only scaffold is not original entry');
  requireBinding(build.status === 'built_not_executed' && build.runtimeCompile?.passed === true &&
    build.productionUnchanged === true && build.copiedProductionUnchanged === true && build.temporaryProjectRemoved === true,
    'incomplete build/source provenance');
  const strict = build.task08Strict, observer = build.nativeUIObserver, config = observer?.config;
  requireBinding(strict?.role === build.role && strict.caseCount === 9 && strict.caseSelection === 'all' &&
    observer?.role === build.role && observer.productionUnchanged === true && config?.role === build.role,
    'missing Task08 original-entry observer');
  requireBinding(['base', 'final', 'timeline'].includes(observer.productionVariant) &&
    config.productionVariant === observer.productionVariant && config.bundleName === build.bundleName &&
    config.moduleName === 'entry', 'wrong original application identity');
  const source = fs.realpathSync(build.source);
  const resolve = relative => {
    const file = fs.realpathSync(path.resolve(source, relative));
    requireBinding(file.startsWith(source + path.sep), 'source input escaped candidate');
    return file;
  };
  const app = json5.parse(fs.readFileSync(resolve('AppScope/app.json5'), 'utf8')).app;
  const module = json5.parse(fs.readFileSync(resolve('entry/src/main/module.json5'), 'utf8')).module;
  requireBinding(app.bundleName === build.bundleName && module.name === 'entry' && module.pages === '$profile:main_pages', 'wrong bundle/pages module');
  const main = module.abilities?.find(ability => ability.name === module.mainElement);
  requireBinding(main && typeof main.srcEntry === 'string', 'no original main ability');
  resolve(path.posix.join('entry/src/main', main.srcEntry));
  const pages = json5.parse(fs.readFileSync(resolve('entry/src/main/resources/base/profile/main_pages.json'), 'utf8'));
  requireBinding(Array.isArray(pages.src) && pages.src.includes('pages/Index'), 'no original Index route');
  const pagePath = 'entry/src/main/ets/pages/Index.ets';
  const page = ts.createSourceFile(pagePath, fs.readFileSync(resolve(pagePath), 'utf8'), ts.ScriptTarget.Latest, true);
  const imports = new Map();
  for (const node of page.statements) if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
    const names = node.importClause?.namedBindings;
    if (names && ts.isNamedImports(names)) for (const item of names.elements) {
      const original = item.propertyName?.text || item.name.text;
      const relative = path.posix.normalize(path.posix.join(path.posix.dirname(pagePath), node.moduleSpecifier.text)) + '.ets';
      requireBinding(!imports.has(original), 'ambiguous original import');
      imports.set(original, { local: item.name.text, relative });
    }
  }
  const variant = observer.productionVariant;
  const symbols = variant === 'timeline' ? ['ThreadTimelinePresenter', 'RoomTimelinePresenter'] :
    variant === 'final' ? ['ThreadPresenter'] : ['RoomTimelinePresenter'];
  const modules = new Map();
  for (const symbol of symbols) {
    const imported = imports.get(symbol);
    requireBinding(imported, 'no original imported ' + symbol);
    const file = resolve(imported.relative);
    const ast = ts.createSourceFile(imported.relative, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    requireBinding(ast.statements.some(node => ts.isClassDeclaration(node) && node.name?.text === symbol &&
      node.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword)), 'no original exported ' + symbol);
    modules.set(symbol, imported.relative);
  }
  const url = relative => '@bundle:' + build.bundleName + '/entry/' + relative.replace(/^entry\/src\/main\//, '').replace(/\.ets$/, '');
  if (variant === 'timeline') {
    requireBinding(config.timelineModuleUrl === url(modules.get('ThreadTimelinePresenter')) &&
      config.roomModuleUrl === url(modules.get('RoomTimelinePresenter')) &&
      config.productionModuleUrl === config.roomModuleUrl, 'mismatched original timeline/room module');
  } else requireBinding(config.productionModuleUrl === url(modules.get(symbols[0])) &&
    config.timelineModuleUrl === null && config.roomModuleUrl === null, 'mismatched original presenter module');
  const sources = [pagePath, ...new Set(modules.values())].sort();
  requireBinding(Array.isArray(observer.sources) && observer.sources.length === sources.length &&
    JSON.stringify(observer.sources.map(item => item.path).sort()) === JSON.stringify(sources), 'missing/extra original source binding');
  for (const item of observer.sources) requireBinding(hash(resolve(item.path)) === item.sha256 &&
    observer.production?.some(entry => entry.path === item.path && entry.sha256 === item.sha256) &&
    build.production?.some(entry => entry.path === item.path && entry.sha256 === item.sha256), 'original source hash mismatch');
  const installer = path.resolve(benchmarkRoot, 'state_tests/runtime/arkts/native/task08_strict/Task08StrictNativeUi.install.cjs');
  requireBinding(observer.installer?.file === installer && observer.installer.sha256 === hash(installer) &&
    strict.installer?.sha256 === observer.installer.sha256, 'wrong/missing original-entry installer');
  requireBinding(Array.isArray(observer.fixtures) && observer.fixtures.length > 0 &&
    observer.fixtures.every(item => item.sha256 === hash(item.file)), 'native fixture hash mismatch');
  return { schema: 'task08.original-entry-eligibility.v3', taskId: build.taskId, role: build.role,
    source, bundleName: build.bundleName, route: 'pages/Index', productionVariant: variant,
    originalSources: observer.sources, nativeEntryExecuted: false,
    subsequentNativeLaunchWindowStateAndSourceProofRequired: true };
}

module.exports = { validateTask08EntryBinding };
