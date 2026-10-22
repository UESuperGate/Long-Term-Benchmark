import { StartChatView } from '../components/StartChatView';

@Entry
@Component
struct Index {
  build() {
    Scroll() {
      Column() {
        Text('Start a chat').fontSize(24).fontWeight(FontWeight.Bold).padding(20).width('100%')
        StartChatView()
      }.width('100%')
    }.height('100%').width('100%').backgroundColor('#F4F6F8')
  }
}
