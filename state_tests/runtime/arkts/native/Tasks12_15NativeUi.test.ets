import { describe, it, expect } from '@ohos/hypium';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import { Driver, ON } from '@ohos.UiTest';
import { Tasks12To15Ui, Tasks12To15Frame, Tasks12To15Prerequisite, Tasks12To15Observation, Tasks12To15Action, configureTasks12To15Selectors } from './Tasks12_15NativeUi';
import { ReportPageObserver, ReportPageSnapshot, readTasks12ReportPage } from './Tasks12_15ReportPageObserver';
import type { BusinessError } from '@ohos.base';
import { installTasks12ReportPageAfterReady } from './Tasks12_15NativeUi.binding';

export interface NativeUiCase {
  taskId: string;
  key: string;
  caseId: string;
  traceDigest: string;
  given: Record<string, Object>;
  event: Record<string, Object>;
  expected: Record<string, Object>;
  invariants: string[];
}

interface NativeUiFieldCheck {
  field: string;
  observed: boolean;
  passed?: boolean;
  expected: Object;
  actual?: Object;
}

interface NativeUiAssertion {
  evaluated: boolean;
  identityMatches: boolean;
  eventEligible: boolean;
  sameUiSession: boolean;
  samePresenterInstance?: boolean;
  missingGivens: string[];
  missingExpected: string[];
  missingInvariants: string[];
  passed?: boolean;
}

interface NativeUnsupportedInvariant {
  description: string;
  reason: string;
}

interface NativeUiInvariant {
  description: string;
  passed: boolean;
  observed: Tasks12To15Frame[];
}

interface NativeUiFailure {
  stage: string;
  message: string;
  stack?: string;
  code?: number;
  presenterEvidence?: ReportPageSnapshot;
  captureError?: string;
}

export interface NativeUiResult {
  taskId: string;
  caseId: string;
  observationLevel: string;
  status: string;
  eventExecuted: boolean;
  entryExecuted: boolean;
  traceDigest?: string;
  sessionId?: string;
  actions?: Tasks12To15Action[];
  givenChecks?: NativeUiFieldCheck[];
  expectedChecks?: NativeUiFieldCheck[];
  canonicalAssertion?: NativeUiAssertion;
  observed?: Tasks12To15Observation;
  prerequisite?: Tasks12To15Prerequisite;
  frames: Tasks12To15Frame[];
  unsupported: string;
  unsupportedInvariants: NativeUnsupportedInvariant[];
  invariantChecks: NativeUiInvariant[];
  failure?: NativeUiFailure;
}

function fieldChecks(expected: Record<string, Object>, frame: Tasks12To15Frame | undefined): NativeUiFieldCheck[] {
  const observed: Record<string, Object> = frame === undefined ? {} : JSON.parse(JSON.stringify(frame.observed));
  const checks: NativeUiFieldCheck[] = [];
  for (const field of Object.keys(expected)) {
    const present = observed[field] !== undefined;
    const check: NativeUiFieldCheck = { field, observed: present, expected: expected[field] };
    if (present) {
      check.actual = observed[field];
      check.passed = JSON.stringify(observed[field]) === JSON.stringify(expected[field]);
    }
    checks.push(check);
  }
  return checks;
}

