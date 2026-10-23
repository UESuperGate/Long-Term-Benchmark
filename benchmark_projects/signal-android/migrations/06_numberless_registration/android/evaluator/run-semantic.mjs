import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const value = name => process.argv[process.argv.indexOf(name) + 1];
const optional = name => process.argv.includes(name) ? value(name) : null;
const project = path.resolve(value('--project'));
const role = value('--role');
const output = path.resolve(value('--output'));
const observationsPath = path.resolve(value('--observations'));
const nativeDevice = optional('--native-device');
const apk = optional('--apk');
const probeCandidate = optional('--probe-candidate');
const migration = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..');
const contract = JSON.parse(fs.readFileSync(path.join(migration, 'canonical', 'transitions.json'), 'utf8'));
const manifestPath = optional('--source-manifest') ? path.resolve(optional('--source-manifest')) : path.join(project, 'IMMUTABLE_SOURCES.json');
const sourceManifest = fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) : null;
const identityPath = path.join(project, 'src', 'main', 'AndroidManifest.xml');

const subset = (actual, expected) => {
  if (expected === null || typeof expected !== 'object') return Object.is(actual, expected);
  if (Array.isArray(expected)) return Array.isArray(actual) && actual.length === expected.length && expected.every((item, index) => subset(actual[index], item));
  const read = (source, key) => key in source ? source[key] : key.split('.').reduce((value, part) => value?.[part], source);
  return actual !== null && typeof actual === 'object' && Object.entries(expected).every(([key, expectedValue]) => subset(read(actual, key), expectedValue));
};

const collectSources = directory => {
  const files = [];
  if (!fs.existsSync(directory)) return files;
  const visit = current => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const target = path.join(current, entry.name);
      if (entry.isDirectory()) visit(target);
      else if (/\.(?:kt|java)$/.test(entry.name)) {
        const bytes = fs.readFileSync(target);
        const relative = path.relative(path.join(project, 'immutable-src'), target);
        const origin = sourceManifest?.files.find(item => item.path === relative);
        files.push({ path: relative, gitBlob: origin?.gitBlob ?? null, sha256: crypto.createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length });
      }
    }
  };
  visit(directory);
  return files.sort((left, right) => left.path.localeCompare(right.path));
};

const productionSources = collectSources(path.join(project, 'immutable-src'));
const provenanceMatches = sourceManifest !== null && productionSources.length === sourceManifest.files.length && productionSources.every(actual => {
  const expected = sourceManifest.files.find(item => item.path === actual.path);
  return expected && expected.sha256 === actual.sha256 && expected.bytes === actual.bytes;
});
const identity = fs.existsSync(identityPath) ? fs.readFileSync(identityPath, 'utf8').match(/\bpackage="([^"]+)"/)?.[1] ?? null : null;
const candidateFailure = sourceManifest === null
  ? 'candidate_source_manifest_missing'
  : identity === null
    ? 'candidate_identity_missing'
    : !provenanceMatches
      ? 'candidate_source_provenance_mismatch'
      : null;
const observations = fs.readFileSync(observationsPath, 'utf8').trim().split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line));
const observationMap = new Map(observations.map(item => [item.caseId, item]));
const observationSetValid = observations.length === contract.cases.length && observationMap.size === contract.cases.length && contract.cases.every(item => observationMap.has(item.caseId));

const rows = contract.cases.map(item => {
  if (candidateFailure !== null) {
    return { caseId: item.caseId, traceDigest: item.traceDigest, status: 'not_scored', reason: candidateFailure, productionSources, invokedProductionMethods: [], checkpoints: [], observed: null, invariantChecks: [] };
  }
  const observed = observationMap.get(item.caseId);
  if (!observationSetValid || !observed) {
    return { caseId: item.caseId, traceDigest: item.traceDigest, status: 'not_scored', reason: 'invalid_runtime_observation_set', checkpoints: [], observed: null, invariantChecks: [] };
  }
  if (observed.terminalFailure) {
    const prefixPassed = observed.givenEstablished === true && observed.terminalFailure.prefixReached === true && observed.before !== null && observed.after !== null;
    return {
      caseId: item.caseId,
      traceDigest: item.traceDigest,
      status: prefixPassed ? 'fail' : 'not_scored',
      productionSources,
      invokedProductionMethods: [observed.productionEntrypoint],
      checkpoints: [{ label: 'reachable_common_prefix_before', state: observed.before }, { label: 'reachable_common_prefix_after', state: observed.after }],
      observed: prefixPassed ? { terminalFailure: observed.terminalFailure } : null,
      invariantChecks: item.invariants.map(text => ({ text, passed: null, evidence: 'canonical post-transition state is unavailable after the observed base semantic terminal' })),
      reason: prefixPassed ? 'canonical_transition_missing_after_reachable_production_prefix' : 'production_prefix_not_established'
    };
  }
  const statePassed = subset(observed.after, item.expected.state);
  const orderedStatesPassed = !item.expected.orderedStates || subset(observed.orderedStates, item.expected.orderedStates);
  const effects = observed.effects ?? [];
  const effectsPassed = (item.expected.effects ?? []).every(expected => effects.some(actual => subset(actual, expected)));
  const absentEffectsPassed = (item.expected.absentEffects ?? []).every(name => effects.every(actual => actual.name !== name));
  const givenPassed = observed.givenEstablished === true;
  const passed = givenPassed && statePassed && orderedStatesPassed && effectsPassed && absentEffectsPassed;
  return {
    caseId: item.caseId,
    traceDigest: item.traceDigest,
    status: passed ? 'pass' : 'fail',
    productionSources,
    invokedProductionMethods: [observed.productionEntrypoint],
    checkpoints: [{ label: 'before', state: observed.before }, { label: 'after', state: observed.after }],
    observed: { state: observed.after, orderedStates: observed.orderedStates ?? null, effects },
    invariantChecks: item.invariants.map(text => ({ text, passed, evidence: 'derived from the runtime before/after state and ordered external-leaf effect log' })),
    diagnostics: { givenPassed, statePassed, orderedStatesPassed, effectsPassed, absentEffectsPassed }
  };
});

const count = status => rows.filter(item => item.status === status).length;
const artifactPath = apk ? path.resolve(apk) : null;
const report = {
  schemaVersion: 1,
  taskId: contract.taskId,
  platform: 'android',
  role,
  candidateProject: project,
  candidateIdentity: identity,
  observationMode: 'api37_art_runtime_state_transition',
  runtime: 'installable_evaluator_owned_android_app_over_focused_official_production_source',
  probeSelection: { method: 'ordered_compile_capability_without_role_or_source_pattern', selected: probeCandidate },
  productionSourceCommit: sourceManifest?.sourceCommit ?? null,
  productionSourceHashes: productionSources,
  productionSourceManifest: manifestPath,
  productionProvenanceMatchesManifest: provenanceMatches,
  runtimeArtifact: artifactPath && fs.existsSync(artifactPath) ? { kind: 'installable_android_harness_apk', sha256: crypto.createHash('sha256').update(fs.readFileSync(artifactPath)).digest('hex'), bytes: fs.statSync(artifactPath).size } : null,
  compile: { passed: true, scope: 'focused_api37_android_harness' },
  semantic: { passed: count('pass'), failed: count('fail'), notScored: count('not_scored'), total: rows.length, cases: rows },
  diagnostics: { adapter: 'executed', nativeAndroidUiEvidence: 'app_runtime_observer_collected', nativeDevice, rawObservationLog: path.relative(migration, observationsPath), publicationEligible: count('not_scored') === 0 }
};

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
process.exit(report.semantic.notScored === 0 ? 0 : 2);
