import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import preferences from '@ohos.data.preferences';
import fs from '@ohos.file.fs';
import inputMethod from '@ohos.inputMethod';
import { Driver, ON } from '@ohos.UiTest';
import { startTask11Page } from './Task11Session';
import { installTask10RepositoryInput } from './Task10RepositoryInput';
import { runTask10RepositoryCase } from './Task10RepositorySuite';

let config;
export function configureTask10Repository(value) { config = JSON.parse(value); }
export function attachTask10Repository(bridge, taskId, caseSpec) {
  if (!config || taskId !== '10_media_upload_quality') throw new Error('Task10 repository binding unavailable');
  let recorder;
  const original = bridge.setObservationRecorder;
  bridge.setObservationRecorder = function(value) { recorder = value; return original.call(this, value); };
  const record = event => { if (recorder) recorder({ ...event, caseId: caseSpec.caseId, traceDigest: caseSpec.traceDigest,
    role: config.role, backend: 'actual_original_arkui_repository_binding' }); };
  const ports = {
    getDelegator: () => abilityDelegatorRegistry.getAbilityDelegator(),
    getApplicationContext: () => abilityDelegatorRegistry.getAbilityDelegator().getAppContext().getApplicationContext(),
    createDriver: () => Driver.create(),
    selector: (spec, bundle) => {
      let selector = ON;
      if (spec.id) selector = selector.id(spec.id);
      if (spec.type) selector = selector.type(spec.type);
      if (spec.text !== undefined) selector = selector.text(spec.text);
      return selector.inWindow(bundle);
    },
    getLastWindow: context => window.getLastWindow(context),
    getInspectorTree: () => getInspectorTree(),
    importModule: url => import(url),
    delay: milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds)),
    preferences: (context, name) => preferences.getPreferences(context, { name }),
    context: () => abilityDelegatorRegistry.getAbilityDelegator().getAppContext(),
    globalTap: async bounds => {
      const x = Math.round((bounds.left + bounds.right) / 2), y = Math.round((bounds.top + bounds.bottom) / 2);
      await Driver.create().click(x, y);
      record({ method: 'Task10.globalTap', x, y, bounds, realDriverInput: true });
    },
    dismissKeyboard: async () => { await inputMethod.getController().hideTextInput(); record({ method: 'Task10.uiKeyboardDismissed', transport: 'native_input_method_hideTextInput' }); },
    createPickedInput: attachment => {
      const file = abilityDelegatorRegistry.getAbilityDelegator().getAppContext().cacheDir + '/canonical-picked-input.' +
        (attachment.mediaType === 'image' ? 'jpg' : 'mp4');
      const fd = fs.openSync(file, fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
      try { fs.writeSync(fd.fd, 'Evaluator-controlled opaque media source; metadata is the external picker boundary.'); fs.truncateSync(fd.fd, attachment.bytes); }
      finally { fs.closeSync(fd.fd); }
      return { path: file, exists: fs.accessSync(file), bytes: fs.statSync(file).size,
        scope: 'original input only, not prepared output; codec correctness is not claimed' };
    },
    fileStatus: path => {
      try { const exists = fs.accessSync(path); return { path, available: true, exists, bytes: exists ? fs.statSync(path).size : null }; }
      catch (error) { return { path, available: false, code: error.code, error: String(error) }; }
    },
    removePickedInput: path => fs.unlinkSync(path)
  };
  bridge.evaluateTask10Repository = async args => {
    let session, observer;
    try {
      session = await startTask11Page(ports, config, record);
      const modules = [];
      for (let i = 0; i < config.moduleUrls.length; i++) {
        const source = config.productionSources[i];
        if (source.path.includes('/features/')) args.load(source.path);
        modules.push(await ports.importModule(config.moduleUrls[i]));
        record({ method: 'Task10.actualModuleImport', source, url: config.moduleUrls[i] });
      }
      observer = await installTask10RepositoryInput(modules, args.caseSpec, ports, record);
      await session.reloadOriginalPage();
      return await runTask10RepositoryCase(args, session, observer, ports, record);
    } catch (error) {
      if (observer) args.trace('diagnostic:last-actual-state', observer.read());
      return { unsupported: String(error) + '\n' + (error.stack || ''), observed: {}, invariantChecks: [] };
    } finally {
      if (observer) observer.dispose();
      if (session) await session.release();
    }
  };
}
