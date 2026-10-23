import { SupportConversation, SupportMessage } from '../features/UnifiedSupportController';
import { UnifiedSupportPageOwner, UnifiedSupportPageRuntime } from './UnifiedSupportPageOwner';

@Entry
@Component
struct Index {
  private owner: UnifiedSupportPageOwner = UnifiedSupportPageRuntime.createOwner();
  @State conversations: SupportConversation[] = [];
  @State selected: SupportConversation | undefined = undefined;
  @State draft: string = '';
  @State error: string = '';
  @State includeAppLogs: boolean = false;
  @State attachment: string = '';

  aboutToAppear(): void {
    this.owner.aboutToAppear();
    this.owner.waitUntilReady().then(() => this.sync());
  }

  private sync(): void {
    const store = this.owner.store();
    this.conversations = store.conversations;
    this.selected = store.selected;
    this.draft = store.replyForm.message;
    this.error = store.error;
    this.includeAppLogs = store.replyForm.includeAppLogs;
    this.attachment = store.replyForm.attachments.length > 0 ? store.replyForm.attachments[0] : '';
  }

  build() {
    Column() {
      Row({ space: 8 }) {
        Text(this.selected ? this.selected.title : 'Get help').fontSize(24).fontWeight(FontWeight.Bold).layoutWeight(1)
        if (!this.selected) {
          Button('New bot').onClick(() => { this.owner.createBotConversation(); this.sync(); })
          Button('Retry').onClick(() => { this.owner.retryConversations().then(() => this.sync()); })
        }
      }.width('100%').padding(16)
      if (this.error.length > 0) { Text(this.error).fontColor('#B3261E').padding(16) }
      if (!this.selected) {
        List() {
          ForEach(this.conversations, (conversation: SupportConversation) => {
            ListItem() {
              Column({ space: 4 }) {
                Text(conversation.title).fontSize(17).fontWeight(FontWeight.Medium)
                Text(conversation.status === 'bot' ? 'Oddie bot' : conversation.status).fontSize(13).fontColor('#5B6B73')
              }.alignItems(HorizontalAlign.Start).width('100%').padding(16).onClick(() => {
                this.owner.openConversation(conversation.id).then(() => this.sync());
              })
            }
          }, (conversation: SupportConversation) => conversation.id.toString())
        }.layoutWeight(1).width('100%')
      } else {
        List() {
          ForEach(this.selected.messages, (message: SupportMessage) => {
            ListItem() { Text(`${message.author}: ${message.text}`).padding(12) }
          }, (message: SupportMessage) => message.id.toString())
        }.layoutWeight(1).width('100%')
        if (this.owner.controller.detailAffordance(this.selected) === 'closed_banner') {
          Text('This conversation is closed').padding(16)
        } else {
          Column({ space: 8 }) {
            Row({ space: 8 }) {
              TextInput({ text: this.draft, placeholder: 'Message' }).layoutWeight(1).onChange((value: string) => {
                this.draft = value;
                this.owner.updateDraft(value);
              })
              Button('Send').enabled(!this.owner.store().sending).onClick(() => {
                const message = this.draft;
                this.owner.sendReply(message).then(() => this.sync());
                this.sync();
              })
            }.width('100%')
            Row({ space: 8 }) {
              TextInput({ text: this.attachment, placeholder: 'Attachment' }).layoutWeight(1).onChange((value: string) => {
                this.attachment = value;
                this.owner.updateAttachments(value.length === 0 ? [] : [value]);
              })
              Toggle({ type: ToggleType.Switch, isOn: this.includeAppLogs }).onChange((value: boolean) => {
                this.includeAppLogs = value;
                this.owner.setIncludeAppLogs(value);
              })
              Text('Include logs')
            }.width('100%')
          }.width('100%').padding(12)
        }
      }
    }.width('100%').height('100%')
  }
}
