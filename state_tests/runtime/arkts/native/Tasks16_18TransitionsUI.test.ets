import { Component, Driver, ON, On, Rect } from '@ohos.UiTest';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import common from '@ohos.app.ability.common';
import cryptoFramework from '@ohos.security.cryptoFramework';
import util from '@ohos.util';
import fs from '@ohos.file.fs';
import { BusinessError } from '@ohos.base';
import { summarizeTasks16To18ProviderEvidence, tasks16To18ProviderMetadataCommand,
  tasks16To18ProviderHostRequest, validateTasks16To18ProviderHostResponse } from './Tasks16_18ProviderEvidence';
import { readTasks16To18Page, readTasks16To18Picker, publishTasks16To18UI, tasks16To18UICancelled,
  prepareTasks16To18Page, finishTasks16To18Page, bindTasks16To18OriginalPage } from './Tasks16_18NativeUi';

let candidateContext: common.Context | undefined = undefined;
let probeActive: boolean = false;
let probeDeadline: number = 0;

export interface Tasks16_18UIRequest {
  taskId: string;
  caseId: string;
  key: string;
  bundleName: string;
  abilityName?: string;
  eventId?: string;
  emitChunks?: boolean;
}

export interface Tasks16_18UINode {
  id: string;
  text: string;
  type: string;
  enabled: boolean;
  clickable: boolean;
  bounds: Rect;
  selectorScope?: string;
}

export interface Tasks16_18UICheckpoint {
  label: string;
  focusedBundle: string;
  focusedTitle: string;
  nodes: Tasks16_18UINode[];
  pageStateJson?: string;
  pickerStateBeforeJson?: string;
  pickerStateJson?: string;
  focusedNodes?: Tasks16_18UINode[];
  focusedTreeTruncated?: boolean;
  error?: string;
  completed?: boolean;
  elapsedMs?: number;
  startedAtMs?: number;
  finishedAtMs?: number;
  queryCount?: number;
  queryResults?: string[];
  initialReadiness?: string;
}

export interface Tasks16_18UIAction {
  kind: string;
  value: string;
  before: string;
  after: string;
}

interface Tasks16_18ProviderCommand {
  command: string;
  phase: string;
  timeoutSecs: number;
  startedAtMs: number;
  finishedAtMs?: number;
  completed: boolean;
  exitCode?: number;
  stdResult?: string;
  error?: string;
  pickerStateBeforeJson: string;
  pickerStateAfterJson?: string;
  hostRequestJson?: string;
  hostResponseJson?: string;
  responseStdoutSha256?: string;
  responseStdoutBytes?: number;
  pollCount?: number;
  lastPollError?: string;
  lastPollErrorCode?: number;
  responseReadPath?: string;
  responseReadApi?: string;
  responseFileBytes?: number;
  responseFinalPath?: string;
  responseRenameApi?: string;
  responseRenamed?: boolean;
  responseFinalBytes?: number;
}

interface Tasks16_18HostResponse { stdResult: string; exitCode: number; }
interface Tasks16_18ProviderSummary { providerIdentityVerified: boolean; }

interface Tasks16_18PickerCallState { status: string; }
interface Tasks16_18PickerSnapshot { calls: Tasks16_18PickerCallState[]; }
interface Tasks16_18CacheContext { origin: string; applicationName: string; cacheDir: string; }

export interface Tasks16_18UIResult {
  schemaVersion: number;
  taskId: string;
  caseId: string;
  key: string;
  bundleName: string;
  observationLevel: string;
  checkpoints: Tasks16_18UICheckpoint[];
  actions: Tasks16_18UIAction[];
  unsupported: string;
  originalModuleBindingJson?: string;
  providerCommands?: Tasks16_18ProviderCommand[];
  providerEvidenceJson?: string;
  deviceUserId?: string;
  deviceUserParameter?: string;
  deviceUserSource?: string;
  deviceUserError?: string;
  executionNonce?: string;
  hostProviderTransportEnabled?: boolean;
  providerTransportContext?: Tasks16_18CacheContext;
}

