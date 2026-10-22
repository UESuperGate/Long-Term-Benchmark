import { Driver, ON } from '@ohos.UiTest';
import { runTask16BaseEntry } from './Task16BaseEntry';
import { createTask16Launch } from './Task16LaunchNative';

export async function probeTask16BaseEntry(bundleName: string): Promise<string> {
  return runTask16BaseEntry(bundleName, Driver.create(), ON, createTask16Launch(bundleName));
}

export async function probeTask16CandidateEntry(bundleName: string): Promise<string> {
  return runTask16BaseEntry(bundleName, Driver.create(), ON, createTask16Launch(bundleName), true);
}
