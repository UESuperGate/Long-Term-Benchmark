import { CreateRoomBasePresenter } from '../features/CreateRoomBase';

@Entry
@Component
struct Index {
  private presenter: CreateRoomBasePresenter = new CreateRoomBasePresenter();
  @State private query: string = '';
  @State private people: string[] = ['Alice', 'Bob', 'Charlie'];
  @State private selectedPerson: string = '';

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Start a chat')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Find a person or create a private room')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      Column({ space: 12 }) {
        TextInput({ text: this.query, placeholder: 'Search people' })
          .id('people_search_input')
          .onChange((value: string) => {
            this.presenter.updateQuery(value);
            this.query = this.presenter.query;
            this.people = this.presenter.visiblePeople();
          })
        Row({ space: 10 }) {
          Button('Create room')
          Button('Invite friends')
        }
        Text('People')
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .width('100%')
        ForEach(this.people, (person: string) => {
          Row() {
            Text(person)
            .fontSize(16)
            Blank()
            if (this.selectedPerson === person) {
              Text('Selected').fontColor('#0F766E')
            }
          }
          .padding(14)
          .width('100%')
          .backgroundColor('#FFFFFF')
          .borderRadius(6)
          .onClick(() => {
            this.presenter.selectPerson(person);
            this.selectedPerson = this.presenter.selectedPerson;
          })
        })
      }
      .padding(20)
      .width('100%')
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

}