function readHostResponse(sample: Tasks16_18ProviderCommand, responsePath: string): string | undefined {
  try {
    const size = fs.statSync(responsePath).size;
    if (size > 3 * 1024 * 1024) throw new Error('Host response file exceeds bounded transport size');
    if (size < 1) { sample.lastPollError = 'Host response temporary file is empty'; return undefined; }
    const raw = fs.readTextSync(responsePath, { length: size, encoding: 'utf-8' });
    if (new util.TextEncoder().encodeInto(raw).length !== size) {
      sample.lastPollError = 'Host response file length changed while reading'; return undefined;
    }
    sample.responseFileBytes = size;
    return raw;
  } catch (error) {
    const failure = error as BusinessError;
    sample.lastPollErrorCode = failure.code;
    sample.lastPollError = ('code=' + failure.code + ': ' + failure.message + ' (' + String(error) + ')').slice(0, 512);
    if (failure.code !== 13900002) throw new Error(sample.lastPollError);
    return undefined;
  }
}

async function hostProviderMetadata(result: Tasks16_18UIResult, driver: Driver, command: string): Promise<void> {
  assertProbeBudget();
  const startedAtMs = Date.now();
  const deadline = Math.min(probeDeadline, startedAtMs + 8000);
  const sample: Tasks16_18ProviderCommand = { command, phase: 'pending_metadata_host', timeoutSecs: 8,
    startedAtMs, completed: false, pickerStateBeforeJson: readTasks16To18Picker(), pollCount: 0 };
  result.providerCommands?.push(sample);
  publish(result, 'provider_host_request_begin');
  try {
    const before = JSON.parse(sample.pickerStateBeforeJson) as Tasks16_18PickerSnapshot;
    if (before.calls.length !== 1 || before.calls[0].status !== 'pending') throw new Error('SDK select is no longer pending before host request');
    const context = abilityDelegatorRegistry.getAbilityDelegator().getAppContext().getApplicationContext();
    result.providerTransportContext = {
      origin: 'AbilityDelegator.getAppContext().getApplicationContext()',
      applicationName: context.applicationInfo.name, cacheDir: context.cacheDir
    };
    const requestJson = tasks16To18ProviderHostRequest(JSON.stringify(result), startedAtMs);
    sample.hostRequestJson = requestJson;
    const responsePath = context.cacheDir + '/Tasks16_18_provider_' + result.executionNonce + '.json';
    sample.responseReadPath = responsePath + '.tmp';
    sample.responseFinalPath = responsePath;
    sample.responseReadApi = '@ohos.file.fs.readTextSync';
    publish(result, 'provider_host_cache_context');
    console.info('ARKTS_16_18_PROVIDER_REQUEST ' + requestJson);
    for (let attempt = 0; attempt < 16 && Date.now() < deadline; attempt++) {
      assertProbeBudget();
      const live = JSON.parse(readTasks16To18Picker()) as Tasks16_18PickerSnapshot;
      if (live.calls.length !== 1 || live.calls[0].status !== 'pending') throw new Error('SDK select settled during host metadata transport');
      sample.pollCount = attempt + 1;
      const raw = readHostResponse(sample, responsePath + '.tmp');
      if (raw !== undefined) {
        sample.hostResponseJson = raw;
        let response: Tasks16_18HostResponse | undefined = undefined;
        try { response = JSON.parse(raw) as Tasks16_18HostResponse; }
        catch (error) { sample.lastPollError = 'Incomplete or invalid response JSON: ' + String(error); }
        if (response !== undefined) {
          if (typeof response.stdResult !== 'string') throw new Error('Host response lacks raw metadata');
          const bytes = new util.TextEncoder().encodeInto(response.stdResult);
          const md = cryptoFramework.createMd('SHA256');
          await md.update({ data: bytes });
          const digest = await md.digest();
          let sha256 = '';
          for (let index = 0; index < digest.data.length; index++) sha256 += digest.data[index].toString(16).padStart(2, '0');
          sample.responseStdoutSha256 = sha256;
          sample.responseStdoutBytes = bytes.length;
          validateTasks16To18ProviderHostResponse(requestJson, raw, sha256, bytes.length);
          if (Date.now() > deadline) throw new Error('Host response arrived outside the bounded pending observation window');
          fs.renameSync(responsePath + '.tmp', responsePath);
          sample.responseRenameApi = '@ohos.file.fs.renameSync';
          sample.responseRenamed = true;
          const finalStat = fs.statSync(responsePath);
          sample.responseFinalBytes = finalStat.size;
          if (finalStat.size !== sample.responseFileBytes ||
            fs.readTextSync(responsePath, { length: finalStat.size, encoding: 'utf-8' }) !== raw) {
            throw new Error('Renamed response differs from the validated temporary file');
          }
          sample.stdResult = response.stdResult;
          sample.exitCode = response.exitCode;
          sample.completed = true;
          return;
        }
      }
      publish(result, 'provider_host_wait');
      if (attempt < 15 && Date.now() < deadline) await driver.delayMs(250);
    }
    throw new Error('Nonce-bound host provider response unavailable within 8 seconds / 16 reads');
  } catch (error) { sample.error = String(error); }
  finally {
    sample.pickerStateAfterJson = readTasks16To18Picker();
    sample.finishedAtMs = Date.now();
    publish(result, 'provider_host_response_end');
  }
}

