import { Component, Driver, ON, Rect } from '@ohos.UiTest';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { UIContext } from '@ohos.arkui.UIContext';
import { installTask13AfterReady, readTask13Page, publishTask13UI, task13UICancelled } from './Task13NativeUi';

export interface Task13Given {
  profileUserId: string;
  isCurrentUser: boolean;
  verificationAvailable: boolean;
}
export interface Task13Case {
  taskId: string;
  caseId: string;
  key: string;
  traceDigest: string;
  given: Task13Given;
}
export interface Task13Config {
  bundleName: string;
  moduleName: string;
  abilityName: string;
}
interface Task13Control {
  id: string;
  text: string;
  type: string;
  enabled: boolean;
  clickable: boolean;
  visible: boolean;
  bounds: Rect;
}
interface Task13Route {
  name: string;
  path: string;
  index: number;
}
interface Task13ErrorDetails {
  message: string;
  stack: string;
  errorInfo: string;
}
interface Task13Frame {
  label: string;
  bundleName: string;
  focusedBundle: string;
  profileUserId: string;
  controls: Task13Control[];
  route?: Task13Route;
  pageEvidenceJson?: string;
  completed: boolean;
  error?: string;
  errorDetails?: Task13ErrorDetails;
}
interface Task13Action {
  id: string;
  executed: boolean;
  before: string;
  after: string;
}
interface Task13Result {
  taskId: string;
  caseId: string;
  key: string;
  traceDigest: string;
  bundleName: string;
  frames: Task13Frame[];
  actions: Task13Action[];
  unsupported: string;
  stage: string;
}

function guard(deadline: number): void {
  if (task13UICancelled() || Date.now() >= deadline) throw new Error('Task13 UI probe cancelled or budget exceeded');
}

async function control(component: Component, viewport: Rect): Promise<Task13Control> {
  const bounds = await component.getBounds();
  return { id: await component.getId(), text: await component.getText(), type: await component.getType(),
    enabled: await component.isEnabled(), clickable: await component.isClickable(), bounds,
    visible: Math.min(bounds.right, viewport.right) > Math.max(bounds.left, viewport.left) &&
      Math.min(bounds.bottom, viewport.bottom) > Math.max(bounds.top, viewport.top) };
}

async function frame(driver: Driver, uiContext: UIContext, spec: Task13Case, result: Task13Result,
  label: string, deadline: number): Promise<Task13Frame> {
  guard(deadline);
  const observed: Task13Frame = { label, bundleName: result.bundleName, focusedBundle: '',
    profileUserId: '', controls: [], completed: false };
  result.frames.push(observed);
  result.stage = 'frame_' + label;
  publishTask13UI(JSON.stringify(result));
  try {
    const focused = await driver.findWindow({ focused: true });
    if (focused) observed.focusedBundle = await focused.getBundleName();
    const candidate = await driver.findWindow({ bundleName: result.bundleName });
    if (!candidate) throw new Error('Original candidate window unavailable');
    const viewport = await candidate.getBounds();
    const profile = (await driver.findComponents(ON.text(spec.given.profileUserId).inWindow(result.bundleName))) ?? [];
    if (profile.length === 1) {
      const node = await control(profile[0], viewport);
      observed.controls.push(node);
      if (node.visible) observed.profileUserId = node.text;
    }
    for (const id of ['verify_user_action', 'verification_remote_accepted', 'cancel_verification',
      'start_sas_verification', 'verification_completed', 'profile_verification_violation']) {
      guard(deadline);
      const matches = (await driver.findComponents(ON.id(id).inWindow(result.bundleName))) ?? [];
      if (matches.length > 1) throw new Error('Ambiguous original control: ' + id);
      if (matches.length === 1) observed.controls.push(await control(matches[0], viewport));
      publishTask13UI(JSON.stringify(result));
    }
    uiContext.runScopedTask(() => {
      const route = uiContext.getRouter().getState();
      observed.route = { name: route.name, path: route.path, index: route.index };
    });
    observed.pageEvidenceJson = readTask13Page();
    observed.completed = true;
  } catch (error) {
    const original = error as Error;
    observed.error = String(error);
    let errorInfo = observed.error;
    try { errorInfo = JSON.stringify(error) || observed.error; }
    catch (serializationError) { errorInfo = observed.error + '; serialization: ' + String(serializationError); }
    const message = original?.message || observed.error;
    const stack = original?.stack || '';
    observed.errorDetails = { message, stack, errorInfo };
    const wrapped = new Error(message);
    if (stack) wrapped.stack = stack;
    throw wrapped;
  }
  finally { publishTask13UI(JSON.stringify(result)); }
  return observed;
}

export async function runTask13UI(spec: Task13Case, config: Task13Config): Promise<string> {
  const result: Task13Result = { taskId: spec.taskId, caseId: spec.caseId, key: spec.key,
    traceDigest: spec.traceDigest, bundleName: config.bundleName, frames: [], actions: [], unsupported: '', stage: 'start' };
  const deadline = Date.now() + 35000;
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  const monitor: abilityDelegatorRegistry.AbilityMonitor = { abilityName: config.abilityName };
  const driver = Driver.create();
  let monitoring = false;
  let uiContext: UIContext | undefined = undefined;
  try {
    if (spec.taskId !== '13_user_verification' || spec.key !== 'profile_routes_user_request') throw new Error('Unsupported Task13 case');
    await delegator.addAbilityMonitor(monitor);
    monitoring = true;
    await delegator.startAbility({ bundleName: config.bundleName, moduleName: config.moduleName, abilityName: config.abilityName });
    const ability = await delegator.waitAbilityMonitor(monitor, 5000);
    if (ability.context.abilityInfo.bundleName !== config.bundleName || ability.context.abilityInfo.moduleName !== config.moduleName) {
      throw new Error('Actual ability identity differs from candidate manifest');
    }
    const candidateWindow = await window.getLastWindow(ability.context);
    uiContext = candidateWindow.getUIContext();
    const ready = await frame(driver, uiContext, spec, result, 'candidate_ready', deadline);
    result.stage = 'postload_original_module';
    publishTask13UI(JSON.stringify(result));
    await installTask13AfterReady(JSON.stringify(ready));
    const before = await frame(driver, uiContext, spec, result, 'before_event', deadline);
    const button = before.controls.find((node: Task13Control) => node.id === 'verify_user_action');
    if (before.focusedBundle !== config.bundleName || before.profileUserId !== spec.given.profileUserId ||
      !button || !button.visible || !button.enabled || !button.clickable) throw new Error('Canonical original-profile action is not available');
    const buttons = (await driver.findComponents(ON.id('verify_user_action').inWindow(config.bundleName))) ?? [];
    if (buttons.length !== 1) throw new Error('Original Verify button is not unique');
    guard(deadline);
    result.stage = 'click_verify_user';
    publishTask13UI(JSON.stringify(result));
    await buttons[0].click();
    result.actions.push({ id: 'verify_user_action', executed: true, before: 'before_event', after: 'after_event' });
    publishTask13UI(JSON.stringify(result));
  } catch (error) { result.unsupported = result.stage + ': ' + String(error); }
  if (uiContext !== undefined) {
    try { await frame(driver, uiContext, spec, result, 'after_event', deadline); }
    catch (error) { result.unsupported = result.unsupported || String(error); }
  }
  if (monitoring) {
    try { await delegator.removeAbilityMonitor(monitor); }
    catch (error) { result.unsupported = result.unsupported || String(error); }
  }
  result.stage = 'finished';
  publishTask13UI(JSON.stringify(result));
  return JSON.stringify(result);
}
