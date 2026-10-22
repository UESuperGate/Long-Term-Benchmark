export function configureTasks16To18UI(probe: (requestJson: string) => Promise<string>,
  bundleName: string, bindingJson: string, sourceJson: string, audioViewPicker?: Object): void;
export function attachTasks16To18UI(bridge: Object, taskId: string, key: string): boolean;
export function readTasks16To18Page(context: Object): Promise<string>;
export function readTasks16To18Picker(): string;
export function publishTasks16To18UI(resultJson: string, stage: string): void;
export function tasks16To18UICancelled(): boolean;
export function prepareTasks16To18Page(context: Object): Promise<void>;
export function finishTasks16To18Page(context: Object): Promise<void>;
export function bindTasks16To18OriginalPage(context: Object, readinessJson: string): Promise<string>;