async function providerCommand(result: Tasks16_18UIResult, phase: string, command: string): Promise<void> {
  assertProbeBudget();
  const sample: Tasks16_18ProviderCommand = { command, phase, timeoutSecs: 3, startedAtMs: Date.now(),
    completed: false, pickerStateBeforeJson: readTasks16To18Picker() };
  if (result.providerCommands === undefined) result.providerCommands = [];
  result.providerCommands.push(sample);
  publish(result, 'provider_command_begin:' + phase + ':' + command);
  try {
    if (phase === 'pending_after' || phase === 'pending_metadata') {
      const picker = JSON.parse(sample.pickerStateBeforeJson) as Tasks16_18PickerSnapshot;
      if (picker.calls.length !== 1 || picker.calls[0].status !== 'pending') {
        throw new Error('No single pending SDK select; provider command was not executed.');
      }
    }
    const output: abilityDelegatorRegistry.ShellCmdResult =
      await abilityDelegatorRegistry.getAbilityDelegator().executeShellCommand(command, 3);
    sample.exitCode = output.exitCode;
    sample.stdResult = output.stdResult;
    sample.completed = true;
  } catch (error) { sample.error = String(error); }
  finally {
    sample.pickerStateAfterJson = readTasks16To18Picker();
    sample.finishedAtMs = Date.now();
    publish(result, 'provider_command_end:' + phase + ':' + command);
  }
}

function emit(result: Tasks16_18UIResult): void {
  const payload = JSON.stringify(result);
  const chunks = Math.ceil(payload.length / 1500);
  for (let index = 0; index < chunks; index++) {
    console.info('ARKTS_16_18_TRANSITION_UI_CHUNK ' + JSON.stringify({ taskId: result.taskId,
      caseId: result.caseId, index, chunks, text: payload.slice(index * 1500, (index + 1) * 1500) }));
  }
}

function selector(kind: string, value: string, bundleName: string): On {
  if (kind === 'id') return ON.id(value).inWindow(bundleName);
  if (kind === 'type') return ON.type(value).inWindow(bundleName);
  return ON.text(value).inWindow(bundleName);
}

function assertProbeBudget(): void {
  if (probeActive && (tasks16To18UICancelled() || Date.now() > probeDeadline)) {
    throw new Error('Bounded UI readback stopped; completed and partial checkpoints retained.');
  }
}

function publish(result: Tasks16_18UIResult, stage: string): void {
  publishTasks16To18UI(JSON.stringify(result), stage);
  const last = result.checkpoints[result.checkpoints.length - 1];
  console.info('ARKTS_16_18_UI_STAGE ' + JSON.stringify({ caseId: result.caseId, stage,
    label: last?.label, nodes: last?.nodes.length, focusedNodes: last?.focusedNodes?.length,
    elapsedMs: last?.elapsedMs, queryCount: last?.queryCount }));
}

// Some on-device UiTest versions return null for an empty query despite the
// SDK array declaration. Only null/undefined mean empty; real query errors propagate.
export async function findTasks16To18Components(driver: Driver, query: On): Promise<Component[]> {
  assertProbeBudget();
  return (await driver.findComponents(query)) ?? [];
}

