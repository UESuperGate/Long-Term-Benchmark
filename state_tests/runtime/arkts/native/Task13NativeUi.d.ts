export function configureTask13UI(probe: (caseJson: string, configJson: string) => Promise<string>, configJson: string): void;
export function attachTask13UI(bridge: Object, taskId: string, key: string): boolean;
export function installTask13AfterReady(readinessJson: string): Promise<void>;
export function readTask13Page(): string;
export function publishTask13UI(resultJson: string): void;
export function task13UICancelled(): boolean;
