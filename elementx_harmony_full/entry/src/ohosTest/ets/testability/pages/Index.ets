@Entry
@Component
struct Index {
  build() {
    Column() {
      Text('Element X reconstruction tests')
        .fontSize(20)
        .fontWeight(FontWeight.Medium)
    }
    .justifyContent(FlexAlign.Center)
    .width('100%')
    .height('100%')
    .backgroundColor('#FFFFFF')
  }
}
