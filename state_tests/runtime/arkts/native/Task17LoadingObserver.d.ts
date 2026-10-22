export interface Task17LoadingObservation {
  snapshot(): string;
  dispose(): void;
}
export function observeTask17Loading(presenter: Object, repository: Object,
  preferences: Object, abilityContext: Object, hooks?: Object): Task17LoadingObservation;