async function readNode(component: Component): Promise<Tasks16_18UINode> {
  assertProbeBudget();
  return { id: await component.getId(), text: await component.getText(), type: await component.getType(),
    enabled: await component.isEnabled(), clickable: await component.isClickable(), bounds: await component.getBounds() };
}

async function soundQuery(driver: Driver, result: Tasks16_18UIResult, frame: Tasks16_18UICheckpoint,
  query: On, scope: string, focused: boolean): Promise<void> {
  frame.queryCount = (frame.queryCount || 0) + 1;
  publish(result, 'query_begin:' + scope);
  const matches = await findTasks16To18Components(driver, query);
  frame.queryResults?.push(scope + ':matches=' + matches.length);
  // Keyed anchors are small. More than two matches is ambiguous, not a reason
  // to inspect an unbounded system tree or select an arbitrary matching node.
  if (matches.length > 2) throw new Error('Ambiguous bounded anchor: ' + scope);
  for (const component of matches) {
    const node = await readNode(component);
    node.selectorScope = scope;
    if (focused) frame.focusedNodes?.push(node);
    else frame.nodes.push(node);
  }
  publish(result, 'query_end:' + scope);
}

async function soundSnapshot(driver: Driver, request: Tasks16_18UIRequest,
  result: Tasks16_18UIResult, frame: Tasks16_18UICheckpoint): Promise<void> {
  frame.pickerStateBeforeJson = readTasks16To18Picker();
  frame.focusedNodes = [];
  frame.queryResults = [];
  frame.queryCount = 0;
  // Read the real page early, including zero-instance evidence. Persistence is
  // needed only at the canonical before/after boundary and initial identity check.
  if (candidateContext !== undefined && ['candidate_entry', 'launch_audio_picker_before', 'after_event'].includes(frame.label)) {
    publish(result, 'page_read_begin');
    frame.pageStateJson = await readTasks16To18Page(candidateContext);
    frame.pickerStateJson = readTasks16To18Picker();
    publish(result, 'page_read_end');
  }
  assertProbeBudget();
  publish(result, 'window_read_begin');
  const focused = await driver.findWindow({ focused: true });
  if (focused) {
    frame.focusedBundle = await focused.getBundleName();
    frame.focusedTitle = await focused.getTitle();
  }
  publish(result, 'window_read_end');
  if (frame.label.startsWith('candidate_entry') && frame.focusedBundle === request.bundleName) {
    await soundQuery(driver, result, frame, ON.text('Notifications').inWindow(request.bundleName), 'candidate:title', false);
    await soundQuery(driver, result, frame, ON.id('message_sound_row').inWindow(request.bundleName), 'candidate:message-row', false);
  } else if (frame.label === 'launch_audio_picker_before') {
    await soundQuery(driver, result, frame, ON.id('message_sound_dialog').inWindow(request.bundleName), 'candidate:dialog', false);
    const extension = ON.type('UIExtensionComponent').inWindow(request.bundleName);
    for (const id of ['audiopicker_selected', 'audiopicker_button']) {
      await soundQuery(driver, result, frame, ON.id(id).within(extension).inWindow(request.bundleName),
        'audio-extension:' + id, true);
    }
  } else if (frame.label === 'after_event' && frame.focusedBundle) {
    // These IDs were observed in actual device output and exist in upstream
    // AudioPickerView. Query the system extension anchors, never all host nodes.
    const extension = ON.type('UIExtensionComponent').inWindow(frame.focusedBundle);
    for (const id of ['audiopicker_selected', 'audiopicker_button']) {
      await soundQuery(driver, result, frame, ON.id(id).within(extension).inWindow(frame.focusedBundle),
        'audio-extension:' + id, true);
    }
    if (frame.focusedNodes.length === 0) {
      // Diagnostic fallback does not establish extension ownership for scoring.
      for (const id of ['audiopicker_selected', 'audiopicker_button']) {
        await soundQuery(driver, result, frame, ON.id(id).inWindow(frame.focusedBundle), 'audio-unbound:' + id, true);
      }
    }
  }
  if (frame.label === 'after_event' && request.key === 'message_picker_launch' &&
    result.actions.some((action: Tasks16_18UIAction) => action.value === 'message_sound_picker')) {
    await providerCommand(result, 'pending_after', 'aa dump -e');
  }
  frame.pickerStateJson = readTasks16To18Picker();
}

