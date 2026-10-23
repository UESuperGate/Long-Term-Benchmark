import { WaveformPageOwner } from '../feature/WaveformPageOwner';

let mountedOwner: WaveformPageOwner | undefined = undefined;

export function registerWaveformPageOwner(owner: WaveformPageOwner): void { mountedOwner = owner; }
export function currentWaveformPageOwner(): WaveformPageOwner | undefined { return mountedOwner; }
