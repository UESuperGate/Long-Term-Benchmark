import AbilityConstant from '@ohos.app.ability.AbilityConstant';
import UIAbility from '@ohos.app.ability.UIAbility';
import Want from '@ohos.app.ability.Want';
import window from '@ohos.window';
import { LaunchIntentStore } from '../services/LaunchIntentStore';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    LaunchIntentStore.capture(want);
  }

  onNewWant(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    LaunchIntentStore.capture(want);
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    try {
      windowStage.loadContent('pages/Index');
    } catch (error) {
      console.error(`Failed to load content: ${JSON.stringify(error)}`);
    }
  }
}
