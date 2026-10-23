import { UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { prepareSemanticCase, runSemanticCase, SemanticPayload } from '../evaluator/SemanticProbe';

export default class EntryAbility extends UIAbility {
  private semanticCase: string = '';
  private semanticToken: string = '';

  onCreate(want: Want): void {
    const parameters = want.parameters;
    if (parameters !== undefined) {
      const caseValue = parameters['semanticCase'];
      const tokenValue = parameters['semanticToken'];
      if (typeof caseValue === 'string') this.semanticCase = caseValue;
      if (typeof tokenValue === 'string') this.semanticToken = tokenValue;
    }
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    if (this.semanticCase.length > 0) prepareSemanticCase(this.semanticCase);
    windowStage.loadContent('pages/Index', () => {
      if (this.semanticCase.length > 0) this.runObserver();
    });
  }

  private async runObserver(): Promise<void> {
    try {
      const payload = await runSemanticCase(this.semanticCase);
      this.emitPayload(payload);
    } catch (error) {
      this.emitRaw(JSON.stringify({ key: this.semanticCase, error: `${error}` }));
    }
  }

  private emitPayload(payload: SemanticPayload): void { this.emitRaw(JSON.stringify(payload)); }

  private emitRaw(value: string): void {
    const size = 420;
    const total = Math.ceil(value.length / size);
    for (let index = 0; index < total; index += 1) {
      const line = `LTB_RUNTIME:${this.semanticToken}:${index}:${total}:${value.substring(index * size, (index + 1) * size)}`;
      hilog.error(0x0000, 'LTBObserver', '%{public}s', line);
    }
  }
}
