import { common } from '@kit.AbilityKit';
import { jsonMap, WaveformPageOwner } from '../feature/WaveformPageOwner';
import { registerWaveformPageOwner } from '../integration/PageOwnerRegistry';

@Entry
@Component
struct Index {
  @State status: string = 'Ready';
  private owner?: WaveformPageOwner;

  async aboutToAppear(): Promise<void> {
    const context = getContext(this) as common.UIAbilityContext;
    this.owner = await WaveformPageOwner.create(context, jsonMap());
    registerWaveformPageOwner(this.owner);
  }

  private fullScale(): number[] {
    const samples: number[] = [];
    for (let index = 0; index < 100; index++) samples.push(32767);
    return samples;
  }

  private async generate(): Promise<void> {
    await this.owner?.generateWaveform(this.fullScale(), 2000000);
    this.status = JSON.stringify(this.owner?.currentState() ?? jsonMap());
  }

  private async prepareUpload(): Promise<void> {
    await this.owner?.startUploadGraph();
    await this.owner?.releaseHeldWaveform(this.fullScale(), 2000000);
    this.status = JSON.stringify(this.owner?.currentState() ?? jsonMap());
  }

  build() {
    Column({ space: 16 }) {
      Text('Voice note waveforms').fontSize(26).fontWeight(FontWeight.Bold)
      Button('Generate waveform').onClick(() => { void this.generate(); })
      Button('Prepare upload').onClick(() => { void this.prepareUpload(); })
      Text(this.status).fontSize(14)
    }
    .width('100%')
    .height('100%')
    .padding(24)
  }
}
