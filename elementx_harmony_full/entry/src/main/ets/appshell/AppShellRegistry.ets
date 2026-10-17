import { AppShellCoordinator } from './AppShellCoordinator';

/** Explicit composition boundary. No fallback installs mock or fixture data. */
export class AppShellRegistry {
  private static coordinator: AppShellCoordinator | null = null;

  static install(coordinator: AppShellCoordinator): void {
    AppShellRegistry.coordinator = coordinator;
  }

  static clear(): void {
    AppShellRegistry.coordinator = null;
  }

  static resolve(): AppShellCoordinator {
    if (AppShellRegistry.coordinator !== null) {
      return AppShellRegistry.coordinator;
    }
    return AppShellCoordinator.unavailable('Production composition is not installed');
  }
}
