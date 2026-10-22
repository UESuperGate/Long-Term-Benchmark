'use strict';
// Source binding discovery only. It neither approves UI layouts nor scores an
// absent selector. The default Python raw guard still requires a native profile.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const native = path.join(root, 'state_tests/runtime/arkts/native');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');

function tokens(source) {
  const scanner = ts.createScanner(ts.ScriptTarget.Latest, true, ts.LanguageVariant.Standard, source);
  const result = [];
  for (let kind = scanner.scan(); kind !== ts.SyntaxKind.EndOfFileToken; kind = scanner.scan())
    result.push({ kind, text: scanner.getTokenText(), value: scanner.getTokenValue(),
      start: scanner.getTokenPos(), end: scanner.getTextPos() });
  return result;
}
function controls(source, file) {
  const t = tokens(source), result = [];
  const close = (start, left, right) => {
    let depth = 0;
    for (let index = start; index < t.length; index++) {
      if (t[index].text === left) depth++;
      if (t[index].text === right && --depth === 0) return index;
    }
    throw Error('Unbalanced ArkUI control: ' + file);
  };
  for (let index = 0; index < t.length; index++) {
    if (!['Button', 'TextInput', 'Toggle'].includes(t[index].text) || t[index + 1]?.text !== '(') continue;
    const start = index, type = t[index].text, argumentEnd = close(index + 1, '(', ')');
    let end = argumentEnd, chain = [];
    while (t[end + 1]?.text === '.' && t[end + 3]?.text === '(') {
      const begin = end + 2, finish = close(end + 3, '(', ')');
      chain.push({ name: t[begin].text, tokens: t.slice(begin + 2, finish) }); end = finish;
    }
    const ids = chain.filter(item => item.name === 'id');
    if (ids.length > 1 || ids.some(item => item.tokens.length !== 1 || item.tokens[0].kind !== ts.SyntaxKind.StringLiteral))
      throw Error('Dynamic/duplicate control ID unsupported; needs review');
    const label = t[index + 2]?.kind === ts.SyntaxKind.StringLiteral ? t[index + 2].value : null;
    result.push({ file, type, id: ids.length ? ids[0].tokens[0].value : '', label,
      sourceSpan: { start: t[start].start, end: t[end].end }, sourceSha256: hash(source),
      handlers: chain.filter(item => item.name === 'onClick' || item.name === 'onChange')
        .map(item => item.tokens.map(token => token.text)),
      enabled: chain.filter(item => item.name === 'enabled').map(item => item.tokens.map(token => token.text)),
      sourceText: source.slice(t[start].start, t[end].end) });
    // Do not skip nested nodes in callback builders; each is independently inventoried.
  }
  return result;
}
function discover(source) {
  source = fs.realpathSync(source);
  const api = require(path.join(native, 'CandidateApiBindings.cjs'));
  const presenter = api.exportedClass(source, 'AccountDeactivationPresenter');
  const service = api.exportedClass(source, 'AccountClient');
  const entry = 'entry/src/main/ets/pages/Index.ets';
  const files = [], inventory = [];
  function visit(relative) {
    for (const item of fs.readdirSync(path.join(source, relative), { withFileTypes: true })) {
      const name = relative + '/' + item.name;
      if (item.isSymbolicLink()) throw Error('Source binding refuses symlink');
      if (item.isDirectory()) visit(name);
      else if (/\.(ets|ts)$/.test(name)) {
        const text = fs.readFileSync(path.join(source, name), 'utf8');
        const nodes = controls(text, name);
        if (nodes.length && api.reaches(source, entry, name)) {
          inventory.push(...nodes); files.push({ path: name, bytes: Buffer.byteLength(text), sha256: hash(text) });
        }
      }
    }
  }
  visit('entry/src/main/ets');
  const unique = (name, predicate) => {
    const matches = inventory.filter(predicate);
    if (matches.length !== 1) throw Error('No unique actual source binding for ' + name + ': ' + matches.length);
    return matches[0];
  };
  const calls = (node, method) => node.handlers.some(body => body.includes(method));
  const bound = {
    entry: unique('entry', node => node.type === 'Button' && node.label === 'Deactivate account' &&
      (calls(node, 'openForm') || (node.handlers.some(body => body.includes('screen') && body.includes('='))))),
    password: unique('password', node => node.type === 'TextInput' && calls(node, 'setPassword')),
    erase: unique('erase', node => node.type === 'Toggle' && calls(node, 'setEraseData')),
    submit: unique('submit', node => node.type === 'Button' && node.enabled.some(body =>
      body.includes('canSubmit') || body.includes('submitEnabled')) && (calls(node, 'submitDeactivation') || calls(node, 'deactivateAccount'))),
    close: unique('failure close', node => node.type === 'Button' && ['Close', 'Dismiss'].includes(node.label) && calls(node, 'closeDialogs'))
  };
  const owners = [...new Set([bound.password.file, bound.erase.file, bound.submit.file])];
  if (owners.length !== 1) throw Error('Form actions do not share one actual production page/component owner');
  for (const target of [presenter.path, service.path, owners[0]])
    if (!api.reaches(source, entry, target)) throw Error('Unreachable original production namespace: ' + target);
  const ownerFile = owners[0], ownerSource = fs.readFileSync(path.join(source, ownerFile), 'utf8');
  const ownerTokens = tokens(ownerSource), properties = [];
  for (let index = 0; index < ownerTokens.length; index++) {
    if (ownerTokens[index].text === ':' && ownerTokens[index + 1]?.text === 'AccountDeactivationPresenter' &&
        ownerTokens[index + 2]?.text === '=' && ownerTokens[index + 3]?.text === 'new')
      properties.push(ownerTokens[index - 1].text);
  }
  if (properties.length !== 1) throw Error('No unique actual page-owned presenter property');
  const selectors = Object.fromEntries(Object.entries(bound).map(([name, node]) => [name,
    node.id ? { id: node.id } : node.type === 'Button' ? { type: node.type, text: node.label } : { type: node.type }]));
  return { protocol: 'task15.source-owner-bindings.v6', source, presenter, service,
    ownerBinding: { pageSourcePath: ownerFile, pageSourceSha256: hash(ownerSource),
      property: properties[0], presenterSourcePath: presenter.path,
      presenterSourceSha256: hash(fs.readFileSync(path.join(source, presenter.path))),
      serviceSourcePath: service.path, serviceSourceSha256: hash(fs.readFileSync(path.join(source, service.path))) },
    sourceFiles: files.sort((a, b) => a.path.localeCompare(b.path)), controlBindings: bound, controlSelectors: selectors,
    ownerAcquisitionMethods: presenter.methods.filter(name => ['loadCapability', 'refreshAvailability', 'canSubmit', 'submitEnabled'].includes(name)),
    approvedNativeProfile: false, semanticResultFromSource: false,
    nativeApprovalRequired: 'Full source-bound window/tree/IME/control closure and actual original page lifecycle/render call stacks' };
}
module.exports = { discover, controls };
if (require.main === module) process.stdout.write(JSON.stringify(discover(process.argv[2]), null, 2) + '\n');