// Do not combine UI frames with an independently constructed domain presenter.
// Missing internal fields, external givens, or invariants keep the whole case NS.
export function finalizeNativeUiResult(result: NativeUiResult, spec: NativeUiCase): void {
  result.status = 'not_scored';
  if (!spec.given || !spec.expected || !spec.event || !Array.isArray(spec.invariants)) return;
  const before = result.frames.find(frame => frame.label === 'before_event');
  const after = result.frames.find(frame => frame.label === 'after_event');
  const identityMatches = result.taskId === spec.taskId && result.caseId === spec.caseId &&
    result.traceDigest === spec.traceDigest && /^[0-9a-f]{64}$/.test(spec.traceDigest);
  const sameUiSession = before !== undefined && after !== undefined &&
    result.sessionId !== undefined && before.sessionId === result.sessionId && after.sessionId === result.sessionId &&
    typeof before.bundleName === 'string' && before.bundleName.length > 0 && before.bundleName === after.bundleName &&
    before.sequence !== undefined && after.sequence !== undefined &&
    before.sequence < after.sequence;
  result.givenChecks = fieldChecks(spec.given, before);
  result.expectedChecks = fieldChecks(spec.expected, after);
  const missingGivens = result.givenChecks.filter(check => check.passed !== true).map(check => check.field);
  const missingExpected = result.expectedChecks.filter(check => !check.observed).map(check => check.field);
  const missingInvariants = spec.invariants.filter(description =>
    !result.invariantChecks.some(check => check.description === description));
  const hasAction = (result.actions || []).some(action => action.executed && action.sessionId === result.sessionId &&
    before !== undefined && after !== undefined && before.sequence !== undefined && after.sequence !== undefined &&
    action.sequence > before.sequence && action.sequence < after.sequence);
  const samePresenterInstance = spec.taskId !== '12_report_room' || spec.key !== 'blank_reason_disabled' ||
    (before?.presenterEvidence?.available === true && after?.presenterEvidence?.available === true &&
      before.presenterEvidence.instanceCount === 1 && after.presenterEvidence.instanceCount === 1 &&
      before.presenterEvidence.instanceId === after.presenterEvidence.instanceId);
  const eventEligible = identityMatches && result.eventExecuted && sameUiSession && samePresenterInstance && missingGivens.length === 0 &&
    (hasAction || spec.event['name'] === 'render_report_form');
  const evaluated = eventEligible && missingExpected.length === 0 && missingInvariants.length === 0;
  result.canonicalAssertion = { evaluated, identityMatches, eventEligible, sameUiSession, samePresenterInstance, missingGivens, missingExpected, missingInvariants };
  result.status = 'not_scored';
  if (evaluated) {
    const passed = result.expectedChecks.every(check => check.passed === true) &&
      result.invariantChecks.every(check => check.passed);
    result.canonicalAssertion.passed = passed;
    result.status = passed ? 'passed' : 'failed';
    result.unsupported = '';
  }
}

function emitResult(result: NativeUiResult): void {
  const json = JSON.stringify(result);
  const chunks = Math.ceil(json.length / 1600);
  for (let index = 0; index < chunks; index++) {
    console.info('ARKTS_12_15_UI_CHUNK ' + JSON.stringify({ taskId: result.taskId, caseId: result.caseId,
      traceDigest: result.traceDigest, sessionId: result.sessionId, index, chunks, text: json.slice(index * 1600, (index + 1) * 1600) }));
  }
}

function checkNativeInvariants(result: NativeUiResult): void {
  const before: Tasks12To15Frame | undefined = result.frames.find(frame => frame.label === 'before_event');
  const after: Tasks12To15Frame | undefined = result.frames.find(frame => frame.label === 'after_event');
  if (!result.eventExecuted || before === undefined || after === undefined) return;
  for (const invariant of result.unsupportedInvariants) {
    let passed: boolean | undefined = undefined;
    if (invariant.description === 'editing the reason does not toggle leave' &&
      before.observed.leaveRoom !== undefined && after.observed.leaveRoom !== undefined) {
      passed = before.observed.leaveRoom === after.observed.leaveRoom;
    } else if (invariant.description === 'leave preference remains selected' &&
      before.observed.leaveRoom !== undefined && after.observed.leaveRoom !== undefined) {
      passed = before.observed.leaveRoom && after.observed.leaveRoom;
    } else if (invariant.description === 'the reason remains unchanged') {
      const prior = before.controls.find(control => control.selector === 'report reason');
      const next = after.controls.find(control => control.selector === 'report reason');
      if (prior !== undefined && next !== undefined && prior.text !== undefined && next.text !== undefined) {
        passed = prior.text === next.text;
      }
    } else if (invariant.description === 'invalid feedback is suppressed before validation is requested' &&
      before.observed.errorVisible !== undefined) {
      passed = !before.observed.errorVisible;
    } else if (invariant.description === 'the SAS challenge is unchanged' &&
      before.observed.renderedChallenge !== undefined && after.observed.renderedChallenge !== undefined) {
      passed = before.observed.renderedChallenge === after.observed.renderedChallenge;
    }
    if (passed !== undefined) result.invariantChecks.push({ description: invariant.description, passed, observed: [before, after] });
  }
  result.unsupportedInvariants = result.unsupportedInvariants.filter(invariant =>
    !result.invariantChecks.some(check => check.description === invariant.description));
}

