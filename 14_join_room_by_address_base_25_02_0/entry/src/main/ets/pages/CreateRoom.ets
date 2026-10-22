import { ChatPerson, CreateRoomPresenter } from '../features/ChatFeature';
import { roomGateway, chatNavigator } from '../features/ChatRuntime';

@Entry
@Component
struct CreateRoom {
  private presenter: CreateRoomPresenter = new CreateRoomPresenter(roomGateway, chatNavigator);
  @State private name: string = '';
  @State private topic: string = '';
  @State private members: string[] = [];
  @State private busy: boolean = false;
  @State private created: boolean = false;
  @State private error: string = '';
  private people: ChatPerson[] = this.presenter.people();

  aboutToDisappear(): void {
    this.presenter.cancel();
  }

  private refresh(): void {
    this.name = this.presenter.name;
    this.topic = this.presenter.topic;
    this.members = this.presenter.memberIds.slice();
    this.busy = this.presenter.busy;
    this.created = this.presenter.createdRoomId.length > 0;
    this.error = this.presenter.error;
  }

  build() {
    Scroll() {
      Column({ space: 16 }) {
        Text('Create room').fontSize(24).fontWeight(FontWeight.Bold).id('create_room_title')
        TextInput({ text: this.name, placeholder: 'Room name' })
          .id('create_room_name').enabled(!this.busy && !this.created)
          .onChange((value: string) => { this.presenter.setName(value); this.refresh(); })
        TextInput({ text: this.topic, placeholder: 'Topic (optional)' })
          .id('create_room_topic').enabled(!this.busy && !this.created)
          .onChange((value: string) => { this.presenter.setTopic(value); this.refresh(); })
        Text('Members').width('100%')
        ForEach(this.people, (person: ChatPerson) => {
          Row() {
            Checkbox({ name: person.userId }).select(this.members.includes(person.userId))
              .enabled(!this.busy && !this.created)
              .onChange((selected: boolean) => {
                this.presenter.toggleMember(person.userId, selected);
                this.refresh();
              })
            Text(person.displayName)
          }.width('100%')
        }, (person: ChatPerson) => person.userId)
        if (this.error.length > 0) {
          Text(this.error).id('create_room_error').fontColor('#B42318')
        }
        Button(this.busy ? 'Creating...' : this.created ? 'Open room' : 'Create')
          .id('create_room_submit').width('100%').enabled(!this.busy)
          .onClick(() => {
            const action: Promise<void> = this.presenter.submit();
            this.refresh();
            action.then(() => this.refresh());
          })
        Button('Cancel').id('create_room_cancel').width('100%').onClick(() => {
          this.presenter.cancel();
          chatNavigator.back().catch((error: Error) => { this.error = error.message; });
        })
      }.padding(20).width('100%')
    }.height('100%').width('100%').backgroundColor('#F4F6F8')
  }
}
