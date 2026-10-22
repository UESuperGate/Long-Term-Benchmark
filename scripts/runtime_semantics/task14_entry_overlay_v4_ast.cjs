'use strict';
// SDK parser ONLY: no checker, transform, ABC/HAP compile, renderer, device, or score.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const sdk = path.join(process.env.HOME, 'Library/OpenHarmony/Sdk/23/ets/build-tools/ets-loader');
const parserPath = path.join(sdk, 'node_modules/typescript/lib/typescript.js');
const ts = require(parserPath);
const components = fs.readdirSync(path.join(sdk, 'components')).filter(name => name.endsWith('.json'))
  .map(name => JSON.parse(fs.readFileSync(path.join(sdk, 'components', name), 'utf8')).name).filter(Boolean);

function parse(file, source = fs.readFileSync(file, 'utf8')) {
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.ETS, {ets: {components}});
  if (ast.parseDiagnostics.length) throw Error(JSON.stringify(ast.parseDiagnostics.map(row => ({file,
    location: ast.getLineAndCharacterOfPosition(row.start), message: ts.flattenDiagnosticMessageText(row.messageText, ' ')}))));
  return ast;
}

function walk(node, callback) { callback(node); ts.forEachChild(node, child => walk(child, callback)); }

function inventory(file, source) {
  const ast = parse(file, source), controls = [];
  walk(ast, node => {
    if (!ts.isEtsComponentExpression(node) || !['Button', 'TextInput'].includes(node.expression.getText(ast))) return;
    const attrs = {};
    let current = node;
    while (current.parent && ts.isPropertyAccessExpression(current.parent) && current.parent.expression === current) {
      const member = current.parent, call = member.parent;
      if (!ts.isCallExpression(call)) break;
      attrs[member.name.text] = call.arguments.map(arg => arg.getText(ast));
      current = call;
    }
    controls.push({type: node.expression.getText(ast), position: node.pos, attrs});
  });
  return controls;
}

function assertClosed(file, source, expectedIds) {
  const controls = inventory(file, source);
  const ids = controls.map(row => {
    if (!row.attrs.id || row.attrs.id.length !== 1) throw Error('Unbound interactive control');
    return row.attrs.id[0];
  });
  if (JSON.stringify(ids.slice().sort()) !== JSON.stringify(expectedIds.slice().sort())) throw Error('Unknown/renamed/extra control');
  return controls;
}

function graph(project) {
  const root = path.join(project, 'entry/src/main/ets');
  const pages = JSON.parse(fs.readFileSync(path.join(project, 'entry/src/main/resources/base/profile/main_pages.json'), 'utf8')).src;
  const pending = [...pages.map(page => page + '.ets'), 'entryability/EntryAbility.ets'], seen = new Set(), rows = [];
  while (pending.length) {
    const name = pending.shift();
    if (seen.has(name)) continue;
    seen.add(name);
    if (name.startsWith('../') || path.isAbsolute(name)) throw Error('Import leaves project');
    const file = path.join(root, name), ast = parse(file), imports = [], constructors = [];
    for (const statement of ast.statements) {
      if ((ts.isImportDeclaration(statement) || ts.isExportDeclaration(statement)) && statement.moduleSpecifier) {
        if (!ts.isStringLiteral(statement.moduleSpecifier)) throw Error('Nonliteral import');
        const specifier = statement.moduleSpecifier.text;
        imports.push(specifier);
        if (specifier.startsWith('.')) pending.push(path.posix.normalize(path.posix.join(path.posix.dirname(name), specifier)) + '.ets');
      }
    }
    walk(ast, node => { if (ts.isNewExpression(node)) constructors.push(node.expression.getText(ast)); });
    rows.push({path: name, imports, constructors});
  }
  return rows.sort((a, b) => a.path.localeCompare(b.path));
}

function identity(file) {
  const bytes = fs.readFileSync(file);
  return {path: file, bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex')};
}

function describe(project) {
  const rows = graph(project), root = path.join(project, 'entry/src/main/ets');
  return {scope: 'OFFLINE_SOURCE_CLOSURE_ONLY_NOT_NATIVE_OR_RENDERED_EVIDENCE',
    parser: identity(parserPath),
    componentRegistry: fs.readdirSync(path.join(sdk, 'components')).filter(name => name.endsWith('.json')).sort()
      .map(name => identity(path.join(sdk, 'components', name))),
    modules: rows.map(row => ({...row, identity: identity(path.join(root, row.path)),
      controls: row.path.startsWith('pages/') ? inventory(path.join(root, row.path)) : []})),
    compiled: false, nativeOrRenderedExecution: false, ready: false};
}

module.exports = {ts, parserPath, parse, walk, inventory, assertClosed, graph, describe};
if (require.main === module) process.stdout.write(JSON.stringify(describe(path.resolve(process.argv[2]))));
