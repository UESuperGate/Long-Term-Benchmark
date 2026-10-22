'use strict';
const fs = require('node:fs');
const path = require('node:path');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');

function exportedClass(work, name) {
  const root = fs.realpathSync(work), matches = [];
  function visit(directory) {
    for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, item.name);
      if (item.isSymbolicLink()) throw new Error('Candidate API symlink unsupported');
      if (item.isDirectory()) visit(file);
      else if (/\.(ets|ts)$/.test(file)) {
        const tree = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
        for (const node of tree.statements) if (ts.isClassDeclaration(node) && node.name?.text === name &&
            node.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword)) {
          const constructor = node.members.find(ts.isConstructorDeclaration);
          matches.push({ path: path.relative(root, file),
            parameters: constructor ? constructor.parameters.map(parameter => parameter.name.getText(tree)) : [],
            methods: node.members.filter(ts.isMethodDeclaration).map(method => method.name.getText(tree)) });
        }
      }
    }
  }
  visit(path.join(root, 'entry/src/main/ets'));
  if (matches.length !== 1) throw new Error('Candidate has no unique exported ' + name + ' binding');
  return matches[0];
}

function reaches(work, entry, target) {
  const root = fs.realpathSync(work), seen = new Set();
  function visit(relative) {
    const file = path.resolve(root, relative);
    if (!file.startsWith(root + path.sep)) throw new Error('Candidate import escaped source root');
    if (seen.has(file)) return false;
    seen.add(file);
    if (relative === target) return true;
    const tree = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    for (const node of tree.statements) if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const request = node.moduleSpecifier.text;
      if (!request.startsWith('.')) continue;
      const stem = path.resolve(path.dirname(file), request);
      const found = [stem, stem + '.ets', stem + '.ts'].find(candidate => fs.existsSync(candidate) && fs.statSync(candidate).isFile());
      if (!found) throw new Error('Unbound candidate import: ' + request);
      if (visit(path.relative(root, found))) return true;
    }
    return false;
  }
  return visit(entry);
}

module.exports = { exportedClass, reaches };
