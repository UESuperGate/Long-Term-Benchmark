import router from '@ohos.router';
import { ChatMessage, RoomPresenter } from '../features/ChatFeature';
import { RoomRouteParams } from '../features/ChatRoutes';
import { roomGateway, chatNavigator } from '../features/ChatRuntime';

@Entry
@Component
struct Room {
  private presenter: RoomPresenter = new RoomPresenter(roomGateway);
  @State private roomId: string = '';
  @State private name: string = '';
  @State private topic: string = '';
  @State private members: string = '';
  @State private messages: ChatMessage[] = [];
  @State private draft: string = '';
  @State private error: string = '';
  @State private loaded: boolean = false;
  @State private busy: boolean = false;

  aboutToAppear(): void {
    const params: RoomRouteParams = router.getParams() as RoomRouteParams;
    const roomId: string = params === undefined || params === null ? '' : params.roomId;
    const serverNames: string[] = params === undefined || params === null || params.serverNames === undefined ?
      [] : params.serverNames;
    this.presenter.load(roomId, serverNames).then(() => this.refresh());
  }

  private refresh(): void {
    const room = this.presenter.room;
    this.loaded = room !== undefined;
    this.error = this.presenter.error;
    this.busy = this.presenter.busy;
    if (room !== undefined) {
      this.roomId = room.roomId;
      this.name = room.name;
      this.topic = room.topic;
      this.members = room.memberIds.join(', ');
      this.messages = room.messages.slice();
    }
  }

  build() {
    Column({ space: 12 }) {
      Row() {
        Button('Back').id('room_back').onClick(() => {
          chatNavigator.back().catch((error: Error) => { this.error = error.message; });
        })
        Text(this.name).fontSize(22).fontWeight(FontWeight.Bold).layoutWeight(1).margin({ left: 12 })
      }.width('100%')
      if (this.loaded) {
        Text(this.roomId).id('room_id').fontSize(12).width('100%')
        Text(this.members).id('room_members').fontSize(12).width('100%')
        if (this.topic.length > 0) {
          Text(this.topic).width('100%')
        }
        List({ space: 8 }) {
          ForEach(this.messages, (message: ChatMessage) => {
            ListItem() {
              Column({ space: 4 }) {
                Text(message.senderId).fontSize(12).fontColor('#596168')
                Text(message.body).fontSize(16)
              }.width('100%').alignItems(HorizontalAlign.Start).padding(12).backgroundColor('#FFFFFF')
            }
          }, (message: ChatMessage) => message.id)
        }.layoutWeight(1).width('100%').id('room_timeline')
        TextInput({ text: this.draft, placeholder: 'Message' })
          .id('room_message_input').enabled(!this.busy).onChange((value: string) => { this.draft = value; })
        Button('Send').id('room_send').enabled(!this.busy && this.draft.trim().length > 0)
          .width('100%').onClick(() => {
            const action: Promise<boolean> = this.presenter.send(this.draft);
            this.refresh();
            action.then((sent: boolean) => {
              if (sent) { this.draft = ''; }
              this.refresh();
            });
          })
      } else {
        Blank()
      }
      if (this.error.length > 0) {
        Text(this.error).id('room_error').fontColor('#B42318')
      }
    }.padding(20).height('100%').width('100%').backgroundColor('#F4F6F8')
  }
}
