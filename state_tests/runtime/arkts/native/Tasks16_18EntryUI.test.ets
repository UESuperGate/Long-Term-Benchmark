import { describe, it, expect } from '@ohos/hypium';
import { Component, Driver, ON } from '@ohos.UiTest';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';

interface EntrySelector {
  kind: string;
  value: string;
}

interface EntryNode {
  selector: EntrySelector;
  id: string;
  text: string;
  type: string;
  enabled: boolean;
  clickable: boolean;
}

interface EntrySnapshot {
  taskId: string;
  bundleName: string;
  abilityName: string;
  stage: string;
  roots: EntryNode[];
  features: EntryNode[];
  legacyControls: EntryNode[];
  detail: EntryNode[];
  visibleText: EntryNode[];
}

interface EntryProbe {
  before: EntrySnapshot;
  after: EntrySnapshot;
  action: string;
  featureEntryPresent: boolean;
  observationLevel: string;
}

function text(value: string): EntrySelector { return { kind: 'text', value }; }
function id(value: string): EntrySelector { return { kind: 'id', value }; }

function emit(label: string, taskId: string, payload: string): void {
  const chunks = Math.ceil(payload.length / 1500);
  for (let index = 0; index < chunks; index++) {
    console.info('ARKTS_16_18_UI_CHUNK ' + JSON.stringify({ label, taskId, index, chunks,
      text: payload.slice(index * 1500, (index + 1) * 1500) }));
  }
}

function rootSelectors(taskId: string): EntrySelector[] {
  if (taskId === '16_identity_reset') return [text('Chat backup'), text('Reset cryptographic identity'), text('Reset identity')];
  if (taskId === '17_pinned_messages') return [text('Design team'), id('pinned_messages_banner')];
  if (taskId === '18_custom_notification_sounds') return [text('Notifications')];
  throw new Error('Task is not owned by this UI probe: ' + taskId);
}

function featureSelectors(taskId: string): EntrySelector[] {
  if (taskId === '16_identity_reset') return [id('identity_reset_continue'), text('Reset identity')];
  if (taskId === '17_pinned_messages') return [id('open_pinned_messages'), id('pinned_banner_open')];
  return [id('message_sound_row'), id('call_ringtone_row')];
}

function legacySelectors(taskId: string): EntrySelector[] {
  if (taskId === '16_identity_reset') return [text('Enable backup'), text('Recover')];
  if (taskId === '17_pinned_messages') return [id('pinned_banner_next')];
  return [id('notifications_enabled'), id('call_notifications_enabled'), id('mentions_enabled')];
}

function detailSelectors(taskId: string): EntrySelector[] {
  if (taskId === '16_identity_reset') return [text('Confirm identity reset?'), text('Reset my identity'),
    text('Continue'), text('Keep my identity'), id('identity_reset_password'), text('Backup state: enabled')];
  if (taskId === '17_pinned_messages') return [id('pinned_messages_loading'), id('pinned_loading'),
    id('pinned_messages_filled'), id('pinned_list'), id('pinned_messages_empty'), id('pinned_empty'),
    id('pinned_messages_failed'), id('pinned_failed'), text('Pinned messages')];
  return [id('message_sound_dialog'), id('call_sound_dialog'), id('message_sound_value'), id('call_ringtone_value'),
    text('Choose audio file'), text('Choose from device')];
}

async function nodes(driver: Driver, selectors: EntrySelector[]): Promise<EntryNode[]> {
  const found: EntryNode[] = [];
  for (const selector of selectors) {
    const matches: Component[] = await driver.findComponents(selector.kind === 'id'
      ? ON.id(selector.value) : selector.kind === 'type' ? ON.type(selector.value) : ON.text(selector.value));
    for (const component of matches) {
      found.push({ selector, id: await component.getId(), text: await component.getText(),
        type: await component.getType(), enabled: await component.isEnabled(), clickable: await component.isClickable() });
    }
  }
  return found;
}

async function snapshot(driver: Driver, taskId: string, bundleName: string, abilityName: string,
  stage: string): Promise<EntrySnapshot> {
  return { taskId, bundleName, abilityName, stage,
    roots: await nodes(driver, rootSelectors(taskId)), features: await nodes(driver, featureSelectors(taskId)),
    legacyControls: await nodes(driver, legacySelectors(taskId)), detail: await nodes(driver, detailSelectors(taskId)),
    visibleText: await nodes(driver, [{ kind: 'type', value: 'Text' }]) };
}

// Launch the candidate ability itself. A generated Hypium/Previewer host page
// never qualifies as evidence that a candidate feature is absent.
export async function probeTasks16To18Entry(taskId: string, bundleName: string,
  abilityName: string = 'EntryAbility'): Promise<EntryProbe> {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  await delegator.startAbility({ bundleName, abilityName });
  const driver = Driver.create();
  let before = await snapshot(driver, taskId, bundleName, abilityName, 'before_event');
  for (let attempt = 0; before.roots.length === 0 && attempt < 20; attempt++) {
    await driver.delayMs(100);
    before = await snapshot(driver, taskId, bundleName, abilityName, 'before_event');
  }
  if (before.roots.length === 0) throw new Error('Candidate root not observed; feature absence is not established.');
  emit('before_event', taskId, JSON.stringify(before));
  const feature = before.features.find((node: EntryNode) => node.enabled && node.clickable);
  const legacy = before.legacyControls.find((node: EntryNode) => node.enabled);
  const target = feature || legacy;
  let action: string = 'no_enabled_entry_control';
  if (target !== undefined) {
    const component = await driver.findComponent(target.selector.kind === 'id'
      ? ON.id(target.selector.value) : ON.text(target.selector.value));
    await component.click();
    action = target.selector.kind + ':' + target.selector.value;
    await driver.delayMs(100);
  }
  const after = await snapshot(driver, taskId, bundleName, abilityName, 'after_event');
  emit('after_event', taskId, JSON.stringify(after));
  const result: EntryProbe = { before, after, action,
    featureEntryPresent: before.features.some((node: EntryNode) => node.selector.kind === 'id' || node.type === 'Button'),
    observationLevel: 'native_candidate_ui' };
  emit('entry_probe', taskId, JSON.stringify(result));
  return result;
}

// The runner supplies candidate identity, never a base/final/agent role. This
// smoke only validates UI transport; canonical scoring consumes the raw record.
export default function tasks16To18EntryTests(taskId: string, bundleName: string): void {
  describe('Tasks16To18ActualEntry', () => {
    it('candidate_entry_runtime_evidence', 0, async () => {
      const result = await probeTasks16To18Entry(taskId, bundleName);
      expect(result.before.roots.length > 0).assertTrue();
      expect(result.observationLevel).assertEqual('native_candidate_ui');
    });
  });
}
