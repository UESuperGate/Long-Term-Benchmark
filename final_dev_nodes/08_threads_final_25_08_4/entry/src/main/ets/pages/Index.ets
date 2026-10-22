import { ThreadFocusState, ThreadGateway, ThreadPresenter, ThreadSendState, ThreadSurface } from '../features/ThreadFeature';

@Entry
@Component
struct Index {
  private presenter: ThreadPresenter = new ThreadPresenter(new ThreadGateway());
  @State private surface: ThreadSurface = ThreadSurface.Room;
  @State private threadRootId: string = '';
  @State private threadEvents: string[] = [];
  @State private focusedEventId: string | null = '';
  @State private focusState: ThreadFocusState = ThreadFocusState.Idle;
  @State private composerText: string = '';
  @State private replyTargetId: string = '';
  @State private sendState: ThreadSendState = ThreadSendState.Idle;
  @State private statusText: string = 'Room timeline';

  build() {
    Column() {
      this.Header()
      Scroll() {
        Column({ space: 12 }) {
          if (this.surface === ThreadSurface.Room) {
            Text('Roadmap discussion')
              .fontSize(20)
              .fontWeight(FontWeight.Bold)
              .width('100%')
            ForEach(this.presenter.mainRoomEvents, (eventId: string) => {
              Button(eventId === '$root' ? 'Open thread from $root' : eventId)
                .id(eventId === '$root' ? 'room_event_root' : `room_event_${eventId}`)
                .width('100%')
                .onClick(() => {
                  if (eventId === '$root') {
                    this.presenter.openThread(eventId);
                    this.statusText = 'Thread opened';
                    this.refresh();
                  }
                })
            })
          } else if (this.surface !== ThreadSurface.Thread) {
            Text(this.surface === ThreadSurface.LocationPicker ? 'Location' :
              this.surface === ThreadSurface.PollComposer ? 'Poll' : 'Attachment preview')
              .id('thread_nested_surface')
              .fontSize(20)
              .fontWeight(FontWeight.Bold)
            Button('Return to thread')
              .id('return_to_thread')
              .onClick(() => {
                this.presenter.returnToThread();
                this.refresh();
              })
          } else {
            Row() {
              Button('Back')
                .id('thread_back')
                .onClick(() => {
                  this.presenter.navigateBack();
                  this.statusText = 'Room timeline';
                  this.refresh();
                })
              Text(`Thread ${this.threadRootId}`)
                .fontSize(20)
                .fontWeight(FontWeight.Bold)
                .layoutWeight(1)
            }
            .width('100%')
            ForEach(this.threadEvents, (eventId: string) => {
              Row({ space: 8 }) {
                Button(eventId)
                  .id(eventId === '$root' ? 'thread_event_root' :
                    eventId === '$reply' ? 'thread_event_reply' : `thread_event_${eventId}`)
                  .layoutWeight(1)
                  .onClick(() => {
                    this.presenter.focusEvent(eventId);
                    this.refresh();
                  })
                Button('Reply')
                  .id(eventId === '$root' ? 'thread_reply_root' :
                    eventId === '$reply' ? 'thread_reply_reply' : `thread_reply_${eventId}`)
                  .onClick(() => {
                    this.presenter.setReplyTarget(eventId);
                    this.refresh();
                  })
              }
              .width('100%')
            })
            Text(`Focus: ${this.focusedEventId ? this.focusedEventId : this.focusState}`)
              .id('thread_focus_state')
              .width('100%')
            if (this.replyTargetId.length > 0) {
              Text(`Replying to ${this.replyTargetId}`)
                .id('thread_reply_target')
            }
            TextInput({ text: this.composerText, placeholder: 'Reply in thread' })
              .id('thread_composer')
              .onChange((value: string) => {
                this.presenter.setComposerText(value);
                this.composerText = value;
              })
            Row({ space: 8 }) {
              Button('Send')
                .id('thread_send')
                .onClick(() => {
                  this.statusText = this.presenter.sendMessage() ? 'Sent in thread' : 'Send failed; draft kept';
                  this.refresh();
                })
              Button('Fail next')
                .id('thread_fail_next')
                .onClick(() => {
                  this.presenter.gateway.failNextSend = true;
                })
              Button('Retry')
                .id('thread_retry')
                .enabled(this.sendState === ThreadSendState.Failure)
                .onClick(() => {
                  this.statusText = this.presenter.retrySend() ? 'Retry sent' : 'Retry failed';
                  this.refresh();
                })
            }
            Row({ space: 8 }) {
              Button('Preview attachment')
                .id('thread_attachment_preview')
                .onClick(() => {
                  this.presenter.openAttachmentPreview();
                  this.refresh();
                })
              Button('Send attachment')
                .id('thread_send_attachment')
                .onClick(() => {
                  this.presenter.sendAttachment('image-1', 'diagram');
                  this.refresh();
                })
            }
            Row({ space: 8 }) {
              Button('Location')
                .id('thread_location_picker')
                .onClick(() => {
                  this.presenter.openNestedSurface(ThreadSurface.LocationPicker);
                  this.refresh();
                })
              Button('Poll')
                .id('thread_poll_composer')
                .onClick(() => {
                  this.presenter.openNestedSurface(ThreadSurface.PollComposer);
                  this.refresh();
                })
            }
          }
          Text(this.statusText)
            .id('thread_status')
            .fontColor('#475569')
            .width('100%')
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

  private refresh(): void {
    this.surface = this.presenter.surface;
    this.threadRootId = this.presenter.threadRootId;
    this.threadEvents = this.presenter.threadEvents.slice();
    this.focusedEventId = this.presenter.focusedEventId;
    this.focusState = this.presenter.focusState;
    this.composerText = this.presenter.composerText;
    this.replyTargetId = this.presenter.replyTargetId;
    this.sendState = this.presenter.sendState;
  }

  @Builder
  Header() {
    Column({ space: 4 }) {
      Text('Element X Threads')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
      Text('Android v25.08.4 behavior: scoped thread timeline and composer')
        .fontSize(13)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(20)
    .width('100%')
    .backgroundColor('#FFFFFF')
  }
}
