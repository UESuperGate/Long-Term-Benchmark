import common from '@ohos.app.ability.common';
import { AppShellTransport } from '../appshell/AppShellCoordinator';
import { RootNavigationStateMachine } from '../appnav/RootNavigationStateMachine';
import { RootSessionCoordinator } from '../appnav/RootSessionCoordinator';
import { PasswordLoginCoordinator } from '../features/login/PasswordLoginCoordinator';
import { NativeMatrixAuthenticationService } from '../matrix/production/NativeMatrixAuthenticationService';
import { NativeAppShellTransport } from '../matrix/production/NativeAppShellTransport';
import { AddonNativeMatrixBridge, NativeMatrixBridge } from '../nativebridge/Index';
import { SessionPersistence } from '../session/SessionPersistence';
import { AssetSessionCredentialStore } from '../session/platform/AssetSessionCredentialStore';
import { PreferencesSessionMetadataStore } from '../session/platform/PreferencesSessionMetadataStore';

/** Owns production dependencies shared by the root navigation flow. */
export class ProductionCompositionRoot {
  readonly nativeBridge: NativeMatrixBridge;
  readonly rootNavigation: RootNavigationStateMachine;
  readonly passwordLogin: PasswordLoginCoordinator;
  readonly sessionCoordinator: RootSessionCoordinator;
  readonly appShellTransport: AppShellTransport;

  private constructor(
    nativeBridge: NativeMatrixBridge,
    rootNavigation: RootNavigationStateMachine,
    passwordLogin: PasswordLoginCoordinator,
    sessionCoordinator: RootSessionCoordinator,
    appShellTransport: AppShellTransport
  ) {
    this.nativeBridge = nativeBridge;
    this.rootNavigation = rootNavigation;
    this.passwordLogin = passwordLogin;
    this.sessionCoordinator = sessionCoordinator;
    this.appShellTransport = appShellTransport;
  }

  static async create(context: common.Context): Promise<ProductionCompositionRoot> {
    const nativeBridge = new AddonNativeMatrixBridge();
    const authentication = new NativeMatrixAuthenticationService(nativeBridge);
    const metadataStore = await PreferencesSessionMetadataStore.create(context);
    const credentialStore = new AssetSessionCredentialStore();
    const persistence = new SessionPersistence(metadataStore, credentialStore);
    const rootNavigation = new RootNavigationStateMachine();
    const passwordLogin = new PasswordLoginCoordinator(authentication, persistence, rootNavigation);
    const sessionCoordinator = new RootSessionCoordinator(authentication, persistence, rootNavigation);
    const appShellTransport = new NativeAppShellTransport(nativeBridge, rootNavigation);
    return new ProductionCompositionRoot(
      nativeBridge,
      rootNavigation,
      passwordLogin,
      sessionCoordinator,
      appShellTransport
    );
  }
}