async function snapshot(driver: Driver, request: Tasks16_18UIRequest,
  result: Tasks16_18UICheckpoint, transition: Tasks16_18UIResult): Promise<void> {
  if (request.taskId === '18_custom_notification_sounds') return soundSnapshot(driver, request, transition, result);
  assertProbeBudget();
  const focused = await driver.findWindow({ focused: true });
  if (focused) {
    result.focusedBundle = await focused.getBundleName();
    result.focusedTitle = await focused.getTitle();
  }
  const candidateWindow = await driver.findWindow({ bundleName: request.bundleName });
  if (!candidateWindow) {
    return;
  }
  const viewport = await candidateWindow.getBounds();
  // Read the candidate window only, even when the event opened another app.
  const queries: On[] = ['Button', 'Text', 'TextInput', 'Toggle'].map((type: string) => ON.type(type).inWindow(request.bundleName));
  for (const id of ['pinned_messages_loading', 'pinned_loading', 'pinned_messages_filled', 'pinned_list',
    'pinned_messages_empty', 'pinned_empty', 'pinned_messages_failed', 'pinned_failed',
    'message_sound_dialog', 'call_sound_dialog']) queries.push(ON.id(id).inWindow(request.bundleName));
  for (const query of queries) {
    const matches = await findTasks16To18Components(driver, query);
    for (const component of matches) {
      if (result.nodes.length >= 200) throw new Error('Candidate UI snapshot exceeded the bounded 200-node probe.');
      const bounds = await component.getBounds();
      if (Math.min(bounds.right, viewport.right) <= Math.max(bounds.left, viewport.left) ||
        Math.min(bounds.bottom, viewport.bottom) <= Math.max(bounds.top, viewport.top)) continue;
      result.nodes.push({ id: await component.getId(), text: await component.getText(), type: await component.getType(),
        enabled: await component.isEnabled(), clickable: await component.isClickable(), bounds });
    }
  }
}

function hasId(checkpoint: Tasks16_18UICheckpoint, ids: string[]): boolean {
  return checkpoint.nodes.some((node: Tasks16_18UINode) => ids.includes(node.id));
}

function hasText(checkpoint: Tasks16_18UICheckpoint, text: string): boolean {
  return checkpoint.nodes.some((node: Tasks16_18UINode) => node.text === text);
}

async function checkpoint(driver: Driver, request: Tasks16_18UIRequest,
  result: Tasks16_18UIResult, label: string): Promise<Tasks16_18UICheckpoint> {
  const started = Date.now();
  const observed: Tasks16_18UICheckpoint = { label, focusedBundle: '', focusedTitle: '', nodes: [], completed: false,
    startedAtMs: started };
  result.checkpoints.push(observed);
  publish(result, 'checkpoint_begin');
  try { await snapshot(driver, request, observed, result); observed.completed = true; }
  catch (error) { observed.error = String(error); throw new Error(observed.error); }
  finally { observed.finishedAtMs = Date.now(); observed.elapsedMs = observed.finishedAtMs - started; publish(result, 'checkpoint_end'); }
  return observed;
}

