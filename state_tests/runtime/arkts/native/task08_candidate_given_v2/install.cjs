'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const previous = require('../task08_strict/Task08StrictNativeUi.install.cjs');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function install(work) {
  const result = previous.install(work);
  const replacements = [];
  for (const name of ['Task08TimelineUI.js', 'Task08StrictNativeUiAdapter.js']) {
    const file = path.join(__dirname, name);
    const bytes = fs.readFileSync(file);
    const fixture = result.fixtures.find(item => item.installedPath === 'entry/src/test/' + name);
    if (!fixture) throw new Error('Task08 private successor fixture is not installed: ' + name);
    const target = path.join(work, fixture.installedPath);
    if (sha(fs.readFileSync(target)) !== fixture.sha256) throw new Error('Task08 parent fixture drift: ' + name);
    replacements.push({ before: { ...fixture }, after: { file, installedPath: fixture.installedPath, sha256: sha(bytes) } });
    fs.writeFileSync(target, bytes);
    Object.assign(fixture, replacements[replacements.length - 1].after);
  }
  const productionAfter = result.production.map(item => ({ path: item.path,
    sha256: sha(fs.readFileSync(path.join(work, item.path))) }));
  if (JSON.stringify(productionAfter) !== JSON.stringify(result.production))
    throw new Error('Task08 candidate production changed during private successor installation');
  result.candidateGivenSuccessor = { schema: 'task08.candidate-given.v2',
    parentInstaller: result.installer, replacements, derivedFocusWritesAllowed: false,
    unreachableGiven: 'not_scored', publicPromotion: false };
  result.installer = { file: __filename, sha256: sha(fs.readFileSync(__filename)) };
  return result;
}

module.exports = { install };
