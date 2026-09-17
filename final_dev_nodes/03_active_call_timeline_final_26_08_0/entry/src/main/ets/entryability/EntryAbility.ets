import UIAbility from '@ohos.app.ability.UIAbility';
import Want from '@ohos.app.ability.Want';
import window from '@ohos.window';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want): void {
    this.captureStateTestCase(want);
  }

  onNewWant(want: Want): void {
    this.captureStateTestCase(want);
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    try {
      windowStage.loadContent('pages/Index');
    } catch (error) {
      console.error(`Failed to load content: ${JSON.stringify(error)}`);
    }
  }

  private captureStateTestCase(want: Want): void {
    const caseId = this.stateTestCaseIdFromWant(want);
    if (caseId.length === 0) {
      return;
    }
    if (!AppStorage.set<string>('elementx_state_test_case_id', caseId)) {
      AppStorage.setOrCreate<string>('elementx_state_test_case_id', caseId);
    }
  }

  private stateTestCaseIdFromWant(want: Want): string {
    const fromParameters = this.parameterString(want, 'caseId');
    if (fromParameters.length > 0) {
      return fromParameters;
    }
    const uri = want.uri ?? '';
    return this.queryValue(uri, 'caseId');
  }

  private parameterString(want: Want, key: string): string {
    const parameters = want.parameters;
    if (parameters === undefined) {
      return '';
    }
    const raw = parameters[key];
    if (raw === undefined || raw === null) {
      return '';
    }
    return String(raw).trim();
  }

  private queryValue(uri: string, key: string): string {
    const queryIndex = uri.indexOf('?');
    if (queryIndex < 0) {
      return '';
    }
    const prefix = `${key}=`;
    const parts = uri.substring(queryIndex + 1).split('&');
    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index];
      if (part.startsWith(prefix)) {
        return decodeURIComponent(part.substring(prefix.length).replace(/\+/g, '%20')).trim();
      }
    }
    return '';
  }
}
