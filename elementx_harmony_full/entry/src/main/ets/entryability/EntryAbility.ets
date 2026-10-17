import AbilityConstant from '@ohos.app.ability.AbilityConstant';
import UIAbility from '@ohos.app.ability.UIAbility';
import Want from '@ohos.app.ability.Want';
import window from '@ohos.window';
import {
  AppShellCoordinator,
  DefaultAppShellRuntime
} from '../appshell/AppShellCoordinator';
import { AppShellRegistry } from '../appshell/AppShellRegistry';
import { ProductionCompositionRoot } from '../composition/ProductionCompositionRoot';
import { LaunchIntentStore } from '../services/LaunchIntentStore';

export default class EntryAbility extends UIAbility {
  private compositionRoot: ProductionCompositionRoot | null = null;

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    LaunchIntentStore.capture(want);
  }

  onNewWant(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    LaunchIntentStore.capture(want);
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    this.initializeProductionShell(windowStage);
  }

  onDestroy(): void {
    AppShellRegistry.clear();
    this.compositionRoot = null;
  }

  private async initializeProductionShell(windowStage: window.WindowStage): Promise<void> {
    try {
      const compositionRoot = await ProductionCompositionRoot.create(this.context);
      this.compositionRoot = compositionRoot;
      await compositionRoot.sessionCoordinator.restoreLatestSession();
      AppShellRegistry.install(new AppShellCoordinator(
        compositionRoot.rootNavigation,
        compositionRoot.passwordLogin,
        compositionRoot.appShellTransport,
        new DefaultAppShellRuntime(),
        'Matrix timeline transport reconstruction is incomplete'
      ));
    } catch (error) {
      console.error(`Failed to initialize production composition: ${JSON.stringify(error)}`);
      AppShellRegistry.install(AppShellCoordinator.unavailable(
        'Production composition failed to initialize'
      ));
    }
    try {
      windowStage.loadContent('pages/ReconstructedRoot');
    } catch (error) {
      console.error(`Failed to load reconstructed root: ${JSON.stringify(error)}`);
    }
  }
}
