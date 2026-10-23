import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { runRuntimeCase } from '../evaluator/RuntimeHarness';

export default class EntryAbility extends UIAbility {
  private caseKey: string = '';

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    const value = want.parameters?.['caseKey'];
    this.caseKey = typeof value === 'string' ? value : '';
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index');
    if (this.caseKey.length > 0) void runRuntimeCase(this.caseKey);
  }
}
