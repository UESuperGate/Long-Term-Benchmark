import { ChatPerson, StartChatPresenter } from '../features/ChatFeature';
import { startChatPresenter } from '../features/ChatRuntime';

@Component
export struct StartChatView {
  showJoin: boolean = false;
  onJoin: () => void = () => {};
  private presenter: StartChatPresenter = startChatPresenter;
  @State private query: string = '';
  @State private people: ChatPerson[] = this.presenter.visiblePeople();
  @State private busy: boolean = false;
  @State private error: string = '';

  aboutToAppear(): void {
    this.refresh();
  }

  aboutToDisappear(): void {
    this.presenter.cancel();
  }

  private refresh(): void {
    this.query = this.presenter.query;
    this.people = this.presenter.visiblePeople();
    this.busy = this.presenter.busy;
    this.error = this.presenter.error;
  }

  build() {
    Column({ space: 12 }) {
      TextInput({ text: this.query, placeholder: 'Search people' })
        .id('people_search_input')
        .enabled(!this.busy)
        .onChange((value: string) => {
          this.presenter.updateQuery(value);
          this.refresh();
        })
      Button('Create room')
        .id('create_room_action')
        .width('100%')
        .enabled(!this.busy)
        .onClick(() => {
          const action: Promise<void> = this.presenter.createRoom();
          this.refresh();
          action.then(() => this.refresh());
        })
      if (this.showJoin) {
        Button('Join a room by address')
          .id('join_room_by_address')
          .width('100%')
          .enabled(!this.busy)
          .onClick(() => this.onJoin())
      }
      if (this.busy) {
        LoadingProgress().width(28).height(28).id('start_chat_loading')
      }
      if (this.error.length > 0) {
        Text(this.error).id('start_chat_error').fontColor('#B42318')
      }
      Text('People').fontSize(14).width('100%')
      ForEach(this.people, (person: ChatPerson) => {
        Row() {
          Column({ space: 4 }) {
            Text(person.displayName).fontSize(16)
            Text(person.userId).fontSize(12).fontColor('#596168')
          }.alignItems(HorizontalAlign.Start)
          Blank()
          Text('Chat').fontSize(14).fontColor('#17635C')
        }
        .id('person_' + person.userId)
        .padding(14)
        .width('100%')
        .backgroundColor('#FFFFFF')
        .borderRadius(6)
        .enabled(!this.busy)
        .onClick(() => {
          const action: Promise<void> = this.presenter.selectPerson(person.userId);
          this.refresh();
          action.then(() => this.refresh());
        })
      }, (person: ChatPerson) => person.userId)
    }.padding(20).width('100%')
  }
}
