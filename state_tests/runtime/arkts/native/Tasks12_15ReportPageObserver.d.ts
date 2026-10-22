export interface ReportPageCall {
  instanceId: number;
  sequence: number;
  method: string;
  value?: string;
  completed: boolean;
}
export interface ReportPageSnapshot {
  available: boolean;
  reason?: string;
  instanceId?: number;
  instanceCount?: number;
  leaveRoom?: boolean;
  canReport?: boolean;
  binding?: Object;
  calls: ReportPageCall[];
}
export interface ReportPageObserver {
  read(): ReportPageSnapshot;
  dispose(): void;
}
export function configureTasks12ReportPage(Presenter: Object): void;
export function installTasks12ReportPageObserver(): ReportPageObserver;
export function readTasks12ReportPage(): ReportPageSnapshot;
