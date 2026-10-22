'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v14/install.cjs');
const original = require('../task14_full_native_v6/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V15 derivation changed: ' + old);
  return text.replace(old, next);
};

function scalarSource() {
  let source = original.scalarSource();
  source = replace(source,
    `export async function runTask14ScalarCasesV6(spec, config, session, observer, clock, emit) {`,
    `export async function runTask14ScalarCasesV15(spec, config, session, observer, clock, emit, providerStatus) {`);
  source = replace(source,
    `      await tick(1); await capture('after:event');
      const first = observer.read().resolverRequests.find(r=>r.samePageResolver && !r.settled);
      need(first && clock.read().calls.some(c=>c.method==='timerCallback' && c.at===300), 'Original SDK leaf did not actually fire at300; NS');`,
    `      await tick(1); await capture('after:event');
      let first, external;
      for (let attempt = 0; attempt < 40; attempt++) {
        first = observer.read().resolverRequests.find(r=>r.samePageResolver && !r.settled);
        external = await providerStatus();
        if (first && external.held?.some(item => item.caseId === spec.caseId && item.alias === '#team:example.org')) break;
        await Promise.resolve();
      }
      need(first && external?.held?.some(item => item.caseId === spec.caseId && item.alias === '#team:example.org') &&
        clock.read().calls.some(c=>c.method==='timerCallback' && c.at===300),
        'Original SDK leaf and nonce-bound provider request did not both fire at300; NS');`);
  return source.replace("protocol:'task14.same-page-scalar.v6'", "protocol:'task14.same-page-scalar.v15'");
}

function adapterSource() {
  let source = previous.adapterSource()
    .replace("import { runTask14ScalarCasesV6 } from './Task14ScalarCasesV6';",
      "import { runTask14ScalarCasesV15 } from './Task14ScalarCasesV15';")
    .replace('evaluateTask14FullNativeV14', 'evaluateTask14FullNativeV15')
    .replaceAll('task14.full-nine-configured-sdk.v14', 'task14.full-nine-configured-sdk.v15')
    .replaceAll('fullNativeEpisodeV14', 'fullNativeEpisodeV15');
  return replace(source,
    `raw.transition = await runTask14ScalarCasesV6(spec, config, session, owner, clock, emit);`,
    `raw.transition = await runTask14ScalarCasesV15(spec, config, session, owner, clock, emit,
      () => owner.providerStatus());`);
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV14 } from './Task14FullNativeV14.adapter';",
      "import { evaluateTask14FullNativeV15 } from './Task14FullNativeV15.adapter';")
    .replace('return evaluateTask14FullNativeV14(args, config, ports, record);',
      'return evaluateTask14FullNativeV15(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14ScalarCasesV6.js', 'Task14FullNativeV14.adapter.js',
      'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14ScalarCasesV15.js', sha256: hash(scalarSource()) },
      { name: 'Task14FullNativeV15.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v15' };
  const scalar = scalarSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.rmSync(path.join(testRoot, 'Task14ScalarCasesV6.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14ScalarCasesV15.js'), scalar);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV14.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV15.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => !['Task14ScalarCasesV6.js', 'Task14FullNativeV14.adapter.js'].includes(path.basename(item.path)))
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14ScalarCasesV15.js', source: __filename,
    sha256: hash(scalar), derivedBy: __filename });
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV15.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    controlledBoundary: { ...report.controlledBoundary,
      debounceAdmission: 'page-owned pending request plus nonce-bound provider-held request after the 300ms timer' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, scalarSource, e2eSource: previous.e2eSource,
  coreSource: previous.coreSource, ownerSource: previous.ownerSource,
  adapterSource, bridgeSource, expectedFixtures, pageObserverAlias: previous.pageObserverAlias };