async function initialSoundRoot(driver: Driver, request: Tasks16_18UIRequest,
  result: Tasks16_18UIResult): Promise<Tasks16_18UICheckpoint> {
  const deadline = Math.min(probeDeadline, Date.now() + 5000);
  // Retry only initial readiness. Failed frames stay partial, and no existing
  // Window/Component handle is reused across attempts.
  for (let attempt = 0; attempt < 6 && Date.now() < deadline; attempt++) {
    assertProbeBudget();
    try {
      const root = await checkpoint(driver, request, result, attempt === 0 ? 'candidate_entry' : 'candidate_entry_' + attempt);
      const titles = root.nodes.filter((node: Tasks16_18UINode) => node.text === 'Notifications' &&
        node.bounds.right > node.bounds.left && node.bounds.bottom > node.bounds.top);
      const rows = root.nodes.filter((node: Tasks16_18UINode) => node.id === 'message_sound_row' &&
        node.enabled && node.clickable && node.bounds.right > node.bounds.left && node.bounds.bottom > node.bounds.top);
      if (root.completed === true && !root.error && root.focusedBundle === request.bundleName && titles.length === 1 && rows.length === 1) {
        root.initialReadiness = 'focused_candidate_and_visible_root_controls';
        publish(result, 'candidate_root_ready');
        return root;
      }
      root.initialReadiness = 'awaiting_focused_candidate_and_visible_root_controls';
      publish(result, 'candidate_root_wait');
    } catch (error) {
      // UiTest's device error contains the literal typo "dose". Do not treat
      // unrelated query/permission errors or post-event stale handles as readiness.
      const raw = String(error);
      if (!/Display\s*\d+\s*Window\s*\d+\s*(dose|does)\s+not\s+exist\s+on\s+current\s+UI/i.test(raw)) throw new Error(raw);
      const frame = result.checkpoints[result.checkpoints.length - 1];
      frame.initialReadiness = 'transient_stale_initial_window';
      publish(result, 'candidate_root_stale_window');
    }
    if (attempt < 5 && Date.now() < deadline) await driver.delayMs(100);
  }
  throw new Error('Notification settings root was not established within bounded initial readiness (6 samples / 5 seconds); raw frames retained.');
}

async function click(driver: Driver, request: Tasks16_18UIRequest, result: Tasks16_18UIResult,
  kind: string, value: string, label: string): Promise<Tasks16_18UICheckpoint> {
  const before = await checkpoint(driver, request, result, label + '_before');
  if (before.focusedBundle !== request.bundleName) throw new Error('Candidate is not the focused window before ' + label);
  const matches = await findTasks16To18Components(driver, selector(kind, value, request.bundleName));
  if (matches.length !== 1) throw new Error('Unique candidate control unavailable: ' + kind + ':' + value);
  const component = matches[0];
  assertProbeBudget();
  if (request.taskId === '18_custom_notification_sounds') {
    // The queried actual control supplies its properties, not selector-derived flags.
    const node = await readNode(component);
    before.nodes.push(node);
    publish(result, 'action_control_read');
    if (!node.enabled || !node.clickable || node.bounds.right <= node.bounds.left || node.bounds.bottom <= node.bounds.top) {
      throw new Error('Candidate control is not visibly actionable: ' + value);
    }
    if (value === 'message_sound_picker' && request.key === 'message_picker_launch') {
      await providerCommand(result, 'before_picker', 'aa dump -e');
    }
    assertProbeBudget();
    await component.click();
    result.actions.push({ kind, value, before: before.label, after: label + '_after' });
    publish(result, 'action_completed');
    return checkpoint(driver, request, result, label + '_after');
  }
  const bounds = await component.getBounds();
  if (!await component.isEnabled() || !await component.isClickable() || bounds.right <= bounds.left || bounds.bottom <= bounds.top) {
    throw new Error('Candidate control is not visibly actionable: ' + value);
  }
  await component.click();
  result.actions.push({ kind, value, before: before.label, after: label + '_after' });
  publish(result, 'action_completed');
  return checkpoint(driver, request, result, label + '_after');
}

async function settlePinned(driver: Driver, request: Tasks16_18UIRequest,
  result: Tasks16_18UIResult): Promise<Tasks16_18UICheckpoint> {
  let observed = await checkpoint(driver, request, result, 'list_sample_0');
  for (let attempt = 1; attempt <= 15; attempt++) {
    if (hasId(observed, ['pinned_messages_filled', 'pinned_list', 'pinned_messages_empty', 'pinned_empty',
      'pinned_messages_failed', 'pinned_failed'])) return observed;
    await driver.delayMs(100);
    observed = await checkpoint(driver, request, result, 'list_sample_' + attempt);
  }
  throw new Error('Pinned list did not expose a settled candidate UI state within the bounded probe.');
}

