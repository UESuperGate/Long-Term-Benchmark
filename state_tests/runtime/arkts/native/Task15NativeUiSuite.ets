// Loaded only by the generated suite after DeviceTestRunner.onRun.
import { Driver, ON } from '@ohos.UiTest';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import http from '@ohos.net.http';
import asset from '@ohos.security.asset';
import fs from '@ohos.file.fs';
import fileUri from '@ohos.file.fileuri';
import util from '@ohos.util';
import certificateManager from '@ohos.security.certManager';
import wantConstant from '@ohos.app.ability.wantConstant';
import inputMethod from '@ohos.inputMethod';
import { UIContext } from '@ohos.arkui.UIContext';
import { runTask15NativeUi } from './Task15NativeUi';
import { createTask15Launch } from './Task15LaunchNative';
import { createTask15NativeE2E, task15NativeE2EConfig } from './Task15NativeE2E';

class Task15Inspector {
  private uiContext: UIContext;

  constructor(uiContext: UIContext) {
    this.uiContext = uiContext;
  }

  byKey(id: string): Object | null {
    let raw: string = '';
    this.uiContext.runScopedTask(() => raw = getInspectorByKey(id));
    return raw.length > 0 ? JSON.parse(raw) as Object : null;
  }

  tree(): Object | null {
    let tree: Object | null = null;
    this.uiContext.runScopedTask(() => tree = getInspectorTree());
    return tree;
  }
}

export async function runTask15Probe(caseJson: string, bundleName: string): Promise<string> {
  const driver: Driver = Driver.create();
  const appContext = abilityDelegatorRegistry.getAbilityDelegator().getAppContext();
  const resourceContext = appContext.createModuleContext('entry_test');
  const context = appContext.getApplicationContext();
  const config = task15NativeE2EConfig(abilityDelegatorRegistry.getArguments().parameters);
  const uiContext: UIContext = UIContext.resolveUIContext();
  const inspector: Task15Inspector = new Task15Inspector(uiContext);
  const integration = config ? createTask15NativeE2E(config, context, resourceContext, driver, ON,
    { http, asset, fs, fileUri, util, certificateManager, wantConstant,
      abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() }) : undefined;
  return runTask15NativeUi(caseJson, bundleName, driver, ON, createTask15Launch(bundleName), integration, inspector,
    async (): Promise<void> => { await inputMethod.getController().hideTextInput(); });
}
