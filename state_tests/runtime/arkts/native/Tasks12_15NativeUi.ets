import type { Driver, On, Component, Rect } from '@ohos.UiTest';
import inputMethod from '@ohos.inputMethod';
import { readTasks12ReportPage, ReportPageSnapshot } from './Tasks12_15ReportPageObserver';

let ON: On;
// Call only after the runner's onRun has initialized UiTest.
export function configureTasks12To15Selectors(selectors: On): void { ON = selectors; }

// Device-only companion. It queries the unchanged app's accessibility tree, not
// a second presenter. The caller owns app launch, cold reset and service fixtures.
export interface Tasks12To15Control {
  selector: string;
  id?: string;
  present: boolean;
  visible?: boolean;
  enabled?: boolean;
  checked?: boolean;
  focused?: boolean;
  text?: string;
  bounds?: Rect;
}

export interface Tasks12To15Observation {
  reason?: string;
  address?: string;
  surface?: string;
  searchActive?: boolean;
  submitEnabled?: boolean;
  canReport?: boolean;
  retryEnabled?: boolean;
  editingEnabled?: boolean;
  leaveRoom?: boolean;
  eraseData?: boolean;
  confirmationVisible?: boolean;
  deactivateEntryVisible?: boolean;
  addressFlowVisible?: boolean;
  errorVisible?: boolean;
  verifyActionVisible?: boolean;
  profileBadge?: string;
  timelineWarning?: boolean;
  roomMemberWarning?: boolean;
  formControlsDisabled?: boolean;
  acceptEnabled?: boolean;
  declineEnabled?: boolean;
  renderedChallenge?: string;
  completionVisible?: boolean;
}

export interface Tasks12To15Frame {
  label: string;
  sessionId?: string;
  sequence?: number;
  bundleName?: string;
  observed: Tasks12To15Observation;
  controls: Tasks12To15Control[];
  presenterEvidence?: ReportPageSnapshot;
}

export interface Tasks12To15Action {
  sessionId: string;
  sequence: number;
  kind: string;
  target: string;
  executed: boolean;
  attemptedAt: number;
  completedAt?: number;
  settleMs: number;
  value?: string;
  error?: string;
}

export interface Tasks12To15Prerequisite {
  status: string;
  rootConfirmed: boolean;
  reason: string;
  controls: Tasks12To15Control[];
}

export class Tasks12To15Ui {
  private driver: Driver;
  private bundleName: string;
  private controls: Tasks12To15Control[] = [];
  private sessionId: string;
  private sequence: number = 0;
  private actions: Tasks12To15Action[] = [];

  constructor(driver: Driver, bundleName: string, sessionId: string = 'ui_' + Date.now()) {
    this.driver = driver;
    this.bundleName = bundleName;
    this.sessionId = sessionId;
  }

  actionLog(): Tasks12To15Action[] { return this.actions.slice(); }

  frame(label: string, observed: Tasks12To15Observation, controls: Tasks12To15Control[]): Tasks12To15Frame {
    return { label, sessionId: this.sessionId, sequence: ++this.sequence,
      bundleName: this.bundleName, observed, controls };
  }

  private async find(selectors: On[]): Promise<Component | undefined> {
    for (const selector of selectors) {
      const matches: Component[] = (await this.driver.findComponents(selector.inWindow(this.bundleName))) || [];
      if (matches.length > 1) throw new Error('Ambiguous native selector; refusing to choose an arbitrary control.');
      if (matches.length === 1) return matches[0];
    }
    return undefined;
  }

  private async inspect(name: string, selectors: On[]): Promise<Tasks12To15Control> {
    const component: Component | undefined = await this.find(selectors);
    const result: Tasks12To15Control = { selector: name, present: component !== undefined };
    if (component !== undefined) {
      result.text = await component.getText();
      result.id = await component.getId();
      result.enabled = await component.isEnabled();
      result.focused = await component.isFocused();
      if (await component.isCheckable()) result.checked = await component.isChecked();
      result.bounds = await component.getBounds();
      const window = await this.driver.findWindow({ bundleName: this.bundleName });
      if (!window) throw new Error('Candidate app window is unavailable.');
      const viewport: Rect = await window.getBounds();
      const bounds: Rect = result.bounds;
      // Intersection establishes onscreen tree visibility, not pixel color,
      // opacity, occlusion or destructive styling.
      result.visible = Math.min(bounds.right, viewport.right) > Math.max(bounds.left, viewport.left) &&
        Math.min(bounds.bottom, viewport.bottom) > Math.max(bounds.top, viewport.top);
    } else {
      result.visible = false;
    }
    this.controls.push(result);
    return result;
  }

