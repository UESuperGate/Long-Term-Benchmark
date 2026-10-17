export interface StateObserver<T> {
  onStateChanged(state: T): void;
}

/** Minimal observable state primitive with no ArkUI dependency. */
export class ObservableState<T> {
  private state: T;
  private nextObserverId: number = 1;
  private readonly observers: Map<number, StateObserver<T>> = new Map<number, StateObserver<T>>();

  constructor(initialState: T) {
    this.state = initialState;
  }

  getValue(): T {
    return this.state;
  }

  setValue(state: T): void {
    this.state = state;
    this.observers.forEach((observer: StateObserver<T>) => {
      observer.onStateChanged(state);
    });
  }

  subscribe(observer: StateObserver<T>): number {
    const observerId = this.nextObserverId;
    this.nextObserverId += 1;
    this.observers.set(observerId, observer);
    observer.onStateChanged(this.state);
    return observerId;
  }

  unsubscribe(observerId: number): void {
    this.observers.delete(observerId);
  }
}
