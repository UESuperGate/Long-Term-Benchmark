'use strict';

const fs = require('node:fs');
const path = require('node:path');
const ts = require('/Users/z1an/Library/OpenHarmony/Sdk/23/ets/build-tools/ets-loader/node_modules/typescript');

function bind(source, observedBinding) {
  if (!['base', 'final'].includes(observedBinding)) throw new Error('Actual Task13 entry binding is unreviewed');
  const page = path.join(source, 'entry/src/main/ets/pages/Index.ets');
  const ast = ts.createSourceFile(page, fs.readFileSync(page, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const imports = new Map();
  for (const statement of ast.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
    const named = statement.importClause?.namedBindings;
    if (!named || !ts.isNamedImports(named)) continue;
    for (const item of named.elements) {
      const exported = (item.propertyName || item.name).text;
      if (imports.has(exported)) throw new Error('Ambiguous actual page module import');
      imports.set(exported, statement.moduleSpecifier.text);
    }
  }
  const required = observedBinding === 'base' ? ['UserProfilePresenter', 'UserProfileGateway', 'getRoomIdentityDataSource'] :
    ['UserVerificationPresenter', 'VerificationGateway', 'IdentityStateStore', 'VerificationRequest'];
  const modules = required.map(name => imports.get(name));
  if (modules.some(name => typeof name !== 'string' || !name.startsWith('.')) || new Set(modules).size !== 1) {
    throw new Error('Actual page presenter/SDK module binding unsupported; NOT_SCORED');
  }
  const resolved = path.resolve(path.dirname(page), modules[0]);
  const file = resolved.endsWith('.ets') ? resolved : resolved + '.ets';
  if (!file.startsWith(path.resolve(source, 'entry/src/main/ets') + path.sep) || !fs.statSync(file).isFile()) {
    throw new Error('Actual page import leaves production ArkTS closure');
  }
  return { observedBinding, page: 'entry/src/main/ets/pages/Index.ets',
    productionFeaturePath: path.relative(source, file),
    productionModuleSuffix: path.relative(path.join(source, 'entry/src/main'), file).replace(/\.ets$/, ''),
    requiredExports: required, evidence: 'Structured page import binding only; never a semantic/source observer' };
}

module.exports = { bind };