// Task17 storage is seeded with the launched ability's original Context before
// opening the list. This probe never creates or replaces its presenter.
export async function probeTasks16To18Transition(request: Tasks16_18UIRequest): Promise<Tasks16_18UIResult> {
  const result: Tasks16_18UIResult = { schemaVersion: 1, taskId: request.taskId, caseId: request.caseId,
    key: request.key, bundleName: request.bundleName, observationLevel: 'native_candidate_ui',
    checkpoints: [], actions: [], unsupported: '' };
  const driver = Driver.create();
  if (probeActive) {
    result.unsupported = 'Another candidate UI probe is active; page instances cannot be merged.';
    return result;
  }
  probeActive = true;
  // Leave 10 seconds under the adapter's 45-second watchdog for evidence and
  // monitor cleanup. No new queries/actions start after this cooperative budget.
  probeDeadline = Date.now() + 35000;
  publish(result, 'probe_begin');
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  const monitor: abilityDelegatorRegistry.AbilityMonitor = { abilityName: request.abilityName || 'EntryAbility' };
  let monitoring = false;
  let fixturePrepared = false;
  try {
    if (request.taskId === '18_custom_notification_sounds') {
      const parameters = abilityDelegatorRegistry.getArguments().parameters;
      const user = parameters['-s ltbDeviceUser'];
      result.executionNonce = parameters['-s ltbExecutionNonce'];
      result.hostProviderTransportEnabled = parameters['-s ltbProviderHostBridge'] === '1';
      result.deviceUserParameter = user;
      result.deviceUserSource = 'AbilityDelegatorRegistry.getArguments().parameters["-s ltbDeviceUser"]';
      if (typeof user === 'string' && /^(0|[1-9][0-9]{0,9})$/.test(user) && Number(user) <= 2147483647) {
        result.deviceUserId = user;
      } else {
        result.deviceUserError = 'Missing/invalid executor installed-user inventory parameter; no default user is assumed.';
      }
      publish(result, 'device_user_parameter');
    }
    await delegator.addAbilityMonitor(monitor);
    monitoring = true;
    await delegator.startAbility({ bundleName: request.bundleName,
      abilityName: request.abilityName || 'EntryAbility' });
    const ability = await delegator.waitAbilityMonitor(monitor, 3000);
    candidateContext = ability.context;
    let root: Tasks16_18UICheckpoint;
    if (request.taskId === '18_custom_notification_sounds') {
      root = await initialSoundRoot(driver, request, result);
    } else {
      root = await checkpoint(driver, request, result, 'candidate_entry');
      for (let attempt = 0; root.focusedBundle !== request.bundleName && attempt < 15; attempt++) {
        await driver.delayMs(100);
        root = await checkpoint(driver, request, result, 'candidate_entry_' + attempt);
      }
    }
    if (root.focusedBundle !== request.bundleName) throw new Error('Actual candidate window did not become focused.');
    if (request.taskId === '17_pinned_messages') {
      if (!hasText(root, 'Design team')) throw new Error('Fresh room timeline root was not established.');
      const entry = root.nodes.find((node: Tasks16_18UINode) => ['open_pinned_messages', 'pinned_banner_open'].includes(node.id));
      if (entry === undefined) throw new Error('No mapped actionable pinned-list entry in actual candidate UI.');
      if (request.key === 'view_in_timeline') {
        assertProbeBudget();
        publish(result, 'page_fixture_prepare_begin');
        await prepareTasks16To18Page(candidateContext);
        fixturePrepared = true;
        publish(result, 'page_fixture_prepare_end');
        assertProbeBudget();
      }
      await click(driver, request, result, 'id', entry.id, 'open_pinned_messages');
      if (request.key === 'open_loading') {
        // Preserve the immediate frame even if loading completes before UiTest can sample it.
        const list = await settlePinned(driver, request, result);
        const back = list.nodes.find((node: Tasks16_18UINode) => node.id === 'pinned_messages_back' || node.text === 'Back');
        if (back === undefined) throw new Error('List parent-navigation control is not observable.');
        await click(driver, request, result, back.id ? 'id' : 'text', back.id || back.text, 'return_to_parent');
        result.unsupported = 'UI frames establish only observed navigation/loading. Page-instance timeline-call evidence is still required; a missed loading frame is not a semantic failure.';
      } else if (request.key === 'view_in_timeline') {
        await settlePinned(driver, request, result);
        if (!request.eventId) throw new Error('Canonical GIVEN eventId is required.');
        await click(driver, request, result, 'id', 'view_in_timeline_' + request.eventId, 'view_in_timeline');
      } else {
        throw new Error('UI transition is outside this bounded navigation probe: ' + request.key);
      }
    } else if (request.taskId === '16_identity_reset') {
      if (!hasId(root, ['identity_reset_continue'])) throw new Error('Fresh identity root was not established.');
      if (request.key === 'oidc_handle_routes_and_resets') {
        const toggles = await findTasks16To18Components(driver, ON.type('Toggle').inWindow(request.bundleName));
        if (toggles.length !== 1 || !hasText(root, 'Use SSO approval demo')) throw new Error('No mapped UI authentication selector.');
        if (!await toggles[0].isChecked()) await click(driver, request, result, 'type', 'Toggle', 'select_oidc');
      }
      await click(driver, request, result, 'id', 'identity_reset_continue', 'continue');
      await click(driver, request, result, 'text', 'Reset identity', 'confirm_reset');
      if (request.key === 'cancel_cleans_up') {
        await click(driver, request, result, 'text', 'Exit reset', 'cancel_reset');
        result.unsupported = 'Real page exit is observed, but active SDK jobs, same-handle cancellation and node-destruction cleanup are not exposed by UI. No separate presenter is substituted.';
      } else {
        result.unsupported = 'Approval-page text/window is raw evidence only. OIDC launch, custom-tab fallback and SDK polling require observations from this same page instance.';
      }
    } else if (request.taskId === '18_custom_notification_sounds' && request.key === 'message_picker_launch') {
      if (!hasText(root, 'Notifications')) throw new Error('Notification settings root was not established.');
      assertProbeBudget();
      publish(result, 'original_module_bind_begin');
      result.originalModuleBindingJson = await bindTasks16To18OriginalPage(candidateContext, JSON.stringify(root));
      publish(result, 'originalModuleBound');
      assertProbeBudget();
      await click(driver, request, result, 'id', 'message_sound_row', 'open_message_dialog');
      await click(driver, request, result, 'id', 'message_sound_picker', 'launch_audio_picker');
      // Do not await the picker Promise or select a file: this case observes launch,
      // including persistence while the actual native selection is still pending.
      await driver.delayMs(100);
    } else throw new Error('No mapped real-page probe for this task/key.');
  } catch (error) {
    result.unsupported = String(error);
  }
  try { await checkpoint(driver, request, result, 'after_event'); }
  catch (error) { result.unsupported = result.unsupported || String(error); }
  if (request.taskId === '18_custom_notification_sounds' && result.providerCommands !== undefined) {
    try {
      const command = tasks16To18ProviderMetadataCommand(JSON.stringify(result));
      if (command) await providerCommand(result, 'pending_metadata', command);
      result.providerEvidenceJson = summarizeTasks16To18ProviderEvidence(JSON.stringify(result));
      const summary = JSON.parse(result.providerEvidenceJson) as Tasks16_18ProviderSummary;
      if (command && !summary.providerIdentityVerified && result.hostProviderTransportEnabled) {
        await hostProviderMetadata(result, driver, command);
        result.providerEvidenceJson = summarizeTasks16To18ProviderEvidence(JSON.stringify(result));
      }
    }
    catch (error) { result.unsupported = result.unsupported || 'Provider evidence parsing failed: ' + String(error); }
    publish(result, 'provider_evidence_parsed');
  }
  if (fixturePrepared && candidateContext !== undefined) {
    try {
      assertProbeBudget();
      publish(result, 'page_fixture_readback_begin');
      await finishTasks16To18Page(candidateContext);
      publish(result, 'page_fixture_readback_end');
    } catch (error) { result.unsupported = result.unsupported || String(error); }
  }
  if (monitoring) {
    try { await delegator.removeAbilityMonitor(monitor); }
    catch (error) { result.unsupported = result.unsupported || String(error); }
  }
  candidateContext = undefined;
  probeActive = false;
  publish(result, 'probe_end');
  if (request.emitChunks !== false) emit(result);
  return result;
}
