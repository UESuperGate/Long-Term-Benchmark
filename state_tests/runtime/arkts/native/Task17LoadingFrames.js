// Natural frame sampling only. No held Promise, native I/O gate or state write.
export function createTask17LoadingFrames(ports, readObserver) {
  const frames = [], errors = [];
  let active = false, started = false, posted = 0;
  function capture(phase, clock) {
    if (!active) return;
    const sample = { phase, clock, at: Date.now() };
    try {
      const native = ports.current();
      sample.windowIdentity = native.identity;
      native.uiContext.runScopedTask(() => {
        // Device inspector APIs may return an object, JSON text or an error
        // string. Preserve the actual value before interpreting its transport.
        const raw = ports.getInspectorTree();
        sample.inspector = { rawType: typeof raw };
        try {
          if (raw === undefined) sample.inspector.undefinedValue = true;
          else sample.inspector.rawValue = JSON.parse(JSON.stringify(raw));
        } catch (error) { sample.inspector.serializationError = String(error); }
        try {
          const tree = typeof raw === 'string' ? JSON.parse(raw) : raw;
          if (!tree || typeof tree !== 'object' || Array.isArray(tree)) throw new Error('Inspector result is not a tree object');
          sample.tree = JSON.parse(JSON.stringify(tree));
          sample.inspector.parsed = true;
        } catch (error) {
          sample.inspector.parsed = false;
          sample.inspector.parseError = String(error);
          errors.push({ phase, error: String(error), rawType: typeof raw });
        }
        sample.route = native.uiContext.getRouter().getState();
        const utils = native.uiContext.getComponentUtils();
        const rectangle = id => { try { return utils.getRectangleById(id); } catch (error) { return { error: String(error) }; } };
        sample.rectangles = { pinned_messages_loading: rectangle('pinned_messages_loading'), pinned_messages_back: rectangle('pinned_messages_back') };
      });
    } catch (error) { sample.captureError = String(error); errors.push({ phase, error: String(error) }); }
    try { sample.observer = readObserver(); }
    catch (error) { sample.observerError = String(error); }
    frames.push(sample);
  }
  function post() {
    if (!active || posted >= 8) return;
    posted++;
    ports.current().uiContext.postFrameCallback({
      onFrame(clock) { capture('onFrame', clock); },
      onIdle(clock) {
        capture('onIdle', clock);
        if (active) {
          const state = readObserver().currentPresenterState?.listState;
          if (state === 'loading' && posted < 8) {
            try { post(); } catch (error) { errors.push({ phase: 'post', error: String(error) }); active = false; }
          } else active = false;
        }
      }
    });
  }
  return {
    start() {
      if (started) throw new Error('Loading sampler is single-use');
      started = true; active = true;
      try { post(); } catch (error) { active = false; errors.push({ phase: 'start', error: String(error) }); }
    },
    snapshot() { return JSON.parse(JSON.stringify({ started, active, posted, limit: 8, frames, errors,
      nativePromisePending: 'unproven', mechanism: 'actual original UIContext.postFrameCallback; no timing gate' })); },
    dispose() { active = false; }
  };
}
