'use strict';
// Versioned test-only successor. The original installer/fixtures stay unchanged.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const base = require('./Tasks16_17PagePorts.install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const record = file => ({ path: file, bytes: fs.statSync(file).size, sha256: hash(fs.readFileSync(file)) });
const old = '          const transitions = observer.read().managerTransitions;\n          const stateSequence = [transitions[0]?.from, ...transitions.map(value => value.to)];';
const replacement = '          raw.canonicalManagerTrace = canonicalManagerTraceV2(observer.read(), raw.bootstrap);\n          const transitions = raw.canonicalManagerTrace.canonicalTransitions;\n          const stateSequence = [transitions[0]?.from, ...transitions.map(value => value.to)];';
function compose() {
  const original = fs.readFileSync(path.join(__dirname, 'Tasks16_17PagePortsUi.js'), 'utf8');
  if (original.split(old).length !== 2) throw new Error('Unbound exact case006 test-only derivation');
  return fs.readFileSync(path.join(__dirname, 'Task16Case006CanonicalTraceV2.js'), 'utf8') + '\n' + original.replace(old, replacement);
}
function install(work) {
  const result = base.install(work);
  const code = compose();
  const installed = path.join(work, 'entry/src/test/Tasks16_17PagePortsUi.js');
  fs.writeFileSync(installed, code);
  const fixture = result.fixtures.filter(item => path.basename(item.file) === 'Tasks16_17PagePortsUi.js');
  if (fixture.length !== 1) throw new Error('Missing/ambiguous original UI fixture');
  fixture[0].sourceSha256 = record(fixture[0].file).sha256;
  fixture[0].sha256 = hash(code);
  result.baseInstaller = result.installer;
  result.installer = { file: __filename, sha256: record(__filename).sha256 };
  result.case006Derivation = { version: 'case006.actual-canonical-manager.v2',
    originalUi: record(path.join(__dirname, 'Tasks16_17PagePortsUi.js')),
    scopeModule: record(path.join(__dirname, 'Task16Case006CanonicalTraceV2.js')),
    installer: record(__filename), installedUiSha256: hash(code),
    allWarmupLogsRetained: true, productionLogicChanged: false };
  for (const item of result.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw new Error('Production input changed');
  }
  return result;
}
module.exports = { install, compose };
