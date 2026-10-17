import { abilityDelegatorRegistry, TestRunner } from '@kit.TestKit';

export default class OpenHarmonyTestRunner implements TestRunner {
  onPrepare(): void {
  }

  onRun(): void {
    const delegator = abilityDelegatorRegistry.getAbilityDelegator();
    const argumentsValue = abilityDelegatorRegistry.getArguments();
    const moduleName = argumentsValue.parameters['-m'];
    delegator.startAbility({
      bundleName: argumentsValue.bundleName,
      abilityName: 'TestAbility',
      moduleName: moduleName
    });
  }
}
