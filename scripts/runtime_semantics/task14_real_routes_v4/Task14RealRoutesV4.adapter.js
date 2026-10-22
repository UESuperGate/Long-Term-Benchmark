import { runTask14RealRoutesV3 } from './Task14RealRoutesV3.suite';
import { startTask14Page } from './Task14DeviceUi.core';

const clone = value => JSON.parse(JSON.stringify(value));
export async function evaluateTask14RealRoutesV4(args, config, ports, record) {
  const spec = args.caseSpec;
  const nonce = args.native?.capabilities?.execution?.nonce;
  const episode = { protocol: 'task14.arkts.actual-route-envelope.v4', taskId: args.taskId,
    caseId: spec.caseId, traceDigest: spec.traceDigest, nonce,
    sessionId: nonce + ':' + spec.caseId, actions: [], samples: [], records: [],
    entryExecuted: false, released: false, failure: null };
  let session, sequence = 0;
  const emit = event => {
    const receipt = { sequence: ++sequence, at: Date.now(), event: clone(event) };
    episode.records.push(receipt); record(event);
  };
  try {
    if (!/^[a-f0-9]{32}$/.test(nonce || '') || args.taskId !== '14_join_room_by_address')
      throw Error('Fresh AA execution nonce and actual Task14 required');
    if (!Number.isFinite(config.deadlineEpochMs) || Date.now() >= config.deadlineEpochMs)
      throw Error('Original scorer deadline unavailable/exhausted');
    // load registers source metadata only. The observer imports the ORIGINAL
    // application module after the real page has become ready.
    for (const source of config.productionSources || []) args.load(source.path);
    session = await startTask14Page(ports, config, emit);
    episode.entryExecuted = true;
    const proxy = {
      ...session,
      observeBracketed: async (...parameters) => {
        const beginSequence = ++sequence;
        const frame = await session.observeBracketed(...parameters);
        frame.acquisition = { beginSequence, endSequence: ++sequence, sessionId: episode.sessionId };
        episode.samples.push(clone(frame)); return frame;
      },
      action: async (kind, control, value) => {
        const receipt = { beginSequence: ++sequence, sessionId: episode.sessionId,
          kind, control: clone(control), value, executed: false, startedAt: Date.now() };
        episode.actions.push(receipt);
        try { await session.action(kind, control, value); receipt.executed = true; }
        finally { receipt.endSequence = ++sequence; receipt.finishedAt = Date.now(); }
      }
    };
    episode.transition = await runTask14RealRoutesV3({ ...spec, taskId: args.taskId }, config,
      proxy, ports.importModule, emit, args.trace);
    episode.productionSources = config.productionSources;
  } catch (error) { episode.failure = String(error); }
  finally {
    if (session) {
      try { await session.release(); episode.released = true; }
      catch (error) { episode.failure = 'Original lifecycle cleanup: ' + String(error); }
    }
    episode.finishedAt = Date.now(); episode.deadlineEpochMs = config.deadlineEpochMs;
  }
  record({ method: 'Task14.actualRouteEpisodeV4', available: episode.entryExecuted,
    nativeUI: true, ...episode });
  // Raw transport MUST NOT assign a semantic verdict. The independent guard
  // checks packaged fixture identities and derives every observation anew.
  return { observed: {}, invariantChecks: [], evidence: [{ actualRouteEpisodeV4: episode }],
    unsupported: 'Actual-route raw awaits independent v4 admission', observationLevel: 'native_candidate_ui' };
}