  async click(selectors: On[], settleMs: number = 100): Promise<void> {
    if (!Number.isFinite(settleMs) || settleMs < 0 || settleMs > 1000) throw new Error('Invalid UI settling interval.');
    const target: Component | undefined = await this.find(selectors);
    if (target === undefined) throw new Error('Required native event control is absent.');
    if (!await target.isEnabled()) throw new Error('Native event control is disabled; presenter event was not injected.');
    const visible = await this.inspect('action target', selectors);
    if (visible.visible !== true) throw new Error('Native event target is offscreen.');
    const action: Tasks12To15Action = { sessionId: this.sessionId, sequence: ++this.sequence,
      kind: 'click', target: visible.id || visible.text || 'unkeyed control', executed: false,
      attemptedAt: Date.now(), settleMs };
    this.actions.push(action);
    await target.click();
    action.executed = true;
    action.completedAt = Date.now();
    if (settleMs > 0) await this.driver.delayMs(settleMs);
  }

  async input(selectors: On[], value: string): Promise<void> {
    const target: Component | undefined = await this.find(selectors);
    if (target === undefined || !await target.isEnabled()) throw new Error('Native input is absent or disabled.');
    const visible = await this.inspect('input target', selectors);
    if (visible.visible !== true) throw new Error('Native input is offscreen.');
    const action: Tasks12To15Action = { sessionId: this.sessionId, sequence: ++this.sequence,
      kind: 'input', target: visible.id || 'unkeyed input', executed: false,
      attemptedAt: Date.now(), settleMs: 100, value };
    this.actions.push(action);
    await target.inputText(value);
    action.executed = true;
    action.completedAt = Date.now();
    // This wait is for UI settling only. Never use it as exact debounce evidence.
    await this.driver.delayMs(100);
  }

  async select(selectors: On[], value: boolean): Promise<void> {
    const target: Component | undefined = await this.find(selectors);
    if (target === undefined) throw new Error('Native toggle is absent from the candidate window tree.');
    if (!await target.isCheckable()) throw new Error('Native toggle is present but not checkable: ' +
      JSON.stringify(await this.inspect('uncheckable toggle', selectors)));
    if (await target.isChecked() !== value) await this.click(selectors);
  }

  async dismissInputMethod(): Promise<void> {
    // OS-only fixture housekeeping, never Back (which could navigate away).
    // Success is not proof of visibility; subsequent native queries still are.
    const action: Tasks12To15Action = { sessionId: this.sessionId, sequence: ++this.sequence,
      kind: 'hide_input_method', target: 'inputMethod.getController().hideTextInput',
      executed: false, attemptedAt: Date.now(), settleMs: 100 };
    this.actions.push(action);
    try {
      await inputMethod.getController().hideTextInput();
      action.executed = true;
    } catch (error) {
      action.error = String(error);
    }
    action.completedAt = Date.now();
    await this.driver.delayMs(100);
  }

