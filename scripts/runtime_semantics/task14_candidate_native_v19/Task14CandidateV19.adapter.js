import { startTask14Page } from './Task14DeviceUi.core';
import { runTask14CandidateV19 } from './Task14CandidateV19.suite';

const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));

export async function evaluateTask14CandidateV19(args, config, ports, record) {
  const nonce = args.native?.capabilities?.execution?.nonce;
  const raw = { protocol: 'task14.candidate-native.v19', taskId: args.taskId,
    caseId: args.caseSpec.caseId, traceDigest: args.caseSpec.traceDigest, nonce,
    sessionId: nonce + ':' + args.caseSpec.caseId, productionSources: config.productionSources,
    samples: [], actions: [], records: [], entryExecuted: false, released: false, failure: null };
  let original, sequence = 0;
  const emit = event => { raw.records.push({ sequence: ++sequence, at: Date.now(), event: clone(event) }); record(event); };
  try {
    if (!/^[a-f0-9]{32}$/.test(nonce || '') || Date.now() >= config.deadlineEpochMs)
      throw new Error('Fresh native nonce/deadline missing');
    if (typeof ports.providerControl !== 'function') throw new Error('External Matrix provider control unavailable');
    original = await startTask14Page(ports, config, emit); raw.entryExecuted = true;
    const session = { ...original,
      observeBracketed: async (label, selectors, read = () => ({})) => {
        const value = await original.observeBracketed(label, selectors, read);
        raw.samples.push(clone(value)); return value;
      },
      action: async (kind, control, value) => {
        const action = { kind, control: clone(control), value, beginSequence: ++sequence,
          sessionId: raw.sessionId, executed: false };
        raw.actions.push(action);
        try { await original.action(kind, control, value); action.executed = true; }
        finally { action.endSequence = ++sequence; }
      } };
    raw.transition = await runTask14CandidateV19({ ...args.caseSpec, taskId: args.taskId }, config,
      session, ports.providerControl, emit, args.trace);
    raw.providerFinal = await ports.providerControl('status', {});
  } catch (error) { raw.failure = String(error); }
  finally {
    try { if (original) { await original.release(); raw.released = true; } }
    catch (error) { raw.failure = 'Owned runtime cleanup: ' + String(error); }
    raw.finishedAt = Date.now(); raw.deadlineEpochMs = config.deadlineEpochMs;
  }
  emit({ method: 'Task14.candidateNativeEpisodeV19', available: raw.entryExecuted,
    caseId: raw.caseId, sessionId: raw.sessionId });
  const transition = raw.transition;
  const invariantDescriptions = new Set((transition?.invariantChecks || []).map(item => item.description));
  const admitted = raw.failure === null && raw.entryExecuted === true && raw.released === true && transition &&
    transition.failure === null && transition.eventExecuted === true && transition.observed &&
    Object.keys(transition.observed).length > 0 && raw.actions.length > 0 &&
    raw.actions.every(item => item.executed === true) &&
    (args.caseSpec.invariants || []).every(item => invariantDescriptions.has(item));
  if (!admitted) return { observed: {}, invariantChecks: [], evidence: [{ candidateNativeV19: raw }],
    unsupported: 'Fresh candidate native episode failed independent admission',
    observationLevel: 'native_candidate_ui_and_matrix_sdk_https' };
  return { observed: clone(transition.observed), invariantChecks: clone(transition.invariantChecks),
    evidence: [{ candidateNativeV19: raw }], observationLevel: 'native_candidate_ui_and_matrix_sdk_https' };
}
