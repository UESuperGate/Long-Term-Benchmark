import { PollAnswer, PollGateway, PollPresenter } from '../features/PollFeature';

@Entry
@Component
struct Index {
  private presenter: PollPresenter = new PollPresenter(new PollGateway());
  @State private question: string = '';
  @State private answers: PollAnswer[] = [new PollAnswer('a', ''), new PollAnswer('b', '')];
  @State private selectedAnswerId: string = '';
  @State private resultText: string = 'Ready';

  build() {
    Column() {
      this.Header()
      Scroll() {
        Column({ space: 14 }) {
          Text('Create poll')
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
            .width('100%')
          TextInput({ text: this.question, placeholder: 'Question' })
            .id('poll_question_input')
            .onChange((value: string) => {
              this.presenter.setQuestion(value);
              this.question = value;
            })
          ForEach(this.answers, (answer: PollAnswer, index: number) => {
            Row({ space: 8 }) {
              TextInput({ text: answer.text, placeholder: `Answer ${index + 1}` })
                .layoutWeight(1)
                .onChange((value: string) => {
                  this.presenter.setAnswer(index, value);
                  this.answers = this.presenter.draft.answers.slice();
                })
              if (this.answers.length > 2) {
                Button('Remove')
                  .onClick(() => {
                    this.presenter.removeAnswer(index);
                    this.answers = this.presenter.draft.answers.slice();
                  })
              }
            }
          })
          Button('Add answer')
            .id('add_poll_answer')
            .onClick(() => {
              this.presenter.addAnswer();
              this.answers = this.presenter.draft.answers.slice();
            })
          Button('Create poll')
            .id('save_poll')
            .enabled(this.presenter.canSave())
            .onClick(() => {
              this.resultText = this.presenter.save() ? 'Poll created' : 'Unable to create poll';
            })

          Divider()
          Text('Vote')
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
            .width('100%')
          ForEach(['a', 'b', 'c'], (answerId: string) => {
            Button(this.selectedAnswerId === answerId ? `Selected ${answerId}` : `Answer ${answerId}`)
              .enabled(this.presenter.isAnswerEnabled(false))
              .onClick(() => {
                this.presenter.toggleAnswer(answerId);
                this.selectedAnswerId = this.presenter.selectedAnswerId;
              })
          })
          Button('Submit vote')
            .id('submit_poll_vote')
            .enabled(this.selectedAnswerId.length > 0)
            .onClick(() => {
              this.resultText = this.presenter.submitVote() ? 'Vote sent' : 'Vote failed';
            })
          Text(this.resultText)
            .id('poll_result')
            .fontColor('#475569')
        }
        .padding(20)
        .width('100%')
      }
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  @Builder
  Header() {
    Column({ space: 4 }) {
      Text('Element X Polls')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
      Text('Android v26.08.4 behavior: one answer per vote')
        .fontSize(13)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(20)
    .width('100%')
    .backgroundColor('#FFFFFF')
  }
}