// Install with the candidate's device ohosTest target, NOT the domain-only
// Previewer sidecar. Run once per cold app process. Runner parameters:
// taskId, caseSpec (canonical case JSON), optional abilityName. No role switch.
// Blank-reason rendering can be complete with the original same-page observer.
// Other missing gateway/state fields remain NS. Never combine separate instances.
export async function runTasks12To15NativeUi(caseSpec: NativeUiCase, bundleName: string,
  abilityName: string = 'EntryAbility'): Promise<NativeUiResult> {
      const result: NativeUiResult = {
        taskId: '', caseId: '', observationLevel: 'native_ui', status: 'not_scored', eventExecuted: false, entryExecuted: false,
        frames: [], unsupported: 'Partial UI evidence; external effects and remaining invariants require same-instance live fixtures.',
        unsupportedInvariants: [], invariantChecks: []
      };
      let ui: Tasks12To15Ui | undefined = undefined;
      let pageObserver: ReportPageObserver | undefined = undefined;
      let stage: string = 'validate_case';
      try {
        const taskId: string = caseSpec.taskId;
        if (!bundleName || !taskId || !caseSpec.caseId || !/^[0-9a-f]{64}$/.test(caseSpec.traceDigest) ||
          !caseSpec.given || !caseSpec.event || !caseSpec.expected || !Array.isArray(caseSpec.invariants)) {
          throw new Error('A complete canonical case including traceDigest is required.');
        }
        result.taskId = taskId;
        result.caseId = caseSpec.caseId;
        result.traceDigest = caseSpec.traceDigest;
        result.sessionId = taskId + ':' + caseSpec.caseId + ':' + Date.now();
        for (const description of caseSpec.invariants) {
          result.unsupportedInvariants.push({ description, reason: 'This standalone UI probe does not observe external effects or all invariant dependencies.' });
        }
        // DeviceTestRunner must lazy-load this suite after onRun. Static OS
        // imports preserve the working native binding shape on that path.
        configureTasks12To15Selectors(ON);
        const delegator = abilityDelegatorRegistry.getAbilityDelegator();
        stage = 'launch';
        await delegator.startAbility({ bundleName, abilityName });
        result.entryExecuted = true;
        const driver: Driver = Driver.create();
        ui = new Tasks12To15Ui(driver, bundleName, result.sessionId);
        // Poll rendering/capability initialization. No exact-timer assertion is
        // derived from these real waits or the UiTest action durations.
        let prerequisite: Tasks12To15Prerequisite = await ui.prerequisite(taskId);
        const rootBefore: Tasks12To15Frame = ui.frame('before_prerequisite', {}, prerequisite.controls);
        result.frames.push(rootBefore);
        console.info('ARKTS_NATIVE_UI_CHECKPOINT ' + JSON.stringify(rootBefore));
        for (let attempt: number = 0; attempt < 10 && prerequisite.status !== 'available'; attempt++) {
          await driver.delayMs(500);
          prerequisite = await ui.prerequisite(taskId);
        }
        result.prerequisite = prerequisite;
        console.info('ARKTS_NATIVE_UI_PREREQUISITE ' + JSON.stringify(prerequisite));
        if (prerequisite.status === 'absent') {
          result.unsupported = prerequisite.reason + ' Entry absence alone does not establish canonical givens or execute the required event; no baseline failure is scored.';
        } else if (prerequisite.status !== 'available') {
          result.unsupported = prerequisite.reason;
        } else {
          const key: string = caseSpec.key;
          const given = caseSpec.given;
          const event = caseSpec.event;
          const opensFlow: boolean = key === 'initial_form' || key === 'entry_opens_address_flow' || key === 'default_form_blocks_submit';
          if (opensFlow) {
            const beforeOpen = await ui.capture(taskId, 'before_event');
            result.frames.push(beforeOpen);
            console.info('ARKTS_NATIVE_UI_CHECKPOINT ' + JSON.stringify(beforeOpen));
          }
          stage = 'open_original_page';
          if (key !== 'capability_gates_entry') await ui.open(taskId);
          if (taskId === '12_report_room' && key === 'blank_reason_disabled') {
            const ready = await ui.prerequisite(taskId);
            const formReady = await ui.capture(taskId, 'original_page_ready_before_binding');
            result.frames.push(formReady);
            const window = await driver.findWindow({ bundleName });
            stage = 'bind_original_page_after_ready';
            pageObserver = await installTasks12ReportPageAfterReady(JSON.stringify({
              bundleName, windowConfirmed: !!window, rootConfirmed: ready.rootConfirmed,
              available: ready.status === 'available', controls: formReady.controls
            }));
            result.frames.push(await ui.capture(taskId, 'original_page_observer_installed'));
          }
          if (taskId === '12_report_room' && key === 'blank_reason_disabled') {
            // Prepare the switch before the input method can obscure it. Both
            // givens are still checked together, on the same page, before_event.
            stage = 'fixture_leave_preference';
            if (typeof given['leaveRoom'] === 'boolean') await ui.select([ON.id('report_room_leave_toggle'), ON.id('leave_room_toggle')], given['leaveRoom'] as boolean);
            result.frames.push(await ui.capture(taskId, 'fixture_leave_selected'));
            stage = 'fixture_reason_input';
            if (typeof given['reason'] === 'string') await ui.input([ON.id('report_room_reason'), ON.id('report_reason_input')], given['reason'] as string);
            stage = 'fixture_dismiss_input_method';
            await ui.dismissInputMethod();
          } else if (taskId === '12_report_room' && !opensFlow) {
            if (typeof given['reason'] === 'string') await ui.input([ON.id('report_room_reason'), ON.id('report_reason_input')], given['reason'] as string);
            if (typeof given['leaveRoom'] === 'boolean') await ui.select([ON.id('report_room_leave_toggle'), ON.id('leave_room_toggle')], given['leaveRoom'] as boolean);
          } else if (taskId === '13_user_verification' && key === 'local_cancel') {
            await ui.click([ON.id('verify_user_action'), ON.id('start_user_verification')]);
            if (!await driver.findComponent(ON.text('Waiting for Alice to accept...').inWindow(bundleName))) {
              throw new Error('The canonical awaiting-response fixture is not observable on this page.');
            }
          } else if (taskId === '13_user_verification' &&
            (key === 'accept_challenge_once' || key === 'decline_challenge_once' || key === 'finish_clears_violation')) {
            await ui.click([ON.id('verify_user_action'), ON.id('start_user_verification')]);
            const accepted = await driver.findComponent(ON.id('verification_remote_accepted').inWindow(bundleName));
            if (accepted) {
              await ui.click([ON.id('verification_remote_accepted')]);
              await ui.click([ON.id('start_sas_verification')]);
            }
            // This only prepares state via production UI controls. SDK-bound
            // fixture variants without those controls need the live bridge.
            if (key === 'finish_clears_violation') await ui.click([ON.id('accept_sas_challenge'), ON.id('accept_challenge')]);
          } else if (taskId === '15_account_deactivation' && !opensFlow && key !== 'capability_gates_entry') {
            if (typeof given['password'] === 'string') await ui.input([ON.id('deactivation_password'), ON.type('TextInput')], given['password'] as string);
            if (typeof given['eraseData'] === 'boolean') await ui.select([ON.type('Toggle'), ON.type('Checkbox')], given['eraseData'] as boolean);
            if (key === 'confirm_sends_payload') await ui.click([ON.id('deactivate_submit'), ON.type('Button').text('Deactivate account')]);
          } else if (taskId === '14_join_room_by_address' && key === 'invalid_after_continue') {
            await ui.input([ON.id('room_address_input'), ON.id('address_input')], given['address'] as string);
            await driver.delayMs(350);
          }
          stage = 'capture_before_event';
          if (!opensFlow) result.frames.push(await ui.capture(taskId, 'before_event'));
          stage = 'canonical_event';
          let supported: boolean = true;
          if (taskId === '12_report_room') {
            if (key === 'reason_enables_report') await ui.input([ON.id('report_room_reason'), ON.id('report_reason_input')], event['reason'] as string);
            else if (key === 'toggle_leave') await ui.click([ON.id('report_room_leave_toggle'), ON.id('leave_room_toggle')]);
            else if (key === 'report_only_success' || key === 'report_then_leave') await ui.click([ON.id('submit_report_room'), ON.id('submit_report')]);
            else if (key !== 'initial_form' && key !== 'blank_reason_disabled') supported = false;
          } else if (taskId === '13_user_verification') {
            if (key === 'profile_routes_user_request' || key === 'request_targets_user') {
              await ui.click([ON.id('verify_user_action'), ON.id('start_user_verification')]);
            } else if (key === 'local_cancel') {
              await ui.click([ON.id('cancel_verification')]);
            } else if (key === 'accept_challenge_once') {
              await ui.click([ON.id('accept_sas_challenge'), ON.id('accept_challenge')]);
            } else if (key === 'decline_challenge_once') {
              await ui.click([ON.id('decline_sas_challenge'), ON.id('decline_challenge')]);
            } else if (key === 'finish_clears_violation') {
              await ui.click([ON.id('finish_verification')]);
            } else if (key !== 'identity_violation_surfaces') supported = false;
          } else if (taskId === '14_join_room_by_address') {
            if (key === 'invalid_after_continue') await ui.click([ON.id('join_room_continue'), ON.id('address_continue_button')]);
            else if (key === 'update_trims_and_debounces') await ui.input([ON.id('room_address_input'), ON.id('address_input')], event['value'] as string);
            else if (key !== 'entry_opens_address_flow') supported = false;
          } else if (taskId === '15_account_deactivation') {
            if (key === 'password_enables_submit') await ui.input([ON.id('deactivation_password'), ON.type('TextInput')], event['value'] as string);
            else if (key === 'erase_data_option') await ui.select([ON.type('Toggle'), ON.type('Checkbox')], event['value'] as boolean);
            else if (key === 'first_submit_confirms') await ui.click([ON.id('deactivate_submit'), ON.type('Button').text('Deactivate account')]);
            else if (key === 'confirm_sends_payload') await ui.click([ON.type('Button').text('Confirm deactivation')], 0);
            else if (key !== 'default_form_blocks_submit' && key !== 'capability_gates_entry') supported = false;
          }
          stage = 'capture_after_event';
          const after = await ui.capture(taskId, supported ? 'after_event' : 'fixture_only_no_event');
          result.frames.push(after);
          result.eventExecuted = supported;
          if (supported) result.observed = after.observed;
          if (!supported) result.unsupported = 'Canonical fixture/event unavailable through standalone UI. Supply same-page external-service fixtures, then call Tasks12To15Ui.capture; these frames do not represent that transition.';
        }
      } catch (error) {
        result.unsupported = 'Native launch, fixture, event or observation unavailable: ' + String(error);
        const nativeError = error as BusinessError;
        result.failure = { stage, message: String(error), stack: nativeError.stack, code: nativeError.code };
        if (result.taskId === '12_report_room') {
          result.failure.presenterEvidence = readTasks12ReportPage();
          if (ui !== undefined) {
            try {
              result.frames.push(await ui.capture(result.taskId, 'failure_diagnostic_only'));
            } catch (captureError) {
              result.failure.captureError = String(captureError);
            }
          }
        }
        console.info('ARKTS_NATIVE_UI_FAILURE ' + JSON.stringify(result.failure));
      } finally {
        if (pageObserver !== undefined) pageObserver.dispose();
      }
      if (ui !== undefined) result.actions = ui.actionLog();
      checkNativeInvariants(result);
      if (caseSpec !== undefined) finalizeNativeUiResult(result, caseSpec);
      return result;
}

export default function tasks12To15NativeUiTests(): void {
  describe('Tasks12To15NativeUi', () => {
    it('actual_entry_and_controls', 0, async () => {
      const args = abilityDelegatorRegistry.getArguments();
      const caseSpec = JSON.parse(args.parameters['caseSpec']) as NativeUiCase;
      // Preserve fail-closed caller identity validation without launching UI.
      const requested = args.parameters['taskId'];
      const result = await runTasks12To15NativeUi(caseSpec,
        requested === caseSpec.taskId ? args.bundleName : '', args.parameters['abilityName'] || 'EntryAbility');
      emitResult(result);
      // Hypium only checks a fully eligible, fully observed canonical assertion.
      // NS transport completion is not a semantic pass.
      if (result.canonicalAssertion?.evaluated === true) expect(result.canonicalAssertion.passed).assertTrue();
    });
  });
}
