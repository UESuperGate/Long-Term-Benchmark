// Import transport and observer instrumentation only; never construct a presenter
// or invoke a product method to manufacture an observed receiver.
export function createOriginalRoomObserverFactory(config, importModule, installObserver) {
  const mode = config.originalModuleImportMode || 'disabled';
  if (mode === 'disabled') {
    const unavailableReason = 'Original app observer import disabled after native ArkVM fatal; post-page-load diagnostic requires explicit opt-in. No production receiver is bound.';
    return async () => ({ unavailableReason, read: () => ({ available: false, reason: unavailableReason }), dispose() {} });
  }
  if (!['after-page-ready-diagnostic', 'after-page-ready'].includes(mode)) throw new Error('Unsafe original module import mode: ' + mode);
  const prefix = '@bundle:' + config.bundleName + '/' + config.moduleName + '/ets/features/';
  if (typeof config.productionModuleUrl !== 'string' || !config.productionModuleUrl.startsWith(prefix) ||
      !['RoomUpgradeFeature', 'RoomFeature'].includes(config.productionModuleUrl.slice(prefix.length)))
    throw new Error('Original app module URL is not bound to the candidate manifest');
  if (!['RoomUpgradePresenter', 'RoomPresenter'].includes(config.presenterExport))
    throw new Error('Original presenter export is not bound');
  const describe = descriptor => ({ configurable: descriptor.configurable, enumerable: descriptor.enumerable,
    writable: descriptor.writable, valueType: typeof descriptor.value,
    getter: typeof descriptor.get === 'function', setter: typeof descriptor.set === 'function' });
  return async function originalRoomObserver(pageReadiness) {
    if (!pageReadiness || pageReadiness.available !== true || pageReadiness.anchor?.id !== 'current_room_id' ||
        pageReadiness.anchor.inDriverTree !== true || pageReadiness.snapshot?.routeName !== config.entryRoute)
      throw new Error('Original module import requires an observed original candidate room page');
    const requestedModuleUrl = config.productionModuleUrl;
    let namespace;
    try { namespace = await importModule(requestedModuleUrl); }
    catch (error) { throw new Error('Original app dynamic import failed for ' + requestedModuleUrl + ': ' + String(error)); }
    const Presenter = namespace && namespace[config.presenterExport];
    if (typeof Presenter !== 'function' || !Presenter.prototype)
      throw new Error('Original app export unavailable: ' + requestedModuleUrl + '#' + config.presenterExport);
    const before = Object.getOwnPropertyDescriptors(Presenter.prototype);
    const observer = installObserver(Presenter);
    const after = Object.getOwnPropertyDescriptors(Presenter.prototype);
    const wrappedNames = Object.keys(before).filter(name => name !== 'constructor' && after[name] &&
      (before[name].value !== after[name].value || before[name].get !== after[name].get));
    if (!wrappedNames.length) {
      observer.dispose();
      throw new Error('Original app observer wrapped no prototype members: ' + requestedModuleUrl);
    }
    observer.binding = { requestedModuleUrl, importCompleted: true, presenterExport: config.presenterExport,
      namespaceExports: Object.keys(namespace), wrappedNames,
      prototypeDescriptors: Object.fromEntries(Object.entries(before).map(([name, descriptor]) => [name, describe(descriptor)])),
      resolutionEvidence: 'Standard dynamic import completed for this request; compiled OHM URL must be audited independently.',
      receiverObserved: false };
    return observer;
  };
}
