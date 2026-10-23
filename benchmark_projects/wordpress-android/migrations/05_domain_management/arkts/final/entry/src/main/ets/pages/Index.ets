import { MountedDomainPageOwner, DomainPageRuntime } from './DomainPageOwner';

function emptyEvent(): Record<string, Object> { return JSON.parse('{}') as Record<string, Object>; }
function filterEvent(query: string): Record<string, Object> {
  const event = emptyEvent(); event['query'] = query; return event;
}

@Entry
@Component
struct Index {
  private owner: MountedDomainPageOwner = DomainPageRuntime.createOwner();
  @State summary: string = 'Loading domains';
  @State query: string = '';

  aboutToAppear(): void { void this.refreshSummary(); }
  private async refreshSummary(): Promise<void> {
    await this.owner.waitUntilReady();
    this.summary = JSON.stringify(this.owner.currentState());
  }
  private async invoke(name: string, event: Record<string, Object>): Promise<void> {
    await this.owner.invoke(name, event);
    await this.refreshSummary();
  }

  build() {
    Column({ space: 14 }) {
      Text('All Domains').fontSize(28).fontWeight(FontWeight.Bold).width('100%')
      TextInput({ text: this.query, placeholder: 'Filter domains' })
        .onChange((value: string) => { this.query = value; void this.invoke('enterLocalFilter', filterEvent(value)); })
      Row({ space: 12 }) {
        Button('Refresh').onClick(() => void this.invoke('openDomainManagement', emptyEvent()))
        Button('Add domain').onClick(() => void this.invoke('openDomainManagementThenTapAddDomain', emptyEvent()))
      }.width('100%')
      Text(this.summary).fontSize(14).width('100%')
    }.width('100%').height('100%').padding(24)
  }
}
