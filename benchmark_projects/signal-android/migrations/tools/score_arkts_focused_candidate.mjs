import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const value = flag => process.argv[process.argv.indexOf(flag) + 1];
const optional = flag => process.argv.includes(flag) ? value(flag) : null;
const project = path.resolve(value('--project'));
const migration = path.resolve(value('--migration'));
const output = path.resolve(value('--output'));
const role = value('--role');
const observationsPath = path.resolve(value('--observations'));
const hapPath = optional('--hap') ? path.resolve(optional('--hap')) : null;
const nativeTarget = optional('--native-target');
const contract = JSON.parse(fs.readFileSync(path.join(migration, 'canonical', 'transitions.json'), 'utf8'));
const manifestPath = optional('--source-manifest') ? path.resolve(optional('--source-manifest')) : path.join(project, 'SOURCE_MANIFEST.json');
const identityPath = path.join(project, 'AppScope', 'app.json5');
const manifest = fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) : null;

const subset = (actual, expected) => {
  if (expected === null || typeof expected !== 'object') return Object.is(actual, expected);
  if (Array.isArray(expected)) return Array.isArray(actual) && actual.length === expected.length && expected.every((item, index) => subset(actual[index], item));
  const read = (source, key) => key in source ? source[key] : key.split('.').reduce((current, part) => current?.[part], source);
  return actual !== null && typeof actual === 'object' && Object.entries(expected).every(([key, expectedValue]) => subset(read(actual, key), expectedValue));
};
const collectSources = () => {
  const files = [];
  const root = path.join(project, 'entry', 'src', 'main', 'ets');
  if (!fs.existsSync(root)) return files;
  const visit = directory => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '.benchmark-evaluator') continue;
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(target);
      else if (/\.(?:ets|ts)$/.test(entry.name)) {
        const bytes = fs.readFileSync(target);
        files.push({ path: path.relative(project, target), sha256: crypto.createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length });
      }
    }
  };
  visit(root);
  return files.sort((left, right) => left.path.localeCompare(right.path));
};
const productionSources = collectSources();
let identity = null;
try { identity = JSON.parse(fs.readFileSync(identityPath, 'utf8')).app?.bundleName ?? null; } catch {}
const provenanceMatches = manifest !== null && productionSources.length === manifest.files.length && productionSources.every(actual => {
  const expected = manifest.files.find(item => item.path === actual.path);
  return expected && expected.sha256 === actual.sha256 && expected.bytes === actual.bytes;
});
const candidateFailure = manifest === null
  ? 'candidate_source_manifest_missing'
  : identity === null || identity !== manifest.bundleName
    ? 'candidate_identity_missing'
    : !provenanceMatches
      ? 'candidate_source_provenance_mismatch'
      : null;
let observations = [];
try { observations = fs.readFileSync(observationsPath, 'utf8').trim().split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line)); } catch {}
const observationMap = new Map(observations.map(item => [item.caseId, item]));
const observationSetValid = observations.length === contract.cases.length && observationMap.size === contract.cases.length && contract.cases.every(item => observationMap.has(item.caseId));

const rows = contract.cases.map(item => {
  if (candidateFailure !== null) return {
    caseId: item.caseId, traceDigest: item.traceDigest, status: 'not_scored', reason: candidateFailure,
    productionSources, invokedProductionMethods: [], checkpoints: [], observed: null, invariantChecks: []
  };
  const observed = observationMap.get(item.caseId);
  if (!observationSetValid || !observed) return {
    caseId: item.caseId, traceDigest: item.traceDigest, status: 'not_scored', reason: 'invalid_runtime_observation_set',
    productionSources, invokedProductionMethods: [], checkpoints: [], observed: null, invariantChecks: []
  };
  const givenPassed = observed.givenEstablished === true && subset(observed.given, item.given);
  const ownerPassed = observed.entryLifecycle === 'Index.aboutToAppear'
    && observed.availability === 'executed_api23_arkvm_index_page_owner'
    && typeof observed.ownerId === 'string' && observed.ownerId.length > 0;
  const statePassed = subset(observed.after, item.expected.state);
  const orderedStatesPassed = !item.expected.orderedStates || subset(observed.orderedStates, item.expected.orderedStates);
  const effects = observed.effects ?? [];
  const effectsPassed = (item.expected.effects ?? []).every(expected => effects.some(actual => subset(actual, expected)));
  const absentEffectsPassed = (item.expected.absentEffects ?? []).every(name => effects.every(actual => actual.name !== name));
  const facts = Array.isArray(observed.invariantFacts) ? observed.invariantFacts : [];
  const invariantChecks = item.invariants.map((text, index) => ({ text, passed: facts[index] === true, evidence: observed.invariantEvidence?.[index] ?? 'native before/after and external-leaf trace' }));
  const passed = givenPassed && ownerPassed && statePassed && orderedStatesPassed && effectsPassed && absentEffectsPassed && invariantChecks.every(check => check.passed);
  return {
    caseId: item.caseId, traceDigest: item.traceDigest, status: passed ? 'pass' : 'fail', productionSources,
    invokedProductionMethods: [observed.productionEntrypoint],
    checkpoints: [{ label: 'before', state: observed.before }, { label: 'after', state: observed.after }],
    observed: { state: observed.after, orderedStates: observed.orderedStates ?? null, effects }, invariantChecks,
    diagnostics: { givenPassed, ownerPassed, statePassed, orderedStatesPassed, effectsPassed, absentEffectsPassed, persistenceReopened: observed.persistenceReopened === true }
  };
});
const count = status => rows.filter(item => item.status === status).length;
const report = {
  schemaVersion: 1, taskId: contract.taskId, platform: 'arkts', role, candidateProject: project,
  candidateIdentity: identity, observationMode: 'api23_arkvm_runtime_state_transition',
  runtime: 'entryability_arkui_index_page_owned_production_controller', sourceObserver: false,
  productionSourceHashes: productionSources, productionProvenanceMatchesManifest: provenanceMatches,
  productionSourceManifest: manifestPath,
  runtimeArtifact: hapPath && fs.existsSync(hapPath) ? { kind: 'api23_hap', sha256: crypto.createHash('sha256').update(fs.readFileSync(hapPath)).digest('hex'), bytes: fs.statSync(hapPath).size } : null,
  compile: { passed: candidateFailure === null ? true : null, scope: 'api23_hvigor_hap' },
  semantic: { passed: count('pass'), failed: count('fail'), notScored: count('not_scored'), total: rows.length, cases: rows },
  diagnostics: { adapter: candidateFailure === null ? 'executed' : 'fail_closed', nativeArkvmUiEvidence: candidateFailure === null ? 'entryability_page_owner_runtime_observer_collected' : 'not_collected', nativeTarget, rawObservationLog: path.relative(migration, observationsPath), hostRunnerUsedForScoring: false, sourceObserver: false, roleUsedForScoring: false, publicationEligible: count('not_scored') === 0 }
};
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ output, role, passed: report.semantic.passed, failed: report.semantic.failed, notScored: report.semantic.notScored })}\n`);
process.exit(report.semantic.notScored === 0 ? 0 : 2);
