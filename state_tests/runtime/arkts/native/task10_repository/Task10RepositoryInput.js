const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
export function findRuntimeClass(modules, methods) {
  const found = [...new Set(modules.flatMap(module => Object.values(module)).filter(value =>
    typeof value === 'function' && methods.every(method => typeof value.prototype?.[method] === 'function')))];
  if (found.length !== 1) throw new Error('Unbound/ambiguous actual runtime capability: ' + methods.join(','));
  return found[0];
}

export async function installTask10RepositoryInput(modules, spec, ports, emit) {
  const Presenter = findRuntimeClass(modules, ['onChange', 'openAttachmentPreview', 'setCaption', 'toggleQualitySelector', 'send']);
  const Limits = findRuntimeClass(modules, ['fetchMaxUploadSize', 'release']);
  const Picker = findRuntimeClass(modules, ['pick']);
  const Store = findRuntimeClass(modules, ['open', 'load', 'saveOptimizeImages', 'saveVideoQuality']);
  const Gateway = findRuntimeClass(modules, ['sendAsync', 'cleanupTemporaryMedia']);
  const Metadata = findRuntimeClass(modules, ['describe']);
  const restores = [], calls = [], requests = [], receivers = [];
  let active, releaseLimit, releaseMetadata, metadataPending = false, disposed = false;
  const limit = spec.key === 'block_when_all_oversized' ? 1 : (spec.given.maxUploadSize || 35000000);
  const attachment = { id: 'canonical-selected-media', uri: 'file://canonical-picked-media',
    fileName: spec.given.mediaType === 'image' ? 'fixture.jpg' : 'fixture.mp4',
    mediaType: spec.given.mediaType || 'video', order: 0, bytes: spec.given.mediaType === 'image' ? 5000000 : 50000000,
    width: spec.given.width || 1920, height: spec.given.height || 1080,
    durationMs: spec.given.mediaType === 'image' ? 0 : spec.given.durationMs || 60000 };
  const patch = (owner, method, wrapper) => {
    const previous = Object.getOwnPropertyDescriptor(owner, method);
    if (!previous || typeof previous.value !== 'function' || previous.configurable !== true)
      throw new Error('Cannot bind original SDK/method descriptor: ' + method);
    Object.defineProperty(owner, method, { ...previous, value: wrapper(previous.value) });
    restores.push(() => Object.defineProperty(owner, method, previous));
  };
  const note = value => { const item = copy(value); calls.push(item); emit({ method: 'Task10.originalOrBoundaryCall', ...item }); };
  let sourceFile;
  try {
    sourceFile = ports.createPickedInput(attachment);
    if (!sourceFile.exists || sourceFile.bytes !== attachment.bytes) throw new Error('Real SDK source fixture could not be established');
    attachment.uri = sourceFile.path;
    note({ owner: 'native_fs', method: 'original_input_established', ...sourceFile });
    const store = await ports.preferences(ports.context(), Store.STORE_NAME);
    await store.put(Store.KEY_OPTIMIZE_IMAGES, true);
    await store.put(Store.KEY_VIDEO_QUALITY, spec.given.defaultPreset || spec.given.selectedPreset || 'standard');
    await store.flush();
    note({ owner: 'native_preferences', method: 'seed_external_preferences', preset: spec.given.defaultPreset || spec.given.selectedPreset || 'standard' });
    patch(Picker.prototype, 'pick', () => function() {
      note({ owner: 'external_picker', method: 'pick', attachment });
      return Promise.resolve([copy(attachment)]);
    });
    patch(Limits.prototype, 'fetchMaxUploadSize', original => function(...args) {
      const client = this.client;
      note({ owner: 'http_sdk', method: 'bind_original_http_handle', available: Boolean(client), requestCallable: typeof client?.request === 'function' });
      if (!client || typeof client.request !== 'function') throw new Error('Original HTTP SDK handle unavailable');
      const controlledRequest = function(url, options) {
        if (!String(url).endsWith('/_matrix/client/v3/config')) throw new Error('Unexpected SDK HTTP request');
        requests.push({ url, options: copy(options), completed: false });
        const entry = requests[requests.length - 1];
        const complete = () => {
          entry.completed = true;
          note({ owner: 'http_sdk', method: 'request_completion', url,
            transportFailure: spec.key === 'limit_fallback', advertisedLimit: limit });
          return spec.key === 'limit_fallback' ? Promise.reject(new Error('Controlled external transport failure')) :
            Promise.resolve({ responseCode: 200, result: JSON.stringify({ 'm.upload.size': limit }) });
        };
        note({ owner: 'http_sdk', method: 'request', url, held: spec.key === 'async_loading' });
        if (['async_loading', 'limit_fallback'].includes(spec.key)) return new Promise((resolve, reject) => { releaseLimit = () => complete().then(resolve, reject); });
        return complete();
      };
      this.client = { request: controlledRequest, destroy: () => client.destroy() };
      const receiver = this;
      restores.push(() => { receiver.client = client; });
      return original.apply(this, args);
    });
    patch(Metadata.prototype, 'describe', original => async function(...args) {
      const value = await original.apply(this, args);
      note({ owner: 'metadata_boundary', method: 'original_describe_completed', result: copy(value) });
      if (!active || this !== active.metadataRepository) return value;
      if (!['estimate_video_presets', 'choose_best_preset', 'block_when_all_oversized'].includes(spec.key)) return value;
      metadataPending = true;
      return new Promise(resolve => { releaseMetadata = () => {
        metadataPending = false;
        note({ owner: 'metadata_boundary', method: 'deliver_original_describe_result', result: copy(value) });
        resolve(value);
      }; });
    });
    for (const method of ['onChange', 'openAttachmentPreview', 'setCaption', 'cancelPreview', 'toggleQualitySelector',
      'chooseQuality', 'dismissQualitySelector', 'confirmQualitySelection', 'setImageOptimization', 'send']) {
      patch(Presenter.prototype, method, original => function(...args) {
        active = this;
        if (!receivers.includes(this)) receivers.push(this);
        note({ owner: 'presenter', method, args: method === 'openAttachmentPreview' ? [copy(args[1])] :
          args.map(arg => typeof arg === 'function' ? '[callback]' : copy(arg)) });
        const result = original.apply(this, args);
        if (result && typeof result.then === 'function') result.then(() => {}, error =>
          note({ owner: 'presenter', method: method + '_rejected', error: String(error) }));
        return result;
      });
    }
    patch(Gateway.prototype, 'sendAsync', original => function(request) {
      note({ owner: 'gateway', method: 'sendAsync', request: copy(request) });
      if (spec.key === 'background_failure_cleanup') this.failNextSend = true;
      const result = original.call(this, request);
      note({ owner: 'gateway', method: 'actual_stage_before_async_completion',
        files: (this.temporaryMedia || []).map(path => ports.fileStatus(path)) });
      result.then(value => note({ owner: 'gateway', method: 'sendAsync_completed', result: copy(value) }));
      return result;
    });
    return {
      read() {
        if (!active || typeof active.snapshot !== 'function') return { available: false };
        return { available: true, instanceCount: receivers.length, view: copy(active.snapshot()),
          calls: copy(calls), requests: copy(requests),
          temporaryMedia: copy(active.gateway?.temporaryMedia || []),
          metadataPending,
          estimatorSpecs: copy(active.estimator?.constructor?.VIDEO_SPECS) };
      },
      attachment,
      releaseLimit() { if (!releaseLimit) throw new Error('No held HTTP response'); const release = releaseLimit; releaseLimit = undefined; release(); },
      releaseMetadata() { if (!releaseMetadata) throw new Error('No held original metadata response'); const release = releaseMetadata; releaseMetadata = undefined; release(); },
      inclusiveComparison() {
        const view = active.snapshot();
        const standard = view.plan.options.find(option => option.preset === 'standard');
        if (!standard || !active.metadataState || typeof active.estimator?.buildVideoOptions !== 'function')
          throw new Error('Actual estimator inclusive boundary unavailable');
        const options = active.estimator.buildVideoOptions(copy(active.metadataState), standard.estimatedBytes);
        const matched = options.find(option => option.preset === 'standard');
        const result = { limit: standard.estimatedBytes, option: copy(matched) };
        note({ owner: 'original_estimator', method: 'buildVideoOptions_at_exact_limit', ...result });
        return result;
      },
      dispose() { if (disposed) return; disposed = true; if (releaseLimit) releaseLimit(); if (releaseMetadata) releaseMetadata();
        restores.reverse().forEach(restore => restore()); if (sourceFile) ports.removePickedInput(sourceFile.path); }
    };
  } catch (error) { restores.reverse().forEach(restore => restore()); if (sourceFile) ports.removePickedInput(sourceFile.path); throw error; }
}
