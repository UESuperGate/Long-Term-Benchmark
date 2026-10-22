import { abilityDelegatorRegistry, TestRunner } from '@kit.TestKit';
import { Hypium } from '@ohos/hypium';

// Follow Hypium's bundled runner: its asynchronous execution owns completion.
export default class OpenHarmonyTestRunner implements TestRunner {
  private started: boolean = false;

  onPrepare(): void {}

  onRun(): void {
    if (this.started) {
      return;
    }
    this.started = true;
    const delegator = abilityDelegatorRegistry.getAbilityDelegator();
    const args = abilityDelegatorRegistry.getArguments();
    console.info('ARKTS_DEVICE_HARNESS_START');
    // UiTest resolves its delegator when imported; load it only after onRun.
    import('../test/List.test').then((suite) => {
      Hypium.hypiumTest(delegator, args, suite.default);
      console.info('ARKTS_DEVICE_HARNESS_SCHEDULED');
    }).catch((error: Error) => {
      console.error('ARKTS_DEVICE_HARNESS_START_ERROR ' + String(error));
      delegator.finishTest('Evaluator Hypium initialization failed: ' + String(error), -1, () => {});
    });
  }
}
