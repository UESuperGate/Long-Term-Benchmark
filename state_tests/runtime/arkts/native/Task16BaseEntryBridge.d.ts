export function configureTask16BaseEntry(probe: (bundleName: string) => Promise<string>, bundleName: string,
  sourcesJson: string, releaseLaunch?: (bundleName: string) => Promise<void>): void;
export function attachTask16BaseEntry(bridge: Object, taskId: string): boolean;
