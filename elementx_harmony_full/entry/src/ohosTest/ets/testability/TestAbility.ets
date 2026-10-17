import AbilityConstant from '@ohos.app.ability.AbilityConstant';
import UIAbility from '@ohos.app.ability.UIAbility';
import Want from '@ohos.app.ability.Want';
import { abilityDelegatorRegistry } from '@kit.TestKit';
import window from '@ohos.window';
import { Hypium } from '@ohos/hypium';
import testsuite from '../test/List.test';

const UNEXPECTED_DESTROY_CODE: number = -2;

export default class TestAbility extends UIAbility {
  private readonly delegator: abilityDelegatorRegistry.AbilityDelegator =
    abilityDelegatorRegistry.getAbilityDelegator();

  onCreate(_want: Want, _launchParam: AbilityConstant.LaunchParam): void {
    const argumentsValue = abilityDelegatorRegistry.getArguments();
    Hypium.hypiumTest(this.delegator, argumentsValue, testsuite);
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('testability/pages/Index');
  }

  onDestroy(): void {
    this.delegator.finishTest(
      'TestAbility was destroyed before Hypium completed',
      UNEXPECTED_DESTROY_CODE,
      () => {}
    );
  }
}