  async prerequisite(taskId: string): Promise<Tasks12To15Prerequisite> {
    this.controls = [];
    let root: boolean = false;
    let entry: Tasks12To15Control;
    if (taskId === '12_report_room') {
      root = (await this.inspect('room title', [ON.text('Community support')])).visible === true;
      entry = await this.inspect('report entry or form', [ON.id('open_report_room'), ON.id('submit_report_room'), ON.id('submit_report'), ON.type('Button').text('Report room')]);
      root = root || (await this.inspect('report reason', [ON.id('report_room_reason'), ON.id('report_reason_input')])).visible === true;
    } else if (taskId === '13_user_verification') {
      root = (await this.inspect('profile user', [ON.text('@alice:example.org')])).visible === true &&
        (await this.inspect('profile title', [ON.text('Alice')])).visible === true;
      entry = await this.inspect('verify user entry', [ON.id('verify_user_action'), ON.id('start_user_verification')]);
    } else if (taskId === '14_join_room_by_address') {
      root = (await this.inspect('start chat', [ON.text('Start a chat')])).visible === true &&
        (await this.inspect('create room', [ON.type('Button').text('Create room')])).visible === true &&
        (await this.inspect('invite friends', [ON.type('Button').text('Invite friends')])).visible === true;
      entry = await this.inspect('join address entry', [ON.id('join_room_by_address'), ON.id('join_by_address_button'), ON.type('Button').text('Join a room by address')]);
    } else if (taskId === '15_account_deactivation') {
      root = (await this.inspect('settings', [ON.text('Settings')])).visible === true &&
        (await this.inspect('notifications', [ON.type('Button').text('Notifications')])).visible === true &&
        (await this.inspect('sign out', [ON.type('Button').text('Sign out')])).visible === true;
      entry = await this.inspect('deactivation entry', [ON.id('deactivate_account_entry'), ON.type('Button').text('Deactivate account')]);
    } else {
      throw new Error('Task is outside the native 12-15 adapter.');
    }
    let status: string = 'unavailable';
    let reason: string = 'The expected app root was not confirmed; no semantic absence is inferred.';
    if (root && entry.visible === true) {
      status = 'available';
      reason = 'Actual app root and feature entry/form are present in the native tree.';
    } else if (root && !entry.present) {
      status = 'absent';
      reason = 'Actual app root rendered, but its feature entry/form is absent. Not a missing-class failure.';
    } else if (root) {
      reason = 'Feature exists in the tree but is offscreen; scroll/render binding is required.';
    }
    return { status, rootConfirmed: root, reason, controls: this.controls.slice() };
  }

  async open(taskId: string): Promise<void> {
    if (taskId === '12_report_room') {
      if (await this.find([ON.id('report_room_reason'), ON.id('report_reason_input')]) === undefined) {
        await this.click([ON.id('open_report_room'), ON.type('Button').text('Report room')]);
      }
    } else if (taskId === '14_join_room_by_address') {
      await this.click([ON.id('join_room_by_address'), ON.id('join_by_address_button'), ON.type('Button').text('Join a room by address')]);
    } else if (taskId === '15_account_deactivation') {
      await this.click([ON.id('deactivate_account_entry'), ON.type('Button').text('Deactivate account')]);
    }
  }

