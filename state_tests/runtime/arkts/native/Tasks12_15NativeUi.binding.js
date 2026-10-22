import { configureTasks12ReportPage, installTasks12ReportPageObserver } from './Tasks12_15ReportPageObserver';

let configured;

export function configureTasks12ReportPageBinding(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  const expected = '@bundle:' + config.bundleName + '/entry/ets/features/ReportRoomFeature';
  if (!config.bundleName || config.moduleName !== 'entry' || config.productionModuleUrl !== expected ||
      config.presenterExport !== 'ReportRoomPresenter') throw new Error('Task12 original app binding identity is invalid');
  configured = { config, importModule };
}

export async function installTasks12ReportPageAfterReady(readinessJson) {
  if (!configured) throw new Error('Task12 postload original app binding was not configured');
  const readiness = JSON.parse(readinessJson);
  const { config, importModule } = configured;
  if (readiness.bundleName !== config.bundleName || readiness.windowConfirmed !== true ||
      readiness.rootConfirmed !== true || readiness.available !== true ||
      !readiness.controls?.some(control => control.id === 'report_room_reason' && control.present === true && control.visible === true)) {
    throw new Error('Original app import requires the actual candidate window and visible report form first');
  }
  // Standard JS dynamic import, deliberately AFTER original page/window load.
  // Never import this URL during suite registration or before startAbility.
  const namespace = await importModule(config.productionModuleUrl);
  const Presenter = namespace && namespace[config.presenterExport];
  if (typeof Presenter !== 'function' || !Presenter.prototype) throw new Error('Original app ReportRoomPresenter export unavailable');
  const before = Object.getOwnPropertyDescriptors(Presenter.prototype);
  configureTasks12ReportPage(Presenter);
  const observer = installTasks12ReportPageObserver();
  const after = Object.getOwnPropertyDescriptors(Presenter.prototype);
  const wrappedNames = Object.keys(before).filter(name => before[name].value !== after[name]?.value);
  if (!['updateReason', 'toggleLeaveRoom'].every(name => wrappedNames.includes(name))) {
    observer.dispose();
    throw new Error('Original app presenter observation methods were not wrapped');
  }
  const binding = { requestedModuleUrl: config.productionModuleUrl, presenterExport: config.presenterExport,
    importCompleted: true, importPhase: 'after_original_page_ready_before_fixture',
    namespaceExports: Object.keys(namespace), wrappedNames, readiness,
    receiverObserved: false, resolutionEvidence: 'Standard JS import of explicit app URL; actual receiver still required; no test-module fallback.' };
  const read = observer.read.bind(observer);
  observer.read = () => {
    const result = read();
    return { ...result, binding: { ...binding, receiverObserved: result.available === true } };
  };
  return observer;
}