  // A live fixture bridge can call capture before/after its events on the
  // SAME rendered instance. Never merge these frames with a separate presenter.
  async capture(taskId: string, label: string): Promise<Tasks12To15Frame> {
    this.controls = [];
    if (!await this.driver.findWindow({ bundleName: this.bundleName })) throw new Error('Candidate app window is unavailable.');
    const observed: Tasks12To15Observation = {};
    let presenterEvidence: ReportPageSnapshot | undefined = undefined;
    if (taskId === '12_report_room') {
      const input = await this.inspect('report reason', [ON.id('report_room_reason'), ON.id('report_reason_input')]);
      if (!input.present) throw new Error('Report form is not rendered.');
      const submit = await this.inspect('report submit', [ON.id('submit_report_room'), ON.id('submit_report')]);
      const retry = await this.inspect('report retry', [ON.id('retry_leave_room'), ON.id('retry_report_room'), ON.id('retry_leave_only')]);
      const leave = await this.inspect('leave preference', [ON.id('report_room_leave_toggle'), ON.id('leave_room_toggle')]);
      observed.submitEnabled = submit.enabled;
      observed.reason = input.text;
      observed.retryEnabled = retry.enabled;
      observed.leaveRoom = leave.checked;
      const live = readTasks12ReportPage();
      presenterEvidence = live;
      // Never stitch a separately constructed presenter's getter onto this UI.
      // Unique page calls must agree with the actual rendered form values.
      if (input.visible === true && submit.visible === true && leave.visible === true &&
        live.available && live.reason === input.text && live.leaveRoom === leave.checked &&
        live.calls.some(call => call.completed && call.method === 'updateReason' && call.value === input.text) &&
        live.calls.some(call => call.completed && call.method === 'toggleLeaveRoom')) {
        observed.canReport = live.canReport;
      }
    } else if (taskId === '13_user_verification') {
      if (!(await this.inspect('profile user', [ON.text('@alice:example.org')])).present) throw new Error('Profile surface is not rendered.');
      const profile = await this.inspect('profile violation', [ON.id('profile_verification_violation'), ON.id('identity_violation_badge')]);
      if (profile.visible) observed.profileBadge = 'verification_violation';
      observed.timelineWarning = (await this.inspect('timeline warning', [ON.id('timeline_identity_warning')])).visible;
      observed.roomMemberWarning = (await this.inspect('member warning', [ON.id('room_member_identity_warning')])).visible;
      observed.verifyActionVisible = (await this.inspect('verify user', [ON.id('verify_user_action'), ON.id('start_user_verification')])).visible;
      observed.acceptEnabled = (await this.inspect('accept challenge', [ON.id('accept_sas_challenge'), ON.id('accept_challenge')])).enabled;
      observed.declineEnabled = (await this.inspect('decline challenge', [ON.id('decline_sas_challenge'), ON.id('decline_challenge')])).enabled;
      observed.renderedChallenge = (await this.inspect('SAS', [ON.id('sas_challenge'), ON.id('sas_text')])).text;
      observed.completionVisible = (await this.inspect('verification complete', [ON.id('verification_completed'), ON.id('verified_user_badge')])).visible;
    } else if (taskId === '14_join_room_by_address') {
      const input = await this.inspect('room address', [ON.id('room_address_input'), ON.id('address_input')]);
      if (!input.present && await this.find([ON.text('Start a chat'), ON.id('preview_room_id')]) === undefined) throw new Error('Neither the address flow nor its navigation destination is rendered.');
      observed.addressFlowVisible = input.visible;
      if (input.present) observed.address = input.text;
      observed.editingEnabled = input.enabled;
      if (!input.present) {
        const search = await this.inspect('people search', [ON.id('people_search_input'), ON.type('TextInput')]);
        if (search.present && search.text === '' && search.focused === false) observed.searchActive = false;
        observed.surface = 'start_chat';
      }
      if (input.present) {
        observed.errorVisible = (await this.inspect('address error', [ON.id('address_error_message'), ON.id('address_validation_message'), ON.id('address_notfound_label'), ON.text('Enter a valid Matrix room address'), ON.text('Room not found. Check the address and retry.')])).visible;
      }
      await this.inspect('room preview', [ON.id('preview_room_id')]);
    } else if (taskId === '15_account_deactivation') {
      const input = await this.inspect('deactivation password', [ON.id('deactivation_password'), ON.type('TextInput')]);
      if (input.present) {
        const submit = await this.inspect('deactivation submit', [ON.id('deactivate_submit'), ON.type('Button').text('Deactivate account')]);
        const erase = await this.inspect('erase preference', [ON.type('Toggle'), ON.type('Checkbox')]);
        observed.submitEnabled = submit.enabled;
        observed.eraseData = erase.checked;
        observed.confirmationVisible = (await this.inspect('deactivation confirmation', [ON.text('Are you sure you want to deactivate this account?'), ON.text('Confirm deactivation')])).visible;
        observed.retryEnabled = (await this.inspect('deactivation retry', [ON.type('Button').text('Retry')])).enabled;
        if (input.enabled !== undefined && submit.enabled !== undefined && erase.enabled !== undefined) {
          observed.formControlsDisabled = !input.enabled && !submit.enabled && !erase.enabled;
        }
        observed.completionVisible = (await this.inspect('deactivation completed', [ON.text('Account deactivated')])).visible;
      } else {
        if (await this.find([ON.text('Settings')]) === undefined) throw new Error('Settings surface is not rendered.');
        observed.surface = 'settings';
        observed.deactivateEntryVisible = (await this.inspect('deactivation entry', [ON.id('deactivate_account_entry'), ON.type('Button').text('Deactivate account')])).visible;
      }
    }
    const frame: Tasks12To15Frame = this.frame(label, observed, this.controls.slice());
    if (presenterEvidence !== undefined) frame.presenterEvidence = presenterEvidence;
    console.info('ARKTS_NATIVE_UI_CHECKPOINT ' + JSON.stringify(frame));
    return frame;
  }
}
